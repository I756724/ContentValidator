# UA Content Validator

Internal tool for SAP User Assistance developers. Validates English content against **SAP writing standards** — Fiori UI text guidelines, approved terminology, abbreviations, SAP-standard term consistency, grammar/style, and German (or other language) translation readiness — before content ships or goes to translation.

Open: http://localhost:5000

---

## What It Validates

Six validation pillars run on every check:

| Pillar | What it does | Source |
|---|---|---|
| **Fiori Guidelines** | Element-specific UI text rules (verb forms, length, articles, punctuation, case) for 10 element types | SAP Fiori UI Text Guidelines (rule-based) |
| **Terminology** | Looks up the term in SAPterm; shows the approved translation and component | SAPterm API |
| **Abbreviations** | Flags unapproved abbreviations and suggests expansions | Approved abbreviation list (rule-based) |
| **SAP Term Consistency** | Catches non-standard wording (e.g. *vendor* → *supplier*, *utilize* → *use*) | SAP standard term map (rule-based) |
| **Translation Readiness** | Compound-noun ambiguity, length expansion risk, passive voice, vague pronouns | NLP (spaCy) + MT Portal/estimate |
| **Grammar & Style + Suggestions** | AI grammar check, improvement suggestions, translation-complexity rating | AI engine (Claude via Hai proxy) |

Two content modes: **UI Text** (labels, buttons, titles — 10 element types) and **Text** (documentation, descriptions, help content).

Results can be exported with **Copy Findings** and **Download Report**.

---

## Quick Start

```bash
cd ua-content-validator

# 1. Create and activate a virtual environment
python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate     # Mac/Linux

# 2. Install dependencies
pip install -r requirements.txt
python -m spacy download en_core_web_sm

# 3. Configure credentials
copy .env.example .env         # Windows  (cp on Mac/Linux)
# then edit .env — see "Service Setup" below

# 4. Run
python app.py
```

Open http://localhost:5000. On startup the console prints the status of each service.

---

## Service Status Indicators

The header shows a colored dot per service:

- 🟢 **Green (connected)** — working
- 🟠 **Orange (expired / not configured)** — credentials missing or stale; see setup below

Three indicators are shown: **SAPterm**, **Wiki**, **AI Engine**. The app degrades gracefully — if a service is orange, the other pillars still run (e.g. no AI means rule-based complexity is used instead; no SAPterm means the terminology row is skipped).

---

## Service Setup

The app reads credentials from a `.env` file (gitignored — never committed). Two of the four services use `.env`; the others use external files.

### 1. SAPterm (cookie in `.env`) — ~24h expiry

SAPterm uses a session cookie that lives on the **backend API domain**, not the `sapterm.sap.com` UI. The reliable way to grab it:

1. Open this URL directly in Chrome (triggers SSO, then returns JSON):
   ```
   https://lpiprod-term.ingress.prod.lp.shoot.live.k8s-hana.ondemand.com/api/termsearch/search?term=supplier&sourceLanguage=en-US&targetLanguage=de-DE&searchMethod=EXACT&pageSize=1&pageNo=1
   ```
2. Log in with SAP SSO if prompted. When you see raw JSON (`{"count":...,"matches":[...]}`), you are authenticated on the correct domain.
3. Press **F12** → **Application** tab → left sidebar **Cookies** → click the `lpiprod-term…` entry.
4. Copy the **JSESSIONID** and **INGRESSCOOKIE** values.
5. Put them in `.env` as a single `name=value; name=value` string:
   ```
   SAPTERM_COOKIE=JSESSIONID=s%3A...; INGRESSCOOKIE=...
   ```
6. Restart the app.

The cookie expires roughly every 24 hours. When SAPterm goes orange, repeat the steps above — it's a ~60-second paste.

> The app accepts the cookie in three forms, in priority order: `SAPTERM_COOKIE` plain string in `.env` (above), `SAPTERM_COOKIES` JSON env var (BTP), or a `sap_cookies.json` file at `~/.sap-mcp/cookies/sapterm/`.

### 2. AI Engine (Hai proxy key in `.env`)

The AI pillar calls Claude through SAP's internal **Hai / LiteLLM proxy** running locally at `http://localhost:6655`.

1. Open `http://localhost:6655` in your browser.
2. Go to **Settings → API Keys** and generate a new key.
3. Put it in `.env`:
   ```
   ANTHROPIC_API_KEY=your-hai-proxy-key
   ```
