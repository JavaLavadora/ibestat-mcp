# Structural Resources (Semantic Assets) Integration

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Integrate IBESTAT's structural-resources API to give the MCP server a semantic layer — topic browsing, codelist hierarchy discovery, and a cache so static metadata is fetched once per session.

**Architecture:** Two new tools (`browse_topics`, `get_codelist`) and one enhancement (`get_dataset_info` gains `codelist_id` per dimension). A module-level `SemanticCache` avoids redundant API calls. `get_data` stays unchanged — all intelligence is in discovery, not query time.

**Tech Stack:** Python 3.10+, httpx (async), pydantic v2, mcp SDK (FastMCP), pytest + pytest-asyncio + respx

---

## Design: Current vs Proposed

### The workflow — same example, side by side

User asks: *"How has tourism impacted employment in the Balearic Islands?"*

#### CURRENT: guess and hope

```
Step 1: DISCOVER — guess keywords, no map

  Input:  search_datasets("turisme")
  Output: [{id: "000064A_000001", name: "Establecimientos abiertos y plazas
            en alojamientos de turismo rural..."}]
          → 1 result (rural tourism only)

  Input:  search_datasets("hotel")
  Output: [{id: "000061A_000002", name: "Viajeros entrados, pernoctaciones
            y estancia media en establecimientos hoteleros..."}]
          → 1 result

  Input:  search_datasets("pasajeros aeropuerto")
  Output: []
          → 0 results, dead end

  5 calls. Guessing. No way to know what was missed.


Step 2: INSPECT — flat codes, no structure

  Input:  get_dataset_info("000061A_000002", language="es")
  Output: {
            name: "Viajeros entrados...",
            dimensions: [
              {id: "TERRITORIO", name: "Territorio",
               values: [{code: "07001", label: "Alaro"},
                        {code: "07040", label: "Palma"},
                        ... 65 more flat codes]},
              {id: "MEDIDAS", ...},
              ...
            ]
          }

  67 territory codes in a flat list. No idea Alaró and Palma are
  both in Mallorca. Can't filter by island.


Step 3: QUERY — one municipality at a time

  Input:  get_data("000061A_000002", filters={
            "TIME_PERIOD": "2024M06", "TERRITORIO": "07040"
          }, language="es")
  Output: [{"Territorio": "Palma", "Viajeros entrados": 125000, ...}]

  Only Palma. To get all Mallorca data, would need to list all 39
  municipality codes — but doesn't know which 39 those are.
```

#### PROPOSED: discover, then query

```
Step 1: DISCOVER — see the map first

  Input:  browse_topics(language="es")
  Output: {
            name: "TEMAS_BALEARS",
            categories: [
              {id: "010", name: "Demografia", parent_id: null},
              {id: "010_010", name: "Poblacion", parent_id: "010"},
              {id: "020", name: "Economia", parent_id: null},
              {id: "020_030", name: "Turismo", parent_id: "020"},
              {id: "030", name: "Trabajo", parent_id: null},
              {id: "030_010", name: "Mercado laboral", parent_id: "030"},
              ... 46 more
            ]
          }

  LLM sees "Turismo" and "Mercado laboral" — IBESTAT's own vocabulary.
  Served from cache after first call (52 categories, ~5KB).

  Input:  search_datasets("turismo")
  Output: [{id: "000061A_000002", ...}, {id: "000064A_000001", ...}]
          → 2 targeted results

  Input:  search_datasets("mercado laboral")
  Output: [{id: "000137A_000023", ...}]
          → 1 targeted result

  3 calls (1 cached + 2 searches). No dead ends.


Step 2: INSPECT — dimensions now include codelist references

  Input:  get_dataset_info("000061A_000002", language="es")
  Output: {
            name: "Viajeros entrados...",
            dimensions: [
              {id: "TERRITORIO", name: "Territorio",
               codelist_id: "CL_AREA_ES53",          ← NEW
               values: [{code: "07001", label: "Alaro"},
                        {code: "07040", label: "Palma"},
                        ... 65 more]},
              {id: "MEDIDAS", name: "Medidas",
               codelist_id: null,                     ← no codelist (measures)
               values: [...]},
              ...
            ]
          }

  Same data as before, plus codelist_id per dimension.
  LLM knows TERRITORIO has a codelist it can explore.
  DSD fetched once, cached for this dataset.


Step 3: EXPLORE FILTERS — fetch codelist to see hierarchy

  Input:  get_codelist("CL_AREA_ES53", limit=100, language="es")
  Output: {
            id: "CL_AREA_ES53",
            name: "CL_AREA_ES53",
            total: 8275,
            codes: [
              {code: "ES53", label: "Illes Balears", parent_code: null},
              {code: "07",   label: "Mallorca",      parent_code: "ES53"},
              {code: "07001",label: "Alaró",          parent_code: "07"},
              {code: "07040",label: "Palma",          parent_code: "07"},
              ... 96 more
            ]
          }

  LLM now sees: Palma (07040) is in Mallorca (07).
  Mallorca municipalities: all codes starting with 07 that are children of "07".
  Codelist cached for subsequent calls.

  LLM can cross-reference: which of these codes exist in the dataset?
  → Intersect codelist children of "07" with dataset's TERRITORIO values
  → Build filter: ["07001", "07003", ..., "07040"]


Step 4: QUERY — with known-valid filters

  Input:  get_data("000061A_000002", filters={
            "TIME_PERIOD": "2024M06",
            "TERRITORIO": ["07001", "07003", ..., "07040"]
          }, language="es")
  Output: [
            {"Territorio": "Alaró", "Viajeros entrados": 1200, ...},
            {"Territorio": "Palma", "Viajeros entrados": 125000, ...},
            ... all 39 Mallorca municipalities
          ]

  get_data is unchanged. No magic. Filters are valid because
  the LLM discovered them through the semantic layer.
```

