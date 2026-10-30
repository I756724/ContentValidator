"""
Fiori UI Text Guidelines - Rule-based validation
Source: SAP Fiori Design System (fiori.design/guidelines/fiori-design-web)
Covers all 10 element types used in UA Content Validator.
"""
import re


class FioriRulesService:
    """Validates UI labels against SAP Fiori UI Text Guidelines."""

    ARTICLES = ["the", "a", "an"]

    INSTRUCTIONAL_WORDS = ["click", "press", "tap", "hit", "select here", "click here"]

    ACTION_VERBS = [
        "add", "approve", "assign", "cancel", "change", "check", "clear", "close",
        "confirm", "copy", "create", "decline", "delete", "deselect", "display",
        "download", "edit", "enable", "enter", "export", "filter", "find",
        "generate", "go", "hide", "import", "insert", "link", "log",
        "manage", "merge", "move", "open", "order", "post", "print", "process",
        "provide", "publish", "read", "refresh", "reject", "release", "remove",
        "rename", "replace", "request", "reset", "resolve", "restart", "restore",
        "retry", "return", "review", "run", "save", "schedule", "search", "select",
        "send", "set", "share", "show", "sign", "sort", "specify", "split", "start",
        "stop", "submit", "switch", "sync", "transfer", "trigger",
        "undo", "update", "upload", "validate", "verify", "view"
    ]

    FORBIDDEN_PUNCTUATION = [".", "!", ";", ":", ","]

    SUCCESS_WORDS = ["successfully", "successfully."]

    def _is_gerund_of_action_verb(self, word: str) -> bool:
        """
        True only when word is a gerund form of a known ACTION_VERB.
        Avoids false positives on noun/adjective -ing words (Billing, Marketing, etc.).
        """
        w = word.lower()
        if not w.endswith("ing"):
            return False
        root = w[:-3]                          # saving  → sav
        root_e = root + "e"                    # saving  → save
        root_de = root[:-1] if len(root) > 1 and root[-1] == root[-2] else None  # running → run

        return (
            root in self.ACTION_VERBS          # edit → editing
            or root_e in self.ACTION_VERBS     # save → saving
            or (root_de and root_de in self.ACTION_VERBS)  # run → running
        )

    def validate_ui_label(self, text: str, element_type: str = "field_label") -> list:
        """
        Validate a UI label against Fiori guidelines.

        element_type values (matching the frontend dropdown):
            app_title, button, action, tab, section_heading,
            field_label, column_header, status_text, message_text, facet_title
        """
        issues = []
        words = text.split()
        word_count = len(words)

        dispatch = {
            "button":         self._check_button_rules,
            "app_title":      self._check_app_title_rules,
            "action":         self._check_action_rules,
            "tab":            self._check_tab_rules,
            "section_heading": self._check_section_heading_rules,
            "field_label":    self._check_field_label_rules,
            # legacy alias kept for backward compat
            "field":          self._check_field_label_rules,
            "column_header":  self._check_column_header_rules,
            "column":         self._check_column_header_rules,
            "status_text":    self._check_status_text_rules,
            "message_text":   self._check_message_text_rules,
            "facet_title":    self._check_facet_title_rules,
        }

        handler = dispatch.get(element_type)
        if handler:
            issues.extend(handler(text, words, word_count))

        issues.extend(self._check_general_rules(text, words, element_type))

        return issues

    # ── element-specific rules ──────────────────────────────────────────────

    def _check_app_title_rules(self, text: str, words: list, word_count: int) -> list:
        """App title rules: verb+object for transactional, noun-only for analytical."""
        issues = []
        if not words:
            return issues

        first_lower = words[0].lower()

        # Analytical/overview apps: no verb-first constraint, but check for "Analysis" suffix
        if text.lower().endswith("analysis"):
            issues.append({
                "type": "fiori_app_title_analysis",
                "severity": "warning",
                "message": "App title ends with 'Analysis' — Fiori recommends avoiding this suffix",
                "suggestion": "Use a noun-based title describing the content, e.g. 'Revenue Trends' instead of 'Revenue Analysis'",
                "guideline": "Fiori: Analytical app names should not end in 'Analysis'"
            })

        # Transactional apps should start with standard Fiori action verbs
        transactional_verbs = ["manage", "process", "approve", "create", "monitor", "display", "run", "post", "release"]
        if first_lower not in transactional_verbs and first_lower not in self.ACTION_VERBS:
            # Not necessarily wrong — could be an analytical app. Only warn if it reads like a task.
            if word_count > 2 and first_lower.endswith("ing"):
                issues.append({
                    "type": "fiori_app_title_gerund",
                    "severity": "warning",
                    "message": f"App title starts with gerund '{words[0]}' — use imperative verb or noun",
                    "suggestion": f"Try '{first_lower[:-3].capitalize()} ...' or a noun-based title",
                    "guideline": "Fiori: Transactional app titles use imperative verb (Manage, Process, Approve)"
                })

        # No ampersands
        if "&" in text:
            issues.append({
                "type": "fiori_app_title_ampersand",
                "severity": "error",
                "message": "App title contains '&' — Fiori guidelines require spelling out 'and'",
                "suggestion": text.replace("&", "and"),
                "guideline": "Fiori: Do not use '&' in app titles"
            })

        return issues

    def _check_button_rules(self, text: str, words: list, word_count: int) -> list:
        """Button: imperative verb, max 3 words, no instructional words."""
        issues = []
        if not words:
            return issues

        if word_count > 3:
            issues.append({
                "type": "fiori_button_length",
                "severity": "error",
                "message": f"Button text too long ({word_count} words, max 3)",
                "suggestion": f"Shorten to 1-3 words: '{' '.join(words[:2])}'",
                "guideline": "Fiori: Button labels should be 1-3 words (verb + object)"
            })

        first_word = words[0].lower()
        if self._is_gerund_of_action_verb(first_word):
            issues.append({
                "type": "fiori_button_verb_form",
                "severity": "error",
                "message": f"Button uses gerund '{words[0]}' — must use imperative verb",
                "suggestion": f"Use '{first_word[:-3].capitalize()}' instead of '{words[0]}'",
                "guideline": "Fiori: Buttons use imperative verb form (Save, not Saving)"
            })
        elif first_word not in self.ACTION_VERBS:
            is_likely_verb = any(first_word.startswith(v[:3]) for v in self.ACTION_VERBS)
            if not is_likely_verb and word_count > 1:
                issues.append({
                    "type": "fiori_button_no_verb",
                    "severity": "warning",
                    "message": "Button should start with an action verb",
                    "suggestion": "Start with: Create, Save, Delete, Add, Open, Submit, Approve",
                    "guideline": "Fiori: Button text = Action verb + Object (e.g. 'Save Draft')"
                })

        text_lower = text.lower()
        for word in self.INSTRUCTIONAL_WORDS:
            if word in text_lower:
                issues.append({
                    "type": "fiori_instructional_word",
                    "severity": "error",
                    "message": f"Instructional word '{word}' not allowed in button text",
                    "suggestion": "Describe the action, not the gesture. Remove 'Click', 'Press', 'Tap'.",
                    "guideline": "Fiori: Never use 'Click', 'Press', 'Tap' in button text"
                })
                break

        return issues

    def _check_action_rules(self, text: str, words: list, word_count: int) -> list:
        """Action (link/toolbar): verb + object, max 5 words."""
        issues = []
        if not words:
            return issues

        if word_count > 5:
            issues.append({
                "type": "fiori_action_length",
                "severity": "warning",
                "message": f"Action text is long ({word_count} words, recommended max 5)",
                "suggestion": f"Shorten to verb + object. Example: '{' '.join(words[:3])}'",
                "guideline": "Fiori: Actions (links/toolbar) should be concise verb phrases (1-5 words)"
            })

        if words:
            first_lower = words[0].lower()
            if self._is_gerund_of_action_verb(first_lower):
                issues.append({
                    "type": "fiori_action_gerund",
                    "severity": "warning",
                    "message": f"Action starts with gerund '{words[0]}' — prefer imperative verb",
                    "suggestion": f"Use '{first_lower[:-3].capitalize()}' instead of '{words[0]}'",
                    "guideline": "Fiori: Actions use imperative verb + object (Edit List, Copy Template)"
                })

        return issues

    def _check_tab_rules(self, text: str, words: list, word_count: int) -> list:
        """Tab: noun phrase, 1-3 words, title case."""
        issues = []

        if word_count > 3:
            issues.append({
                "type": "fiori_tab_length",
                "severity": "warning",
                "message": f"Tab label is long ({word_count} words, recommended max 3)",
                "suggestion": f"Shorten: '{' '.join(words[:2])}'",
                "guideline": "Fiori: Tab labels should be concise noun phrases (1-3 words)"
            })

        if words:
            first_lower = words[0].lower()
            if first_lower in self.ACTION_VERBS:
                issues.append({
                    "type": "fiori_tab_verb",
                    "severity": "warning",
                    "message": f"Tab starts with verb '{words[0]}' — tabs use noun phrases",
                    "suggestion": "Use a noun phrase: 'General Information', 'Items', 'Price Details'",
                    "guideline": "Fiori: Tab labels are noun phrases, not actions"
                })

        return issues

    def _check_section_heading_rules(self, text: str, words: list, word_count: int) -> list:
        """Section heading: noun phrase, title case, don't repeat parent."""
        issues = []

        if word_count > 4:
            issues.append({
                "type": "fiori_section_length",
                "severity": "warning",
                "message": f"Section heading is long ({word_count} words, recommended max 4)",
                "suggestion": "Use a concise noun phrase like 'Account', 'Processing Data', 'General'",
                "guideline": "Fiori: Section headings are concise noun phrases"
            })

        return issues

    def _check_field_label_rules(self, text: str, words: list, word_count: int) -> list:
        """Field label: noun phrase, no verbs, max 4 words, no colon."""
        issues = []

        if word_count > 4:
            issues.append({
                "type": "fiori_field_length",
                "severity": "warning",
                "message": f"Field label is long ({word_count} words, recommended max 4)",
                "suggestion": "Shorten. Move extra detail to a tooltip or placeholder text.",
                "guideline": "Fiori: Field labels are concise noun phrases (1-4 words)"
            })

        if text.endswith(":"):
            issues.append({
                "type": "fiori_field_colon",
                "severity": "error",
                "message": "Field label ends with ':' — the colon is added automatically by the UI framework",
                "suggestion": text.rstrip(":").strip(),
                "guideline": "Fiori: Do not include the colon in field label text"
            })

        if words:
            first_lower = words[0].lower()
            if first_lower in self.ACTION_VERBS:
                issues.append({
                    "type": "fiori_field_verb",
                    "severity": "error",
                    "message": f"Field label starts with verb '{words[0]}' — field labels are noun phrases",
                    "suggestion": "Remove the verb. Example: 'Customer Name' not 'Enter Customer Name'",
                    "guideline": "Fiori: Field labels do not contain verbs"
                })

        return issues

    def _check_column_header_rules(self, text: str, words: list, word_count: int) -> list:
        """Column header: max 3 words, title case."""
        issues = []

        if word_count > 3:
            issues.append({
                "type": "fiori_column_length",
                "severity": "warning",
                "message": f"Column header is long ({word_count} words, recommended max 3)",
                "suggestion": "Shorten for table readability. Use standard abbreviations if needed.",
                "guideline": "Fiori: Column headers should be brief (1-3 words)"
            })

        return issues

    def _check_status_text_rules(self, text: str, words: list, word_count: int) -> list:
        """Status text: no ending period, sentence case for long, title for short."""
        issues = []

        if text.endswith("."):
            issues.append({
                "type": "fiori_status_period",
                "severity": "error",
                "message": "Status text should not end with a period",
                "suggestion": text.rstrip(".").strip(),
                "guideline": "Fiori: Status texts do not end with a period"
            })

        if word_count > 4:
            # Long status texts use sentence case — check if first word only is capitalized
            if len(words) > 1 and any(w[0].isupper() and w.lower() not in ("id", "sap") for w in words[1:] if len(w) > 3):
                issues.append({
                    "type": "fiori_status_case",
                    "severity": "warning",
                    "message": "Long status text should use sentence case (capitalize first word only)",
                    "suggestion": words[0] + " " + " ".join(w.lower() for w in words[1:]),
                    "guideline": "Fiori: Status texts longer than 3 words use sentence case"
                })

        return issues

    def _check_message_text_rules(self, text: str, words: list, word_count: int) -> list:
        """Message text: no 'successfully', no (s), no semicolons, action-oriented."""
        issues = []
        text_lower = text.lower()

        if "successfully" in text_lower:
            issues.append({
                "type": "fiori_message_successfully",
                "severity": "error",
                "message": "Message text contains 'successfully' — Fiori prohibits this word",
                "suggestion": "State the completed action instead. Example: 'Order created' not 'Order created successfully'",
                "guideline": "Fiori: Never use 'successfully' in message texts"
            })

        if "(s)" in text:
            issues.append({
                "type": "fiori_message_plural_s",
                "severity": "error",
                "message": "Message text contains '(s)' — not allowed in Fiori",
                "suggestion": "Use plural form instead: 'items' not 'item(s)'",
                "guideline": "Fiori: Do not use (s) to indicate optional plural"
            })

        if ";" in text:
            issues.append({
                "type": "fiori_message_semicolon",
                "severity": "error",
                "message": "Message text contains semicolon — not allowed in Fiori messages",
                "suggestion": "Split into two sentences or use a comma",
                "guideline": "Fiori: No semicolons in message texts"
            })

        # Complete sentences need periods, sentence fragments do not
        if text and text[-1] == "." and word_count <= 4:
            issues.append({
                "type": "fiori_message_short_period",
                "severity": "warning",
                "message": "Short message text ends with period — omit for fragments",
                "suggestion": text.rstrip("."),
                "guideline": "Fiori: Only use periods for complete sentences in messages"
            })

        return issues

    def _check_facet_title_rules(self, text: str, words: list, word_count: int) -> list:
        """Facet title (Object Page header): noun phrase, title case."""
        issues = []

        if word_count > 4:
            issues.append({
                "type": "fiori_facet_length",
                "severity": "warning",
                "message": f"Facet title is long ({word_count} words, recommended max 4)",
                "suggestion": "Keep facet titles concise: 'Price Overview', 'Life Cycle Status'",
                "guideline": "Fiori: Facet titles are concise noun phrases (1-4 words)"
            })

        return issues

    # ── general rules (apply to all element types) ──────────────────────────

    def _check_general_rules(self, text: str, words: list, element_type: str) -> list:
        """Rules that apply to every UI element type."""
        issues = []
        if not words:
            return issues

        # No articles at start
        if words[0].lower() in self.ARTICLES:
            issues.append({
                "type": "fiori_article_start",
                "severity": "error",
                "message": f"UI labels must not start with article '{words[0]}'",
                "suggestion": f"Remove '{words[0]}': '{' '.join(words[1:])}'",
                "guideline": "Fiori: Omit articles (the, a, an) in UI labels"
            })

        # No internal articles in short labels (not for message_text)
        if element_type not in ("message_text",):
            for i, word in enumerate(words):
                if i > 0 and word.lower() in self.ARTICLES and i < len(words) - 1:
                    issues.append({
                        "type": "fiori_article_internal",
                        "severity": "warning",
                        "message": f"Article '{word}' inside label — consider removing",
                        "suggestion": "Omit article for conciseness",
                        "guideline": "Fiori: Omit articles in UI labels where possible"
                    })
                    break

        # No ending punctuation (message_text is exempt — it uses periods)
        if element_type not in ("message_text",) and text and text[-1] in self.FORBIDDEN_PUNCTUATION:
            issues.append({
                "type": "fiori_punctuation",
                "severity": "error",
                "message": f"UI label ends with '{text[-1]}' — not allowed",
                "suggestion": f"Remove ending punctuation: '{text[:-1]}'",
                "guideline": "Fiori: No ending punctuation in labels (exception: '?' for questions)"
            })

        # No ellipsis except file-browse buttons
        if "..." in text and element_type != "button":
            issues.append({
                "type": "fiori_ellipsis",
                "severity": "warning",
                "message": "Ellipsis '...' in label — only allowed in file-browse buttons",
                "suggestion": "Remove ellipsis unless this is a file-browse button",
                "guideline": "Fiori: Avoid ellipsis in UI labels"
            })

        return issues

    # ── German length estimation ─────────────────────────────────────────────

    # Abbreviations that are SAP-approved and should NOT be flagged
    APPROVED_ABBREVIATIONS = {
        "SAP", "ID", "UI", "UX", "API", "URL", "PDF", "XML", "CSV", "JSON",
        "HTTP", "HTTPS", "RFC", "BAPI", "CDS", "OData", "REST", "UUID",
        "VAT", "GST", "PO",   # PO is ambiguous but very common
        "GL", "AR", "AP",     # Financial abbreviations standard in SAP
        "HR", "HCM", "SD", "MM", "FI", "CO", "PM", "QM", "WM", "EWM",
        "MDG", "GRC", "SRM", "CRM", "SCM", "ERP", "BTP", "ABAP",
        "S4", "HANA",         # flagged in terminology, not abbreviation check
    }

    # Wrong SAP term → correct SAP term (S/4HANA era naming)
    SAP_STANDARD_TERMS = {
        # Product naming
        "s4hana":       ("SAP S/4HANA",         "Use full product name 'SAP S/4HANA'"),
        "s/4":          ("SAP S/4HANA",          "Use full product name 'SAP S/4HANA'"),
        "fiori":        ("SAP Fiori",            "Use full product name 'SAP Fiori' on first reference"),
        "hana":         ("SAP HANA",             "Use full product name 'SAP HANA'"),
        "business objects": ("SAP BusinessObjects", "Use official product name 'SAP BusinessObjects'"),
        "bobj":         ("SAP BusinessObjects",  "Use official product name, not internal acronym 'BOBJ'"),
        "solman":       ("SAP Solution Manager", "Use official product name, not internal acronym"),

        # Role / entity naming (S/4HANA renamed these)
        "vendor":       ("supplier",             "In SAP S/4HANA, 'vendor' was renamed to 'supplier'"),
        "customer master": ("business partner",  "In SAP S/4HANA, use 'business partner' not 'customer master'"),
        "vendor master": ("business partner",    "In SAP S/4HANA, use 'business partner' not 'vendor master'"),
        "material":     ("product",              "In SAP S/4HANA, 'material' was renamed to 'product' in most contexts"),

        # Common wrong phrasings
        "click on":     ("select",               "Fiori: Use 'Select' not 'Click on' in UI text"),
        "press on":     ("select",               "Fiori: Use 'Select' not 'Press on' in UI text"),
        "the user":     ("[specific role]",      "Address the user directly or use a specific role (administrator, purchaser)"),
        "end user":     ("user",                 "SAP style: use 'user' not 'end user'"),
        "utilize":      ("use",                  "SAP style: use 'use' instead of 'utilize'"),
        "utilise":      ("use",                  "SAP style: use 'use' instead of 'utilise'"),
        "in order to":  ("to",                   "SAP style: use 'to' instead of 'in order to'"),
        "as well as":   ("and",                  "SAP style: use 'and' instead of 'as well as' for clarity"),
    }

    def check_abbreviations(self, text: str) -> list:
        """
        Flag all-caps sequences (≥2 chars) that are not in the approved list.
        Catches abbreviations that may need spelling out on first use.
        """
        issues = []
        # Match sequences of 2+ uppercase letters, optionally with digits
        pattern = re.compile(r'\b([A-Z]{2,}[0-9]*|[A-Z][0-9]+[A-Z]+)\b')
        found = set()
        for match in pattern.finditer(text):
            abbr = match.group(0)
            if abbr not in self.APPROVED_ABBREVIATIONS and abbr not in found:
                found.add(abbr)
                issues.append({
                    "type": "abbreviation_review",
                    "severity": "warning",
                    "abbreviation": abbr,
                    "message": f"Abbreviation '{abbr}' — verify it is spelled out on first use and appears in SAPedia or SAP style guide",
                    "suggestion": f"If '{abbr}' is not universally known, spell it out on first use: '[Full Name] ({abbr})'",
                    "guideline": "SAP Style Guide: Spell out abbreviations on first use unless universally known"
                })
        return issues

    def check_sap_standard_terminology(self, text: str) -> list:
        """
        Flag deviations from SAP standard naming conventions.
        Checks against known renamed/standardized terms in the SAP S/4HANA era.
        """
        issues = []
        text_lower = text.lower()

        for wrong, (correct, reason) in self.SAP_STANDARD_TERMS.items():
            # Use word-boundary matching to avoid partial matches
            pattern = re.compile(r'\b' + re.escape(wrong) + r'\b', re.IGNORECASE)
            if pattern.search(text):
                issues.append({
                    "type": "sap_terminology_consistency",
                    "severity": "warning",
                    "wrong_term": wrong,
                    "correct_term": correct,
                    "message": f"'{wrong}' — SAP standard term is '{correct}'",
                    "suggestion": reason,
                    "guideline": "SAP Terminology Standards: Use current SAP product and entity names"
                })

        return issues

    def estimate_german_length(self, text: str) -> dict:
        """
        Estimate German translation length.
        German UI text is typically 25-40% longer than English.
        Fallback when SAP MT Portal is unavailable.
        """
        en_len = len(text)

        if en_len <= 15:
            expansion = 40
            de_len = int(en_len * 1.4)
        elif en_len <= 30:
            expansion = 35
            de_len = int(en_len * 1.35)
        else:
            expansion = 30
            de_len = int(en_len * 1.3)

        # Risk: absolute length matters most; expansion penalty only for labels of meaningful length
        if de_len > 40 or (en_len <= 15 and expansion >= 40 and de_len > 20):
            risk = "high"
        elif de_len > 25 or (expansion > 35 and de_len > 15):
            risk = "medium"
        else:
            risk = "low"

        return {
            "english_chars": en_len,
            "estimated_german_chars": de_len,
            "expansion_percent": expansion,
            "risk": risk
        }
