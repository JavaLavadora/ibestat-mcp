# IBESTAT MCP Server Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an MCP server that exposes IBESTAT eDades statistical data through three tools: search_datasets, get_dataset_info, get_data.

**Architecture:** Python package with layered modules — `models.py` (Pydantic output schemas), `client.py` (async HTTP client for eDades API), `parser.py` (pipe-delimited observation flattening), `tools.py` (MCP tool definitions), `server.py` (MCP server entry point). Each module has a single responsibility; only `client.py` knows about IBESTAT API URLs.

**Tech Stack:** Python 3.10+, mcp SDK, httpx, pydantic, pytest + pytest-asyncio + respx for testing.

**Language policy:** Code in English. User-facing data labels in Catalan (lang=ca). Product references in Catalan (eDades, not eDatos). No accents or special characters in code identifiers.

---

## File Map

| File | Responsibility |
|------|---------------|
| `src/ibestat_mcp/models.py` | Pydantic models for tool outputs: DatasetSummary, DimensionValue, DimensionInfo, DatasetInfo |
| `src/ibestat_mcp/client.py` | IbestatClient class — async HTTP calls to eDades API, returns raw JSON dicts |
| `src/ibestat_mcp/parser.py` | Functions to extract Catalan labels, parse pipe-delimited observations into flat row dicts |
| `src/ibestat_mcp/tools.py` | MCP tool functions wiring client + parser → model outputs |
| `src/ibestat_mcp/server.py` | MCP server setup, tool registration, CLI entry point |
| `tests/conftest.py` | Shared fixtures: sample API response dicts |
| `tests/test_models.py` | Model validation tests |
| `tests/test_parser.py` | Parser unit tests with synthetic observation data |
| `tests/test_client.py` | Client tests with mocked HTTP (respx) |
| `tests/test_tools.py` | Tool integration tests with mocked client |
| `tests/test_server.py` | Server startup and tool registration test |
| `tests/fixtures/` | JSON files with captured real API responses for test fixtures |

---

## Task 1: Capture API Response Fixtures

**Purpose:** Before writing any code, capture real API responses to use as test fixtures. This ensures our models and parser match the actual API shape, not guesses.

**Files:**
- Create: `tests/fixtures/search_datasets_response.json`
- Create: `tests/fixtures/dataset_metadata_response.json`
- Create: `tests/fixtures/dataset_data_response.json`

- [ ] **Step 1: Capture search response**

```bash
curl -s "https://ibestat.es/edatos/apis/statistical-resources/v1.0/datasets?query=name%20ILIKE%20%27poblaci%27&limit=5&_type=json" | python3 -m json.tool > tests/fixtures/search_datasets_response.json
```

Verify it contains a JSON object with `total`, `limit`, `offset`, and a `dataset` array. Note the exact field names for multilingual `name` fields.

- [ ] **Step 2: Capture dataset metadata response**

```bash
curl -s "https://ibestat.es/edatos/apis/statistical-resources/v1.0/datasets/IBESTAT/000001A_000001/~latest?_type=json" | python3 -m json.tool > tests/fixtures/dataset_metadata_response.json
```

Verify it contains dimension definitions with representations (code-to-index mappings and multilingual labels).

- [ ] **Step 3: Capture dataset data response**

```bash
curl -s "https://ibestat.es/edatos/apis/statistical-resources/v1.0/datasets/IBESTAT/000001A_000001/~latest?dim=TIME_PERIOD:2024&dim=TERRITORIO:07001&dim=SEXO:_T&dim=MEDIDAS:POBLACION_PADRON&_type=json&fields=-metadata" | python3 -m json.tool > tests/fixtures/dataset_data_response.json
```

Verify it contains `data.dimensions`, `data.observations` (pipe-delimited string), and `data.attributes`.

- [ ] **Step 4: Document actual JSON field names**

Read through the three fixture files and note:
- How multilingual names are structured (e.g., `name.text[].value` vs `name.__default__`)
- How dimension representations map codes to indices
- The exact path to observations data
- How dimension values carry their labels

Write these observations as comments in `tests/conftest.py`:

```python
# IBESTAT eDades API response structure notes:
#
# Search response: root has 'total', 'limit', 'offset', 'dataset' (array)
#   Each dataset: 'id', 'name' (multilingual), 'selfLink', 'visualizerHtmlLink'
#
# Metadata response: 'metadata.dimensions.dimension' array
#   Each dimension: 'dimensionId', 'type', 'representations.representation' array
#   Each representation: 'code', 'index', 'title' (multilingual)
#
# Data response: 'data.dimensions.dimension' array + 'data.observations' (pipe string)
#   Dimension representations carry code-to-index mappings
#
# Multilingual text: check actual structure in fixtures and adapt parser accordingly
#
# UPDATE THESE NOTES after reading the actual fixture files.
```

- [ ] **Step 5: Commit**

```bash
git add tests/fixtures/ tests/conftest.py
git commit -m "feat: capture real API response fixtures for test development"
```

---

## Task 2: Pydantic Models

**Purpose:** Define the data models that the MCP tools return. These are the contract between tools and the LLM.

**Files:**
- Create: `src/ibestat_mcp/models.py`
- Create: `tests/test_models.py`

- [ ] **Step 1: Write failing tests for models**