---

## Caching strategy

All structural data is static. Fetched once per session, reused everywhere.

| Data | Size | Fetched when | Used by |
|------|------|-------------|---------|
| Topic tree | 52 categories (~5KB) | First `browse_topics` | All subsequent `browse_topics` |
| DSD mappings | ~1KB per dataset | First `get_dataset_info` per dataset | All subsequent inspects of same dataset |
| Codelists | 3 to 8,275 codes per list | First `get_codelist` per list | All subsequent `get_codelist` calls for same list |

The cache is a module-level object that persists for the server process lifetime. The `IbestatClient` is created per tool call, but the cache lives outside it.

```python
class SemanticCache:
    def __init__(self):
        self.topics: TopicTree | None = None
        self.dsd_codelist_maps: dict[str, dict[str, str]] = {}  # dataset_id → {dim → codelist}
        self.codelists: dict[str, CodelistResult] = {}           # codelist_id → result

_cache = SemanticCache()
```

---

## File structure

| Action | File | Responsibility |
|--------|------|----------------|
| Create | `src/ibestat_mcp/_i18n.py` | Shared `extract_localized_text()` and `strip_accents()` |
| Modify | `src/ibestat_mcp/parser.py` | Import from `_i18n` instead of defining locally |
| Create | `src/ibestat_mcp/structural_parser.py` | Parse category and codelist responses |
| Create | `src/ibestat_mcp/cache.py` | `SemanticCache` class, module-level `_cache` instance |
| Modify | `src/ibestat_mcp/models.py` | Add `Category`, `TopicTree`, `CodelistEntry`, `CodelistResult`; add `codelist_id` to `DimensionInfo` |
| Modify | `src/ibestat_mcp/client.py` | Add `STRUCTURAL_BASE_URL` and methods: `get_categories()`, `get_codelist_codes()`, `get_data_structure()` |
| Modify | `src/ibestat_mcp/tools.py` | Add `browse_topics()`, `get_codelist()` with caching; enhance `get_dataset_info()` with `codelist_id` |
| Modify | `src/ibestat_mcp/server.py` | Register two new MCP tools |
| Create | `tests/fixtures/categories_response.json` | Fixture for category scheme response |
| Create | `tests/fixtures/codelist_codes_response.json` | Fixture for codelist codes response |
| Create | `tests/fixtures/data_structure_response.json` | Fixture for DSD response |
| Create | `tests/test_i18n.py` | Tests for extracted i18n utilities |
| Create | `tests/test_structural_parser.py` | Tests for structural response parsing |
| Create | `tests/test_cache.py` | Tests for SemanticCache behavior |
| Modify | `tests/test_client.py` | Tests for new client methods |
| Modify | `tests/test_tools.py` | Tests for new/enhanced tool functions |
| Modify | `tests/test_server.py` | Tests for new tool registration |
| Modify | `tests/conftest.py` | Add fixtures for structural API responses |
| Modify | `tests/test_e2e.py` | E2E tests for new tools |
| Modify | `CLAUDE.md` | Add semantic layer workflow for LLM agents |
| Modify | `README.md` | Add new tools and workflow for human users |
| Modify | `docs/design.md` | Add structural resources architecture and tool specs |

---

## Task 1: Extract shared i18n utilities

Both `parser.py` and the new `structural_parser.py` need `extract_localized_text` and `strip_accents`. Extract them into `_i18n.py` to avoid circular imports.

**Files:**
- Create: `src/ibestat_mcp/_i18n.py`
- Modify: `src/ibestat_mcp/parser.py`
- Create: `tests/test_i18n.py`

- [ ] **Step 1: Create `_i18n.py` with the two functions**

```python
"""Shared internationalization utilities for IBESTAT response parsing."""

from __future__ import annotations

import unicodedata


def strip_accents(text: str) -> str:
    if not text:
        return text
    normalized = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn")


def extract_localized_text(multilingual: dict | None, lang: str = "ca") -> str:
    if not multilingual:
        return ""
    texts = multilingual.get("text")
    if not texts:
        return ""
    for item in texts:
        if item.get("lang") == lang:
            return item["value"]
    return texts[0]["value"]
```

- [ ] **Step 2: Create `tests/test_i18n.py`**

```python
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
```

- [ ] **Step 3: Run tests**

Run: `pytest tests/test_i18n.py -v`
Expected: All 8 tests PASS

- [ ] **Step 4: Update `parser.py` to import from `_i18n`**

Replace the `strip_accents` and `extract_localized_text` function definitions in `parser.py` with:

```python
from ibestat_mcp._i18n import extract_localized_text, strip_accents
```

Remove the function bodies. The names remain importable from `parser` so existing code continues to work.

- [ ] **Step 5: Run full test suite to confirm no regressions**

Run: `pytest -m "not e2e" -v`
Expected: All existing tests PASS

- [ ] **Step 6: Commit**

```bash
git add src/ibestat_mcp/_i18n.py tests/test_i18n.py src/ibestat_mcp/parser.py
git commit -m "refactor: extract i18n utilities into shared module"
```

---

## Task 2: Add new Pydantic models

**Files:**
- Modify: `src/ibestat_mcp/models.py`

- [ ] **Step 1: Add structural resource models**

Append after the existing `DataRow` type alias in `models.py`:

