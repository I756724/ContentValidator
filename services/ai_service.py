"""
AI Service - Uses Claude via LiteLLM proxy (local) or SAP AI Core (BTP)
"""
import requests
import json
import os
import time
import hashlib
from config import ANTHROPIC_API_KEY

DEPLOYMENT = os.environ.get("DEPLOYMENT", "local")


def _get_btp_ai_config():
    """Extract AI Core credentials from VCAP_SERVICES on BTP."""
    vcap = os.environ.get("VCAP_SERVICES", "")
    if not vcap:
        return None
    try:
        services = json.loads(vcap)
        ai_services = services.get("aicore", services.get("HealthScore_AI_Core", []))
        if not ai_services:
            for key, val in services.items():
                if "ai" in key.lower():
                    ai_services = val
                    break
        if ai_services and len(ai_services) > 0:
            creds = ai_services[0].get("credentials", {})
            return {
                "clientid": creds.get("clientid", ""),
                "clientsecret": creds.get("clientsecret", ""),
                "token_url": creds.get("url", "") + "/oauth/token",
                "api_url": creds.get("serviceurls", {}).get("AI_API_URL", "")
            }
    except Exception:
        pass
    return None


def _get_oauth_token(config):
    """Get OAuth token from AI Core credentials."""
    try:
        response = requests.post(
            config["token_url"],
            data={"grant_type": "client_credentials"},
            auth=(config["clientid"], config["clientsecret"]),
            timeout=10
        )
        if response.status_code == 200:
            return response.json().get("access_token", "")
    except Exception:
        pass
    return ""


# Element-specific rules from SAP Fiori UI Text Guidelines
ELEMENT_RULES = {
    "app_title": {
        "name": "APP TITLE (Application Name)",
        "rules": """- Transactional/hybrid apps: VERB + plural business object
  Standard verbs: Manage (CRUD), Process (documents), Approve (approvals), Create, Monitor, Run, Post
  Examples: "Manage Purchase Orders", "Process Sales Orders", "Approve Supplier Invoices"
- Analytical apps: Noun-based. Avoid "Analysis" suffix. Use plural.
  Examples: "Journal Entries", "Liquidity Forecast", "Cash Flow"
- Overview pages: Noun-based. Don't use "Overview Page" as suffix.
  Examples: "Quality Engineer Overview", "My Sales Overview"
- No ampersands (&). No gerunds (-ing). No technical jargon.
- Title case throughout."""
    },
    "button": {
        "name": "BUTTON",
        "rules": """- Start with imperative verb (not gerund). Max 3 words.
- No instructional words: Click, Press, Tap, Hit.
- No articles (the, a, an). No ending punctuation.
- Standard verbs: Save, Edit, Delete, Create, Cancel, Copy, Share, Submit, Approve, Reject.
  Examples: "Approve Order", "Save", "Delete", "Create Follow-Up", "Submit Request" """
    },
    "action": {
        "name": "ACTION (Link / Toolbar Action)",
        "rules": """- Imperative verb + object. Up to 5 words.
- Title case. No ending punctuation.
  Examples: "Edit List", "Copy from Template", "Release All Items", "Export to Excel" """
    },
    "tab": {
        "name": "TAB (Navigation Tab)",
        "rules": """- Noun phrase. 1-3 words. Title case.
- Optional count format: "Items (4)". No verbs.
  Examples: "Items", "General Information", "Timeline", "Price Details", "Notes" """
    },
    "section_heading": {
        "name": "SECTION HEADING",
        "rules": """- Noun phrase. Title case. 1-4 words.
- Don't duplicate the parent section name.
  Examples: "Account", "Processing Data", "Dates", "General Data", "Address" """
    },
    "field_label": {
        "name": "FIELD LABEL",
        "rules": """- Noun phrase only. NO verbs ("Enter", "Select", "Choose" are not allowed).
- No articles (the, a, an). Title case. Max 4 words.
- Do NOT add a colon — it is rendered automatically by the UI.
- No ending punctuation.
  Examples: "Sold-To Party", "External Reference", "Priority", "Delivery Date" """
    },
    "column_header": {
        "name": "COLUMN HEADER",
        "rules": """- Title case. Singular (one item per row) or plural (multiple).
- Use slash with spaces for composite values (e.g. "Unit / Currency").
- Max 3 words. No ending punctuation.
  Examples: "Item Number", "Product ID", "Quantity", "Net Value", "Status" """
    },
    "status_text": {
        "name": "STATUS TEXT",
        "rules": """- Short (1-3 words): title case. Longer: sentence case.
- No ending period. Describes a state, not an action.
  Examples: "Completed", "Not Billed", "No Items Billed", "In Progress", "Approved" """
    },
    "message_text": {
        "name": "MESSAGE TEXT (Error / Info / Success)",
        "rules": """- Never use "successfully". Never use (s) for plural. No semicolons.
- Only use a period for complete sentences; omit for sentence fragments.
- State what happened or what to do next.
  Examples: "Leave request created", "Enter a valid email address", "Select at least one item" """
    },
    "facet_title": {
        "name": "FACET TITLE (Object Page Header Facet)",
        "rules": """- Noun phrase. Title case. 1-4 words. Optional count: "Items (4)".
  Examples: "Price Overview", "Duration", "Progress", "Life Cycle Status", "Contact Data" """
    }
}