```python
# tests/test_models.py
from ibestat_mcp.models import DatasetSummary, DimensionValue, DimensionInfo, DatasetInfo


class TestDatasetSummary:
    def test_create_with_all_fields(self):
        ds = DatasetSummary(
            id="000001A_000001",
            name="Poblacio municipal empadronada segons el sexe",
            description="Municipis de les Illes Balears per anys",
            link="https://ibestat.es/edatos/apps/statistical-visualizer/visualizer/data.html?resourceType=dataset&agencyId=IBESTAT&resourceId=000001A_000001",
        )
        assert ds.id == "000001A_000001"
        assert ds.name == "Poblacio municipal empadronada segons el sexe"
        assert ds.description == "Municipis de les Illes Balears per anys"
        assert ds.link.startswith("https://")

    def test_description_is_optional(self):
        ds = DatasetSummary(
            id="000001A_000001",
            name="Poblacio municipal",
            link="https://example.com",
        )
        assert ds.description is None


class TestDimensionValue:
    def test_create(self):
        dv = DimensionValue(code="07001", label="Alaro")
        assert dv.code == "07001"
        assert dv.label == "Alaro"


class TestDimensionInfo:
    def test_create_with_values(self):
        dim = DimensionInfo(
            id="TERRITORIO",
            name="Territori",
            values=[
                DimensionValue(code="07001", label="Alaro"),
                DimensionValue(code="07002", label="Alcudia"),
            ],
        )
        assert dim.id == "TERRITORIO"
        assert len(dim.values) == 2
        assert dim.values[0].label == "Alaro"


class TestDatasetInfo:
    def test_create(self):
        info = DatasetInfo(
            name="Poblacio municipal empadronada segons el sexe",
            dimensions=[
                DimensionInfo(
                    id="TERRITORIO",
                    name="Territori",
                    values=[DimensionValue(code="07001", label="Alaro")],
                ),
            ],
        )
        assert info.name == "Poblacio municipal empadronada segons el sexe"
        assert len(info.dimensions) == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /home/jovyan/projects/ibestat-mcp && python -m pytest tests/test_models.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'ibestat_mcp.models'` or `ImportError`

- [ ] **Step 3: Implement models**

```python
# src/ibestat_mcp/models.py
from pydantic import BaseModel


class DatasetSummary(BaseModel):
    id: str
    name: str
    description: str | None = None
    link: str


class DimensionValue(BaseModel):
    code: str
    label: str


class DimensionInfo(BaseModel):
    id: str
    name: str
    values: list[DimensionValue]


class DatasetInfo(BaseModel):
    name: str
    dimensions: list[DimensionInfo]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /home/jovyan/projects/ibestat-mcp && python -m pytest tests/test_models.py -v`
Expected: All 5 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/ibestat_mcp/models.py tests/test_models.py
git commit -m "feat: add Pydantic models for MCP tool outputs"
```

---

## Task 3: Observation Parser

**Purpose:** Build the parser that converts IBESTAT's pipe-delimited observation strings + dimension index maps into flat row dicts with Catalan labels. This is the core complexity of the project.

**Files:**
- Create: `src/ibestat_mcp/parser.py`
- Create: `tests/test_parser.py`

**Important:** The parser functions take raw API response dicts as input. The exact field names must match what was discovered in Task 1 fixtures. Read the fixture files before implementing.

- [ ] **Step 1: Write test for extract_localized_text helper**

This helper extracts Catalan text from the multilingual name structures in API responses. The exact structure depends on what was captured in Task 1 — adapt the test fixture accordingly.

```python
# tests/test_parser.py
from ibestat_mcp.parser import extract_localized_text, strip_accents


class TestExtractLocalizedText:
    def test_extracts_catalan_text(self):
        # Adapt this structure to match actual API response format from fixtures
        multilingual = {
            "text": [
                {"lang": "ca", "value": "Poblacio municipal"},
                {"lang": "es", "value": "Poblacion municipal"},
            ]
        }
        assert extract_localized_text(multilingual) == "Poblacio municipal"

    def test_falls_back_to_first_available(self):
        multilingual = {
            "text": [
                {"lang": "es", "value": "Poblacion municipal"},
            ]
        }
        assert extract_localized_text(multilingual) == "Poblacion municipal"

    def test_returns_empty_string_for_missing(self):
        assert extract_localized_text(None) == ""
        assert extract_localized_text({}) == ""
```

- [ ] **Step 2: Write test for strip_accents helper**

```python
class TestStripAccents:
    def test_strips_common_catalan_accents(self):
        assert strip_accents("Poblacio") == "Poblacio"
        assert strip_accents("Població") == "Poblacio"
        assert strip_accents("Període") == "Periode"
        assert strip_accents("Variació anual") == "Variacio anual"

    def test_preserves_plain_ascii(self):
        assert strip_accents("Total") == "Total"
        assert strip_accents("TIME_PERIOD") == "TIME_PERIOD"

    def test_handles_empty_string(self):
        assert strip_accents("") == ""
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `cd /home/jovyan/projects/ibestat-mcp && python -m pytest tests/test_parser.py -v -k "TestExtractLocalizedText or TestStripAccents"`
Expected: FAIL with ImportError

- [ ] **Step 4: Implement extract_localized_text and strip_accents**

```python
# src/ibestat_mcp/parser.py
from __future__ import annotations

import unicodedata
from typing import Any


def strip_accents(text: str) -> str:
    nfkd = unicodedata.normalize("NFKD", text)
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def extract_localized_text(
    multilingual: dict[str, Any] | None, lang: str = "ca"
) -> str:
    if not multilingual:
        return ""
    texts = multilingual.get("text", [])
    if not texts:
        return ""
    for entry in texts:
        if entry.get("lang") == lang:
            return entry.get("value", "")
    return texts[0].get("value", "") if texts else ""
```

**Note:** The `multilingual` dict structure above (`{"text": [{"lang": ..., "value": ...}]}`) is a best guess. After Task 1 captures real fixtures, verify and adapt the field names (could be `__default__`, `value` vs `text`, etc.).