```python
class Category(BaseModel):
    id: str = Field(description="Category identifier (e.g., '010')")
    name: str = Field(description="Category name in the requested language")
    parent_id: str | None = Field(
        default=None, description="Parent category ID, None for top-level"
    )


class TopicTree(BaseModel):
    name: str = Field(description="Category scheme name")
    categories: list[Category] = Field(
        description="Flat list of categories with parent references"
    )


class CodelistEntry(BaseModel):
    code: str = Field(description="Code identifier (e.g., '07040' for Palma)")
    label: str = Field(description="Human-readable label")
    parent_code: str | None = Field(
        default=None, description="Parent code for hierarchical codelists"
    )


class CodelistResult(BaseModel):
    id: str = Field(description="Codelist identifier (e.g., 'CL_AREA_ES53')")
    name: str = Field(description="Codelist name in the requested language")
    total: int = Field(description="Total number of codes in the full codelist")
    codes: list[CodelistEntry] = Field(description="Code entries (may be paginated)")
```

- [ ] **Step 2: Add `codelist_id` to `DimensionInfo`**

Add one field to the existing class:

```python
class DimensionInfo(BaseModel):
    id: str = Field(
        description="Dimension identifier used as filter key (e.g., 'TERRITORIO', 'TIME_PERIOD')"
    )
    name: str = Field(description="Dimension name (Catalan by default)")
    values: list[DimensionValue] = Field(
        description="Available values for this dimension"
    )
    codelist_id: str | None = Field(
        default=None,
        description="Codelist identifier for this dimension. Use with get_codelist to explore the full hierarchy of valid codes.",
    )
```

- [ ] **Step 3: Run existing tests**

Run: `pytest -m "not e2e" -v`
Expected: All pass (`codelist_id` defaults to `None`)

- [ ] **Step 4: Commit**

```bash
git add src/ibestat_mcp/models.py
git commit -m "feat: add models for structural resources and codelist_id to DimensionInfo"
```

---

## Task 3: Semantic cache

A module-level cache so structural data is fetched once per server session.

**Files:**
- Create: `src/ibestat_mcp/cache.py`
- Create: `tests/test_cache.py`

- [ ] **Step 1: Write cache tests**

```python
"""Tests for ibestat_mcp.cache module."""

from ibestat_mcp.cache import SemanticCache
from ibestat_mcp.models import TopicTree, Category, CodelistResult, CodelistEntry


class TestSemanticCache:
    def test_topics_initially_none(self) -> None:
        cache = SemanticCache()
        assert cache.topics is None

    def test_store_and_retrieve_topics(self) -> None:
        cache = SemanticCache()
        tree = TopicTree(name="TEST", categories=[Category(id="1", name="Test", parent_id=None)])
        cache.topics = tree
        assert cache.topics.name == "TEST"

    def test_dsd_map_initially_empty(self) -> None:
        cache = SemanticCache()
        assert cache.get_dsd_codelist_map("any") is None

    def test_store_and_retrieve_dsd_map(self) -> None:
        cache = SemanticCache()
        cache.set_dsd_codelist_map("DS1", {"TERRITORIO": "CL_AREA_ES53"})
        assert cache.get_dsd_codelist_map("DS1") == {"TERRITORIO": "CL_AREA_ES53"}

    def test_codelist_initially_empty(self) -> None:
        cache = SemanticCache()
        assert cache.get_codelist("CL_AREA_ES53") is None

    def test_store_and_retrieve_codelist(self) -> None:
        cache = SemanticCache()
        result = CodelistResult(
            id="CL_AREA_ES53", name="Test", total=1,
            codes=[CodelistEntry(code="ES53", label="Illes Balears", parent_code=None)],
        )
        cache.set_codelist("CL_AREA_ES53", result)
        assert cache.get_codelist("CL_AREA_ES53").id == "CL_AREA_ES53"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_cache.py -v`
Expected: FAIL (module not found)

- [ ] **Step 3: Implement the cache**

```python
"""In-memory cache for IBESTAT structural metadata.

Structural data (topic tree, DSDs, codelists) is static and changes
very rarely. This cache stores it for the server process lifetime,
avoiding redundant API calls within a session.
"""

from __future__ import annotations

from ibestat_mcp.models import CodelistResult, TopicTree


class SemanticCache:
    def __init__(self) -> None:
        self.topics: TopicTree | None = None
        self._dsd_maps: dict[str, dict[str, str]] = {}
        self._codelists: dict[str, CodelistResult] = {}

    def get_dsd_codelist_map(self, dataset_id: str) -> dict[str, str] | None:
        return self._dsd_maps.get(dataset_id)

    def set_dsd_codelist_map(self, dataset_id: str, mapping: dict[str, str]) -> None:
        self._dsd_maps[dataset_id] = mapping

    def get_codelist(self, codelist_id: str) -> CodelistResult | None:
        return self._codelists.get(codelist_id)

    def set_codelist(self, codelist_id: str, result: CodelistResult) -> None:
        self._codelists[codelist_id] = result


cache = SemanticCache()
```

- [ ] **Step 4: Run cache tests**

Run: `pytest tests/test_cache.py -v`
Expected: All 6 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/ibestat_mcp/cache.py tests/test_cache.py
git commit -m "feat: add SemanticCache for structural metadata"
```

---

## Task 4: Structural API client methods + fixtures

**Files:**
- Modify: `src/ibestat_mcp/client.py`
- Create: `tests/fixtures/categories_response.json`
- Create: `tests/fixtures/codelist_codes_response.json`
- Create: `tests/fixtures/data_structure_response.json`
- Modify: `tests/conftest.py`
- Modify: `tests/test_client.py`

- [ ] **Step 1: Add `STRUCTURAL_BASE_URL` and methods to `client.py`**

Add constant below `BASE_URL`:

```python
STRUCTURAL_BASE_URL = "https://ibestat.es/edatos/apis/structural-resources/v1.0"
```

Extend `__init__`:

```python
def __init__(
    self,
    base_url: str = BASE_URL,
    structural_base_url: str = STRUCTURAL_BASE_URL,
) -> None:
    self._base_url = base_url
    self._structural_base_url = structural_base_url
    self._http: httpx.AsyncClient | None = None