class AIService:
    """AI-powered content analysis via LiteLLM (local) or AI Core (BTP)."""

    # Response cache: (text, element_type, context_hash) → result. Survives the request.
    _response_cache: dict = {}

    @staticmethod
    def _sanitize_context(context: str, max_chars: int = 400) -> str:
        """Truncate and strip characters that break the JSON template in the prompt."""
        if not context:
            return ""
        # Remove curly braces (confuse the JSON template), keep the rest readable
        safe = context.replace("{", "(").replace("}", ")").replace('"', "'")
        return safe[:max_chars] + ("…" if len(safe) > max_chars else "")

    def __init__(self):
        self.btp_config = _get_btp_ai_config() if DEPLOYMENT == "btp" else None

        if self.btp_config:
            self.available = True
            self.mode = "btp"
            deployment_id = os.environ.get("AICORE_DEPLOYMENT_ID", "d557e6da0545e7b6")
            self.api_url = f"{self.btp_config['api_url']}/v2/inference/deployments/{deployment_id}/chat/completions"
            self.model = os.environ.get("ANTHROPIC_DEFAULT_MODEL", "claude-sonnet-4-5")
        else:
            self.available = bool(ANTHROPIC_API_KEY)
            self.mode = "local"
            self.api_url = "http://localhost:6655/litellm/v1/chat/completions"
            self.model = "anthropic--claude-sonnet-4-5"
            self.api_key = ANTHROPIC_API_KEY

    def _call_llm(self, prompt: str, max_tokens: int = 1000) -> str:
        """Call LLM — handles both local proxy and BTP AI Core."""
        try:
            headers = {"Content-Type": "application/json"}

            if self.mode == "btp":
                token = _get_oauth_token(self.btp_config)
                if not token:
                    return '{"error": "Failed to get AI Core OAuth token"}'
                headers["Authorization"] = f"Bearer {token}"
                headers["AI-Resource-Group"] = "default"
            else:
                headers["Authorization"] = f"Bearer {self.api_key}"

            response = requests.post(
                self.api_url,
                headers=headers,
                json={
                    "model": self.model,
                    "max_tokens": max_tokens,
                    "temperature": 0,
                    "messages": [{"role": "user", "content": prompt}]
                },
                timeout=60
            )

            if response.status_code == 200:
                return response.json()["choices"][0]["message"]["content"]
            return f'{{"error": "AI returned {response.status_code}: {response.text[:200]}"}}'

        except requests.ConnectionError:
            return '{"error": "Cannot connect to AI service"}'
        except Exception as e:
            return f'{{"error": "{str(e)}"}}'

    def analyze_ui_label(self, text: str, element_type: str, context: str = "") -> dict:
        """AI analysis of a UI label for German translation readiness."""
        if not self.available:
            return {"german_issues": [], "suggestions": [], "complexity": "Unknown",
                    "grammar_issues": [], "note": "", "error": "AI not configured"}

        safe_context = self._sanitize_context(context)
        cache_key = hashlib.md5(f"{text}|{element_type}|{safe_context}".encode()).hexdigest()
        if cache_key in AIService._response_cache:
            return AIService._response_cache[cache_key]

        context_instruction = f"Context: {safe_context}" if safe_context else "No additional context."
        element_info = ELEMENT_RULES.get(element_type, ELEMENT_RULES["field_label"])
        element_name = element_info["name"]
        element_rules = element_info["rules"]

        prompt = f"""You are an SAP UA (User Assistance) expert specializing in German translation readiness.
Validate the following UI element text strictly against SAP Fiori UI Text Guidelines.

ELEMENT TYPE: {element_name}
Text: "{text}"
{context_instruction}

RULES FOR {element_name}:
{element_rules}

ADDITIONAL CHECKS:
- No technical jargon (Run, Execute, Batch, Instance, Entity)
- Consistent with SAP terminology standards
- Suitable for German translation (no idioms, culturally neutral)

Instructions: Be concise (1-2 sentences per item). Only flag REAL issues — do not invent problems.

Return ONLY valid JSON — no markdown, no extra text:
{{"german_issues":[{{"issue":"title","explanation":"one sentence"}}],"suggestions":[{{"text":"improved version","reason":"one sentence"}}],"complexity":"Low|Medium|High","grammar_issues":[{{"text":"problematic part","issue":"description","fix":"fix"}}],"note":""}}"""

        result_text = self._call_llm(prompt)
        try:
            if result_text.startswith("```"):
                result_text = result_text.split("\n", 1)[1].rsplit("```", 1)[0]
            parsed = json.loads(result_text)
            AIService._response_cache[cache_key] = parsed
            return parsed
        except json.JSONDecodeError:
            return {"german_issues": [], "suggestions": [], "complexity": "Unknown",
                    "grammar_issues": [], "note": "", "error": result_text[:300]}

    def analyze_text(self, text: str, context: str = "") -> dict:
        """AI analysis of general text/documentation for German translation readiness."""
        if not self.available:
            return {"german_issues": [], "suggestions": [], "overall_assessment": "",
                    "complexity": "Unknown", "grammar_issues": [], "note": "", "error": "AI not configured"}

        safe_context = self._sanitize_context(context)
        cache_key = hashlib.md5(f"text|{text[:200]}|{safe_context}".encode()).hexdigest()
        if cache_key in AIService._response_cache:
            return AIService._response_cache[cache_key]

        context_instruction = f"Context: {safe_context}" if safe_context else ""

        prompt = f"""You are an SAP UA expert specializing in German translation readiness.
Validate the following documentation text.

Text: "{text[:800]}"
{context_instruction}

Check for:
- Compound noun chains (3+ nouns in a row — German reverses their order)
- Passive voice (German passive is more complex)
- Vague pronouns at sentence start (this, it, that — need gender in German)
- Long sentences over 25 words (German words are longer)
- Ambiguous terms with multiple German translations
- Jargon or idioms that do not translate well

Be concise. Only flag real issues. Return ONLY valid JSON — no markdown, no extra text:
{{"german_issues":[{{"text":"phrase","issue":"problem","suggestion":"fix","reason":"why"}}],"suggestions":[{{"original":"original text","improved":"improved version","reason":"why"}}],"overall_assessment":"one sentence","complexity":"Low|Medium|High","grammar_issues":[{{"text":"text","issue":"description","fix":"fix"}}],"note":""}}"""

        result_text = self._call_llm(prompt, max_tokens=1000)
        try:
            if result_text.startswith("```"):
                result_text = result_text.split("\n", 1)[1].rsplit("```", 1)[0]
            parsed = json.loads(result_text)
            AIService._response_cache[cache_key] = parsed
            return parsed
        except json.JSONDecodeError:
            return {"german_issues": [], "suggestions": [], "overall_assessment": "",
                    "complexity": "Unknown", "grammar_issues": [], "note": "", "error": result_text[:300]}

    def is_available(self) -> bool:
        return self.available

    def test_connection(self) -> dict:
        """Ping the LLM with a minimal call. Result cached for 5 minutes."""
        now = time.time()
        if hasattr(self, '_conn_cache') and now - self._conn_cache['ts'] < 300:
            return self._conn_cache['result']

        if not self.available:
            result = {"status": "not_configured", "message": "No API key set"}
        else:
            raw = self._call_llm("Reply with the single word OK.", max_tokens=5)
            if '"error"' in raw or "error" in raw.lower():
                result = {"status": "expired", "message": "AI key invalid — refresh Hai proxy key"}
            else:
                result = {"status": "connected"}

        self._conn_cache = {"ts": now, "result": result}
        return result