- [ ] **Step 5: Run helper tests to verify they pass**

Run: `cd /home/jovyan/projects/ibestat-mcp && python -m pytest tests/test_parser.py -v -k "TestExtractLocalizedText or TestStripAccents"`
Expected: All 6 tests PASS

- [ ] **Step 6: Write test for parse_dimensions (metadata extraction)**

This function takes a full dataset metadata response and extracts dimension info with Catalan labels.

```python
class TestParseDimensions:
    def test_parses_dimensions_from_metadata(self):
        # Build a minimal metadata response matching the fixture structure.
        # Adapt field names to match actual API response from Task 1.
        metadata = {
            "metadata": {
                "dimensions": {
                    "dimension": [
                        {
                            "dimensionId": "TERRITORIO",
                            "type": "GEOGRAPHIC_DIMENSION",
                            "representations": {
                                "representation": [
                                    {
                                        "code": "07001",
                                        "index": 0,
                                        "title": {
                                            "text": [
                                                {"lang": "ca", "value": "Alaro"},
                                                {"lang": "es", "value": "Alaro"},
                                            ]
                                        },
                                    },
                                    {
                                        "code": "07002",
                                        "index": 1,
                                        "title": {
                                            "text": [
                                                {"lang": "ca", "value": "Alcudia"},
                                                {"lang": "es", "value": "Alcudia"},
                                            ]
                                        },
                                    },
                                ]
                            },
                        },
                        {
                            "dimensionId": "TIME_PERIOD",
                            "type": "TIME_DIMENSION",
                            "representations": {
                                "representation": [
                                    {"code": "2024", "index": 0, "title": {"text": [{"lang": "ca", "value": "2024"}]}},
                                    {"code": "2023", "index": 1, "title": {"text": [{"lang": "ca", "value": "2023"}]}},
                                ]
                            },
                        },
                    ]
                }
            }
        }
        from ibestat_mcp.parser import parse_dimensions

        dims = parse_dimensions(metadata)
        assert len(dims) == 2
        assert dims[0].id == "TERRITORIO"
        assert dims[0].values[0].code == "07001"
        assert dims[0].values[0].label == "Alaro"
        assert dims[1].id == "TIME_PERIOD"
        assert len(dims[1].values) == 2
```

- [ ] **Step 7: Run test to verify it fails**

Run: `cd /home/jovyan/projects/ibestat-mcp && python -m pytest tests/test_parser.py::TestParseDimensions -v`
Expected: FAIL with ImportError for `parse_dimensions`

- [ ] **Step 8: Implement parse_dimensions**

```python
# Add to src/ibestat_mcp/parser.py
from ibestat_mcp.models import DimensionInfo, DimensionValue


def parse_dimensions(metadata_response: dict[str, Any]) -> list[DimensionInfo]:
    # Adapt these field paths after verifying against Task 1 fixtures
    dims_data = (
        metadata_response
        .get("metadata", {})
        .get("dimensions", {})
        .get("dimension", [])
    )
    dimensions = []
    for dim in dims_data:
        dim_id = dim.get("dimensionId", "")
        representations = (
            dim.get("representations", {}).get("representation", [])
        )
        values = []
        for rep in representations:
            code = rep.get("code", "")
            label = strip_accents(extract_localized_text(rep.get("title")))
            values.append(DimensionValue(code=code, label=label))
        dim_name = strip_accents(dim_id.replace("_", " ").title())
        dimensions.append(DimensionInfo(id=dim_id, name=dim_name, values=values))
    return dimensions
```

- [ ] **Step 9: Run test to verify it passes**

Run: `cd /home/jovyan/projects/ibestat-mcp && python -m pytest tests/test_parser.py::TestParseDimensions -v`
Expected: PASS

- [ ] **Step 10: Write test for parse_observations (data flattening)**

This is the core function. It takes a data response (with `data.dimensions` and `data.observations`) and returns flat row dicts.