```

Add three methods:

```python
async def get_categories(self) -> dict[str, Any]:
    return await self._get(
        f"{self._structural_base_url}/categoryschemes/IBESTAT/TEMAS_BALEARS/~latest/categories",
    )

async def get_codelist_codes(
    self, codelist_id: str, limit: int = 100, offset: int = 0
) -> dict[str, Any]:
    return await self._get(
        f"{self._structural_base_url}/codelists/IBESTAT/{codelist_id}/~latest/codes",
        params=[("limit", str(limit)), ("offset", str(offset))],
    )

async def get_data_structure(self, dsd_id: str) -> dict[str, Any]:
    return await self._get(
        f"{self._structural_base_url}/datastructures/IBESTAT/{dsd_id}/~latest",
    )
```

- [ ] **Step 2: Create test fixtures**

`tests/fixtures/categories_response.json`:

```json
{
  "kind": "structuralResources#categories",
  "total": 4,
  "offset": 0,
  "limit": 25,
  "category": [
    {
      "id": "010",
      "urn": "urn:sdmx:org.sdmx.infomodel.categoryscheme.Category=IBESTAT:TEMAS_BALEARS(03.000).010",
      "name": {"text": [{"value": "Demografia", "lang": "ca"}, {"value": "Demografía", "lang": "es"}, {"value": "Demography", "lang": "en"}]}
    },
    {
      "id": "010_010",
      "urn": "urn:sdmx:org.sdmx.infomodel.categoryscheme.Category=IBESTAT:TEMAS_BALEARS(03.000).010.010_010",
      "name": {"text": [{"value": "Poblacio", "lang": "ca"}, {"value": "Población", "lang": "es"}, {"value": "Population", "lang": "en"}]},
      "parent": "urn:sdmx:org.sdmx.infomodel.categoryscheme.Category=IBESTAT:TEMAS_BALEARS(03.000).010"
    },
    {
      "id": "020",
      "urn": "urn:sdmx:org.sdmx.infomodel.categoryscheme.Category=IBESTAT:TEMAS_BALEARS(03.000).020",
      "name": {"text": [{"value": "Economia", "lang": "ca"}, {"value": "Economía", "lang": "es"}, {"value": "Economy", "lang": "en"}]}
    },
    {
      "id": "020_010",
      "urn": "urn:sdmx:org.sdmx.infomodel.categoryscheme.Category=IBESTAT:TEMAS_BALEARS(03.000).020.020_010",
      "name": {"text": [{"value": "Macroeconomiques", "lang": "ca"}, {"value": "Macroeconómicas", "lang": "es"}, {"value": "Macroeconomics", "lang": "en"}]},
      "parent": "urn:sdmx:org.sdmx.infomodel.categoryscheme.Category=IBESTAT:TEMAS_BALEARS(03.000).020"
    }
  ]
}
```

`tests/fixtures/codelist_codes_response.json`:

```json
{
  "kind": "structuralResources#codes",
  "total": 3,
  "offset": 0,
  "limit": 100,
  "code": [
    {
      "id": "ES53",
      "urn": "urn:sdmx:org.sdmx.infomodel.codelist.Code=IBESTAT:CL_AREA_ES53(01.000).ES53",
      "name": {"text": [{"value": "Illes Balears", "lang": "ca"}, {"value": "Illes Balears", "lang": "es"}]}
    },
    {
      "id": "07",
      "urn": "urn:sdmx:org.sdmx.infomodel.codelist.Code=IBESTAT:CL_AREA_ES53(01.000).07",
      "name": {"text": [{"value": "Mallorca", "lang": "ca"}, {"value": "Mallorca", "lang": "es"}]},
      "parent": "urn:sdmx:org.sdmx.infomodel.codelist.Code=IBESTAT:CL_AREA_ES53(01.000).ES53"
    },
    {
      "id": "07040",
      "urn": "urn:sdmx:org.sdmx.infomodel.codelist.Code=IBESTAT:CL_AREA_ES53(01.000).07040",
      "name": {"text": [{"value": "Palma", "lang": "ca"}, {"value": "Palma de Mallorca", "lang": "es"}]},
      "parent": "urn:sdmx:org.sdmx.infomodel.codelist.Code=IBESTAT:CL_AREA_ES53(01.000).07"
    }
  ]
}
```

`tests/fixtures/data_structure_response.json`:

```json
{
  "id": "DSD_000001A_00001",
  "urn": "urn:sdmx:org.sdmx.infomodel.datastructure.DataStructureDefinition=IBESTAT:DSD_000001A_00001(01.000)",
  "name": {"text": [{"value": "Poblacio municipal", "lang": "ca"}]},
  "dataStructureComponents": {
    "dimensions": {
      "dimension": [
        {
          "id": "TERRITORIO",
          "position": 1,
          "type": "DIMENSION",
          "localRepresentation": {
            "enumerationCodelist": {
              "urn": "urn:sdmx:org.sdmx.infomodel.codelist.Codelist=IBESTAT:CL_AREA_ES53(01.000)"
            }
          }
        },
        {
          "id": "TIME_PERIOD",
          "position": 2,
          "type": "TIME_DIMENSION",
          "localRepresentation": {
            "textFormat": {"textType": "OBSERVATIONAL_TIME_PERIOD"}
          }
        },
        {
          "id": "SEXO",
          "position": 3,
          "type": "DIMENSION",
          "localRepresentation": {
            "enumerationCodelist": {
              "urn": "urn:sdmx:org.sdmx.infomodel.codelist.Codelist=IBESTAT:CL_SEX(01.000)"
            }
          }
        }
      ],
      "measureDimension": {
        "id": "MEDIDAS",
        "position": 4,
        "type": "MEASURE_DIMENSION",
        "localRepresentation": {
          "enumerationConceptScheme": {
            "urn": "urn:sdmx:org.sdmx.infomodel.conceptscheme.ConceptScheme=IBESTAT:CSM_000001A_PADRON(01.000)"
          }
        }
      }
    }
  }
}
```

- [ ] **Step 3: Add fixture loaders to `tests/conftest.py`**

```python
@pytest.fixture()
def categories_response() -> dict[str, Any]:
    return _load_fixture("categories_response.json")

