"""
Fiori UI Text Guidelines - Rule-based validation
Source: https://www.sap.com/design-system/fiori-design-web/v1-145/foundations/writing-and-wording/ux-writing/ui-text-guidelines-for-sap-fiori
"""
import re


class FioriRulesService:
    """Validates UI labels against SAP Fiori UI Text Guidelines."""

    # Articles that should not appear in UI labels
    ARTICLES = ["the", "a", "an"]

    # Instructional words not allowed in buttons
    INSTRUCTIONAL_WORDS = ["click", "press", "tap", "hit", "select here", "click here"]

    # Valid action verbs for buttons (imperative form)
    ACTION_VERBS = [
        "add", "approve", "assign", "cancel", "change", "check", "close",
        "confirm", "copy", "create", "decline", "delete", "display", "download",
        "edit", "enable", "export", "filter", "find", "generate", "go",
        "hide", "import", "insert", "log", "manage", "merge", "move",
        "open", "order", "post", "print", "process", "publish", "read",
        "refresh", "reject", "release", "remove", "rename", "replace",
        "request", "reset", "resolve", "restart", "restore", "retry",
        "return", "review", "run", "save", "schedule", "search", "select",
        "send", "set", "share", "show", "sign", "sort", "split", "start",
        "stop", "submit", "switch", "sync", "transfer", "trigger",
        "undo", "update", "upload", "validate", "verify", "view"
    ]

    # Punctuation not allowed in labels (except ?)
    FORBIDDEN_PUNCTUATION = [".", "!", ";", ":", ","]

    def validate_ui_label(self, text: str, element_type: str = "field") -> list:
        """
        Validate a UI label against Fiori guidelines.
        
        Args:
            text: The UI label text
            element_type: "button", "field", "column", "app_name", "section"
            
        Returns:
            List of issue dicts with: type, severity, message, suggestion, guideline
        """
        issues = []
        words = text.split()
        word_count = len(words)

        # === BUTTON-SPECIFIC RULES ===
        if element_type == "button":
            issues.extend(self._check_button_rules(text, words, word_count))

        # === FIELD LABEL RULES ===
        elif element_type == "field":
            issues.extend(self._check_field_rules(text, words, word_count))

        # === COLUMN HEADER RULES ===
        elif element_type == "column":
            issues.extend(self._check_column_rules(text, words, word_count))

        # === GENERAL UI TEXT RULES (apply to all) ===
        issues.extend(self._check_general_rules(text, words))

        return issues

    def _check_button_rules(self, text: str, words: list, word_count: int) -> list:
        """Button-specific Fiori rules."""
        issues = []

        # Rule: Buttons should be max 3 words
        if word_count > 3:
            issues.append({
                "type": "fiori_button_length",
                "severity": "error",
                "message": f"Button text too long ({word_count} words, max 3)",
                "suggestion": f"Shorten to 1-3 words. Example: '{' '.join(words[:2])}'",
                "guideline": "Fiori: Button labels should be 1-3 words (verb + object)"
            })

        # Rule: Button should start with action verb (imperative)
        if words:
            first_word = words[0].lower()
            # Check if it's a gerund (-ing form) instead of imperative
            if first_word.endswith("ing") and first_word not in ["ring", "string", "thing"]:
                base_verb = first_word[:-3]  # rough stem
                issues.append({
                    "type": "fiori_button_verb_form",
                    "severity": "error",
                    "message": f"Button should use imperative verb, not gerund ('{words[0]}')",
                    "suggestion": f"Use imperative form: '{first_word[:-3].capitalize() if len(first_word) > 4 else first_word[:-3].capitalize()}' instead of '{words[0]}'",
                    "guideline": "Fiori: Buttons use imperative verb form (Save, not Saving)"
                })
            elif first_word not in self.ACTION_VERBS and not first_word.endswith("e"):
                # Check if first word looks like a verb
                is_likely_verb = any(first_word.startswith(v[:3]) for v in self.ACTION_VERBS)
                if not is_likely_verb and word_count > 1:
                    issues.append({
                        "type": "fiori_button_no_verb",
                        "severity": "warning",
                        "message": f"Button should start with an action verb",
                        "suggestion": f"Start with a verb like: Create, Save, Delete, Add, Open",
                        "guideline": "Fiori: Button text = Action verb + Object (e.g., 'Save Draft')"
                    })

        # Rule: No instructional words
        text_lower = text.lower()
        for word in self.INSTRUCTIONAL_WORDS:
            if word in text_lower:
                issues.append({
                    "type": "fiori_instructional_word",
                    "severity": "error",
                    "message": f"Instructional word '{word}' not allowed in buttons",
                    "suggestion": "Button describes the ACTION, not the gesture. Remove instructional words.",
                    "guideline": "Fiori: Never use 'Click', 'Press', 'Tap' in button text"
                })
                break

        return issues

    def _check_field_rules(self, text: str, words: list, word_count: int) -> list:
        """Field label-specific Fiori rules."""
        issues = []

        # Rule: Field labels should be max 4 words
        if word_count > 4:
            issues.append({
                "type": "fiori_field_length",
                "severity": "warning",
                "message": f"Field label is long ({word_count} words, recommended max 4)",
                "suggestion": "Consider shortening. Move details to tooltip or placeholder text.",
                "guideline": "Fiori: Field labels should be concise noun phrases (1-4 words)"
            })

        return issues

    def _check_column_rules(self, text: str, words: list, word_count: int) -> list:
        """Column header-specific Fiori rules."""
        issues = []

        # Rule: Column headers should be max 3 words
        if word_count > 3:
            issues.append({
                "type": "fiori_column_length",
                "severity": "warning",
                "message": f"Column header is long ({word_count} words, recommended max 3)",
                "suggestion": "Shorten for table readability. Use abbreviations if standard.",
                "guideline": "Fiori: Column headers should be brief (1-3 words)"
            })

        return issues

    def _check_general_rules(self, text: str, words: list) -> list:
        """General Fiori UI text rules (apply to all element types)."""
        issues = []
        text_lower = text.lower()

        # Rule: No articles at the beginning
        if words and words[0].lower() in self.ARTICLES:
            issues.append({
                "type": "fiori_article",
                "severity": "error",
                "message": f"UI labels should not start with article '{words[0]}'",
                "suggestion": f"Remove '{words[0]}': '{' '.join(words[1:])}'",
                "guideline": "Fiori: Omit articles (the, a, an) in UI labels"
            })

        # Rule: No articles anywhere in the label
        for i, word in enumerate(words):
            if i > 0 and word.lower() in self.ARTICLES:
                # Check if it's likely an article vs part of a name
                if i < len(words) - 1:
                    issues.append({
                        "type": "fiori_article_internal",
                        "severity": "warning",
                        "message": f"Article '{word}' in label — consider removing",
                        "suggestion": f"Omit article for conciseness",
                        "guideline": "Fiori: Omit articles in UI labels where possible"
                    })
                    break  # Only flag once

        # Rule: No ending punctuation (except ?)
        if text and text[-1] in self.FORBIDDEN_PUNCTUATION:
            issues.append({
                "type": "fiori_punctuation",
                "severity": "error",
                "message": f"UI labels should not end with '{text[-1]}'",
                "suggestion": f"Remove the ending punctuation: '{text[:-1]}'",
                "guideline": "Fiori: No ending punctuation in labels (exception: '?' for questions)"
            })

        # Rule: Check capitalization (Title Case for buttons, Sentence case for fields)
        # We just flag inconsistency, not enforce one style
        if len(words) > 1:
            all_title = all(w[0].isupper() for w in words if len(w) > 3)
            all_sentence = words[0][0].isupper() and all(w[0].islower() for w in words[1:] if len(w) > 3)
            if not all_title and not all_sentence:
                # Mixed capitalization
                pass  # Don't flag — too noisy for beta

        return issues

    def estimate_german_length(self, text: str) -> dict:
        """
        Estimate German translation length.
        German is typically 30-40% longer than English for UI text.
        
        Returns:
            {
                "english_chars": int,
                "estimated_german_chars": int,
                "expansion_percent": int,
                "risk": "low" | "medium" | "high"
            }
        """
        en_len = len(text)
        # UI text expansion factor is ~35% on average
        de_len = int(en_len * 1.35)

        if en_len <= 15:
            expansion = 40  # Short text expands more
            de_len = int(en_len * 1.4)
        elif en_len <= 30:
            expansion = 35
            de_len = int(en_len * 1.35)
        else:
            expansion = 30
            de_len = int(en_len * 1.3)

        # Risk assessment
        if de_len > 40:
            risk = "high"
        elif de_len > 25:
            risk = "medium"
        else:
            risk = "low"

        return {
            "english_chars": en_len,
            "estimated_german_chars": de_len,
            "expansion_percent": expansion,
            "risk": risk
        }