```python
class TestParseObservations:
    def test_flattens_simple_2d_data(self):
        # 2 territories x 1 measure = 2 observations
        data_response = {
            "data": {
                "dimensions": {
                    "dimension": [
                        {
                            "dimensionId": "TERRITORIO",
                            "representations": {
                                "representation": [
                                    {"code": "07001", "index": 0, "title": {"text": [{"lang": "ca", "value": "Alaro"}]}},
                                    {"code": "07002", "index": 1, "title": {"text": [{"lang": "ca", "value": "Alcudia"}]}},
                                ]
                            },
                        },
                        {
                            "dimensionId": "MEDIDAS",
                            "representations": {
                                "representation": [
                                    {"code": "POBLACION_PADRON", "index": 0, "title": {"text": [{"lang": "ca", "value": "Població padró"}]}},
                                ]
                            },
                        },
                    ]
                },
                "observations": "2035 | 50000",
            }
        }
        from ibestat_mcp.parser import parse_observations

        rows = parse_observations(data_response)
        assert len(rows) == 2
        assert rows[0]["Territori"] == "Alaro"
        assert rows[0]["Poblacio padro"] == 2035.0
        assert rows[1]["Territori"] == "Alcudia"
        assert rows[1]["Poblacio padro"] == 50000.0

    def test_flattens_multidimensional_data(self):
        # 2 territories x 2 sexes = 4 observations, 1 measure
        data_response = {
            "data": {
                "dimensions": {
                    "dimension": [
                        {
                            "dimensionId": "TERRITORIO",
                            "representations": {
                                "representation": [
                                    {"code": "07001", "index": 0, "title": {"text": [{"lang": "ca", "value": "Alaro"}]}},
                                    {"code": "07002", "index": 1, "title": {"text": [{"lang": "ca", "value": "Alcudia"}]}},
                                ]
                            },
                        },
                        {
                            "dimensionId": "SEXO",
                            "representations": {
                                "representation": [
                                    {"code": "_T", "index": 0, "title": {"text": [{"lang": "ca", "value": "Total"}]}},
                                    {"code": "M", "index": 1, "title": {"text": [{"lang": "ca", "value": "Home"}]}},
                                ]
                            },
                        },
                        {
                            "dimensionId": "MEDIDAS",
                            "representations": {
                                "representation": [
                                    {"code": "POBLACION_PADRON", "index": 0, "title": {"text": [{"lang": "ca", "value": "Població"}]}},
                                ]
                            },
                        },
                    ]
                },
                "observations": "2035 | 1012 | 50000 | 25000",
            }
        }
        from ibestat_mcp.parser import parse_observations

        rows = parse_observations(data_response)
        assert len(rows) == 4
        # Verify dimension labels appear as column names (accents stripped)
        assert "Territori" in rows[0]
        assert "Sexe" in rows[0]

    def test_handles_null_observations(self):
        data_response = {
            "data": {
                "dimensions": {
                    "dimension": [
                        {
                            "dimensionId": "TERRITORIO",
                            "representations": {
                                "representation": [
                                    {"code": "07001", "index": 0, "title": {"text": [{"lang": "ca", "value": "Alaro"}]}},
                                ]
                            },
                        },
                        {
                            "dimensionId": "MEDIDAS",
                            "representations": {
                                "representation": [
                                    {"code": "POBLACION_PADRON", "index": 0, "title": {"text": [{"lang": "ca", "value": "Població"}]}},
                                ]
                            },
                        },
                    ]
                },
                "observations": " ",
            }
        }
        from ibestat_mcp.parser import parse_observations

        rows = parse_observations(data_response)
        assert len(rows) == 1
        assert rows[0]["Poblacio"] is None
```

- [ ] **Step 11: Run test to verify it fails**

Run: `cd /home/jovyan/projects/ibestat-mcp && python -m pytest tests/test_parser.py::TestParseObservations -v`
Expected: FAIL with ImportError for `parse_observations`

- [ ] **Step 12: Implement parse_observations**

```python
# Add to src/ibestat_mcp/parser.py
import itertools

MEASURE_DIMENSION_ID = "MEDIDAS"


def _parse_observation_value(raw: str) -> float | None:
    stripped = raw.strip()
    if not stripped or stripped == "." or stripped == "..":
        return None
    try:
        return float(stripped)
    except ValueError:
        return None


def _build_dimension_info(
    dims_data: list[dict[str, Any]],
) -> tuple[list[tuple[str, list[str]]], list[str] | None]:
    """Returns (regular_dimensions, measure_labels).
    
    Regular dimensions become row keys. The MEDIDAS dimension (if present) 
    is separated out — its labels become column names for observation values.
    """
    regular_dims: list[tuple[str, list[str]]] = []
    measure_labels: list[str] | None = None

    for dim in dims_data:
        dim_id = dim.get("dimensionId", "")
        reps = dim.get("representations", {}).get("representation", [])
        indexed_values: list[tuple[int, str]] = []
        for rep in reps:
            idx = rep.get("index", 0)
            label = strip_accents(extract_localized_text(rep.get("title")))
            indexed_values.append((idx, label))
        indexed_values.sort(key=lambda x: x[0])
        labels = [label for _, label in indexed_values]

        if dim_id == MEASURE_DIMENSION_ID:
            measure_labels = labels
        else:
            col_name = strip_accents(dim_id.replace("_", " ").title())
            regular_dims.append((col_name, labels))

    return regular_dims, measure_labels


def parse_observations(data_response: dict[str, Any]) -> list[dict[str, Any]]:
    data = data_response.get("data", {})
    dims_data = data.get("dimensions", {}).get("dimension", [])
    obs_str = data.get("observations", "")

    regular_dims, measure_labels = _build_dimension_info(dims_data)

    raw_values = [v.strip() for v in obs_str.split("|")] if obs_str.strip() else []
    num_measures = len(measure_labels) if measure_labels else 1

    dim_labels = [labels for _, labels in regular_dims]
    dim_names = [name for name, _ in regular_dims]

    rows: list[dict[str, Any]] = []
    for i, combo in enumerate(itertools.product(*dim_labels)):
        row: dict[str, Any] = {}
        for name, val in zip(dim_names, combo):
            row[name] = val

        base_idx = i * num_measures
        if measure_labels:
            for j, m_label in enumerate(measure_labels):
                idx = base_idx + j
                row[m_label] = _parse_observation_value(raw_values[idx]) if idx < len(raw_values) else None
        else:
            row["value"] = _parse_observation_value(raw_values[base_idx]) if base_idx < len(raw_values) else None

        rows.append(row)

    return rows
```

**Important note:** The observation ordering (which dimension varies fastest) must be verified against the real fixtures from Task 1. The implementation assumes MEDIDAS is the fastest-varying dimension (innermost loop). Adjust if the API orders differently.

- [ ] **Step 13: Run test to verify it passes**

Run: `cd /home/jovyan/projects/ibestat-mcp && python -m pytest tests/test_parser.py -v`
Expected: All parser tests PASS

- [ ] **Step 14: Commit**

```bash
git add src/ibestat_mcp/parser.py tests/test_parser.py
git commit -m "feat: add observation parser with accent stripping and localization"
```

---

## Task 4: HTTP Client

**Purpose:** Build the async HTTP client that calls the IBESTAT eDades API. This is the only module that knows about API URLs and query parameter shapes.