@pytest.fixture()
def codelist_codes_response() -> dict[str, Any]:
    return _load_fixture("codelist_codes_response.json")

@pytest.fixture()
def data_structure_response() -> dict[str, Any]:
    return _load_fixture("data_structure_response.json")
```

- [ ] **Step 4: Write client tests**

Add to `tests/test_client.py`:

```python
from ibestat_mcp.client import STRUCTURAL_BASE_URL


class TestGetCategories:
    @pytest.mark.asyncio
    @respx.mock
    async def test_correct_url(self, categories_response: dict[str, Any]) -> None:
        route = respx.get(
            f"{STRUCTURAL_BASE_URL}/categoryschemes/IBESTAT/TEMAS_BALEARS/~latest/categories"
        ).mock(return_value=httpx.Response(200, json=categories_response))
        async with IbestatClient() as client:
            result = await client.get_categories()
        assert route.called
        assert result["total"] == 4


class TestGetCodelistCodes:
    @pytest.mark.asyncio
    @respx.mock
    async def test_correct_url_and_pagination(self, codelist_codes_response: dict[str, Any]) -> None:
        route = respx.get(
            f"{STRUCTURAL_BASE_URL}/codelists/IBESTAT/CL_AREA_ES53/~latest/codes"
        ).mock(return_value=httpx.Response(200, json=codelist_codes_response))
        async with IbestatClient() as client:
            result = await client.get_codelist_codes("CL_AREA_ES53", limit=50, offset=10)
        assert route.called
        request = route.calls[0].request
        url_decoded = urllib.parse.unquote_plus(str(request.url))
        assert "limit=50" in url_decoded
        assert "offset=10" in url_decoded


class TestGetDataStructure:
    @pytest.mark.asyncio
    @respx.mock
    async def test_correct_url(self, data_structure_response: dict[str, Any]) -> None:
        route = respx.get(
            f"{STRUCTURAL_BASE_URL}/datastructures/IBESTAT/DSD_000001A_00001/~latest"
        ).mock(return_value=httpx.Response(200, json=data_structure_response))
        async with IbestatClient() as client:
            result = await client.get_data_structure("DSD_000001A_00001")
        assert route.called
        assert result["id"] == "DSD_000001A_00001"
```

- [ ] **Step 5: Run client tests**

Run: `pytest tests/test_client.py -v`
Expected: All pass

- [ ] **Step 6: Commit**

```bash
git add src/ibestat_mcp/client.py tests/test_client.py tests/conftest.py tests/fixtures/categories_response.json tests/fixtures/codelist_codes_response.json tests/fixtures/data_structure_response.json
git commit -m "feat: add structural-resources API methods to client"
```

---

## Task 5: Structural parser

**Files:**
- Create: `src/ibestat_mcp/structural_parser.py`
- Create: `tests/test_structural_parser.py`

- [ ] **Step 1: Write all parser tests**

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_structural_parser.py -v`
Expected: FAIL

- [ ] **Step 3: Implement the parser**

```python
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
    results: list[Category] = []
    for entry in response.get("category", []):
        parent_urn = entry.get("parent")
        parent_id = _extract_id_from_urn(parent_urn) if parent_urn else None
        results.append(Category(
            id=entry["id"],
            name=strip_accents(extract_localized_text(entry.get("name"), lang)),
            parent_id=parent_id,
        ))
    return results


def parse_codelist_codes(response: dict[str, Any], lang: str = "ca") -> list[CodelistEntry]:
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
```

- [ ] **Step 4: Run parser tests**

Run: `pytest tests/test_structural_parser.py -v`
Expected: All pass

- [ ] **Step 5: Commit**

```bash
git add src/ibestat_mcp/structural_parser.py tests/test_structural_parser.py
git commit -m "feat: add parser for structural-resources API responses"
```

---

## Task 6: Tool functions — `browse_topics`, `get_codelist`, enhanced `get_dataset_info`

All three use the cache: check cache first, fetch from API only on miss.

**Files:**
- Modify: `src/ibestat_mcp/tools.py`
- Modify: `tests/test_tools.py`

- [ ] **Step 1: Write tests for `browse_topics`**

```python
from unittest.mock import AsyncMock
from ibestat_mcp.tools import browse_topics, get_codelist, get_dataset_info
from ibestat_mcp.models import TopicTree, CodelistResult
from ibestat_mcp.cache import SemanticCache


class TestBrowseTopics:
    @pytest.mark.asyncio
    async def test_returns_topic_tree(self, categories_response: dict[str, Any]) -> None:
        client = AsyncMock()
        client.get_categories.return_value = categories_response
        test_cache = SemanticCache()

        result = await browse_topics(client, lang="ca", _cache=test_cache)

        assert isinstance(result, TopicTree)
        assert result.name == "TEMAS_BALEARS"
        assert len(result.categories) == 4

    @pytest.mark.asyncio
    async def test_uses_cache_on_second_call(self, categories_response: dict[str, Any]) -> None:
        client = AsyncMock()
        client.get_categories.return_value = categories_response
        test_cache = SemanticCache()

        await browse_topics(client, lang="ca", _cache=test_cache)
        await browse_topics(client, lang="ca", _cache=test_cache)

        assert client.get_categories.call_count == 1
```

