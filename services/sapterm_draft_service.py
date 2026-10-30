"""
SAPterm Draft Service - Generates SAPterm-ready term definitions using AI.
Follows official SAPterm standards from the Help Portal Term Farmer skill.

DO rules:
  - Nouns: article + noun family + qualifiers ("A document that...")
  - Verbs: "To" + verb ("To confirm the receipt of...")
  - Capital letter start, period at end.

DON'T rules:
  - No "refers to", "describes", "defines", "denotes", "and so on", "etc."
  - No circular definitions (term cannot be the subject of its own definition)
  - No addressing the reader ("you can", "the user")
  - No links inside the definition
"""
import json
from datetime import date
from services.ai_service import AIService
from services.help_portal_service import HelpPortalService

SAPTERM_RULES = """You are an SAP terminology specialist drafting an entry for SAPterm, SAP's official terminology database.

DEFINITION — DO:
- Nouns: start with article + noun family + qualifiers. Example: "A document that records..."
- Verbs: start with "To" + infinitive. Example: "To confirm the receipt of goods..."
- Adjectives: start with an adjectival phrase. Example: "Capable of being processed..."
- Plain text only. Capital letter. Period at end.
- A second sentence is allowed and may contain the term.

DEFINITION — DO NOT:
- Do NOT use: "refers to", "describes", "defines", "denotes", "is used to", "and so on", "etc."
- Do NOT write a circular definition (the term itself cannot be the grammatical subject)
- Do NOT address the reader ("you can use", "the user", "you should")
- Do NOT add links or URLs inside the definition text"""


class SAPTermDraftService:
    """Drafts SAPterm-ready terminology entries using AI + Help Portal context."""

    def __init__(self):
        self.ai = AIService()
        self.help_portal = HelpPortalService()

    def draft_entry(self, term: str, context: str = "",
                    element_type: str = "field_label") -> dict:
        """
        Draft a complete SAPterm entry for a term not in SAPterm.

        Returns:
            {
                "term": str,
                "part_of_speech": str,
                "definition": str,
                "context_field": str,
                "product": str,
                "application_component": str,
                "source": str,
                "plain_text": str,   # copy-paste ready SAPterm block
                "confidence": "high|medium|low",
                "warnings": [str],
                "error": str or None
            }
        """
        if not self.ai.is_available():
            return {"error": "AI service not available — cannot draft entry"}

        hp = self._fetch_help_portal_context(term)
        draft = self._draft_with_ai(term, context, element_type, hp)

        if "error" in draft:
            return draft

        draft["plain_text"] = self._build_plain_text(draft)
        draft["error"] = None
        return draft

    # ── Help Portal context ──────────────────────────────────────────────────

    def _fetch_help_portal_context(self, term: str) -> dict:
        """Fetch the top Help Portal result for context and source fields."""
        try:
            result = self.help_portal.search_term_usage(term)
            hits = result.get("results", [])
            if hits:
                top = hits[0]
                return {
                    "title": top.get("title", ""),
                    "url": top.get("url", ""),
                    "excerpt": top.get("description", "")[:300]
                }
        except Exception:
            pass
        return {}

    # ── AI drafting ──────────────────────────────────────────────────────────

    def _draft_with_ai(self, term: str, user_context: str,
                       element_type: str, hp: dict) -> dict:
        today = date.today().strftime("%d %B %Y")

        context_lines = []
        if user_context:
            context_lines.append(f"User context: {user_context}")
        if hp.get("excerpt"):
            context_lines.append(
                f"From SAP Help Portal ({hp.get('title', 'help.sap.com')}):\n{hp['excerpt']}"
            )
        context_block = "\n".join(context_lines) if context_lines else "No additional context provided."

        hp_title = hp.get("title", "SAP Help Portal")
        hp_url = hp.get("url", "https://help.sap.com")

        prompt = f"""{SAPTERM_RULES}

Draft a SAPterm entry for the following term.

Term: "{term}"
UI element type: {element_type}
Today's date: {today}

Additional context:
{context_block}

Instructions:
1. Detect part_of_speech: noun, verb, adjective, or adverb.
2. Write a definition strictly following the DO/DON'T rules above. Recheck against every DON'T rule before finalising.
3. context_field: Extract or paraphrase a short relevant quote from the Help Portal excerpt. Format: [1] "quote." ({hp_title}, {hp_url})
   If no excerpt is available, write: [1] Based on UI element type "{element_type}" in SAP S/4HANA.
4. application_component: Suggest the most likely SAP component code and description (e.g. MM-PUR — Purchasing). Mark as Provisional if uncertain.
5. confidence: "high" if this is a well-known SAP term, "medium" if a general business term, "low" if ambiguous.
6. warnings: list any issues (ambiguous term, component guessed, definition required verification, etc.)

Return only valid JSON, no markdown:
{{"term":"{term}","part_of_speech":"","definition":"","context_field":"","product":"SAP S/4HANA","application_component":"","source":"SAP Help Portal, \\"{hp_title}\\" {hp_url} (Accessed {today})","confidence":"","warnings":[]}}"""

        raw = self.ai._call_llm(prompt, max_tokens=700)
        try:
            if raw.startswith("```"):
                raw = raw.split("\n", 1)[1].rsplit("```", 1)[0]
            return json.loads(raw)
        except json.JSONDecodeError:
            return {"error": f"AI returned unexpected format: {raw[:200]}"}

    # ── Plain-text SAPterm format ────────────────────────────────────────────

    def _build_plain_text(self, d: dict) -> str:
        warnings = d.get("warnings", [])
        warn_block = ("".join(f"!! WARNING: {w}\n" for w in warnings) + "\n") if warnings else ""

        return (
            "!! DISCLAIMER: AI-generated content. Review and verify with a terminology\n"
            "!! specialist before adding to SAPterm.\n"
            f"{warn_block}"
            "========================================\n"
            f"TERM: {d.get('term', '')}\n"
            f"PART OF SPEECH: {d.get('part_of_speech', '').capitalize()}\n"
            "----------------------------------------\n"
            "DEFINITION:\n"
            f"{d.get('definition', '')}\n"
            "\n"
            "CONTEXT:\n"
            f"{d.get('context_field', '')}\n"
            "\n"
            f"PRODUCT: {d.get('product', '')}\n"
            f"APPLICATION COMPONENT: {d.get('application_component', '')}\n"
            f"SOURCE: {d.get('source', '')}\n"
            "========================================"
        )