**Files:**
- Create: `src/ibestat_mcp/client.py`
- Create: `tests/test_client.py`

- [ ] **Step 1: Write failing tests for IbestatClient**

```python
# tests/test_client.py
import json
import pytest
import httpx
import respx
from ibestat_mcp.client import IbestatClient

BASE_URL = "https://ibestat.es/edatos/apis/statistical-resources/v1.0"


@pytest.fixture
def search_response():
    with open("tests/fixtures/search_datasets_response.json") as f:
        return json.load(f)


@pytest.fixture
def metadata_response():
    with open("tests/fixtures/dataset_metadata_response.json") as f:
        return json.load(f)


@pytest.fixture
def data_response():
    with open("tests/fixtures/dataset_data_response.json") as f:
        return json.load(f)


class TestIbestatClientSearch:
    @pytest.mark.asyncio
    @respx.mock
    async def test_search_datasets_calls_correct_url(self, search_response):
        route = respx.get(f"{BASE_URL}/datasets").mock(
            return_value=httpx.Response(200, json=search_response)
        )
        async with IbestatClient() as client:
            result = await client.search_datasets("poblaci", limit=5)
        assert route.called
        request = route.calls[0].request
        assert "name ILIKE 'poblaci'" in str(request.url)
        assert "_type=json" in str(request.url)
        assert "limit=5" in str(request.url)

    @pytest.mark.asyncio
    @respx.mock
    async def test_search_datasets_returns_raw_json(self, search_response):
        respx.get(f"{BASE_URL}/datasets").mock(
            return_value=httpx.Response(200, json=search_response)
        )
        async with IbestatClient() as client:
            result = await client.search_datasets("poblaci")
        assert isinstance(result, dict)
        assert "dataset" in result or "total" in result


class TestIbestatClientMetadata:
    @pytest.mark.asyncio
    @respx.mock
    async def test_get_dataset_metadata_calls_correct_url(self, metadata_response):
        route = respx.get(
            f"{BASE_URL}/datasets/IBESTAT/000001A_000001/~latest"
        ).mock(return_value=httpx.Response(200, json=metadata_response))
        async with IbestatClient() as client:
            result = await client.get_dataset_metadata("000001A_000001")
        assert route.called
        assert "_type=json" in str(route.calls[0].request.url)


class TestIbestatClientData:
    @pytest.mark.asyncio
    @respx.mock
    async def test_get_dataset_data_with_filters(self, data_response):
        route = respx.get(
            f"{BASE_URL}/datasets/IBESTAT/000001A_000001/~latest"
        ).mock(return_value=httpx.Response(200, json=data_response))
        async with IbestatClient() as client:
            result = await client.get_dataset_data(
                "000001A_000001",
                filters={"TIME_PERIOD": "2024", "TERRITORIO": "07001"},
            )
        assert route.called
        url = str(route.calls[0].request.url)
        assert "dim=TIME_PERIOD:2024" in url
        assert "dim=TERRITORIO:07001" in url

    @pytest.mark.asyncio
    @respx.mock
    async def test_get_dataset_data_with_multi_value_filter(self, data_response):
        route = respx.get(
            f"{BASE_URL}/datasets/IBESTAT/000001A_000001/~latest"
        ).mock(return_value=httpx.Response(200, json=data_response))
        async with IbestatClient() as client:
            result = await client.get_dataset_data(
                "000001A_000001",
                filters={"TIME_PERIOD": ["2023", "2024"]},
            )
        assert route.called
        url = str(route.calls[0].request.url)
        assert "dim=TIME_PERIOD:2023|2024" in url

    @pytest.mark.asyncio
    @respx.mock
    async def test_get_dataset_data_without_filters(self, data_response):
        route = respx.get(
            f"{BASE_URL}/datasets/IBESTAT/000001A_000001/~latest"
        ).mock(return_value=httpx.Response(200, json=data_response))
        async with IbestatClient() as client:
            result = await client.get_dataset_data("000001A_000001")
        assert route.called
        url = str(route.calls[0].request.url)
        assert "dim=" not in url


class TestIbestatClientErrors:
    @pytest.mark.asyncio
    @respx.mock
    async def test_raises_on_404(self):
        respx.get(f"{BASE_URL}/datasets/IBESTAT/INVALID_ID/~latest").mock(
            return_value=httpx.Response(404)
        )
        async with IbestatClient() as client:
            with pytest.raises(Exception, match="not found"):
                await client.get_dataset_metadata("INVALID_ID")

    @pytest.mark.asyncio
    @respx.mock
    async def test_raises_on_timeout(self):
        respx.get(f"{BASE_URL}/datasets").mock(side_effect=httpx.ConnectTimeout)
        async with IbestatClient() as client:
            with pytest.raises(Exception, match="unavailable"):
                await client.search_datasets("test")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /home/jovyan/projects/ibestat-mcp && python -m pytest tests/test_client.py -v`
Expected: FAIL with ImportError

- [ ] **Step 3: Implement IbestatClient**

