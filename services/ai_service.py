"""
AI Service - Uses Claude/GPT via LiteLLM proxy
- Local: localhost:6655 proxy with API key
- BTP: SAP AI Core with OAuth (VCAP_SERVICES binding)
"""
import requests
import json
import os
from config import ANTHROPIC_API_KEY

# Detect deployment environment
DEPLOYMENT = os.environ.get("DEPLOYMENT", "local")


def _get_btp_ai_config():
    """Extract AI Core credentials from VCAP_SERVICES on BTP."""
    vcap = os.environ.get("VCAP_SERVICES", "")
    if not vcap:
        return None
    try:
        services = json.loads(vcap)
        # Look for AI Core service binding
        ai_services = services.get("aicore", services.get("HealthScore_AI_Core", []))
        if not ai_services:
            # Try finding any service with "ai" in the name
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
        "rules": """- Transactional/hybrid apps: Start with VERB + plural business object
  Verbs: Manage (CRUD), Process (documents), Approve (approvals), Create, Monitor
  Examples: "Manage Purchase Orders", "Process Sales Orders", "Approve Supplier Invoices"
- Analytical apps: Noun-based name. Avoid "Analysis". Use plural.
  Examples: "Journal Entries", "Liquidity Forecast", "Cash Flow"
- Overview pages: Noun-based. Don't use "Overview Page".
  Examples: "Quality Engineer Overview", "My Sales Overview"
- No ampersands (&). No technical jargon. Title case."""
    },
    "button": {
        "name": "BUTTON",
        "rules": """- Start with action verb (imperative form)
- Keep short (1-3 words max)
- No instructional words (Click, Press, Tap)
- No articles (the, a, an)
- No ending punctuation
- No ellipsis (except for file browse)
- Standard actions: Save, Edit, Delete, Create, Cancel, Copy, Share
  Examples: "Approve Order", "Save", "Delete", "Create Follow-Up" """
    },
    "action": {
        "name": "ACTION (Link/Toolbar Action)",
        "rules": """- Start with verb + object
- Can be longer than buttons (up to 4-5 words)
- Title case
- Standard: "Edit List", "Copy from Template", "Release All Items" """
    },
    "tab": {
        "name": "TAB (Navigation Tab)",
        "rules": """- Title case. Noun or noun phrase.
- Keep concise (1-3 words). Count format: "Items (4)"
  Examples: "Items", "General Information", "Timeline", "Price Details" """
    },
    "section_heading": {
        "name": "SECTION HEADING",
        "rules": """- Title case. Noun phrase.
- Don't overlap with parent section name.
  Examples: "Account", "Processing Data", "Dates", "General Data" """
    },
    "field_label": {
        "name": "FIELD LABEL",
        "rules": """- Title case. Noun phrase (NO verbs, NO articles).
- Colon added automatically — do NOT include colon. No punctuation.
- Keep concise (1-4 words).
  Examples: "Sold-To Party", "External Reference", "Priority" """
    },
    "column_header": {
        "name": "COLUMN HEADER",
        "rules": """- Title case. Singular if one entry per row, plural if multiple.
- Slash with spaces for multiple values. Keep short (1-3 words).
  Examples: "Item Number", "Product ID", "Quantity", "Net Value" """
    },
    "status_text": {
        "name": "STATUS TEXT",
        "rules": """- Sentence case if long, title case if short. No ending period.
  Examples: "Completed", "Not Billed", "No Items Billed", "In Progress" """
    },
    "message_text": {
        "name": "MESSAGE TEXT (Error/Info/Success)",
        "rules": """- Don't use "successfully". No "(s)" for plural. No semicolons.
- Use periods for complete sentences only. Tell user what to do.
  Examples: "Leave request created", "Enter a valid email address" """
    },
    "facet_title": {
        "name": "FACET TITLE (Object Page Header Facet)",
        "rules": """- Title case. Noun phrase. Can include count: "Items (4)".
  Examples: "Price Overview", "Duration", "Progress", "Life Cycle Status" """
    }
}


