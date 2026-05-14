"""
AI Service - Uses Claude via LiteLLM proxy for intelligent analysis
Proxy at localhost:6655/litellm/v1 (OpenAI-compatible format)
"""
import requests
import json
from config import ANTHROPIC_API_KEY

# Use direct Hyperspace URL on BTP, localhost proxy locally
import os
if os.environ.get("DEPLOYMENT") == "btp":
    PROXY_BASE_URL = os.environ.get("AI_PROXY_URL", "https://api.hyperspace.tools.sap/llm-proxy/litellm/v1")
else:
    PROXY_BASE_URL = "http://localhost:6655/litellm/v1"

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
- Follow button naming conventions
- Title case
- Standard: "Edit List", "Copy from Template", "Release All Items"
- For dropdowns with options: no ellipsis (dropdown arrow indicates options)"""
    },
    "tab": {
        "name": "TAB (Navigation Tab)",
        "rules": """- Title case
- Noun or noun phrase
- Don't repeat the section heading in subsection headings
- Keep concise (1-3 words)
- If using count: "Items (4)" format
  Examples: "Items", "General Information", "Timeline", "Price Details" """
    },
    "section_heading": {
        "name": "SECTION HEADING",
        "rules": """- Title case
- Noun phrase describing the content area
- Don't overlap with parent section name
- Align with other apps in your app family if similar grouping
  Examples: "Account", "Processing Data", "Dates", "General Data", "Service Order Details" """
    },
    "field_label": {
        "name": "FIELD LABEL",
        "rules": """- Title case
- Noun phrase (NO verbs, NO articles)
- Colon is added automatically by UI control — do NOT include colon
- No ending punctuation
- Keep concise (1-4 words)
  Examples: "Sold-To Party", "External Reference", "Priority", "Requested Start" """
    },
    "column_header": {
        "name": "COLUMN HEADER",
        "rules": """- Title case
- Use singular if one entry per row, plural if multiple
- For multiple values in one column: use slash with spaces "Value A / Value B"
- Keep short (1-3 words)
  Examples: "Item Number", "Product ID", "Quantity", "Net Value" """
    },
    "status_text": {
        "name": "STATUS TEXT",
        "rules": """- Sentence case if long, title case if short
- No ending period for short statuses
- Can use color coding (semantic colors)
- Keep factual and clear
  Examples: "Completed", "Not Billed", "No Items Billed", "In Progress" """
    },
    "message_text": {
        "name": "MESSAGE TEXT (Error/Info/Success)",
        "rules": """- Don't use "successfully" for success messages
- No "(s)" for plural — use separate strings for singular/plural
- No semicolons — use two separate sentences
- Include variables in single string (not concatenated)
- Use periods for complete sentences only
- Specific error guidance: tell user what to do
- No generic messages ("Something went wrong")
  Examples: "Leave request created", "Enter a valid email address" """
    },
    "facet_title": {
        "name": "FACET TITLE (Object Page Header Facet)",
        "rules": """- Title case
- Noun phrase
- Can include count in parentheses: "Items (4)"
- Keep short and descriptive
  Examples: "Price Overview", "Duration", "Progress", "Life Cycle Status" """
    }
}


class AIService:
    """AI-powered content analysis and suggestions via LiteLLM proxy."""

    def __init__(self):
        self.available = bool(ANTHROPIC_API_KEY)
        self.api_key = ANTHROPIC_API_KEY
        self.base_url = PROXY_BASE_URL

    def _call_llm(self, prompt: str, max_tokens: int = 1000) -> str:
        """Make OpenAI-compatible call to LiteLLM proxy."""
        try:
            response = requests.post(
                f"{self.base_url}/chat/completions",
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self.api_key}"
                },
                json={
                    "model": "anthropic--claude-4.6-opus",
                    "max_tokens": max_tokens,
                    "messages": [{"role": "user", "content": prompt}]
                },
                timeout=60
            )

            if response.status_code == 200:
                data = response.json()
                return data["choices"][0]["message"]["content"]
            else:
                return f'{{"error": "API returned {response.status_code}: {response.text[:200]}"}}'

        except requests.ConnectionError:
            return '{"error": "Cannot connect to AI proxy at localhost:6655. Is it running?"}'
        except Exception as e:
            return f'{{"error": "{str(e)}"}}'

    def analyze_ui_label(self, text: str, element_type: str, context: str = "") -> dict:
        """AI analysis of a UI label for German translation readiness."""
        if not self.available:
            return {"german_issues": [], "suggestions": [], "complexity": "Unknown", "grammar_issues": [], "note": "", "error": "AI not configured"}

        context_instruction = f'Context provided: {context}' if context else 'No context provided.'

        # Get element-specific rules
        element_info = ELEMENT_RULES.get(element_type, ELEMENT_RULES.get("field_label"))
        element_name = element_info["name"]
        element_rules = element_info["rules"]

        prompt = f"""You are an SAP UA expert. Validate this UI element for German translation readiness.

