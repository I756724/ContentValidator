"""
Orchestrator - Coordinates all validation services and produces final results
Sources: SAPterm, Fiori Rules, NLP, AI, Wiki, Help Portal, Glossary
"""
from services.sapterm_service import SAPTermService
from services.fiori_rules import FioriRulesService
from services.nlp_analyzer import NLPAnalyzer
from services.ai_service import AIService
from services.glossary_service import GlossaryService
from services.wiki_service import WikiService
from services.help_portal_service import HelpPortalService


class Orchestrator:
    """Coordinates validation workflow for UI Labels and General Text."""

    def __init__(self):
        self.sapterm = SAPTermService()
        self.fiori = FioriRulesService()
        self.nlp = NLPAnalyzer()
        self.ai = AIService()
        self.glossary = GlossaryService()
        self.wiki = WikiService()
        self.help_portal = HelpPortalService()

    def validate_ui_label(self, text: str, element_type: str = "field", context: str = "") -> dict:
        """Full validation pipeline for UI labels."""
        result = {
            "input": {"text": text, "type": element_type, "context": context},
            "terminology": {},
            "guidelines": [],
            "german_readiness": {},
            "ai_analysis": {},
            "sources_checked": [],
            "summary": {}
        }

        # === 1. TERMINOLOGY (SAPterm + Glossary) ===
        result["terminology"] = self._check_terminology(text)
        result["sources_checked"].append("SAPterm")

        # === 2. FIORI GUIDELINES (rule-based) ===
        result["guidelines"] = self.fiori.validate_ui_label(text, element_type)
        result["sources_checked"].append("Fiori UI Text Guidelines")

        # === 3. GERMAN READINESS (NLP-based) ===
        result["german_readiness"] = self._check_german_readiness_label(text)

        # === 4. WIKI + HELP PORTAL SEARCH (for additional context) ===
        wiki_context = self._search_guidelines_context(text, element_type)
        result["sources_checked"].append("SAP Wiki")
        result["sources_checked"].append("Help Portal")

        # === 5. AI ANALYSIS (with all context from other sources) ===
        if self.ai.is_available():
            # Build enriched context for AI
            enriched_context = self._build_ai_context(context, result["terminology"], wiki_context)
            result["ai_analysis"] = self.ai.analyze_ui_label(text, element_type, enriched_context)
        else:
            result["ai_analysis"] = {"error": "AI not configured"}

        # === 6. SUMMARY ===
        result["summary"] = self._build_summary(result)

        return result

    def validate_text(self, text: str, context: str = "") -> dict:
        """Full validation pipeline for general text/documentation."""
        result = {
            "input": {"text": text, "type": "text", "context": context},
            "terminology": {},
            "guidelines": [],
            "german_readiness": {},
            "ai_analysis": {},
            "sources_checked": [],
            "summary": {}
        }

        # === 1. NLP ANALYSIS ===
        nlp_result = self.nlp.analyze(text)

        # === 2. TERMINOLOGY ===
        result["terminology"] = self._check_terminology_from_text(text, nlp_result)
        result["sources_checked"].append("SAPterm")

        # === 3. GUIDELINE ISSUES (from NLP) ===
        result["guidelines"] = self._build_text_guidelines(nlp_result)

        # === 4. GERMAN READINESS ===
        result["german_readiness"] = self._check_german_readiness_text(text, nlp_result)

        # === 5. WIKI SEARCH for relevant guidelines ===
        wiki_context = self._search_text_guidelines(text)
        result["sources_checked"].append("SAP Wiki")
        result["sources_checked"].append("Help Portal")

        # === 6. AI ANALYSIS ===
        if self.ai.is_available():
            enriched_context = context
            if wiki_context:
                enriched_context = f"{context}\n\nRelevant guidelines found: {wiki_context}" if context else f"Relevant guidelines: {wiki_context}"
            result["ai_analysis"] = self.ai.analyze_text(text, enriched_context)
        else:
            result["ai_analysis"] = {"error": "AI not configured"}

        # === 7. SUMMARY ===
        result["summary"] = self._build_summary(result)

        return result

    def _search_guidelines_context(self, text: str, element_type: str) -> str:
        """Search wiki and help portal for relevant guidelines and term renames."""
        context_parts = []

        # Search wiki for TERM RENAMES / DEPRECATIONS
        try:
            rename_result = self.wiki.search(f'"{text}" renamed OR deprecated OR "replaced by"', limit=3)
            if rename_result.get("results"):
                for r in rename_result["results"][:2]:
                    title = r.get("title", "")
                    excerpt = r.get("excerpt", "")[:150]
                    if "renam" in title.lower() or "renam" in excerpt.lower() or "deprecated" in excerpt.lower():
                        context_parts.append(f"⚠️ TERMINOLOGY CHANGE: {title} - {excerpt}")
        except Exception:
            pass

        # Search wiki for element-specific guidelines
        try:
            wiki_result = self.wiki.search_guidelines(text, element_type)
            if wiki_result.get("results"):
                for r in wiki_result["results"][:2]:
                    context_parts.append(f"Wiki: {r['title']} - {r.get('excerpt', '')[:100]}")
        except Exception:
            pass

        # Search help portal for term usage
        try:
            hp_result = self.help_portal.search_term_usage(text)
            if hp_result.get("results"):
                for r in hp_result["results"][:2]:
                    context_parts.append(f"Help Portal: {r['title']}")
        except Exception:
            pass

        return "; ".join(context_parts) if context_parts else ""

    def _search_text_guidelines(self, text: str) -> str:
        """Search for guidelines relevant to the text content."""
        # Extract key terms for searching
        words = text.split()[:5]  # First 5 words as search key
        search_term = " ".join(words)
        
        context_parts = []
        try:
            wiki_result = self.wiki.search(f"UA writing guidelines {search_term}", limit=2)
            if wiki_result.get("results"):
                for r in wiki_result["results"][:1]:
                    context_parts.append(f"{r['title']}: {r.get('excerpt', '')[:80]}")
        except Exception:
            pass

        return "; ".join(context_parts) if context_parts else ""

    def _build_ai_context(self, user_context: str, terminology: dict, wiki_context: str) -> str:
        """Build enriched context for AI from all sources."""
        parts = []
        
        if user_context:
            parts.append(f"User context: {user_context}")
        
        # Add SAPterm info
        if terminology.get("sapterm", {}).get("found"):
            results = terminology["sapterm"].get("results", [])
            if results:
                r = results[0]
                sapterm_info = f"SAPterm: '{r.get('term', '')}' found"
                if r.get("german"):
                    sapterm_info += f", German: '{r['german']}'"
                if r.get("component"):
                    sapterm_info += f", Component: {r['component']}"
                parts.append(sapterm_info)
        
        # Add wiki context
        if wiki_context:
            parts.append(f"Guidelines found: {wiki_context}")
        
        return " | ".join(parts) if parts else ""

    def _check_terminology(self, text: str) -> dict:
        """Check a UI label term in SAPterm and Glossary."""
        terminology = {
            "sapterm": {"searched": text},
            "glossary": {"searched": text},
            "similar_terms": []
        }

        sapterm_result = self.sapterm.search_term(text)
        terminology["sapterm"]["found"] = sapterm_result["found"]
        terminology["sapterm"]["results"] = sapterm_result["results"]
        terminology["sapterm"]["error"] = sapterm_result.get("error")

        words = text.split()
        if len(words) > 1:
            key_phrase = " ".join(words[-2:])
            similar = self.sapterm.search_similar(key_phrase)
            terminology["similar_terms"] = similar.get("results", [])[:5]

        glossary_result = self.glossary.search_term(text)
        terminology["glossary"]["found"] = glossary_result["found"]
        terminology["glossary"]["entries"] = glossary_result.get("entries", [])

        return terminology

    def _check_terminology_from_text(self, text: str, nlp_result: dict) -> dict:
        """Extract key terms from text and check in SAPterm."""
        terminology = {"terms_checked": [], "sapterm_error": None}

        compounds = nlp_result.get("compounds", [])
        terms_to_check = [c["text"] for c in compounds]

        import re
        capitalized = re.findall(r'[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+', text)
        terms_to_check.extend(capitalized[:5])
        terms_to_check = list(set(terms_to_check))[:8]

        for term in terms_to_check:
            sapterm_result = self.sapterm.search_term(term)
            terminology["terms_checked"].append({
                "term": term,
                "found": sapterm_result["found"],
                "german": sapterm_result["results"][0]["german"] if sapterm_result["results"] else None,
                "component": sapterm_result["results"][0]["component"] if sapterm_result["results"] else None
            })
            if sapterm_result.get("error"):
                terminology["sapterm_error"] = sapterm_result["error"]
                break

        return terminology

    def _check_german_readiness_label(self, text: str) -> dict:
        """German translation readiness checks for UI label."""
        readiness = {
            "length_expansion": self.fiori.estimate_german_length(text),
            "compound_issues": self.nlp.check_compound_nouns_short(text),
            "issues": []
        }

        words = text.split()
        ambiguous_words = {
            "service": "Dienst / Service / Leistung",
            "order": "Auftrag / Bestellung / Reihenfolge",
            "case": "Fall / Vorgang / Gehaeuse",
            "note": "Notiz / Hinweis / Vermerk",
            "type": "Art / Typ / Kategorie",
            "status": "Status / Zustand",
            "item": "Position / Element / Artikel",
            "process": "Prozess / Vorgang / Verarbeitung",
            "request": "Anfrage / Anforderung / Antrag",
            "document": "Dokument / Beleg / Unterlage",
            "report": "Bericht / Report / Meldung",
            "record": "Datensatz / Aufzeichnung / Eintrag",
            "entry": "Eintrag / Eingabe / Position",
            "view": "Ansicht / Sicht / Anzeige",
            "action": "Aktion / Massnahme / Vorgang"
        }

        for word in words:
            word_lower = word.lower()
            if word_lower in ambiguous_words:
                readiness["issues"].append({
                    "type": "german_ambiguity",
                    "severity": "info",
                    "message": f"'{word}' has multiple German translations: {ambiguous_words[word_lower]}",
                    "suggestion": "Add context so translator knows which meaning applies"
                })

        return readiness

    def _check_german_readiness_text(self, text: str, nlp_result: dict) -> dict:
        """German translation readiness checks for general text."""
        readiness = {
            "compound_nouns": [],
            "passive_voice": [],
            "vague_pronouns": [],
            "long_sentences": [],
            "issues": []
        }

        for compound in nlp_result.get("compounds", []):
            readiness["compound_nouns"].append({
                "type": "compound_noun", "severity": "warning",
                "text": compound["text"],
                "message": f"Noun compound ({compound['count']} nouns): '{compound['text']}'",
                "suggestion": "German reverses compound order. Add prepositions or hyphens."
            })

        for passive in nlp_result.get("passive_voice", []):
            readiness["passive_voice"].append({
                "type": "passive_voice", "severity": "info",
                "text": passive["text"],
                "message": f"Passive voice: '...{passive['text']}...'",
                "suggestion": "Consider active voice — German passive is more complex"
            })

        for pronoun in nlp_result.get("vague_pronouns", []):
            readiness["vague_pronouns"].append({
                "type": "vague_pronoun", "severity": "warning",
                "text": pronoun["pronoun"],
                "message": f"'{pronoun['pronoun']}' at sentence start — unclear reference",
                "suggestion": "Replace with specific noun (German pronouns need gender)"
            })

        for long_sent in nlp_result.get("long_sentences", []):
            readiness["long_sentences"].append({
                "type": "long_sentence", "severity": "info",
                "text": long_sent["sentence"][:80] + "...",
                "message": f"{long_sent['word_count']} words — German will be ~{int(long_sent['word_count'] * 1.3)} words",
                "suggestion": "Consider splitting for easier German translation"
            })

        return readiness

    def _build_text_guidelines(self, nlp_result: dict) -> list:
        """Convert NLP findings to guideline issues."""
        issues = []
        for vague in nlp_result.get("vague_verbs", []):
            issues.append({
                "type": "vague_verb", "severity": "info",
                "message": f"Generic verb '{vague['verb']}' — consider specific verb",
                "suggestion": f"Replace '{vague['lemma']}' with: create, configure, assign, process"
            })
        return issues

    def _build_summary(self, result: dict) -> dict:
        """Build a summary of all findings."""
        errors = 0
        warnings = 0
        infos = 0

        for issue in result.get("guidelines", []):
            sev = issue.get("severity", "info")
            if sev == "error": errors += 1
            elif sev == "warning": warnings += 1
            else: infos += 1

        german = result.get("german_readiness", {})
        for key in ["compound_nouns", "passive_voice", "vague_pronouns", "long_sentences", "issues", "compound_issues"]:
            items = german.get(key, [])
            if isinstance(items, list):
                for item in items:
                    sev = item.get("severity", "info")
                    if sev == "error": errors += 1
                    elif sev == "warning": warnings += 1
                    else: infos += 1

        if errors > 0:
            status = "issues_found"
            status_text = f"{errors} issue(s) to fix"
        elif warnings > 0:
            status = "review_recommended"
            status_text = f"{warnings} item(s) to review"
        else:
            status = "looks_good"
            status_text = "No major issues found"

        term_data = result.get("terminology", {})
        sapterm_found = False
        if "sapterm" in term_data:
            sapterm_found = term_data["sapterm"].get("found", False)
        elif "terms_checked" in term_data:
            sapterm_found = any(t.get("found") for t in term_data.get("terms_checked", []))

        return {
            "status": status,
            "status_text": status_text,
            "counts": {"errors": errors, "warnings": warnings, "info": infos},
            "sapterm_found": sapterm_found,
            "ai_available": self.ai.is_available()
        }

    def get_status(self) -> dict:
        """Get status of all services."""
        return {
            "sapterm": self.sapterm.get_status(),
            "ai": {"status": "connected" if self.ai.is_available() else "not_configured"},
            "wiki": {"status": "connected" if self.wiki.is_available() else "not_configured"},
            "help_portal": {"status": "connected"}
        }