class AIService:
    """AI-powered content analysis via LiteLLM (local) or AI Core (BTP)."""

    def __init__(self):
        self.btp_config = _get_btp_ai_config() if DEPLOYMENT == "btp" else None
        
        if self.btp_config:
            # BTP mode: use AI Core
            self.available = True
            self.mode = "btp"
            deployment_id = os.environ.get("AICORE_DEPLOYMENT_ID", "d557e6da0545e7b6")
            self.api_url = f"{self.btp_config['api_url']}/v2/inference/deployments/{deployment_id}/chat/completions"
            self.model = os.environ.get("ANTHROPIC_DEFAULT_MODEL", "claude-sonnet-4-5")
        else:
            # Local mode: use LiteLLM proxy
            self.available = bool(ANTHROPIC_API_KEY)
            self.mode = "local"
            self.api_url = "http://localhost:6655/litellm/v1/chat/completions"
            self.model = "anthropic--claude-4.6-opus"
            self.api_key = ANTHROPIC_API_KEY

    def _call_llm(self, prompt: str, max_tokens: int = 1000) -> str:
        """Call LLM - handles both local and BTP modes."""
        try:
            headers = {"Content-Type": "application/json"}
            
            if self.mode == "btp":
                # Get fresh OAuth token
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
                    "messages": [{"role": "user", "content": prompt}]
                },
                timeout=60
            )

            if response.status_code == 200:
                data = response.json()
                return data["choices"][0]["message"]["content"]
            else:
                return f'{{"error": "AI returned {response.status_code}: {response.text[:200]}"}}'

        except requests.ConnectionError:
            return '{"error": "Cannot connect to AI service"}'
        except Exception as e:
            return f'{{"error": "{str(e)}"}}'

    def analyze_ui_label(self, text: str, element_type: str, context: str = "") -> dict:
        """AI analysis of a UI label for German translation readiness."""
        if not self.available:
            return {"german_issues": [], "suggestions": [], "complexity": "Unknown", "grammar_issues": [], "note": "", "error": "AI not configured"}

        context_instruction = f'Context provided: {context}' if context else 'No context provided.'
        element_info = ELEMENT_RULES.get(element_type, ELEMENT_RULES.get("field_label"))
        element_name = element_info["name"]
        element_rules = element_info["rules"]

        prompt = f"""You are an SAP UA expert. Validate this UI element for German translation readiness.

THIS IS A: {element_name}
Text: "{text}"
{context_instruction}

RULES FOR {element_name} (SAP Fiori UI Text Guidelines):
{element_rules}

GENERAL: No technical jargon. "Runs","Execute","Batch" are jargon.

Be CONCISE (1-2 sentences per item). Only flag REAL issues.

Return JSON:
{{"german_issues":[{{"issue":"title","explanation":"one sentence"}}],"suggestions":[{{"text":"improved","reason":"one sentence"}}],"complexity":"Low|Medium|High","grammar_issues":[{{"text":"part","issue":"desc","fix":"fix"}}],"note":"{'' if context else 'Provide context for better suggestions.'}"}}

JSON only, no markdown."""

        result_text = self._call_llm(prompt)
        try:
            if result_text.startswith("```"):
                result_text = result_text.split("\n", 1)[1].rsplit("```", 1)[0]
            return json.loads(result_text)
        except json.JSONDecodeError:
            return {"german_issues": [], "suggestions": [], "complexity": "Unknown", "grammar_issues": [], "note": "", "error": result_text[:300]}

    def analyze_text(self, text: str, context: str = "") -> dict:
        """AI analysis of general text for German translation readiness."""
        if not self.available:
            return {"german_issues": [], "suggestions": [], "overall_assessment": "", "complexity": "Unknown", "grammar_issues": [], "note": "", "error": "AI not configured"}

        context_instruction = f'Context: {context}' if context else ''

        prompt = f"""SAP UA expert. Validate for German translation readiness.

Text: "{text}"
{context_instruction}

Be CONCISE. Only real issues. Check grammar, compounds, passive voice, pronouns.

Return JSON:
{{"german_issues":[{{"text":"phrase","issue":"problem","suggestion":"fix","reason":"why"}}],"suggestions":[{{"original":"orig","improved":"better","reason":"why"}}],"overall_assessment":"one sentence","complexity":"Low|Medium|High","grammar_issues":[{{"text":"text","issue":"desc","fix":"fix"}}],"note":""}}

JSON only."""

        result_text = self._call_llm(prompt, max_tokens=1000)
        try:
            if result_text.startswith("```"):
                result_text = result_text.split("\n", 1)[1].rsplit("```", 1)[0]
            return json.loads(result_text)
        except json.JSONDecodeError:
            return {"german_issues": [], "suggestions": [], "overall_assessment": "", "complexity": "Unknown", "grammar_issues": [], "note": "", "error": result_text[:300]}

    def is_available(self) -> bool:
        return self.available