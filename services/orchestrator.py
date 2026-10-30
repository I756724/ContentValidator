"""
Orchestrator - Coordinates all validation services and produces final results
Sources: SAPterm, Fiori Rules, NLP, SAP Translation MCP, AI, Wiki, Help Portal
"""
import concurrent.futures
from services.sapterm_service import SAPTermService
from services.fiori_rules import FioriRulesService
from services.nlp_analyzer import NLPAnalyzer
from services.ai_service import AIService
from services.glossary_service import GlossaryService
from services.wiki_service import WikiService
from services.help_portal_service import HelpPortalService
from services.translation_service import TranslationService

LANGUAGE_NAMES = {
    "de-DE": "German",
    "fr-FR": "French",
    "es-ES": "Spanish",
    "it-IT": "Italian",
    "nl-NL": "Dutch",
    "pt-BR": "Portuguese (BR)",
    "ja-JP": "Japanese",
    "zh-CN": "Chinese Simplified",
    "ko-KR": "Korean",
    "ru-RU": "Russian",
    "pl-PL": "Polish",
}

ALLOWED_LANGUAGES = set(LANGUAGE_NAMES.keys())


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
        self.translation = TranslationService()

    def validate_ui_label(self, text: str, element_type: str = "field_label",
                          context: str = "", target_language: str = "de-DE") -> dict:
        """Full validation pipeline for UI labels."""
        target_language = target_language if target_language in ALLOWED_LANGUAGES else "de-DE"

        result = {
            "input": {"text": text, "type": element_type, "context": context,
                      "target_language": target_language,
                      "language_name": LANGUAGE_NAMES.get(target_language, target_language)},
            "terminology": {},
            "guidelines": [],
            "abbreviations": [],
            "consistency": [],
            "german_readiness": {},
            "translation": {},
            "ai_analysis": {},
            "sources_checked": [],
            "summary": {}
        }

        # 1. TERMINOLOGY (SAPterm) + GLOSSARY — run concurrently
        term_future, glossary_future = self._run_terminology_concurrent(text)
        result["sources_checked"].append("SAPterm")

        # 2. FIORI GUIDELINES (rule-based — all 10 element types)
        result["guidelines"] = self.fiori.validate_ui_label(text, element_type)
        result["sources_checked"].append("Fiori UI Text Guidelines")

        # 2b. ABBREVIATION CHECK
        result["abbreviations"] = self.fiori.check_abbreviations(text)

        # 2c. SAP TERMINOLOGY CONSISTENCY
        result["consistency"] = self.fiori.check_sap_standard_terminology(text)

        # 3. GERMAN TRANSLATION (SAP MT Portal → fallback: length estimate)
        result["translation"] = self._get_translation(text, target_language)
        result["sources_checked"].append("SAP MT Portal")

        # 4. GERMAN READINESS (ambiguity checks)
        result["german_readiness"] = self._check_german_readiness_label(text, result["translation"])

        # 5. WIKI + HELP PORTAL — parallel search for guideline context
        wiki_context = self._search_guidelines_context(text, element_type)
        result["sources_checked"].extend(["SAP Wiki", "Help Portal"])

        # 6. Collect terminology results (waited until after parallel work)
        result["terminology"] = self._collect_terminology(text, term_future, glossary_future)

        # 7. AI ANALYSIS (enriched with all context)
        if self.ai.is_available():
            enriched_context = self._build_ai_context(
                context, result["terminology"], wiki_context, result["translation"]
            )
            result["ai_analysis"] = self.ai.analyze_ui_label(text, element_type, enriched_context)
        else:
            result["ai_analysis"] = {"error": "AI not configured"}

        # 8. SUMMARY
        result["summary"] = self._build_summary(result)

        return result

    def validate_text(self, text: str, context: str = "",
                      target_language: str = "de-DE") -> dict:
        """Full validation pipeline for general text/documentation."""
        target_language = target_language if target_language in ALLOWED_LANGUAGES else "de-DE"

        result = {
            "input": {"text": text, "type": "text", "context": context,
                      "target_language": target_language,
                      "language_name": LANGUAGE_NAMES.get(target_language, target_language)},
            "terminology": {},
            "guidelines": [],
            "abbreviations": [],
            "consistency": [],
            "german_readiness": {},
            "translation": {},
            "ai_analysis": {},
            "sources_checked": [],
            "summary": {}
        }

        # 1. NLP ANALYSIS
        nlp_result = self.nlp.analyze(text)

        # 2. TERMINOLOGY
        term_future, glossary_future = self._run_terminology_concurrent_from_text(text, nlp_result)
        result["sources_checked"].append("SAPterm")

        # 3. GUIDELINE ISSUES (NLP-derived)
        result["guidelines"] = self._build_text_guidelines(nlp_result)

        # 3b. ABBREVIATION + CONSISTENCY checks
        result["abbreviations"] = self.fiori.check_abbreviations(text)
        result["consistency"]   = self.fiori.check_sap_standard_terminology(text)

        # 4. TRANSLATION (first 200 chars for preview)
        result["translation"] = self._get_translation(text[:200], target_language)
        result["sources_checked"].append("SAP MT Portal")

        # 5. GERMAN READINESS
        result["german_readiness"] = self._check_german_readiness_text(text, nlp_result)

        # 6. WIKI SEARCH — parallel
        wiki_context = self._search_text_guidelines(text)
        result["sources_checked"].extend(["SAP Wiki", "Help Portal"])

        # 7. Collect terminology
        result["terminology"] = self._collect_terminology_from_text(text, nlp_result,
                                                                     term_future, glossary_future)

        # 8. AI ANALYSIS
        if self.ai.is_available():
            enriched_context = context
            if wiki_context:
                enriched_context = (f"{context}\n\nRelevant guidelines: {wiki_context}"
                                    if context else f"Relevant guidelines: {wiki_context}")
            result["ai_analysis"] = self.ai.analyze_text(text, enriched_context)
        else:
            result["ai_analysis"] = {"error": "AI not configured"}

        # 9. SUMMARY
        result["summary"] = self._build_summary(result)

        return result

    # ── translation ──────────────────────────────────────────────────────────

    @staticmethod
    def _calc_translation_risk(en_len: int, de_len: int) -> str:
        """
        Risk based on absolute German char count AND expansion ratio.
        Short labels with extreme expansion are also marked high risk.
        """
        if en_len == 0:
            return "low"
        expansion = (de_len - en_len) / en_len * 100
        if de_len > 40 or (en_len <= 15 and expansion > 50):
            return "high"
        if de_len > 25 or expansion > 35:
            return "medium"
        return "low"

    def _get_translation(self, text: str, target_language: str = "de-DE") -> dict:
        """Get translation from SAP MT Portal; fall back to estimate (German only)."""
        if self.translation.is_available():
            res = self.translation.translate(text, target_language=target_language,
                                             source_language="en-US")
            if res.get("translated"):
                translated = res["translated"]
                de_len = len(translated)
                en_len = len(text)
                expansion = round((de_len - en_len) / en_len * 100) if en_len > 0 else 0
                return {
                    "source": "mt_portal",
                    "target_language": target_language,
                    "translated": translated,
                    "english_chars": en_len,
                    "german_chars": de_len,
                    "expansion_percent": expansion,
                    "risk": self._calc_translation_risk(en_len, de_len),
                    "error": None
                }
            # MT Portal available but returned no translation
            fallback = self.fiori.estimate_german_length(text) if target_language == "de-DE" else None
            return {
                "source": "mt_portal",
                "target_language": target_language,
                "translated": None,
                "error": res.get("error"),
                "fallback": fallback
            }

        # MT Portal unavailable — estimate for German only
        if target_language == "de-DE":
            estimate = self.fiori.estimate_german_length(text)
            return {
                "source": "estimate",
                "target_language": target_language,
                "translated": None,
                "error": None,
                "fallback": estimate
            }

        return {
            "source": "unavailable",
            "target_language": target_language,
            "translated": None,
            "error": None,
            "fallback": None,
            "note": f"Length estimate not available for {LANGUAGE_NAMES.get(target_language, target_language)}. "
                    "Connect MT Portal for live translation."
        }

    # ── terminology (concurrent) ─────────────────────────────────────────────

    def _run_terminology_concurrent(self, text: str):
        """Submit SAPterm and Glossary lookups in parallel; return futures."""
        executor = concurrent.futures.ThreadPoolExecutor(max_workers=2)
        term_future = executor.submit(self.sapterm.search_term, text)
        glossary_future = executor.submit(self.glossary.search_term, text)
        executor.shutdown(wait=False)
        return term_future, glossary_future

    def _collect_terminology(self, text: str, term_future, glossary_future) -> dict:
        """Wait for terminology futures and assemble result dict."""
        terminology = {
            "sapterm": {"searched": text},
            "glossary": {"searched": text},
            "similar_terms": []
        }
        try:
            sapterm_result = term_future.result(timeout=15)
            terminology["sapterm"]["found"] = sapterm_result["found"]
            terminology["sapterm"]["results"] = sapterm_result["results"]
            terminology["sapterm"]["error"] = sapterm_result.get("error")
        except Exception as e:
            terminology["sapterm"]["found"] = False
            terminology["sapterm"]["results"] = []
            terminology["sapterm"]["error"] = str(e)

        try:
            glossary_result = glossary_future.result(timeout=15)
            terminology["glossary"]["found"] = glossary_result["found"]
            terminology["glossary"]["entries"] = glossary_result.get("entries", [])
        except Exception:
            terminology["glossary"]["found"] = False
            terminology["glossary"]["entries"] = []

        # Similar terms (last 2 words phrase)
        words = text.split()
        if len(words) > 1:
            key_phrase = " ".join(words[-2:])
            try:
                similar = self.sapterm.search_similar(key_phrase)
                terminology["similar_terms"] = similar.get("results", [])[:5]
            except Exception:
                pass

        return terminology

    def _run_terminology_concurrent_from_text(self, text: str, nlp_result: dict):
        """Submit multiple SAPterm lookups from NLP-extracted terms."""
        import re
        compounds = nlp_result.get("compounds", [])
        terms_to_check = [c["text"] for c in compounds]
        capitalized = re.findall(r'[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+', text)
        terms_to_check.extend(capitalized[:5])
        terms_to_check = list(set(terms_to_check))[:8]

        executor = concurrent.futures.ThreadPoolExecutor(max_workers=min(len(terms_to_check) + 1, 4))
        term_futures = {term: executor.submit(self.sapterm.search_term, term)
                        for term in terms_to_check}
        glossary_future = executor.submit(self.glossary.search_term, text.split()[0] if text else "")
        executor.shutdown(wait=False)
        return term_futures, glossary_future

    def _collect_terminology_from_text(self, text: str, nlp_result: dict,
                                       term_futures, glossary_future) -> dict:
        terminology = {"terms_checked": [], "sapterm_error": None}
        for term, future in term_futures.items():
            try:
                sapterm_result = future.result(timeout=15)
                terminology["terms_checked"].append({
                    "term": term,
                    "found": sapterm_result["found"],
                    "german": sapterm_result["results"][0]["german"] if sapterm_result["results"] else None,
                    "component": sapterm_result["results"][0]["component"] if sapterm_result["results"] else None
                })
                if sapterm_result.get("error"):
                    terminology["sapterm_error"] = sapterm_result["error"]
            except Exception as e:
                terminology["sapterm_error"] = str(e)
        return terminology

    # ── guidelines context (wiki + help portal — parallel) ──────────────────

    def _search_guidelines_context(self, text: str, element_type: str) -> str:
        """Search wiki and help portal in parallel for guideline context."""
        def _search_rename():
            try:
                r = self.wiki.search(f'"{text}" renamed OR deprecated OR "replaced by"', limit=3)
                parts = []
                if r.get("results"):
                    for item in r["results"][:2]:
                        title = item.get("title", "")
                        excerpt = item.get("excerpt", "")[:150]
                        if any(k in (title + excerpt).lower() for k in ("renam", "deprecated", "replaced")):
                            parts.append(f"TERMINOLOGY CHANGE: {title} — {excerpt}")
                return parts
            except Exception:
                return []

        def _search_wiki_guidelines():
            try:
                r = self.wiki.search_guidelines(text, element_type)
                if r.get("results"):
                    return [f"Wiki: {item['title']} — {item.get('excerpt', '')[:100]}"
                            for item in r["results"][:2]]
                return []
            except Exception:
                return []

        def _search_hp():
            try:
                r = self.help_portal.search_term_usage(text)
                if r.get("results"):
                    return [f"Help Portal: {item['title']}" for item in r["results"][:2]]
                return []
            except Exception:
                return []

        context_parts = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            futures = [executor.submit(_search_rename),
                       executor.submit(_search_wiki_guidelines),
                       executor.submit(_search_hp)]
            for future in concurrent.futures.as_completed(futures, timeout=12):
                try:
                    context_parts.extend(future.result())
                except Exception:
                    pass

        return "; ".join(context_parts) if context_parts else ""

    def _search_text_guidelines(self, text: str) -> str:
        """Search wiki for guidelines relevant to a general text snippet."""
        words = text.split()[:5]
        search_term = " ".join(words)

        def _wiki():
            try:
                r = self.wiki.search(f"UA writing guidelines {search_term}", limit=2)
                if r.get("results"):
                    return [f"{item['title']}: {item.get('excerpt', '')[:80]}"
                            for item in r["results"][:1]]
                return []
            except Exception:
                return []

        def _hp():
            try:
                r = self.help_portal.search_term_usage(search_term)
                if r.get("results"):
                    return [f"Help Portal: {item['title']}" for item in r["results"][:1]]
                return []
            except Exception:
                return []

        parts = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            futures = [executor.submit(_wiki), executor.submit(_hp)]
            for future in concurrent.futures.as_completed(futures, timeout=10):
                try:
                    parts.extend(future.result())
                except Exception:
                    pass

        return "; ".join(parts) if parts else ""

    # ── AI context builder ───────────────────────────────────────────────────

    def _build_ai_context(self, user_context: str, terminology: dict,
                          wiki_context: str, translation: dict) -> str:
        parts = []

        if user_context:
            parts.append(f"User context: {user_context}")

        if terminology.get("sapterm", {}).get("found"):
            results = terminology["sapterm"].get("results", [])
            if results:
                r = results[0]
                info = f"SAPterm: '{r.get('term', '')}' found"
                if r.get("german"):
                    info += f", official German: '{r['german']}'"
                if r.get("component"):
                    info += f", Component: {r['component']}"
                parts.append(info)

        if translation.get("source") == "mt_portal" and translation.get("translated"):
            parts.append(
                f"SAP MT translation: '{translation['translated']}' "
                f"({translation['german_chars']} chars, {translation['expansion_percent']:+d}%)"
            )
        elif translation.get("fallback"):
            fb = translation["fallback"]
            parts.append(
                f"Estimated DE length: ~{fb['estimated_german_chars']} chars "
                f"(+{fb['expansion_percent']}%), risk: {fb['risk']}"
            )

        if wiki_context:
            parts.append(f"Guidelines found: {wiki_context}")

        return " | ".join(parts) if parts else ""

    # ── German readiness ─────────────────────────────────────────────────────

    AMBIGUOUS_WORDS = {
        "service": "Dienst / Service / Leistung",
        "order": "Auftrag / Bestellung / Reihenfolge",
        "case": "Fall / Vorgang / Gehäuse",
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
        "action": "Aktion / Maßnahme / Vorgang",
        "account": "Konto / Kundenkonto / Sachkonto",
        "period": "Zeitraum / Periode / Geschäftsjahr",
        "object": "Objekt / Sachkonto / Gegenstand",
        "class": "Klasse / Kategorie / Materialklasse",
        "posting": "Buchung / Buchungsvorgang",
        "run": "Lauf / Ausführung / Stapellauf",
        "plan": "Plan / Planung / Soll",
        "charge": "Belastung / Gebühr / Zuschlag",
        "position": "Position / Stelle / Lage",
        "balance": "Saldo / Bestand / Gleichgewicht",
    }

    def _check_german_readiness_label(self, text: str, translation: dict) -> dict:
        readiness = {
            "length_expansion": translation.get("fallback") or self.fiori.estimate_german_length(text),
            "compound_issues": self.nlp.check_compound_nouns_short(text),
            "issues": []
        }

        if translation.get("source") == "mt_portal" and translation.get("translated"):
            readiness["length_expansion"] = {
                "english_chars": translation["english_chars"],
                "estimated_german_chars": translation["german_chars"],
                "expansion_percent": translation["expansion_percent"],
                "risk": translation["risk"],
                "actual": True
            }

        words = text.split()
        for word in words:
            word_lower = word.lower().rstrip("s")
            match = self.AMBIGUOUS_WORDS.get(word.lower()) or self.AMBIGUOUS_WORDS.get(word_lower)
            if match:
                readiness["issues"].append({
                    "type": "german_ambiguity",
                    "severity": "info",
                    "message": f"'{word}' has multiple German translations: {match}",
                    "suggestion": "Add context so the translator can choose the correct German term"
                })

        return readiness

    def _check_german_readiness_text(self, text: str, nlp_result: dict) -> dict:
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
                "suggestion": "German reverses compound order. Add prepositions or hyphens for clarity."
            })

        for passive in nlp_result.get("passive_voice", []):
            readiness["passive_voice"].append({
                "type": "passive_voice", "severity": "info",
                "text": passive["text"],
                "message": f"Passive voice: '...{passive['text']}...'",
                "suggestion": "Consider active voice — German passive adds extra words"
            })

        for pronoun in nlp_result.get("vague_pronouns", []):
            readiness["vague_pronouns"].append({
                "type": "vague_pronoun", "severity": "warning",
                "text": pronoun["pronoun"],
                "message": f"'{pronoun['pronoun']}' at sentence start — unclear reference",
                "suggestion": "Replace with specific noun (German pronouns require gender agreement)"
            })

        for long_sent in nlp_result.get("long_sentences", []):
            readiness["long_sentences"].append({
                "type": "long_sentence", "severity": "info",
                "text": long_sent["sentence"][:80] + "...",
                "message": f"{long_sent['word_count']} words — German will be ~{int(long_sent['word_count'] * 1.3)} words",
                "suggestion": "Consider splitting for easier German translation"
            })

        # Ambiguous word check for text mode too
        words = text.split()
        seen = set()
        for word in words:
            word_lower = word.lower().rstrip("s")
            key = word.lower()
            if key in seen:
                continue
            match = self.AMBIGUOUS_WORDS.get(key) or self.AMBIGUOUS_WORDS.get(word_lower)
            if match:
                seen.add(key)
                readiness["issues"].append({
                    "type": "german_ambiguity",
                    "severity": "info",
                    "message": f"'{word}' has multiple German translations: {match}",
                    "suggestion": "Add context so the translator can choose the correct German term"
                })

        return readiness

    def _build_text_guidelines(self, nlp_result: dict) -> list:
        issues = []
        for vague in nlp_result.get("vague_verbs", []):
            issues.append({
                "type": "vague_verb", "severity": "info",
                "message": f"Generic verb '{vague['verb']}' — use a specific verb",
                "suggestion": f"Replace '{vague['lemma']}' with: create, configure, assign, process, submit"
            })
        return issues

    # ── summary ──────────────────────────────────────────────────────────────

    def _build_summary(self, result: dict) -> dict:
        errors = warnings = infos = 0

        for issue in result.get("guidelines", []):
            sev = issue.get("severity", "info")
            if sev == "error": errors += 1
            elif sev == "warning": warnings += 1
            else: infos += 1

        german = result.get("german_readiness", {})
        for key in ["compound_nouns", "passive_voice", "vague_pronouns",
                    "long_sentences", "issues", "compound_issues"]:
            for item in german.get(key, []):
                sev = item.get("severity", "info")
                if sev == "error": errors += 1
                elif sev == "warning": warnings += 1
                else: infos += 1

        # Abbreviations and consistency issues are always warnings
        warnings += len(result.get("abbreviations", []))
        warnings += len(result.get("consistency", []))

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

        translation = result.get("translation", {})
        translation_available = (translation.get("source") == "mt_portal"
                                 and bool(translation.get("translated")))

        # Complexity: use AI value if available, otherwise derive from rule counts
        ai_complexity = result.get("ai_analysis", {}).get("complexity", "")
        if ai_complexity in ("Low", "Medium", "High"):
            complexity = ai_complexity
        else:
            if errors > 0 or warnings > 2:
                complexity = "High"
            elif warnings > 0 or infos > 0:
                complexity = "Medium"
            else:
                complexity = "Low"

        return {
            "status": status,
            "status_text": status_text,
            "counts": {"errors": errors, "warnings": warnings, "info": infos},
            "sapterm_found": sapterm_found,
            "translation_available": translation_available,
            "target_language": result.get("input", {}).get("target_language", "de-DE"),
            "complexity": complexity,
            "ai_available": self.ai.is_available()
        }

    def get_status(self) -> dict:
        return {
            "sapterm": self.sapterm.get_status(),
            "wiki": self.wiki.get_status(),
            "translation": self.translation.get_status(),
            "ai": self.ai.test_connection(),
            "help_portal": {"status": "connected"}
        }
