"""Tests for ibestat_mcp.structural_parser module."""

from __future__ import annotations
from typing import Any

import pytest

from ibestat_mcp.structural_parser import (
    parse_categories,
    parse_codelist_codes,
    extract_codelist_ids_from_dsd,
)


class TestParseCategories:
    def test_extracts_categories(self, categories_response: dict[str, Any]) -> None:
        result = parse_categories(categories_response, lang="ca")
        assert len(result) == 4
        assert result[0].id == "010"
        assert result[0].name == "Demografia"
        assert result[0].parent_id is None

    def test_child_has_parent_id(self, categories_response: dict[str, Any]) -> None:
        result = parse_categories(categories_response, lang="ca")
        child = next(c for c in result if c.id == "010_010")
        assert child.parent_id == "010"

    def test_extracts_nested_id(self, categories_response: dict[str, Any]) -> None:
        result = parse_categories(categories_response, lang="ca")
        assert result[0].nested_id == "010"
        child = next(c for c in result if c.id == "010_010")
        assert child.nested_id == "010.010_010"

    def test_empty_response(self) -> None:
        assert parse_categories({"category": []}, lang="ca") == []


class TestParseCodelistCodes:
    def test_extracts_codes(self, codelist_codes_response: dict[str, Any]) -> None:
        result = parse_codelist_codes(codelist_codes_response, lang="ca")
        assert len(result) == 3
        assert result[0].code == "ES53"
        assert result[0].label == "Illes Balears"
        assert result[0].parent_code is None

    def test_parent_code_resolved(self, codelist_codes_response: dict[str, Any]) -> None:
        result = parse_codelist_codes(codelist_codes_response, lang="ca")
        mallorca = next(c for c in result if c.code == "07")
        assert mallorca.parent_code == "ES53"

    def test_grandchild(self, codelist_codes_response: dict[str, Any]) -> None:
        result = parse_codelist_codes(codelist_codes_response, lang="ca")
        palma = next(c for c in result if c.code == "07040")
        assert palma.parent_code == "07"

    def test_spanish_labels(self, codelist_codes_response: dict[str, Any]) -> None:
        result = parse_codelist_codes(codelist_codes_response, lang="es")
        palma = next(c for c in result if c.code == "07040")
        assert palma.label == "Palma de Mallorca"

    def test_empty_response(self) -> None:
        assert parse_codelist_codes({"code": []}, lang="ca") == []


class TestExtractCodelistIdsFromDsd:
    def test_extracts_codelist(self, data_structure_response: dict[str, Any]) -> None:
        result = extract_codelist_ids_from_dsd(data_structure_response)
        assert result["TERRITORIO"] == "CL_AREA_ES53"
        assert result["SEXO"] == "CL_SEX"

    def test_no_codelist_for_time(self, data_structure_response: dict[str, Any]) -> None:
        result = extract_codelist_ids_from_dsd(data_structure_response)
        assert "TIME_PERIOD" not in result

    def test_empty_dsd(self) -> None:
        result = extract_codelist_ids_from_dsd(
            {"dataStructureComponents": {"dimensions": {"dimension": []}}}
        )
        assert result == {}
