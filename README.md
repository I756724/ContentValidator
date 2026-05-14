# UA Content Validator

Internal tool for SAP UAs to validate English content before German translation.

## Quick Start

```bash
cd ua-content-validator

# Create virtual environment
python -m venv venv
venv\Scripts\activate      # Windows
# source venv/bin/activate  # Mac/Linux

# Install dependencies
pip install -r requirements.txt
python -m spacy download en_core_web_sm

# Configure (copy and edit .env)
copy .env.example .env
# Edit .env with your API keys

# Run
python app.py
```

Open: http://localhost:5000

## Configuration

Edit `.env` file:

```
ANTHROPIC_API_KEY=your_key_here
SAPTERM_COOKIE=your_cookie_here
```

### Getting SAPterm Cookie
1. Open https://lpiprod-term.ingress.prod.lp.shoot.live.k8s-hana.ondemand.com/ui/
2. Login with SAP SSO
3. F12 → Network tab → Search any term
4. Copy the Cookie header value
5. Paste in `.env`

Cookie expires every ~24 hours.

### Getting Anthropic API Key
1. Go to https://console.anthropic.com/
2. Create an API key
3. Paste in `.env`

## What It Validates

### UI Labels
- SAPterm lookup (exists? German translation? which LOBs?)
- Fiori UI text guidelines (length, articles, verb forms, punctuation)
- German length expansion risk
- Compound noun ambiguity
- AI suggestions for better alternatives

### General Text
- Terminology consistency
- Compound noun chains (3+ nouns)
- Passive voice detection
- Vague pronoun references
- Sentence length
- AI German translation analysis

## Project Structure

```
ua-content-validator/
├── app.py              # Flask application
├── config.py           # Configuration
├── requirements.txt    # Dependencies
├── .env.example        # Environment template
├── services/
│   ├── orchestrator.py     # Coordinates all services
│   ├── sapterm_service.py  # SAPterm API
│   ├── fiori_rules.py      # Fiori UI guidelines
│   ├── nlp_analyzer.py     # spaCy NLP analysis
│   ├── ai_service.py       # Anthropic Claude AI
│   └── glossary_service.py # SAP Glossary lookup
├── templates/
│   └── index.html          # Main page
└── static/
    ├── style.css           # Styling
    └── app.js              # Frontend logic