- [ ] **Step 2: Write tests for `get_codelist`**

```python
class TestGetCodelist:
    @pytest.mark.asyncio
    async def test_returns_codelist_result(self, codelist_codes_response: dict[str, Any]) -> None:
        client = AsyncMock()
        client.get_codelist_codes.return_value = codelist_codes_response
        test_cache = SemanticCache()

        result = await get_codelist(client, "CL_AREA_ES53", lang="ca", _cache=test_cache)

        assert isinstance(result, CodelistResult)
        assert result.id == "CL_AREA_ES53"
        assert result.total == 3

    @pytest.mark.asyncio
    async def test_uses_cache_on_second_call(self, codelist_codes_response: dict[str, Any]) -> None:
        client = AsyncMock()
        client.get_codelist_codes.return_value = codelist_codes_response
        test_cache = SemanticCache()

        await get_codelist(client, "CL_AREA_ES53", lang="ca", _cache=test_cache)
        await get_codelist(client, "CL_AREA_ES53", lang="ca", _cache=test_cache)

        assert client.get_codelist_codes.call_count == 1

    @pytest.mark.asyncio
    async def test_hierarchy_preserved(self, codelist_codes_response: dict[str, Any]) -> None:
        client = AsyncMock()
        client.get_codelist_codes.return_value = codelist_codes_response
        test_cache = SemanticCache()

        result = await get_codelist(client, "CL_AREA_ES53", lang="ca", _cache=test_cache)

        palma = next(c for c in result.codes if c.code == "07040")
        assert palma.parent_code == "07"
```

- [ ] **Step 3: Write tests for enhanced `get_dataset_info`**

```python
class TestGetDatasetInfoCodelistId:
    @pytest.mark.asyncio
    async def test_includes_codelist_id(
        self,
        dataset_metadata_response: dict[str, Any],
        data_structure_response: dict[str, Any],
    ) -> None:
        client = AsyncMock()
        client.get_dataset_metadata.return_value = dataset_metadata_response
        client.get_data_structure.return_value = data_structure_response
        test_cache = SemanticCache()

        result = await get_dataset_info(client, "000001A_000001", lang="ca", _cache=test_cache)

        territorio = next(d for d in result.dimensions if d.id == "TERRITORIO")
        assert territorio.codelist_id == "CL_AREA_ES53"

    @pytest.mark.asyncio
    async def test_no_codelist_for_time(
        self,
        dataset_metadata_response: dict[str, Any],
        data_structure_response: dict[str, Any],
    ) -> None:
        client = AsyncMock()
        client.get_dataset_metadata.return_value = dataset_metadata_response
        client.get_data_structure.return_value = data_structure_response
        test_cache = SemanticCache()

        result = await get_dataset_info(client, "000001A_000001", lang="ca", _cache=test_cache)

        time_dim = next(d for d in result.dimensions if d.id == "TIME_PERIOD")
        assert time_dim.codelist_id is None

    @pytest.mark.asyncio
    async def test_caches_dsd_map(
        self,
        dataset_metadata_response: dict[str, Any],
        data_structure_response: dict[str, Any],
    ) -> None:
        client = AsyncMock()
        client.get_dataset_metadata.return_value = dataset_metadata_response
        client.get_data_structure.return_value = data_structure_response
        test_cache = SemanticCache()

        await get_dataset_info(client, "000001A_000001", lang="ca", _cache=test_cache)
        await get_dataset_info(client, "000001A_000001", lang="ca", _cache=test_cache)

        assert client.get_data_structure.call_count == 1

    @pytest.mark.asyncio
    async def test_graceful_fallback_on_dsd_error(
        self,
        dataset_metadata_response: dict[str, Any],
    ) -> None:
        client = AsyncMock()
        client.get_dataset_metadata.return_value = dataset_metadata_response
        client.get_data_structure.side_effect = Exception("not found")
        test_cache = SemanticCache()

        result = await get_dataset_info(client, "000001A_000001", lang="ca", _cache=test_cache)

        assert len(result.dimensions) > 0
        assert all(d.codelist_id is None for d in result.dimensions)
```

- [ ] **Step 4: Run tests to verify they fail**

Run: `pytest tests/test_tools.py -v -k "TestBrowseTopics or TestGetCodelist or TestGetDatasetInfoCodelistId"`
Expected: FAIL

- [ ] **Step 5: Implement the tool functions**

Add imports to `tools.py`:

```python
import re

from ibestat_mcp.cache import SemanticCache, cache as _default_cache
from ibestat_mcp.models import CodelistResult, TopicTree
from ibestat_mcp.structural_parser import (
    extract_codelist_ids_from_dsd,
    parse_categories,
    parse_codelist_codes,
)
```

Add new functions:

```python
async def browse_topics(
    client: IbestatClient,
    lang: str = "ca",
    _cache: SemanticCache | None = None,
) -> TopicTree:
    c = _cache or _default_cache
    if c.topics is not None:
        return c.topics
    response = await client.get_categories()
    categories = parse_categories(response, lang)
    c.topics = TopicTree(name="TEMAS_BALEARS", categories=categories)
    return c.topics


async def get_codelist(
    client: IbestatClient,
    codelist_id: str,
    limit: int = 100,
    offset: int = 0,
    lang: str = "ca",
    _cache: SemanticCache | None = None,
) -> CodelistResult:
    c = _cache or _default_cache
    cached = c.get_codelist(codelist_id)
    if cached is not None:
        return cached
    response = await client.get_codelist_codes(codelist_id, limit=limit, offset=offset)
    codes = parse_codelist_codes(response, lang)
    total = response.get("total", len(codes))
    result = CodelistResult(id=codelist_id, name=codelist_id, total=total, codes=codes)
    c.set_codelist(codelist_id, result)
    return result
```