⚠️ THIS IS A: {element_name}
Text: "{text}"
{context_instruction}

RULES FOR {element_name} (from SAP Fiori UI Text Guidelines):
{element_rules}

GENERAL RULES:
- Title case for short UI texts. Sentence case for messages/explanations.
- No ampersands (&) in UI text.
- No technical jargon end users won't understand.
- "Runs", "Execute", "Batch", "Trigger" are jargon — use user-friendly alternatives.

VALIDATION INSTRUCTIONS:
- Be CONCISE. Max 1-2 sentences per item.
- Only flag REAL issues based on the rules above.
- Suggestions must follow the rules for {element_name}.
- Never suggest the same problematic word back.
- Reference "SAP Fiori UI Text Guidelines" when citing a rule.

Return JSON:
{{
  "german_issues": [
    {{"issue": "5-10 word title", "explanation": "One sentence why problematic for German"}}
  ],
  "suggestions": [
    {{"text": "Improved text", "reason": "One sentence why better (reference rule)"}}
  ],
  "complexity": "Low|Medium|High",
  "grammar_issues": [
    {{"text": "problematic part", "issue": "short description", "fix": "max 10 words"}}
  ],
  "note": "{'' if context else 'Provide context for more accurate suggestions.'}"
}}

JSON only, no markdown."""

        result_text = self._call_llm(prompt)
        
        try:
            if result_text.startswith("```"):
                result_text = result_text.split("\n", 1)[1]
                result_text = result_text.rsplit("```", 1)[0]
            return json.loads(result_text)
        except json.JSONDecodeError:
            return {"german_issues": [], "suggestions": [], "complexity": "Unknown", "grammar_issues": [], "note": "", "error": result_text[:300]}

    def analyze_text(self, text: str, context: str = "") -> dict:
        """AI analysis of general text for German translation readiness."""
        if not self.available:
            return {"german_issues": [], "suggestions": [], "overall_assessment": "", "complexity": "Unknown", "grammar_issues": [], "note": "", "error": "AI not configured"}

        context_instruction = f'Context: {context}' if context else 'No context provided.'

        prompt = f"""You are an SAP UA expert. Validate this text for German translation readiness.

Text: "{text}"
{context_instruction}

RULES:
- Be CONCISE. Max 1-2 sentences per item.
- Only flag real issues for German translation.
- Check: grammar, ambiguous terms, compound nouns, passive voice, vague pronouns.
- Periods: Use for complete sentences. Omit for short/incomplete texts.
- No "(s)" for plural. No semicolons. Use specific language.

Return JSON:
{{
  "german_issues": [
    {{"text": "problematic phrase", "issue": "5-10 word problem", "suggestion": "short fix", "reason": "one sentence why problematic for German"}}
  ],
  "suggestions": [
    {{"original": "original phrase", "improved": "better version", "reason": "one sentence why better"}}
  ],
  "overall_assessment": "one sentence summary",
  "complexity": "Low|Medium|High",
  "grammar_issues": [
    {{"text": "problematic text", "issue": "short description", "fix": "short correction"}}
  ],
  "note": ""
}}

JSON only, no markdown."""

        result_text = self._call_llm(prompt, max_tokens=1000)
        
        try:
            if result_text.startswith("```"):
                result_text = result_text.split("\n", 1)[1]
                result_text = result_text.rsplit("```", 1)[0]
            return json.loads(result_text)
        except json.JSONDecodeError:
            return {"german_issues": [], "suggestions": [], "overall_assessment": "", "complexity": "Unknown", "grammar_issues": [], "note": "", "error": result_text[:300]}

    def is_available(self) -> bool:
        """Check if AI service is configured."""
        return self.available