```python
# src/ibestat_mcp/client.py
from __future__ import annotations

from typing import Any

import httpx

BASE_URL = "https://ibestat.es/edatos/apis/statistical-resources/v1.0"
TIMEOUT = 30.0


class IbestatError(Exception):
    pass


class IbestatClient:
    def __init__(self, base_url: str = BASE_URL) -> None:
        self._base_url = base_url
        self._http: httpx.AsyncClient | None = None

    async def __aenter__(self) -> IbestatClient:
        self._http = httpx.AsyncClient(timeout=TIMEOUT)
        return self

    async def __aexit__(self, *args: Any) -> None:
        if self._http:
            await self._http.aclose()

    def _client(self) -> httpx.AsyncClient:
        if self._http is None:
            raise RuntimeError("Use IbestatClient as an async context manager")
        return self._http

    async def _get(self, url: str, params: dict[str, str] | None = None) -> dict[str, Any]:
        all_params = {"_type": "json"}
        if params:
            all_params.update(params)
        try:
            response = await self._client().get(url, params=all_params)
        except (httpx.ConnectTimeout, httpx.ReadTimeout, httpx.ConnectError):
            raise IbestatError(
                "IBESTAT service is unavailable. Please try again later."
            )
        if response.status_code == 404:
            raise IbestatError(f"Dataset not found: {url}")
        response.raise_for_status()
        return response.json()

    async def search_datasets(
        self, query: str, limit: int = 10
    ) -> dict[str, Any]:
        return await self._get(
            f"{self._base_url}/datasets",
            params={
                "query": f"name ILIKE '{query}'",
                "limit": str(limit),
            },
        )

    async def get_dataset_metadata(
        self, dataset_id: str
    ) -> dict[str, Any]:
        return await self._get(
            f"{self._base_url}/datasets/IBESTAT/{dataset_id}/~latest",
        )

    async def get_dataset_data(
        self,
        dataset_id: str,
        filters: dict[str, str | list[str]] | None = None,
    ) -> dict[str, Any]:
        params: dict[str, str] = {}
        if filters:
            dim_parts: list[str] = []
            for dim_id, values in filters.items():
                if isinstance(values, list):
                    dim_parts.append(f"{dim_id}:{"|".join(values)}")
                else:
                    dim_parts.append(f"{dim_id}:{values}")
            params["dim"] = "&dim=".join(dim_parts)
        params["fields"] = "-metadata"
        return await self._get(
            f"{self._base_url}/datasets/IBESTAT/{dataset_id}/~latest",
            params=params,
        )
```

**Note on `dim` parameter encoding:** The IBESTAT API expects multiple `dim=` query params, not a single joined one. Verify against real API behavior. If httpx doesn't support repeated keys via dict, switch to passing `params` as a list of tuples: `[("dim", "TIME_PERIOD:2024"), ("dim", "TERRITORIO:07001")]`. Adapt the test assertions accordingly.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /home/jovyan/projects/ibestat-mcp && python -m pytest tests/test_client.py -v`
Expected: All client tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/ibestat_mcp/client.py tests/test_client.py
git commit -m "feat: add async HTTP client for IBESTAT eDades API"
```

---

## Task 5: MCP Tools

**Purpose:** Wire the client and parser together into MCP tool functions. Each tool handles input validation, calls the client, parses the response, and returns structured output.

**Files:**
- Create: `src/ibestat_mcp/tools.py`
- Create: `tests/test_tools.py`

- [ ] **Step 1: Write failing tests for search_datasets tool**

```python
# tests/test_tools.py
import json
from unittest.mock import AsyncMock, patch
import pytest
from ibestat_mcp.tools import search_datasets, get_dataset_info, get_data


@pytest.fixture
def mock_search_response():
    """Minimal search response matching API structure.
    Adapt field names after verifying Task 1 fixtures."""
    return {
        "total": 2,
        "limit": 10,
        "offset": 0,
        "dataset": [
            {
                "id": "000001A_000001",
                "name": {"text": [{"lang": "ca", "value": "Poblacio municipal empadronada"}]},
                "description": {"text": [{"lang": "ca", "value": "Per anys"}]},
                "visualizerHtmlLink": "https://ibestat.es/edatos/visualizer/000001A_000001",
            },
            {
                "id": "000001A_000001",
                "name": {"text": [{"lang": "ca", "value": "Poblacio municipal empadronada v2"}]},
                "description": {"text": [{"lang": "ca", "value": "Per anys v2"}]},
                "visualizerHtmlLink": "https://ibestat.es/edatos/visualizer/000001A_000001",
            },
        ],
    }


class TestSearchDatasets:
    @pytest.mark.asyncio
    async def test_returns_dataset_summaries(self, mock_search_response):
        mock_client = AsyncMock()
        mock_client.search_datasets.return_value = mock_search_response
        result = await search_datasets(mock_client, "poblaci", limit=10)
        assert len(result) >= 1
        assert result[0].id == "000001A_000001"
        assert "Poblacio" in result[0].name

    @pytest.mark.asyncio
    async def test_deduplicates_by_id(self, mock_search_response):
        mock_client = AsyncMock()
        mock_client.search_datasets.return_value = mock_search_response
        result = await search_datasets(mock_client, "poblaci")
        ids = [ds.id for ds in result]
        assert len(ids) == len(set(ids))

    @pytest.mark.asyncio
    async def test_returns_empty_list_on_no_results(self):
        mock_client = AsyncMock()
        mock_client.search_datasets.return_value = {"total": 0, "dataset": []}
        result = await search_datasets(mock_client, "xyznonexistent")
        assert result == []
```

- [ ] **Step 2: Write failing tests for get_dataset_info tool**

```python
@pytest.fixture
def mock_metadata_response():
    """Minimal metadata response. Adapt after Task 1."""
    return {
        "name": {"text": [{"lang": "ca", "value": "Poblacio municipal"}]},
        "metadata": {
            "dimensions": {
                "dimension": [
                    {
                        "dimensionId": "TERRITORIO",
                        "type": "GEOGRAPHIC_DIMENSION",
                        "representations": {
                            "representation": [
                                {"code": "07001", "index": 0, "title": {"text": [{"lang": "ca", "value": "Alaro"}]}},
                            ]
                        },
                    },
                ]
            }
        },
    }