4. Restart the app. The app runs a live test call on startup, so the indicator reflects the real connection state.

> For BTP deployment, the app instead uses SAP AI Core via `VCAP_SERVICES` (no key needed). Set `DEPLOYMENT=btp`.

### 3. Wiki (mcp-wiki plugin — auto-managed)

Wiki search authenticates through the **Claude Code `mcp-wiki` plugin**, which keeps its own session cookie fresh automatically. No manual setup is needed as long as that plugin has been authenticated at least once.

- The app reads the plugin's cookie from:
  `%LOCALAPPDATA%\Temp\mcp-wiki\wiki.one.int.sap.json`
- If Wiki goes orange, open Claude Code (which runs the mcp-wiki plugin) so it re-authenticates; the app picks up the refreshed cookie automatically.
- Fallback: a manual `sap_cookies.json` at `~/.sap-mcp/cookies/wiki/` is also supported.

Covers the entire internal wiki (`wiki.one.int.sap`) across all spaces via Confluence full-text search.

### 4. MT Portal (optional — live translation)

MT Portal provides live machine translation for length/expansion analysis. It is **not required** — when absent, the app falls back to a rule-based German length estimate, and the indicator is hidden from the UI.

To enable it, place SSO cookies for `mtportal.int.sap` at:
`~/.sap-mcp/cookies/mtportal/sap_cookies.json`
(SAP VPN required.)

---

## `.env` Reference

```ini
# AI engine — key from the local Hai/LiteLLM proxy (http://localhost:6655)
ANTHROPIC_API_KEY=your-hai-proxy-key

# SAPterm — session cookie string from the lpiprod backend (see setup, ~24h expiry)
SAPTERM_COOKIE=JSESSIONID=...; INGRESSCOOKIE=...

# Optional overrides
# DEPLOYMENT=btp                       # use SAP AI Core instead of the local proxy
# SAP_TRANSLATION_BASE_URL=https://mtportal.int.sap
```

`.env` is in `.gitignore` and must never be committed — it holds live session cookies and keys.

---

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| SAPterm orange after ~1 day | Session cookie expired | Re-grab JSESSIONID + INGRESSCOOKIE (see SAPterm setup) |
| AI orange / "key invalid" | Hai proxy key expired or proxy not running | Generate a new key at `localhost:6655`; confirm the proxy is up |
| Wiki orange | mcp-wiki plugin session expired | Open Claude Code so the plugin re-authenticates |
| No cookies visible in DevTools | You were on `sapterm.sap.com`, not the backend domain | Use the direct `lpiprod-term…` URL from step 1 |
| JSON parse / 404 on startup | Server launched from the wrong directory | Run `python app.py` from inside `ua-content-validator/` |
| Port 5000 already in use | A previous instance is still running | Stop old Python processes, then restart |

---

## Project Structure

```
ua-content-validator/
├── app.py                        # Flask app + routes (/, /guide, /validate, /status, /draft-sapterm)
├── config.py                     # Reads .env (keys, cookies, base URLs)
├── requirements.txt              # Python dependencies
├── .env.example                  # Environment template (copy to .env)
├── services/
│   ├── orchestrator.py           # Coordinates all services, builds summary
│   ├── sapterm_service.py        # SAPterm terminology lookup
│   ├── sapterm_draft_service.py  # AI-drafted SAPterm entry for missing terms
│   ├── fiori_rules.py            # Fiori guidelines + abbreviations + term consistency
│   ├── nlp_analyzer.py           # spaCy compound/passive/pronoun analysis
│   ├── ai_service.py             # Claude via Hai proxy (sanitized context, temp=0, cache)
│   ├── translation_service.py    # SAP MT Portal translation (optional)
│   ├── glossary_service.py       # SAP Glossary lookup
│   ├── wiki_service.py           # SAP Wiki search (mcp-wiki plugin cookie bridge)
│   └── help_portal_service.py    # SAP Help Portal usage lookup
├── templates/
│   ├── index.html                # Main page
│   └── guide.html                # User guide
└── static/
    ├── style.css                 # Styling
    └── app.js                    # Frontend logic + export (copy/download)
```

---

## Notes

- **Deterministic AI:** the AI engine runs at `temperature=0` with MD5 response caching, so the same input always produces the same suggestions.
- **Context safety:** user-supplied context is sanitized (braces/quotes stripped) before being embedded in the AI prompt, so rich context no longer breaks AI output.
- **Graceful degradation:** every pillar is independent; a down service never blocks the others.
