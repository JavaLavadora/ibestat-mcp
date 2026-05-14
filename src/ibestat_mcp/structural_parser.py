"""Parse IBESTAT structural-resources API responses."""

from __future__ import annotations

import re
from typing import Any

from ibestat_mcp._i18n import extract_localized_text, strip_accents
from ibestat_mcp.models import Category, CodelistEntry


def _extract_id_from_urn(urn: str) -> str | None:
    """Extract the last segment after ').' in an SDMX URN."""
    match = re.search(r"\)\.(.+)$", urn)
    if not match:
        return None
    segments = match.group(1).split(".")
    return segments[-1] if segments else None


def _extract_codelist_id_from_urn(urn: str) -> str | None:
    """Extract codelist ID from a URN like '...Codelist=IBESTAT:CL_AREA_ES53(01.000)'."""
    match = re.search(r"Codelist=\w+:(\w+)\(", urn)
    return match.group(1) if match else None


def parse_categories(response: dict[str, Any], lang: str = "ca") -> list[Category]:
    """Parse a category list response into Category models.

    Parameters
    ----------
    response:
        Raw JSON response containing a ``"category"`` list from the
        IBESTAT structural-resources categoryscheme endpoint.
    lang:
        ISO 639-1 language code for name extraction.

    Returns
    -------
    list[Category]
        Parsed categories with parent references resolved.
    """
    results: list[Category] = []
    for entry in response.get("category", []):
        parent_urn = entry.get("parent")
        parent_id = _extract_id_from_urn(parent_urn) if parent_urn else None
        results.append(Category(
            id=entry["id"],
            name=strip_accents(extract_localized_text(entry.get("name"), lang)),
            parent_id=parent_id,
            nested_id=entry.get("nestedId"),
        ))
    return results


def parse_codelist_codes(response: dict[str, Any], lang: str = "ca") -> list[CodelistEntry]:
    """Parse a codelist codes response into CodelistEntry models.

    Parameters
    ----------
    response:
        Raw JSON response containing a ``"code"`` list from the
        IBESTAT structural-resources codelist endpoint.
    lang:
        ISO 639-1 language code for label extraction.

    Returns
    -------
    list[CodelistEntry]
        Parsed codelist entries with parent references resolved.
    """
    results: list[CodelistEntry] = []
    for entry in response.get("code", []):
        parent_urn = entry.get("parent")
        parent_code = _extract_id_from_urn(parent_urn) if parent_urn else None
        results.append(CodelistEntry(
            code=entry["id"],
            label=strip_accents(extract_localized_text(entry.get("name"), lang)),
            parent_code=parent_code,
        ))
    return results


def extract_codelist_ids_from_dsd(response: dict[str, Any]) -> dict[str, str]:
    """Extract dimension-to-codelist mappings from a Data Structure Definition.

    Parameters
    ----------
    response:
        Raw JSON response from the IBESTAT structural-resources
        datastructure endpoint, expected to contain
        ``dataStructureComponents.dimensions``.

    Returns
    -------
    dict[str, str]
        Mapping of dimension ID to codelist ID (e.g.
        ``{"TERRITORIO": "CL_AREA_ES53", "SEXO": "CL_SEX"}``).
    """
    result: dict[str, str] = {}
    components = response.get("dataStructureComponents", {})
    dims = components.get("dimensions", {})
    for dim in dims.get("dimension", []):
        codelist_ref = dim.get("localRepresentation", {}).get("enumerationCodelist")
        if codelist_ref:
            codelist_id = _extract_codelist_id_from_urn(codelist_ref.get("urn", ""))
            if codelist_id:
                result[dim["id"]] = codelist_id
    measure_dim = dims.get("measureDimension")
    if measure_dim:
        codelist_ref = measure_dim.get("localRepresentation", {}).get("enumerationCodelist")
        if codelist_ref:
            codelist_id = _extract_codelist_id_from_urn(codelist_ref.get("urn", ""))
            if codelist_id:
                result[measure_dim["id"]] = codelist_id
    return result