class TestGetDatasetInfo:
    @pytest.mark.asyncio
    async def test_returns_dataset_info(self, mock_metadata_response):
        mock_client = AsyncMock()
        mock_client.get_dataset_metadata.return_value = mock_metadata_response
        result = await get_dataset_info(mock_client, "000001A_000001")
        assert "Poblacio" in result.name
        assert len(result.dimensions) == 1
        assert result.dimensions[0].id == "TERRITORIO"
```

- [ ] **Step 3: Write failing tests for get_data tool**

```python
@pytest.fixture
def mock_data_response():
    """Minimal data response. Adapt after Task 1."""
    return {
        "data": {
            "dimensions": {
                "dimension": [
                    {
                        "dimensionId": "TERRITORIO",
                        "representations": {
                            "representation": [
                                {"code": "07001", "index": 0, "title": {"text": [{"lang": "ca", "value": "Alaro"}]}},
                            ]
                        },
                    },
                    {
                        "dimensionId": "MEDIDAS",
                        "representations": {
                            "representation": [
                                {"code": "POBLACION_PADRON", "index": 0, "title": {"text": [{"lang": "ca", "value": "Poblacio padro"}]}},
                            ]
                        },
                    },
                ]
            },
            "observations": "2035",
        },
    }


class TestGetData:
    @pytest.mark.asyncio
    async def test_returns_flat_rows(self, mock_data_response):
        mock_client = AsyncMock()
        mock_client.get_dataset_data.return_value = mock_data_response
        result = await get_data(mock_client, "000001A_000001")
        assert len(result) >= 1
        assert isinstance(result[0], dict)

    @pytest.mark.asyncio
    async def test_passes_filters_to_client(self, mock_data_response):
        mock_client = AsyncMock()
        mock_client.get_dataset_data.return_value = mock_data_response
        filters = {"TIME_PERIOD": "2024"}
        await get_data(mock_client, "000001A_000001", filters=filters)
        mock_client.get_dataset_data.assert_called_once_with(
            "000001A_000001", filters=filters
        )
```

- [ ] **Step 4: Run tests to verify they fail**

Run: `cd /home/jovyan/projects/ibestat-mcp && python -m pytest tests/test_tools.py -v`
Expected: FAIL with ImportError

- [ ] **Step 5: Implement tools**

```python
# src/ibestat_mcp/tools.py
from __future__ import annotations

from typing import Any

from ibestat_mcp.client import IbestatClient
from ibestat_mcp.models import DatasetInfo, DatasetSummary
from ibestat_mcp.parser import (
    extract_localized_text,
    parse_dimensions,
    parse_observations,
    strip_accents,
)


async def search_datasets(
    client: IbestatClient, query: str, limit: int = 10
) -> list[DatasetSummary]:
    response = await client.search_datasets(query, limit=limit)
    datasets = response.get("dataset", [])
    seen_ids: set[str] = set()
    results: list[DatasetSummary] = []
    for ds in datasets:
        ds_id = ds.get("id", "")
        if ds_id in seen_ids:
            continue
        seen_ids.add(ds_id)
        results.append(
            DatasetSummary(
                id=ds_id,
                name=strip_accents(extract_localized_text(ds.get("name"))),
                description=strip_accents(extract_localized_text(ds.get("description"))) or None,
                link=ds.get("visualizerHtmlLink", ""),
            )
        )
    return results


async def get_dataset_info(
    client: IbestatClient, dataset_id: str
) -> DatasetInfo:
    response = await client.get_dataset_metadata(dataset_id)
    name = strip_accents(extract_localized_text(response.get("name")))
    dimensions = parse_dimensions(response)
    return DatasetInfo(name=name, dimensions=dimensions)


async def get_data(
    client: IbestatClient,
    dataset_id: str,
    filters: dict[str, str | list[str]] | None = None,
) -> list[dict[str, Any]]:
    response = await client.get_dataset_data(dataset_id, filters=filters)
    return parse_observations(response)
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `cd /home/jovyan/projects/ibestat-mcp && python -m pytest tests/test_tools.py -v`
Expected: All tool tests PASS

- [ ] **Step 7: Commit**

```bash
git add src/ibestat_mcp/tools.py tests/test_tools.py
git commit -m "feat: add MCP tool functions wiring client, parser, and models"
```

---

## Task 6: MCP Server

**Purpose:** Set up the MCP server that registers the three tools and runs via stdio transport.

**Files:**
- Create: `src/ibestat_mcp/server.py`
- Create: `tests/test_server.py`

- [ ] **Step 1: Write failing test for server setup**

```python
# tests/test_server.py
import pytest
from ibestat_mcp.server import create_server


class TestServerSetup:
    def test_server_has_three_tools(self):
        server = create_server()
        # The mcp SDK exposes registered tools; check they exist
        # Adapt this based on mcp SDK's actual API for listing tools
        assert server is not None

    def test_server_tool_names(self):
        server = create_server()
        # Verify the three expected tools are registered
        # Adapt assertion to mcp SDK's tool inspection API
        assert server is not None
```

**Note:** The exact way to inspect registered tools depends on the `mcp` SDK version. The SWE should check `mcp` SDK docs and adapt the assertions to use the actual API (e.g., `server.list_tools()` or similar).

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/jovyan/projects/ibestat-mcp && python -m pytest tests/test_server.py -v`
Expected: FAIL with ImportError

- [ ] **Step 3: Implement server**

```python
# src/ibestat_mcp/server.py
from __future__ import annotations

import asyncio
import json
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from ibestat_mcp.client import IbestatClient, IbestatError
from ibestat_mcp.tools import get_data, get_dataset_info, search_datasets


