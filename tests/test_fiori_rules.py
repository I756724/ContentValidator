"""
Tests for FioriRulesService — all 10 element types + general rules + edge cases.
Run: python -m pytest tests/test_fiori_rules.py -v
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pytest
from services.fiori_rules import FioriRulesService


@pytest.fixture
def rules():
    return FioriRulesService()


def issue_types(issues):
    return [i["type"] for i in issues]


# ── BUTTON ────────────────────────────────────────────────────────────────────

class TestButton:
    def test_valid_single_verb(self, rules):
        assert rules.validate_ui_label("Save", "button") == []

    def test_valid_verb_object(self, rules):
        assert rules.validate_ui_label("Approve Order", "button") == []

    def test_too_long(self, rules):
        issues = rules.validate_ui_label("Save All Draft Documents", "button")
        assert "fiori_button_length" in issue_types(issues)

    def test_gerund_flagged(self, rules):
        assert "fiori_button_verb_form" in issue_types(rules.validate_ui_label("Saving", "button"))

    def test_gerund_multi_word(self, rules):
        assert "fiori_button_verb_form" in issue_types(rules.validate_ui_label("Editing Record", "button"))

    def test_gerund_double_consonant(self, rules):
        # "Running" = gerund of "run" which is in ACTION_VERBS
        assert "fiori_button_verb_form" in issue_types(rules.validate_ui_label("Running Report", "button"))

    def test_gerund_no_false_positive_billing(self, rules):
        """'Billing' ends in -ing but is not a gerund of an ACTION_VERB."""
        types = issue_types(rules.validate_ui_label("Billing Document", "button"))
        assert "fiori_button_verb_form" not in types

    def test_gerund_no_false_positive_marketing(self, rules):
        types = issue_types(rules.validate_ui_label("Marketing Plan", "button"))
        assert "fiori_button_verb_form" not in types

    def test_gerund_no_false_positive_scheduling(self, rules):
        # "Scheduling" IS a gerund of "schedule" which IS in ACTION_VERBS — should be flagged
        assert "fiori_button_verb_form" in issue_types(rules.validate_ui_label("Scheduling", "button"))

    def test_instructional_word_click(self, rules):
        assert "fiori_instructional_word" in issue_types(rules.validate_ui_label("Click Save", "button"))

    def test_instructional_word_press(self, rules):
        assert "fiori_instructional_word" in issue_types(rules.validate_ui_label("Press Submit", "button"))

    def test_no_verb_warning(self, rules):
        # "Purchase Order" has no verb — multi-word label should warn
        types = issue_types(rules.validate_ui_label("Purchase Order Details", "button"))
        assert "fiori_button_no_verb" in types


# ── FIELD LABEL ───────────────────────────────────────────────────────────────

class TestFieldLabel:
    def test_valid(self, rules):
        assert rules.validate_ui_label("Purchase Order", "field_label") == []

    def test_valid_hyphenated(self, rules):
        assert rules.validate_ui_label("Sold-To Party", "field_label") == []

    def test_verb_at_start_enter(self, rules):
        assert "fiori_field_verb" in issue_types(
            rules.validate_ui_label("Enter Customer Name", "field_label"))

    def test_verb_at_start_select(self, rules):
        assert "fiori_field_verb" in issue_types(
            rules.validate_ui_label("Select Priority", "field_label"))

    def test_colon_suffix(self, rules):
        assert "fiori_field_colon" in issue_types(
            rules.validate_ui_label("Purchase Order:", "field_label"))

    def test_too_long(self, rules):
        assert "fiori_field_length" in issue_types(
            rules.validate_ui_label("Very Long Field Label Name Here", "field_label"))

    def test_legacy_alias_field(self, rules):
        """'field' alias must produce identical results to 'field_label'."""
        assert (issue_types(rules.validate_ui_label("Enter Name", "field_label")) ==
                issue_types(rules.validate_ui_label("Enter Name", "field")))


# ── APP TITLE ─────────────────────────────────────────────────────────────────

class TestAppTitle:
    def test_valid_transactional(self, rules):
        assert rules.validate_ui_label("Manage Purchase Orders", "app_title") == []

    def test_valid_analytical_noun(self, rules):
        assert rules.validate_ui_label("Journal Entries", "app_title") == []

    def test_analysis_suffix(self, rules):
        assert "fiori_app_title_analysis" in issue_types(
            rules.validate_ui_label("Revenue Analysis", "app_title"))

    def test_ampersand(self, rules):
        assert "fiori_app_title_ampersand" in issue_types(
            rules.validate_ui_label("Sales & Distribution", "app_title"))

    def test_gerund_start(self, rules):
        assert "fiori_app_title_gerund" in issue_types(
            rules.validate_ui_label("Managing Purchase Orders Efficiently", "app_title"))


# ── MESSAGE TEXT ──────────────────────────────────────────────────────────────

class TestMessageText:
    def test_valid_fragment(self, rules):
        assert rules.validate_ui_label("Order created", "message_text") == []

    def test_valid_instruction(self, rules):
        assert rules.validate_ui_label("Enter a valid email address", "message_text") == []

    def test_successfully_forbidden(self, rules):
        assert "fiori_message_successfully" in issue_types(
            rules.validate_ui_label("Order created successfully", "message_text"))

    def test_plural_s_forbidden(self, rules):
        assert "fiori_message_plural_s" in issue_types(
            rules.validate_ui_label("Select item(s) to continue", "message_text"))

    def test_semicolon_forbidden(self, rules):
        assert "fiori_message_semicolon" in issue_types(
            rules.validate_ui_label("Save the file; then click Done", "message_text"))

    def test_short_fragment_period_warning(self, rules):
        assert "fiori_message_short_period" in issue_types(
            rules.validate_ui_label("Item saved.", "message_text"))


# ── STATUS TEXT ───────────────────────────────────────────────────────────────

class TestStatusText:
    def test_valid_short(self, rules):
        assert rules.validate_ui_label("In Progress", "status_text") == []

    def test_valid_long_sentence_case(self, rules):
        # "Not yet billed" — all lowercase after first word: should be clean
        assert rules.validate_ui_label("Not yet billed", "status_text") == []

    def test_period_forbidden(self, rules):
        assert "fiori_status_period" in issue_types(
            rules.validate_ui_label("Completed.", "status_text"))


# ── COLUMN HEADER ─────────────────────────────────────────────────────────────

class TestColumnHeader:
    def test_valid(self, rules):
        assert rules.validate_ui_label("Net Value", "column_header") == []

    def test_too_long(self, rules):
        assert "fiori_column_length" in issue_types(
            rules.validate_ui_label("Net Value in Local Currency", "column_header"))

    def test_legacy_alias_column(self, rules):
        assert (issue_types(rules.validate_ui_label("Very Long Column Header Value", "column_header")) ==
                issue_types(rules.validate_ui_label("Very Long Column Header Value", "column")))


# ── TAB ───────────────────────────────────────────────────────────────────────

class TestTab:
    def test_valid(self, rules):
        assert rules.validate_ui_label("General Information", "tab") == []

    def test_too_long(self, rules):
        assert "fiori_tab_length" in issue_types(
            rules.validate_ui_label("General Information Details Overview", "tab"))

    def test_verb_start(self, rules):
        assert "fiori_tab_verb" in issue_types(
            rules.validate_ui_label("Create New Item", "tab"))


# ── SECTION HEADING ───────────────────────────────────────────────────────────

class TestSectionHeading:
    def test_valid(self, rules):
        assert rules.validate_ui_label("Account", "section_heading") == []

    def test_too_long(self, rules):
        assert "fiori_section_length" in issue_types(
            rules.validate_ui_label("Account General Processing Data Overview", "section_heading"))


# ── ACTION ────────────────────────────────────────────────────────────────────

class TestAction:
    def test_valid(self, rules):
        assert rules.validate_ui_label("Edit List", "action") == []

    def test_too_long(self, rules):
        assert "fiori_action_length" in issue_types(
            rules.validate_ui_label("Copy Item From Template To New Record", "action"))

    def test_gerund_action(self, rules):
        assert "fiori_action_gerund" in issue_types(
            rules.validate_ui_label("Editing List", "action"))


# ── FACET TITLE ───────────────────────────────────────────────────────────────

class TestFacetTitle:
    def test_valid(self, rules):
        assert rules.validate_ui_label("Price Overview", "facet_title") == []

    def test_too_long(self, rules):
        assert "fiori_facet_length" in issue_types(
            rules.validate_ui_label("Price Overview Details Header Information", "facet_title"))


# ── GENERAL RULES (apply to all types) ───────────────────────────────────────

class TestGeneralRules:
    ELEMENT_TYPES = ["button", "field_label", "tab", "column_header",
                     "status_text", "section_heading", "app_title", "facet_title"]

    def test_article_start_all_types(self, rules):
        for et in self.ELEMENT_TYPES:
            types = issue_types(rules.validate_ui_label("The Purchase Order", et))
            assert "fiori_article_start" in types, f"article_start not caught for element type: {et}"

    def test_forbidden_punctuation_period(self, rules):
        assert "fiori_punctuation" in issue_types(
            rules.validate_ui_label("Purchase Order.", "field_label"))

    def test_forbidden_punctuation_comma(self, rules):
        assert "fiori_punctuation" in issue_types(
            rules.validate_ui_label("Purchase Order,", "field_label"))

    def test_ellipsis_non_button(self, rules):
        assert "fiori_ellipsis" in issue_types(
            rules.validate_ui_label("Loading...", "status_text"))

    def test_message_text_exempt_from_end_punctuation_rule(self, rules):
        # Complete sentences in messages may end with period — general punctuation rule must not fire
        issues = rules.validate_ui_label("Leave request created.", "message_text")
        types = issue_types(issues)
        assert "fiori_punctuation" not in types


# ── EDGE CASES ────────────────────────────────────────────────────────────────

class TestEdgeCases:
    def test_empty_string(self, rules):
        for et in ["button", "field_label", "message_text", "status_text"]:
            result = rules.validate_ui_label("", et)
            assert isinstance(result, list), f"Expected list for empty string, type={et}"

    def test_single_char(self, rules):
        result = rules.validate_ui_label("X", "button")
        assert isinstance(result, list)

    def test_single_valid_verb(self, rules):
        # "Save" is the canonical minimal valid button
        assert rules.validate_ui_label("Save", "button") == []

    def test_unicode_label(self, rules):
        result = rules.validate_ui_label("Änderungsauftrag", "field_label")
        assert isinstance(result, list)

    def test_unknown_element_type_returns_list(self, rules):
        result = rules.validate_ui_label("Some Text", "nonexistent_type")
        assert isinstance(result, list)


# ── GERMAN LENGTH ESTIMATE ────────────────────────────────────────────────────

class TestGermanEstimate:
    def test_short_text_high_expansion(self, rules):
        result = rules.estimate_german_length("Go")
        assert result["expansion_percent"] == 40
        assert result["english_chars"] == 2

    def test_long_text_lower_expansion(self, rules):
        result = rules.estimate_german_length("This is a somewhat longer label text")
        assert result["expansion_percent"] == 30

    def test_risk_levels(self, rules):
        # Short text: 5 chars → ~7 chars DE (low)
        r = rules.estimate_german_length("Save")
        assert r["risk"] == "low"
        # Medium: ~20 chars EN → ~27 chars DE
        r = rules.estimate_german_length("Purchase Order Number")
        assert r["risk"] in ("medium", "low")
        # High: long text
        r = rules.estimate_german_length("Net Amount in Local Currency of the Company Code")
        assert r["risk"] == "high"

    def test_returns_all_keys(self, rules):
        r = rules.estimate_german_length("Test Label")
        for key in ("english_chars", "estimated_german_chars", "expansion_percent", "risk"):
            assert key in r, f"Missing key: {key}"
