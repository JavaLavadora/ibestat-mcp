"""Tests for ibestat_mcp._i18n module."""

from ibestat_mcp._i18n import extract_localized_text, strip_accents


class TestStripAccents:
    def test_removes_accents(self) -> None:
        assert strip_accents("Població") == "Poblacio"

    def test_empty_string(self) -> None:
        assert strip_accents("") == ""

    def test_no_accents(self) -> None:
        assert strip_accents("Palma") == "Palma"


class TestExtractLocalizedText:
    def test_extracts_catalan(self) -> None:
        intl = {"text": [{"value": "Territori", "lang": "ca"}, {"value": "Territorio", "lang": "es"}]}
        assert extract_localized_text(intl, "ca") == "Territori"

    def test_extracts_spanish(self) -> None:
        intl = {"text": [{"value": "Territori", "lang": "ca"}, {"value": "Territorio", "lang": "es"}]}
        assert extract_localized_text(intl, "es") == "Territorio"

    def test_fallback_to_first(self) -> None:
        intl = {"text": [{"value": "Territori", "lang": "ca"}]}
        assert extract_localized_text(intl, "en") == "Territori"

    def test_none_input(self) -> None:
        assert extract_localized_text(None) == ""

    def test_empty_text_list(self) -> None:
        assert extract_localized_text({"text": []}) == ""