Modify existing `get_dataset_info`:

```python
async def get_dataset_info(
    client: IbestatClient,
    dataset_id: str,
    lang: str = "ca",
    _cache: SemanticCache | None = None,
) -> DatasetInfo:
    c = _cache or _default_cache
    response = await client.get_dataset_metadata(dataset_id)
    name = extract_localized_text(response.get("name"), lang)
    dimensions = parse_dimensions(response, lang)

    codelist_map = c.get_dsd_codelist_map(dataset_id)
    if codelist_map is None:
        try:
            related_dsd = response.get("metadata", {}).get("relatedDsd", {})
            dsd_urn = related_dsd.get("urn", "")
            match = re.search(r"DataStructureDefinition=\w+:(\w+)\(", dsd_urn)
            if match:
                dsd_response = await client.get_data_structure(match.group(1))
                codelist_map = extract_codelist_ids_from_dsd(dsd_response)
                c.set_dsd_codelist_map(dataset_id, codelist_map)
        except Exception:
            codelist_map = {}

    for dim in dimensions:
        dim.codelist_id = codelist_map.get(dim.id)

    return DatasetInfo(name=name, dimensions=dimensions)
```

- [ ] **Step 6: Run tool tests**

Run: `pytest tests/test_tools.py -v`
Expected: All pass

- [ ] **Step 7: Commit**

```bash
git add src/ibestat_mcp/tools.py tests/test_tools.py
git commit -m "feat: add browse_topics, get_codelist tools with caching; enrich get_dataset_info with codelist_id"
```

---

## Task 7: Register new tools in the MCP server

**Files:**
- Modify: `src/ibestat_mcp/server.py`
- Modify: `tests/test_server.py`

- [ ] **Step 1: Write server registration tests**

Add to `tests/test_server.py`:

```python
class TestBrowseTopicsTool:
    @pytest.mark.asyncio
    async def test_tool_registered(self) -> None:
        server = create_server()
        tool_names = [t.name for t in await server.list_tools()]
        assert "browse_topics" in tool_names


class TestGetCodelistTool:
    @pytest.mark.asyncio
    async def test_tool_registered(self) -> None:
        server = create_server()
        tool_names = [t.name for t in await server.list_tools()]
        assert "get_codelist" in tool_names
```

- [ ] **Step 2: Register tools in `server.py`**

Add inside `create_server()` after existing tools:

```python
@mcp.tool(
    description=(
        "Browse IBESTAT's thematic topic tree to discover what statistical "
        "domains are available (e.g., Demographics, Economy, Tourism, Labour). "
        "Returns a hierarchical list of categories with parent references. "
        "Use this FIRST to see what topics exist, then use the topic names "
        "as search terms in search_datasets. "
        "Supports Catalan (ca), Spanish (es), and English (en) labels."
    ),
)
async def browse_topics(
    language: Annotated[
        Literal["ca", "es", "en"],
        Field(description="Language for labels. Default: 'ca'."),
    ] = "ca",
) -> str:
    try:
        async with IbestatClient() as client:
            result = await tool_functions.browse_topics(client, lang=language)
        return json.dumps(result.model_dump(), ensure_ascii=False)
    except IbestatError as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)

@mcp.tool(
    description=(
        "Get codes from an IBESTAT codelist with their hierarchical "
        "parent-child relationships. Use the codelist_id from "
        "get_dataset_info to explore valid filter values at all levels "
        "(e.g., region > island > municipality for geographic codes). "
        "Supports pagination for large codelists."
    ),
)
async def get_codelist(
    codelist_id: Annotated[
        str,
        Field(description="Codelist identifier from get_dataset_info (e.g., 'CL_AREA_ES53')."),
    ],
    limit: Annotated[
        int,
        Field(description="Max codes to return (default: 100)."),
    ] = 100,
    offset: Annotated[
        int,
        Field(description="Pagination offset (default: 0)."),
    ] = 0,
    language: Annotated[
        Literal["ca", "es", "en"],
        Field(description="Language for labels. Default: 'ca'."),
    ] = "ca",
) -> str:
    try:
        async with IbestatClient() as client:
            result = await tool_functions.get_codelist(
                client, codelist_id, limit=limit, offset=offset, lang=language
            )
        return json.dumps(result.model_dump(), ensure_ascii=False)
    except IbestatError as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)
```

- [ ] **Step 3: Run all tests**

Run: `pytest -m "not e2e" -v`
Expected: All pass

- [ ] **Step 4: Commit**

```bash
git add src/ibestat_mcp/server.py tests/test_server.py
git commit -m "feat: register browse_topics and get_codelist MCP tools"
```

---

## Task 8: E2E tests

**Files:**
- Modify: `tests/test_e2e.py`

- [ ] **Step 1: Add e2e tests**

