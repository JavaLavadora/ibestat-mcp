"""
Pytest fixtures for ibestat-mcp tests.

Provides loaded JSON fixtures captured from the real IBESTAT eDades API
(https://ibestat.es/edatos/apis/statistical-resources/v1.0/).

=============================================================================
eDades API RESPONSE STRUCTURE REFERENCE
=============================================================================

1. MULTILINGUAL NAMES (InternationalString)
   ----------------------------------------
   All human-readable text uses the same pattern throughout the API:

       "name": {
           "text": [
               {"value": "Territori", "lang": "ca"},
               {"value": "Territorio", "lang": "es"},
               {"value": "Reference area", "lang": "en"}
           ]
       }

   - The wrapper object has a single key "text" containing a list.
   - Each item has "value" (str) and "lang" (str, ISO 639-1 code).
   - Languages present: "ca" (Catalan), "es" (Spanish), "en" (English).
   - The ORDER of languages varies between responses -- never assume
     a fixed position. Always filter by lang.
   - Catalan ("ca") is the preferred language for display per project policy.
   - The "description" field uses the same structure but may contain HTML.

2. SEARCH RESPONSE (datasets list)
   --------------------------------
   Endpoint: GET /datasets?query=...&limit=N&_type=json

   Top-level keys:
       "kind": "statisticalResources#datasets"
       "dataset": [...]       -- list of dataset summaries
       "total": int           -- total matching datasets
       "limit": int           -- page size
       "offset": int          -- current offset
       "selfLink": str        -- current page URL
       "nextLink": str        -- next page URL (absent on last page)
       "lastLink": str        -- last page URL

   Each dataset summary:
       "id": "000001A_000001"                  -- dataset identifier
       "kind": "statisticalResources#dataset"
       "name": {InternationalString}           -- multilingual name
       "selfLink": {"kind": str, "href": str}  -- API link to this version
       "urn": str                              -- SIEMAC URN
       "visualizerHtmlLink": str               -- web visualizer URL

   IMPORTANT: The same dataset ID can appear multiple times with different
   versions (e.g., 1.0, 1.1). The version is in the selfLink href and urn.

3. DATASET DETAIL RESPONSE (metadata + data)
   ------------------------------------------
   Endpoint: GET /datasets/IBESTAT/{id}/~latest?_type=json

   Top-level keys:
       "id", "urn", "selfLink", "parentLink"
       "name": {InternationalString}
       "description": {InternationalString}    -- may contain HTML
       "selectedLanguages": {"language": [...], "total": int}
       "visualizerHtmlLink": str
       "metadata": {...}                       -- rich metadata (see below)
       "data": {...}                           -- observations (see below)
       "kind": "statisticalResources#dataset"

   3a. metadata.dimensions -- DIMENSION LABELS AND VALUES
       Path: response["metadata"]["dimensions"]["dimension"]
       This is a list of dimension descriptors, each with:
           "id": str                           -- e.g. "TERRITORIO"
           "name": {InternationalString}       -- dimension label
           "type": str                         -- one of:
               "GEOGRAPHIC_DIMENSION"
               "TIME_DIMENSION"
               "DIMENSION"
               "MEASURE_DIMENSION"
           "dimensionValues": {
               "value": [...]                  -- list of possible values
               "total": int
           }
           "showCode": bool
           "pluralName": {InternationalString} -- (only on some dims)

       Each dimensionValue:
           "id": str                           -- the code (e.g. "07001")
           "name": {InternationalString}       -- human label (e.g. "Alaró")
           -- Plus type-specific extras:
           -- GEOGRAPHIC: "variableElement", "geographicGranularity", "open"
           -- TIME: "temporalGranularity" (str, e.g. "YEARLY")
           -- MEASURE: "showDecimalsPrecision" (int), "measureQuantity"
           --   measureQuantity.unitCode.name has the unit label

   3b. metadata.relatedDsd -- DIMENSION LAYOUT
       Path: response["metadata"]["relatedDsd"]
           "heading": {"dimensionId": [...], "total": int}  -- column dims
           "stub": {"dimensionId": [...], "total": int}     -- row dims
       This describes the intended table layout (heading=columns, stub=rows).

   3c. metadata (other useful fields):
       "version": str                         -- e.g. "1.1"
       "lastUpdate": str                      -- ISO datetime
       "statisticalOperation": {resource}     -- parent operation
       "formatExtentObservations": int        -- total observation count
       "geographicCoverages": {resource list} -- covered territories
       "temporalCoverages": {"item": [...]}   -- covered time periods
       "measureCoverages": {resource list}    -- covered measures

4. DATA SECTION (observations)
   ----------------------------
   Path: response["data"]

   4a. data.dimensions -- CODE-TO-INDEX MAPPING
       Path: response["data"]["dimensions"]["dimension"]
       List of dimension descriptors, each with:
           "dimensionId": str                  -- e.g. "TERRITORIO"
           "representations": {
               "representation": [
                   {"code": "07001", "index": 0},
                   {"code": "07003", "index": 1},
                   ...
               ],
               "total": int
           }

       CRITICAL: The representations here carry ONLY "code" and "index"
       -- NO labels. To get human-readable labels, you must cross-reference
       with metadata.dimensions[].dimensionValues[] (matched by id).

       The "index" values define the position in the observations array.

   4b. data.observations -- THE ACTUAL VALUES
       Path: response["data"]["observations"]
       Type: string (pipe-separated)
       Format: "val1 | val2 | val3 | ..."

       This is a FLAT array of observation values. The mapping from
       dimension coordinates to array position uses ROW-MAJOR ORDER
       (last dimension varies fastest):

       Given dimensions D0(size s0), D1(size s1), ..., Dn(size sn),
       the flat index for coordinates (i0, i1, ..., in) is:

           index = i0 * (s1 * s2 * ... * sn)
                 + i1 * (s2 * ... * sn)
                 + ...
                 + in

       Example for this dataset with dims:
           TERRITORIO(67) x TIME_PERIOD(1) x SEXO(3) x MEDIDAS(3)
       To find Alaró (TERRITORIO index 37), 2024 (index 0), Total (index 0),
       Població empadronada (MEDIDAS index 1):
           flat_index = 37 * (1*3*3) + 0 * (3*3) + 0 * 3 + 1 = 334
           observations.split(" | ")[334] == "6037"

       Values can be numeric strings or empty strings for missing data.

   4c. data.attributes
       Path: response["data"]["attributes"]["attribute"]
       List with one entry per attribute, each having:
           "id": str                           -- e.g. "ESTADO_OBSERVACION"
           "value": str                        -- pipe-separated, same count
       Parallel to observations. "A" = normal value.

5. FILTERED DATA REQUEST (with dim= parameters)
   -----------------------------------------------
   Adding ?dim=DIMENSION:value&fields=-metadata strips the metadata section
   and filters observations to the requested slice. The response keeps the
   same data.dimensions/data.observations structure, but:
   - Filtered dimensions may still show ALL codes in representations
     (the API returns the full dimension even when filtering)
   - The observations count = product of all representation sizes
   - The "fields=-metadata" flag removes the "metadata" key entirely

=============================================================================
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def _load_fixture(name: str) -> dict[str, Any]:
    """Load a JSON fixture file by name."""
    path = FIXTURES_DIR / name
    with path.open(encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture()
def search_datasets_response() -> dict[str, Any]:
    """Search response for datasets matching 'poblaci' (limit=5).

    Endpoint: GET /datasets?query=name ILIKE 'poblaci'&limit=5&_type=json

    Contains 5 dataset summaries with multilingual names (ca, es).
    Note: same dataset ID may appear multiple times with different versions.
    """
    return _load_fixture("search_datasets_response.json")


@pytest.fixture()
def dataset_metadata_response() -> dict[str, Any]:
    """Full dataset response with metadata + all observations.

    Endpoint: GET /datasets/IBESTAT/000001A_000001/~latest?_type=json

    Dataset: "Població municipal empadronada segons el sexe"
    (Municipal registered population by sex, Balearic Islands municipalities)

    Dimensions:
        TERRITORIO  (67 municipalities)
        TIME_PERIOD (28 years, 1998-2025)
        SEXO        (3: _T=Total, M=Male, F=Female)
        MEDIDAS     (3: population, annual variation rate, annual variation)

    Total observations: 16,884 (67 * 28 * 3 * 3)
    """
    return _load_fixture("dataset_metadata_response.json")


@pytest.fixture()
def categories_response() -> dict[str, Any]:
    """Category tree from the IBESTAT structural-resources API.

    Endpoint: GET /categoryschemes/IBESTAT/TEMAS_BALEARS/~latest/categories?_type=json

    Contains 4 categories: two top-level (Demografia, Economia) and two children.
    """
    return _load_fixture("categories_response.json")


@pytest.fixture()
def codelist_codes_response() -> dict[str, Any]:
    """Codes from the CL_AREA_ES53 codelist (territory codes).

    Endpoint: GET /codelists/IBESTAT/CL_AREA_ES53/~latest/codes?_type=json

    Contains 3 codes: Illes Balears (root), Mallorca, Palma.
    """
    return _load_fixture("codelist_codes_response.json")


@pytest.fixture()
def data_structure_response() -> dict[str, Any]:
    """Data Structure Definition for the municipal population dataset.

    Endpoint: GET /datastructures/IBESTAT/DSD_000001A_00001/~latest?_type=json

    Dimensions: TERRITORIO, TIME_PERIOD, SEXO, MEDIDAS.
    """
    return _load_fixture("data_structure_response.json")


@pytest.fixture()
def dataset_data_response() -> dict[str, Any]:
    """Filtered dataset response (data only, no metadata section).

    Endpoint: GET /datasets/IBESTAT/000001A_000001/~latest
              ?dim=TIME_PERIOD:2024&dim=TERRITORIO:07001
              &dim=SEXO:_T&dim=MEDIDAS:POBLACION_PADRON
              &_type=json&fields=-metadata

    Note: Despite requesting dim=TERRITORIO:07001, the API returns ALL 67
    territory codes in the representations. The filtering happens at the
    observations level. Similarly for other dim filters -- the
    representations may be broader than the filter.

    The "metadata" key is absent due to fields=-metadata.

    Observations count: 603 (67 territories * 1 year * 3 sexes * 3 measures)
    """
    return _load_fixture("dataset_data_response.json")


# ---------------------------------------------------------------------------
# Helper for extracting a label in a given language from InternationalString
# ---------------------------------------------------------------------------

def get_label(international_string: dict[str, Any], lang: str = "ca") -> str | None:
    """Extract label text from an InternationalString for a given language.

    Args:
        international_string: Dict with "text" key containing list of
            {"value": str, "lang": str} items.
        lang: ISO 639-1 language code. Defaults to "ca" (Catalan).

    Returns:
        The label text, or None if the language is not found.
    """
    for item in international_string.get("text", []):
        if item.get("lang") == lang:
            return item["value"]
    return None