def create_server() -> Server:
    server = Server("ibestat-mcp")

    @server.list_tools()
    async def list_tools() -> list[Tool]:
        return [
            Tool(
                name="search_datasets",
                description=(
                    "Search IBESTAT datasets by keyword. "
                    "Returns matching datasets with IDs, names (in Catalan), and links."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Search term (e.g., 'poblacio', 'turisme', 'atur')",
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Max results to return (default: 10)",
                            "default": 10,
                        },
                    },
                    "required": ["query"],
                },
            ),
            Tool(
                name="get_dataset_info",
                description=(
                    "Get the structure of an IBESTAT dataset: "
                    "its dimensions and available values for filtering."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "dataset_id": {
                            "type": "string",
                            "description": "Dataset identifier (e.g., '000001A_000001')",
                        },
                    },
                    "required": ["dataset_id"],
                },
            ),
            Tool(
                name="get_data",
                description=(
                    "Fetch data from an IBESTAT dataset, optionally filtered by dimensions. "
                    "Returns flat rows with Catalan column names."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "dataset_id": {
                            "type": "string",
                            "description": "Dataset identifier",
                        },
                        "filters": {
                            "type": "object",
                            "description": (
                                "Dimension filters. Keys are dimension IDs, "
                                "values are strings or arrays of strings. "
                                "Example: {\"TIME_PERIOD\": \"2024\", \"TERRITORIO\": \"07001\"}"
                            ),
                            "additionalProperties": {
                                "oneOf": [
                                    {"type": "string"},
                                    {"type": "array", "items": {"type": "string"}},
                                ]
                            },
                        },
                    },
                    "required": ["dataset_id"],
                },
            ),
        ]

    @server.call_tool()
    async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
        try:
            async with IbestatClient() as client:
                if name == "search_datasets":
                    results = await search_datasets(
                        client,
                        arguments["query"],
                        limit=arguments.get("limit", 10),
                    )
                    output = [r.model_dump() for r in results]
                    return [TextContent(type="text", text=json.dumps(output, ensure_ascii=False, indent=2))]

                elif name == "get_dataset_info":
                    info = await get_dataset_info(client, arguments["dataset_id"])
                    return [TextContent(type="text", text=json.dumps(info.model_dump(), ensure_ascii=False, indent=2))]

                elif name == "get_data":
                    rows = await get_data(
                        client,
                        arguments["dataset_id"],
                        filters=arguments.get("filters"),
                    )
                    return [TextContent(type="text", text=json.dumps(rows, ensure_ascii=False, indent=2))]

                else:
                    return [TextContent(type="text", text=f"Unknown tool: {name}")]

        except IbestatError as e:
            return [TextContent(type="text", text=f"Error: {e}")]

    return server


def main() -> None:
    server = create_server()
    asyncio.run(_run(server))


async def _run(server: Server) -> None:
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /home/jovyan/projects/ibestat-mcp && python -m pytest tests/test_server.py -v`
Expected: PASS

- [ ] **Step 5: Run full test suite**

Run: `cd /home/jovyan/projects/ibestat-mcp && python -m pytest tests/ -v`
Expected: All tests PASS

- [ ] **Step 6: Commit**

```bash
git add src/ibestat_mcp/server.py tests/test_server.py
git commit -m "feat: add MCP server with tool registration and stdio transport"
```

---

## Task 7: End-to-End Smoke Test

**Purpose:** Verify the full pipeline works against the real IBESTAT API. This is a manual verification step, not an automated test (since it depends on external API availability).

**Files:**
- Create: `tests/test_e2e.py`

- [ ] **Step 1: Write e2e test (marked for manual run)**

```python
# tests/test_e2e.py
import pytest
from ibestat_mcp.client import IbestatClient
from ibestat_mcp.tools import search_datasets, get_dataset_info, get_data


@pytest.mark.e2e
class TestEndToEnd:
    @pytest.mark.asyncio
    async def test_full_workflow(self):
        async with IbestatClient() as client:
            # Step 1: Search
            results = await search_datasets(client, "poblaci", limit=3)
            assert len(results) > 0
            dataset_id = results[0].id

            # Step 2: Get info
            info = await get_dataset_info(client, dataset_id)
            assert len(info.dimensions) > 0

            # Step 3: Get data (small slice)
            dim_ids = [d.id for d in info.dimensions]
            filters = {}
            for dim in info.dimensions:
                if len(dim.values) > 2:
                    filters[dim.id] = dim.values[0].code
            rows = await get_data(client, dataset_id, filters=filters)
            assert len(rows) > 0
            # Verify rows have the expected column structure
            first_row = rows[0]
            assert len(first_row) > 1
```

- [ ] **Step 2: Add e2e marker to pytest config**

Add to `pyproject.toml`:

```toml
[tool.pytest.ini_options]
markers = [
    "e2e: end-to-end tests hitting real IBESTAT API (deselect with '-m not e2e')",
]
```

- [ ] **Step 3: Run e2e test**

Run: `cd /home/jovyan/projects/ibestat-mcp && python -m pytest tests/test_e2e.py -v -m e2e`
Expected: PASS (depends on API availability)

If the test fails, debug by examining the actual API response shapes and adjusting parser/client field names to match reality.

- [ ] **Step 4: Run full test suite excluding e2e**

Run: `cd /home/jovyan/projects/ibestat-mcp && python -m pytest tests/ -v -m "not e2e"`
Expected: All unit tests PASS

- [ ] **Step 5: Commit**

```bash
git add tests/test_e2e.py pyproject.toml
git commit -m "feat: add end-to-end smoke test for full search-info-data workflow"
```