```python
from ibestat_mcp.tools import browse_topics, get_codelist, get_dataset_info
from ibestat_mcp.client import IbestatClient
from ibestat_mcp.cache import SemanticCache


@pytest.mark.e2e
class TestBrowseTopicsE2E:
    @pytest.mark.asyncio
    async def test_returns_categories(self) -> None:
        async with IbestatClient() as client:
            result = await browse_topics(client, lang="es", _cache=SemanticCache())
        assert len(result.categories) > 0
        top_level = [c for c in result.categories if c.parent_id is None]
        assert len(top_level) > 0


@pytest.mark.e2e
class TestGetCodelistE2E:
    @pytest.mark.asyncio
    async def test_geographic_codelist(self) -> None:
        async with IbestatClient() as client:
            result = await get_codelist(client, "CL_AREA_ES53", limit=10, lang="es", _cache=SemanticCache())
        assert result.total > 0
        assert len(result.codes) <= 10

    @pytest.mark.asyncio
    async def test_hierarchy_present(self) -> None:
        async with IbestatClient() as client:
            result = await get_codelist(client, "CL_AREA_ES53", limit=100, lang="ca", _cache=SemanticCache())
        codes_with_parents = [c for c in result.codes if c.parent_code is not None]
        assert len(codes_with_parents) > 0


@pytest.mark.e2e
class TestGetDatasetInfoCodelistIdE2E:
    @pytest.mark.asyncio
    async def test_includes_codelist_id(self) -> None:
        async with IbestatClient() as client:
            result = await get_dataset_info(client, "000001A_000001", lang="ca", _cache=SemanticCache())
        territorio = next((d for d in result.dimensions if d.id == "TERRITORIO"), None)
        assert territorio is not None
        assert territorio.codelist_id is not None
```

- [ ] **Step 2: Run e2e tests**

Run: `pytest -m e2e -v`
Expected: All pass

- [ ] **Step 3: Commit**

```bash
git add tests/test_e2e.py
git commit -m "test: add e2e tests for structural resources integration"
```

---

## Task 9: Documentation

Update all three doc files to reflect the new tools, the semantic workflow, and the caching layer.

**Files:**
- Modify: `CLAUDE.md`
- Modify: `README.md`
- Modify: `docs/design.md`

- [ ] **Step 1: Update `CLAUDE.md` — add semantic workflow for LLM agents**

Add a new section after "Project Structure":

```markdown
## Semantic Layer & Recommended Workflow

The MCP server has a semantic layer powered by IBESTAT's structural-resources API.
Structural data (topics, codelists, DSDs) is cached in memory for the server session.

### Recommended tool workflow

1. **`browse_topics`** — See all statistical domains IBESTAT covers (cached after first call)
2. **`search_datasets`** — Find datasets using vocabulary from step 1
3. **`get_dataset_info`** — Inspect dataset dimensions; each dimension includes a `codelist_id` if a hierarchical codelist exists
4. **`get_codelist`** — Use the `codelist_id` to explore valid filter values at all hierarchy levels (e.g., region > island > municipality)
5. **`get_data`** — Query with valid filters discovered in step 4

### Tool inventory

| Tool | Purpose | Cached |
|------|---------|--------|
| `browse_topics` | Thematic topic tree (52 categories) | Yes — fetched once per session |
| `search_datasets` | Keyword search for datasets | No |
| `get_dataset_info` | Dataset dimensions + codelist references | DSD mapping cached per dataset |
| `get_codelist` | Hierarchical codes for a codelist | Yes — per codelist |
| `get_data` | Fetch observation data with filters | No |
```

- [ ] **Step 2: Update `README.md` — add new tools and workflow for human users**

Update the Tools section and Quick Start to include the new workflow:

```markdown
## Tools

| Tool | Description |
|------|-------------|
| `browse_topics` | Browse IBESTAT's thematic catalog (Demographics, Economy, Tourism, Labour...) |
| `search_datasets` | Search for datasets by keyword |
| `get_dataset_info` | Inspect a dataset's dimensions and discover linked codelists |
| `get_codelist` | Explore a codelist's hierarchical codes (e.g., geographic: Region > Island > Municipality) |
| `get_data` | Fetch data rows with optional filters |

## Quick Start

The recommended workflow:

1. **Browse topics** to see what's available → `browse_topics`
2. **Search** using terms from the topic tree → `search_datasets`
3. **Inspect** a dataset to see its dimensions and codelist IDs → `get_dataset_info`
4. **Explore codelists** to discover valid filter values at all levels → `get_codelist`
5. **Query** with known-valid filters → `get_data`
```

- [ ] **Step 3: Update `docs/design.md` — bring structural resources in scope**

Remove "Structural Resources API" and "Caching" from the Out of Scope section. Add a new section:

```markdown
## Semantic Layer (Structural Resources)

### API

Base URL: `https://ibestat.es/edatos/apis/structural-resources/v1.0`

Endpoints used:
- `GET /categoryschemes/IBESTAT/TEMAS_BALEARS/~latest/categories` — topic tree
- `GET /codelists/IBESTAT/{id}/~latest/codes` — codelist codes with hierarchy
- `GET /datastructures/IBESTAT/{id}/~latest` — DSD (dimension → codelist mapping)

### Caching

`SemanticCache` (in `cache.py`) stores structural data in memory for the server
process lifetime. Topics, DSD mappings, and codelists are fetched once on first use.

### Key concepts

- **Category scheme (TEMAS_BALEARS)**: 52 thematic categories in a parent-child tree
- **Codelist**: Hierarchical lookup table for a dimension's valid codes (e.g., geographic codes organized as region > island > municipality)
- **DSD (Data Structure Definition)**: Blueprint that maps each dataset dimension to its codelist
- **codelist_id**: Field on DimensionInfo returned by get_dataset_info, linking a dimension to its codelist for use with get_codelist
```

- [ ] **Step 4: Run tests one final time**

Run: `pytest -m "not e2e" -v`
Expected: All pass

- [ ] **Step 5: Commit**

```bash
git add CLAUDE.md README.md docs/design.md
git commit -m "docs: add semantic layer workflow, new tools, and caching to all docs"
```
