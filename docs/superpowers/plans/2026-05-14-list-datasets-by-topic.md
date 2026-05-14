# `list_datasets_by_topic` Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `list_datasets_by_topic` MCP tool that deterministically lists all datasets under a given IBESTAT category, eliminating the keyword-guessing gap between `browse_topics` and `search_datasets`.

**Architecture:** The tool uses the IBESTAT Operations API (`/apis/operations/v1.0`) as an intermediary: category → operations → datasets. Results are cached per `(category_id, lang)`. The `Category` model gains a `nested_id` field (needed for URN construction) populated during topic parsing. Parent categories resolve all leaf children before querying.

**Tech Stack:** Python 3.10+, httpx (async), pydantic v2, FastMCP, pytest + pytest-asyncio + respx

**Team workflow:** PM coordinates. MCP Engineer implements tasks on a feature branch. Senior Reviewer reviews the PR on GitHub. Data Analyst validates data decisions. User merges.

---

### Task 1: Update `Category` model and parser for `nested_id`

**Files:**
- Modify: `src/ibestat_mcp/models.py:46-52`
- Modify: `src/ibestat_mcp/structural_parser.py:27-52`
- Modify: `tests/fixtures/categories_response.json`
- Modify: `tests/test_structural_parser.py`

The IBESTAT structural API returns a `nestedId` field on each category (e.g., `"010.010_010"` for a child of `"010"`). This dot-notation ID is required to construct the SDMX URN for the operations API query. The current `Category` model and parser don't capture it.

- [ ] **Step 1: Update the categories fixture to include `nestedId`**

Add `nestedId` to each entry in `tests/fixtures/categories_response.json`:

```json
{
  "kind": "structuralResources#categories",
  "total": 4,
  "category": [
    {
      "id": "010",
      "nestedId": "010",
      "urn": "urn:sdmx:org.sdmx.infomodel.categoryscheme.Category=IBESTAT:CLASIF_TEMAS_CANALES(01.000).010",
      "name": {
        "text": [
          {"value": "Demografia", "lang": "ca"},
          {"value": "Demografía", "lang": "es"},
          {"value": "Demography", "lang": "en"}
        ]
      }
    },
    {
      "id": "010_010",
      "nestedId": "010.010_010",
      "urn": "urn:sdmx:org.sdmx.infomodel.categoryscheme.Category=IBESTAT:CLASIF_TEMAS_CANALES(01.000).010.010_010",
      "name": {
        "text": [
          {"value": "Població", "lang": "ca"},
          {"value": "Población", "lang": "es"},
          {"value": "Population", "lang": "en"}
        ]
      },
      "parent": "urn:sdmx:org.sdmx.infomodel.categoryscheme.Category=IBESTAT:CLASIF_TEMAS_CANALES(01.000).010"
    },
    {
      "id": "020",
      "nestedId": "020",
      "urn": "urn:sdmx:org.sdmx.infomodel.categoryscheme.Category=IBESTAT:CLASIF_TEMAS_CANALES(01.000).020",
      "name": {
        "text": [
          {"value": "Economia", "lang": "ca"},
          {"value": "Economía", "lang": "es"},
          {"value": "Economy", "lang": "en"}
        ]
      }
    },
    {
      "id": "020_010",
      "nestedId": "020.020_010",
      "urn": "urn:sdmx:org.sdmx.infomodel.categoryscheme.Category=IBESTAT:CLASIF_TEMAS_CANALES(01.000).020.020_010",
      "name": {
        "text": [
          {"value": "Mercat de treball", "lang": "ca"},
          {"value": "Mercado de trabajo", "lang": "es"},
          {"value": "Labour market", "lang": "en"}
        ]
      },
      "parent": "urn:sdmx:org.sdmx.infomodel.categoryscheme.Category=IBESTAT:CLASIF_TEMAS_CANALES(01.000).020"
    }
  ]
}
```

- [ ] **Step 2: Write the failing test for `nested_id` extraction**

Add to `tests/test_structural_parser.py` class `TestParseCategories`:

```python
def test_extracts_nested_id(self, categories_response: dict[str, Any]) -> None:
    result = parse_categories(categories_response, lang="ca")
    assert result[0].nested_id == "010"
    child = next(c for c in result if c.id == "010_010")
    assert child.nested_id == "010.010_010"
```

- [ ] **Step 3: Run test to verify it fails**

Run: `pytest tests/test_structural_parser.py::TestParseCategories::test_extracts_nested_id -v`
Expected: FAIL — `Category` has no `nested_id` attribute

- [ ] **Step 4: Add `nested_id` to `Category` model**

In `src/ibestat_mcp/models.py`, add `nested_id` to the `Category` class. Exclude it from serialization so it doesn't clutter tool output:

```python
class Category(BaseModel):
    id: str = Field(description="Category identifier (e.g., '010')")
    name: str = Field(description="Category name in the requested language")
    parent_id: str | None = Field(
        default=None, description="Parent category ID, None for top-level"
    )
    nested_id: str | None = Field(
        default=None,
        exclude=True,
        description="SDMX nested ID for URN construction (e.g., '010.010_010')",
    )
```

- [ ] **Step 5: Update `parse_categories` to extract `nestedId`**

In `src/ibestat_mcp/structural_parser.py`, update `parse_categories` to populate `nested_id`:

```python
def parse_categories(response: dict[str, Any], lang: str = "ca") -> list[Category]:
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
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `pytest tests/test_structural_parser.py -v`
Expected: All pass including the new `test_extracts_nested_id`

- [ ] **Step 7: Commit**

```bash
git add src/ibestat_mcp/models.py src/ibestat_mcp/structural_parser.py tests/fixtures/categories_response.json tests/test_structural_parser.py
git commit -m "feat: extract nested_id from category entries for URN construction"
```

---

### Task 2: Add Operations API client methods

**Files:**
- Modify: `src/ibestat_mcp/client.py`
- Create: `tests/fixtures/operations_response.json`
- Create: `tests/fixtures/datasets_by_operation_response.json`
- Modify: `tests/conftest.py`
- Create: `tests/test_client.py`

Two new client methods that query the Operations API and the statistical-resources datasets endpoint with operation filters.

- [ ] **Step 1: Create the operations API response fixture**

Create `tests/fixtures/operations_response.json`:

```json
{
  "kind": "operations",
  "total": 2,
  "offset": 0,
  "limit": 25,
  "operation": [
    {
      "id": "000001A",
      "kind": "statisticalOperations#operation",
      "name": {
        "text": [
          {"value": "Estadistica de poblacio", "lang": "ca"},
          {"value": "Estadistica de poblacion", "lang": "es"}
        ]
      },
      "urn": "urn:siemac:org.siemac.metamac.infomodel.statisticaloperations.Operation=000001A",
      "selfLink": {
        "kind": "statisticalOperations#operation",
        "href": "https://ibestat.es/edatos/apis/operations/v1.0/operations/000001A"
      }
    },
    {
      "id": "000002B",
      "kind": "statisticalOperations#operation",
      "name": {
        "text": [
          {"value": "Cens de poblacio", "lang": "ca"},
          {"value": "Censo de poblacion", "lang": "es"}
        ]
      },
      "urn": "urn:siemac:org.siemac.metamac.infomodel.statisticaloperations.Operation=000002B",
      "selfLink": {
        "kind": "statisticalOperations#operation",
        "href": "https://ibestat.es/edatos/apis/operations/v1.0/operations/000002B"
      }
    }
  ]
}
```

- [ ] **Step 2: Create the datasets-by-operation response fixture**

Create `tests/fixtures/datasets_by_operation_response.json`:

```json
{
  "kind": "statisticalResources#datasets",
  "total": 2,
  "offset": 0,
  "limit": 25,
  "dataset": [
    {
      "id": "000001A_000001",
      "kind": "statisticalResources#dataset",
      "name": {
        "text": [
          {"value": "Poblacio municipal empadronada", "lang": "ca"},
          {"value": "Poblacion municipal empadronada", "lang": "es"}
        ]
      },
      "urn": "urn:siemac:org.siemac.metamac.infomodel.statisticalresources.Dataset=IBESTAT:000001A_000001(1.0)",
      "selfLink": {
        "kind": "statisticalResources#dataset",
        "href": "https://ibestat.es/edatos/apis/statistical-resources/v1.0/datasets/IBESTAT/000001A_000001/1.0"
      },
      "visualizerHtmlLink": "https://ibestat.es/edatos/apps/statistical-visualizer/visualizer/data.html?resourceType=dataset&agencyId=IBESTAT&resourceId=000001A_000001&version=1.0"
    },
    {
      "id": "000001A_000002",
      "kind": "statisticalResources#dataset",
      "name": {
        "text": [
          {"value": "Poblacio per edat i sexe", "lang": "ca"},
          {"value": "Poblacion por edad y sexo", "lang": "es"}
        ]
      },
      "urn": "urn:siemac:org.siemac.metamac.infomodel.statisticalresources.Dataset=IBESTAT:000001A_000002(1.0)",
      "selfLink": {
        "kind": "statisticalResources#dataset",
        "href": "https://ibestat.es/edatos/apis/statistical-resources/v1.0/datasets/IBESTAT/000001A_000002/1.0"
      },
      "visualizerHtmlLink": "https://ibestat.es/edatos/apps/statistical-visualizer/visualizer/data.html?resourceType=dataset&agencyId=IBESTAT&resourceId=000001A_000002&version=1.0"
    }
  ]
}
```

- [ ] **Step 3: Add fixture loaders to conftest.py**

Add to `tests/conftest.py`:

```python
@pytest.fixture()
def operations_response() -> dict[str, Any]:
    """Operations for a category from the IBESTAT operations API.

    Endpoint: GET /operations?query=SUBJECT_AREA_URN EQ "..."&_type=json

    Contains 2 statistical operations.
    """
    return _load_fixture("operations_response.json")


@pytest.fixture()
def datasets_by_operation_response() -> dict[str, Any]:
    """Datasets for an operation from the IBESTAT statistical-resources API.

    Endpoint: GET /datasets?query=STATISTICAL_OPERATION_URN EQ "..."&_type=json

    Contains 2 datasets belonging to one operation.
    """
    return _load_fixture("datasets_by_operation_response.json")
```

- [ ] **Step 4: Write failing tests for the new client methods**

Create `tests/test_client.py`:

```python
"""Tests for ibestat_mcp.client module."""

from __future__ import annotations

import pytest
import respx
from httpx import Response

from ibestat_mcp.client import (
    IbestatClient,
    IbestatError,
    OPERATIONS_BASE_URL,
)


@pytest.mark.asyncio
class TestGetOperationsBySubject:
    @respx.mock
    async def test_queries_operations_api(self, operations_response: dict) -> None:
        route = respx.get(f"{OPERATIONS_BASE_URL}/operations").respond(
            json=operations_response
        )

        async with IbestatClient() as client:
            result = await client.get_operations_by_subject("010.010_010")

        assert route.called
        request = route.calls[0].request
        assert "SUBJECT_AREA_URN" in str(request.url)
        assert "010.010_010" in str(request.url)
        assert len(result["operation"]) == 2

    @respx.mock
    async def test_pagination_params(self, operations_response: dict) -> None:
        route = respx.get(f"{OPERATIONS_BASE_URL}/operations").respond(
            json=operations_response
        )

        async with IbestatClient() as client:
            await client.get_operations_by_subject("010.010_010", limit=5, offset=10)

        request = route.calls[0].request
        assert "limit=5" in str(request.url)
        assert "offset=10" in str(request.url)


@pytest.mark.asyncio
class TestGetDatasetsByOperation:
    @respx.mock
    async def test_queries_datasets_with_operation_urn(
        self, datasets_by_operation_response: dict
    ) -> None:
        from ibestat_mcp.client import BASE_URL

        route = respx.get(f"{BASE_URL}/datasets").respond(
            json=datasets_by_operation_response
        )

        async with IbestatClient() as client:
            result = await client.get_datasets_by_operation("000001A")

        assert route.called
        request = route.calls[0].request
        assert "STATISTICAL_OPERATION_URN" in str(request.url)
        assert "000001A" in str(request.url)
        assert len(result["dataset"]) == 2

    @respx.mock
    async def test_limit_param(self, datasets_by_operation_response: dict) -> None:
        from ibestat_mcp.client import BASE_URL

        route = respx.get(f"{BASE_URL}/datasets").respond(
            json=datasets_by_operation_response
        )

        async with IbestatClient() as client:
            await client.get_datasets_by_operation("000001A", limit=50)

        request = route.calls[0].request
        assert "limit=50" in str(request.url)
```

- [ ] **Step 5: Run tests to verify they fail**

Run: `pytest tests/test_client.py -v`
Expected: FAIL — `OPERATIONS_BASE_URL` not defined, methods don't exist

- [ ] **Step 6: Implement the client methods**

In `src/ibestat_mcp/client.py`, add the constant and update `__init__` and add two methods:

```python
OPERATIONS_BASE_URL = "https://ibestat.es/edatos/apis/operations/v1.0"
```

Update `__init__`:

```python
def __init__(
    self,
    base_url: str = BASE_URL,
    structural_base_url: str = STRUCTURAL_BASE_URL,
    operations_base_url: str = OPERATIONS_BASE_URL,
) -> None:
    self._base_url = base_url
    self._structural_base_url = structural_base_url
    self._operations_base_url = operations_base_url
    self._http: httpx.AsyncClient | None = None
```

Add methods after `get_data_structure`:

```python
# ------------------------------------------------------------------
# Operations API
# ------------------------------------------------------------------

async def get_operations_by_subject(
    self, nested_id: str, limit: int = 1000, offset: int = 0
) -> dict[str, Any]:
    """Fetch statistical operations for a category.

    Parameters
    ----------
    nested_id:
        Category nested ID in dot notation (e.g. ``"010.010_010"``).
    limit:
        Maximum number of results (default 1000).
    offset:
        Pagination offset (default 0).

    Returns
    -------
    dict[str, Any]
        Raw API response containing ``operation`` list.
    """
    urn = (
        "urn:sdmx:org.sdmx.infomodel.categoryscheme.Category="
        f"IBESTAT:TEMAS_BALEARS(03.000).{nested_id}"
    )
    return await self._get(
        f"{self._operations_base_url}/operations",
        params=[
            ("query", f'SUBJECT_AREA_URN EQ "{urn}"'),
            ("limit", str(limit)),
            ("offset", str(offset)),
        ],
    )

async def get_datasets_by_operation(
    self, operation_id: str, limit: int = 1000
) -> dict[str, Any]:
    """Fetch datasets for a statistical operation.

    Parameters
    ----------
    operation_id:
        Operation identifier (e.g. ``"000001A"``).
    limit:
        Maximum number of results (default 1000).

    Returns
    -------
    dict[str, Any]
        Raw API response containing ``dataset`` list.
    """
    urn = (
        "urn:siemac:org.siemac.metamac.infomodel."
        f"statisticaloperations.Operation={operation_id}"
    )
    return await self._get(
        f"{self._base_url}/datasets",
        params=[
            ("query", f'STATISTICAL_OPERATION_URN EQ "{urn}"'),
            ("limit", str(limit)),
        ],
    )
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `pytest tests/test_client.py -v`
Expected: All 4 pass

- [ ] **Step 8: Commit**

```bash
git add src/ibestat_mcp/client.py tests/test_client.py tests/fixtures/operations_response.json tests/fixtures/datasets_by_operation_response.json tests/conftest.py
git commit -m "feat: add Operations API client methods for category-to-dataset lookup"
```

---

### Task 3: Add `TopicDatasets` model and cache support

**Files:**
- Modify: `src/ibestat_mcp/models.py`
- Modify: `src/ibestat_mcp/cache.py`
- Modify: `tests/test_cache.py`

- [ ] **Step 1: Write failing cache tests**

Add to `tests/test_cache.py`:

```python
from ibestat_mcp.models import TopicDatasets, DatasetSummary


class TestTopicDatasetsCache:
    def test_initially_none(self) -> None:
        cache = SemanticCache()
        assert cache.get_topic_datasets("010", "ca") is None

    def test_store_and_retrieve(self) -> None:
        cache = SemanticCache()
        result = TopicDatasets(
            category_id="010_010",
            category_name="Poblacio",
            datasets=[DatasetSummary(id="DS1", name="Test", description=None, link="")],
            total=1,
            note="Cached.",
        )
        cache.set_topic_datasets("010_010", "ca", result)
        assert cache.get_topic_datasets("010_010", "ca").total == 1

    def test_keyed_by_language(self) -> None:
        cache = SemanticCache()
        result_ca = TopicDatasets(
            category_id="010_010", category_name="Poblacio",
            datasets=[], total=0, note="CA",
        )
        result_es = TopicDatasets(
            category_id="010_010", category_name="Poblacion",
            datasets=[], total=0, note="ES",
        )
        cache.set_topic_datasets("010_010", "ca", result_ca)
        cache.set_topic_datasets("010_010", "es", result_es)
        assert cache.get_topic_datasets("010_010", "ca").note == "CA"
        assert cache.get_topic_datasets("010_010", "es").note == "ES"
        assert cache.get_topic_datasets("010_010", "en") is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_cache.py::TestTopicDatasetsCache -v`
Expected: FAIL — `TopicDatasets` not defined

- [ ] **Step 3: Add `TopicDatasets` model**

Add to `src/ibestat_mcp/models.py` after `CodelistResult`:

```python
class TopicDatasets(BaseModel):
    category_id: str = Field(description="The category ID that was queried")
    category_name: str = Field(description="Category name in the requested language")
    datasets: list[DatasetSummary] = Field(
        description="All datasets under this category"
    )
    total: int = Field(description="Total number of datasets found")
    note: str = Field(
        description="Caching and performance note for the user"
    )
```

- [ ] **Step 4: Add cache methods**

In `src/ibestat_mcp/cache.py`, import `TopicDatasets` and add:

```python
from ibestat_mcp.models import CodelistResult, TopicDatasets, TopicTree
```

Add to `__init__`:

```python
self._topic_datasets: dict[tuple[str, str], TopicDatasets] = {}
```

Add methods:

```python
def get_topic_datasets(self, category_id: str, lang: str) -> TopicDatasets | None:
    return self._topic_datasets.get((category_id, lang))

def set_topic_datasets(self, category_id: str, lang: str, result: TopicDatasets) -> None:
    self._topic_datasets[(category_id, lang)] = result
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_cache.py -v`
Expected: All pass (old + new)

- [ ] **Step 6: Commit**

```bash
git add src/ibestat_mcp/models.py src/ibestat_mcp/cache.py tests/test_cache.py
git commit -m "feat: add TopicDatasets model and cache support"
```

---

### Task 4: Implement `list_datasets_by_topic` tool function

**Files:**
- Modify: `src/ibestat_mcp/tools.py`
- Modify: `tests/test_tools.py`

This is the core logic: resolve category → query operations → query datasets → deduplicate → cache.

- [ ] **Step 1: Write failing tests**

Add to `tests/test_tools.py`. First, add the import at the top:

```python
from ibestat_mcp.tools import list_datasets_by_topic
from ibestat_mcp.models import TopicDatasets
```

Then add the test class:

```python
# ===========================================================================
# TestListDatasetsByTopic
# ===========================================================================


class TestListDatasetsByTopic:
    def _make_topic_tree(self) -> TopicTree:
        from ibestat_mcp.models import Category
        return TopicTree(
            name="TEMAS_BALEARS",
            categories=[
                Category(id="010", name="Demografia", parent_id=None, nested_id="010"),
                Category(id="010_010", name="Poblacio", parent_id="010", nested_id="010.010_010"),
                Category(id="010_020", name="Natalitat", parent_id="010", nested_id="010.010_020"),
                Category(id="020", name="Economia", parent_id=None, nested_id="020"),
                Category(id="020_010", name="Mercat de treball", parent_id="020", nested_id="020.020_010"),
            ],
        )

    def _make_operations_response(self, op_ids: list[str]) -> dict[str, Any]:
        return {
            "operation": [
                {
                    "id": op_id,
                    "urn": f"urn:siemac:org.siemac.metamac.infomodel.statisticaloperations.Operation={op_id}",
                }
                for op_id in op_ids
            ],
            "total": len(op_ids),
        }

    def _make_datasets_response(self, datasets: list[tuple[str, str]]) -> dict[str, Any]:
        return {
            "dataset": [
                {
                    "id": ds_id,
                    "name": {"text": [{"value": name, "lang": "ca"}]},
                    "visualizerHtmlLink": f"https://ibestat.es/viz/{ds_id}",
                }
                for ds_id, name in datasets
            ],
            "total": len(datasets),
        }

    @pytest.mark.asyncio
    async def test_returns_datasets_for_leaf_category(self) -> None:
        client = AsyncMock()
        client.get_categories.return_value = {"category": []}
        client.get_operations_by_subject.return_value = self._make_operations_response(["OP1"])
        client.get_datasets_by_operation.return_value = self._make_datasets_response([
            ("DS1", "Dataset uno"),
            ("DS2", "Dataset dos"),
        ])
        test_cache = SemanticCache()
        test_cache.set_topics("ca", self._make_topic_tree())

        result = await list_datasets_by_topic(client, "010_010", lang="ca", _cache=test_cache)

        assert isinstance(result, TopicDatasets)
        assert result.category_id == "010_010"
        assert result.total == 2
        assert result.datasets[0].id == "DS1"
        assert result.datasets[1].id == "DS2"

    @pytest.mark.asyncio
    async def test_parent_category_queries_all_children(self) -> None:
        client = AsyncMock()
        client.get_categories.return_value = {"category": []}
        client.get_operations_by_subject.return_value = self._make_operations_response(["OP1"])
        client.get_datasets_by_operation.return_value = self._make_datasets_response([
            ("DS1", "Dataset uno"),
        ])
        test_cache = SemanticCache()
        test_cache.set_topics("ca", self._make_topic_tree())

        result = await list_datasets_by_topic(client, "010", lang="ca", _cache=test_cache)

        assert client.get_operations_by_subject.call_count == 2
        call_args = [c.args[0] for c in client.get_operations_by_subject.call_args_list]
        assert "010.010_010" in call_args
        assert "010.010_020" in call_args

    @pytest.mark.asyncio
    async def test_deduplicates_datasets(self) -> None:
        client = AsyncMock()
        client.get_categories.return_value = {"category": []}
        client.get_operations_by_subject.return_value = self._make_operations_response(["OP1", "OP2"])
        client.get_datasets_by_operation.side_effect = [
            self._make_datasets_response([("DS1", "Dataset uno")]),
            self._make_datasets_response([("DS1", "Dataset uno"), ("DS2", "Dataset dos")]),
        ]
        test_cache = SemanticCache()
        test_cache.set_topics("ca", self._make_topic_tree())

        result = await list_datasets_by_topic(client, "010_010", lang="ca", _cache=test_cache)

        assert result.total == 2
        ids = [d.id for d in result.datasets]
        assert ids == ["DS1", "DS2"]

    @pytest.mark.asyncio
    async def test_uses_cache_on_second_call(self) -> None:
        client = AsyncMock()
        client.get_categories.return_value = {"category": []}
        client.get_operations_by_subject.return_value = self._make_operations_response(["OP1"])
        client.get_datasets_by_operation.return_value = self._make_datasets_response([
            ("DS1", "Dataset uno"),
        ])
        test_cache = SemanticCache()
        test_cache.set_topics("ca", self._make_topic_tree())

        await list_datasets_by_topic(client, "010_010", lang="ca", _cache=test_cache)
        await list_datasets_by_topic(client, "010_010", lang="ca", _cache=test_cache)

        assert client.get_operations_by_subject.call_count == 1

    @pytest.mark.asyncio
    async def test_category_not_found_raises(self) -> None:
        from ibestat_mcp.client import IbestatError

        client = AsyncMock()
        client.get_categories.return_value = {"category": []}
        test_cache = SemanticCache()
        test_cache.set_topics("ca", self._make_topic_tree())

        with pytest.raises(IbestatError, match="Category 'INVALID' not found"):
            await list_datasets_by_topic(client, "INVALID", lang="ca", _cache=test_cache)

    @pytest.mark.asyncio
    async def test_empty_operations_returns_empty(self) -> None:
        client = AsyncMock()
        client.get_categories.return_value = {"category": []}
        client.get_operations_by_subject.return_value = self._make_operations_response([])
        test_cache = SemanticCache()
        test_cache.set_topics("ca", self._make_topic_tree())

        result = await list_datasets_by_topic(client, "010_010", lang="ca", _cache=test_cache)

        assert result.total == 0
        assert result.datasets == []

    @pytest.mark.asyncio
    async def test_note_field_present(self) -> None:
        client = AsyncMock()
        client.get_categories.return_value = {"category": []}
        client.get_operations_by_subject.return_value = self._make_operations_response(["OP1"])
        client.get_datasets_by_operation.return_value = self._make_datasets_response([
            ("DS1", "Dataset uno"),
        ])
        test_cache = SemanticCache()
        test_cache.set_topics("ca", self._make_topic_tree())

        result = await list_datasets_by_topic(client, "010_010", lang="ca", _cache=test_cache)

        assert "cache" in result.note.lower() or "first call" in result.note.lower()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_tools.py::TestListDatasetsByTopic -v`
Expected: FAIL — `list_datasets_by_topic` not importable

- [ ] **Step 3: Implement `list_datasets_by_topic`**

Add to `src/ibestat_mcp/tools.py`:

```python
from ibestat_mcp.models import (
    CodelistResult, DataRow, DatasetInfo, DatasetSummary,
    TopicDatasets, TopicTree,
)
```

Then add the function after `get_codelist`:

```python
async def list_datasets_by_topic(
    client: IbestatClient,
    category_id: str,
    lang: str = "ca",
    _cache: SemanticCache | None = None,
) -> TopicDatasets:
    """List all datasets under an IBESTAT thematic category.

    Resolves category → operations → datasets via the IBESTAT Operations
    API.  For parent categories, all leaf children are queried and results
    are merged.  Results are cached per ``(category_id, lang)``.

    Parameters
    ----------
    client:
        An initialised IBESTAT API client.
    category_id:
        Category ID from ``browse_topics`` (e.g. ``"010_010"``).
    lang:
        Language code for labels (``"ca"``, ``"es"``, or ``"en"``).
    _cache:
        Optional cache override for testing.

    Returns
    -------
    TopicDatasets
        Category info, dataset list, and a caching note.

    Raises
    ------
    IbestatError
        If the category is not found in the topic tree.
    """
    from ibestat_mcp.client import IbestatError

    c = _cache or _default_cache
    cached = c.get_topic_datasets(category_id, lang)
    if cached is not None:
        return cached

    topic_tree = c.get_topics(lang)
    if topic_tree is None:
        topic_tree = await browse_topics(client, lang=lang, _cache=c)

    category = next((cat for cat in topic_tree.categories if cat.id == category_id), None)
    if category is None:
        raise IbestatError(
            f"Category '{category_id}' not found. "
            "Use browse_topics to see available categories."
        )

    children = [
        cat for cat in topic_tree.categories if cat.parent_id == category_id
    ]
    is_parent = len(children) > 0

    if is_parent:
        nested_ids = [cat.nested_id for cat in children if cat.nested_id]
        category_name = category.name
    else:
        nested_ids = [category.nested_id] if category.nested_id else []
        category_name = category.name

    seen: set[str] = set()
    datasets: list[DatasetSummary] = []
    total_operations = 0

    for nested_id in nested_ids:
        try:
            ops_response = await client.get_operations_by_subject(nested_id)
        except Exception:
            logger.debug("Operations lookup failed for %s", nested_id, exc_info=True)
            continue

        operations = ops_response.get("operation", [])
        total_operations += len(operations)

        for op in operations:
            op_id = op["id"]
            try:
                ds_response = await client.get_datasets_by_operation(op_id)
            except Exception:
                logger.debug("Datasets lookup failed for operation %s", op_id, exc_info=True)
                continue

            for entry in ds_response.get("dataset", []):
                ds_id = entry["id"]
                if ds_id in seen:
                    continue
                seen.add(ds_id)
                name = extract_localized_text(entry.get("name"), lang)
                description_field = entry.get("description")
                description_raw = (
                    extract_localized_text(description_field, lang)
                    if description_field is not None
                    else None
                )
                description = description_raw or None
                link = entry.get("visualizerHtmlLink", "")
                datasets.append(DatasetSummary(
                    id=ds_id, name=name, description=description, link=link,
                ))

    note = (
        f"First call fetched from the API and cached the result "
        f"({total_operations} operations queried). "
        f"Subsequent calls for category '{category_id}' in '{lang}' are instant."
    )

    result = TopicDatasets(
        category_id=category_id,
        category_name=category_name,
        datasets=datasets,
        total=len(datasets),
        note=note,
    )
    c.set_topic_datasets(category_id, lang, result)
    return result
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_tools.py::TestListDatasetsByTopic -v`
Expected: All 7 pass

- [ ] **Step 5: Run full test suite**

Run: `pytest -m "not e2e" -v`
Expected: All pass

- [ ] **Step 6: Commit**

```bash
git add src/ibestat_mcp/tools.py tests/test_tools.py
git commit -m "feat: implement list_datasets_by_topic tool function"
```

---

### Task 5: Register MCP tool in server

**Files:**
- Modify: `src/ibestat_mcp/server.py`
- Modify: `tests/test_server.py`

- [ ] **Step 1: Write failing tests**

Update `tests/test_server.py`. First update the existing tool count test:

```python
@pytest.mark.asyncio
async def test_server_has_six_tools():
    """The server should register exactly six tools."""
    server = create_server()
    tools = await server.list_tools()
    tool_names = {t.name for t in tools}
    assert tool_names == {
        "search_datasets", "get_dataset_info", "get_data",
        "browse_topics", "get_codelist", "list_datasets_by_topic",
    }
```

Add registration and invocation tests:

```python
@pytest.mark.asyncio
async def test_list_datasets_by_topic_tool_registered():
    """list_datasets_by_topic tool should be registered."""
    server = create_server()
    tool_names = [t.name for t in await server.list_tools()]
    assert "list_datasets_by_topic" in tool_names


@pytest.mark.asyncio
async def test_list_datasets_by_topic_tool_calls_client():
    """list_datasets_by_topic tool should create a client and return JSON text."""
    from ibestat_mcp.models import TopicDatasets, DatasetSummary

    server = create_server()
    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("ibestat_mcp.server.IbestatClient", return_value=mock_client):
        with patch("ibestat_mcp.server.tool_functions") as mock_tools:
            mock_tools.list_datasets_by_topic = AsyncMock(
                return_value=TopicDatasets(
                    category_id="010_010",
                    category_name="Poblacio",
                    datasets=[DatasetSummary(id="DS1", name="Test", description=None, link="")],
                    total=1,
                    note="Cached.",
                )
            )
            result = await server.call_tool(
                "list_datasets_by_topic", {"category_id": "010_010"}
            )

    text = _extract_text(result)
    data = json.loads(text)
    assert data["category_id"] == "010_010"
    assert len(data["datasets"]) == 1


@pytest.mark.asyncio
async def test_list_datasets_by_topic_passes_language():
    """list_datasets_by_topic should forward language to tool_functions."""
    from ibestat_mcp.models import TopicDatasets

    server = create_server()
    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("ibestat_mcp.server.IbestatClient", return_value=mock_client):
        with patch("ibestat_mcp.server.tool_functions") as mock_tools:
            mock_tools.list_datasets_by_topic = AsyncMock(
                return_value=TopicDatasets(
                    category_id="010_010",
                    category_name="Poblacion",
                    datasets=[],
                    total=0,
                    note="Cached.",
                )
            )
            await server.call_tool(
                "list_datasets_by_topic",
                {"category_id": "010_010", "language": "es"},
            )
            call_kwargs = mock_tools.list_datasets_by_topic.call_args
            assert call_kwargs.kwargs.get("lang") == "es"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_server.py::test_list_datasets_by_topic_tool_registered -v`
Expected: FAIL — tool not registered

- [ ] **Step 3: Register the tool in server.py**

Update the module docstring to say "six tools". Add after the `get_codelist` tool registration in `src/ibestat_mcp/server.py`:

```python
@mcp.tool(
    description=(
        "List all datasets under an IBESTAT thematic category. Use this "
        "after browse_topics to see exactly what datasets exist for a "
        "category — no keyword guessing needed. Takes a category_id from "
        "browse_topics and returns all datasets found. "
        "For parent categories (e.g., '010' Demographics), all child "
        "categories are queried automatically. "
        "IMPORTANT: The first call for a category fetches data from "
        "multiple API endpoints and may take a few seconds. The result "
        "is cached, so subsequent calls for the same category are instant. "
        "Supports Catalan (ca), Spanish (es), and English (en) labels."
    ),
)
async def list_datasets_by_topic(
    category_id: Annotated[
        str,
        Field(
            description=(
                "Category ID from browse_topics results "
                "(e.g., '010_010' for Population, '010' for Demographics). "
                "Parent categories automatically include all child categories."
            )
        ),
    ],
    language: Annotated[
        Literal["ca", "es", "en"],
        Field(
            description=(
                "Language for data labels: 'ca' (Catalan), 'es' (Spanish), "
                "or 'en' (English). Default: 'ca'."
            )
        ),
    ] = "ca",
) -> str:
    """List all datasets under an IBESTAT thematic category."""
    try:
        async with IbestatClient() as client:
            result = await tool_functions.list_datasets_by_topic(
                client, category_id, lang=language
            )
        return json.dumps(result.model_dump(), ensure_ascii=False)
    except IbestatError as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_server.py -v`
Expected: All pass

- [ ] **Step 5: Run full test suite**

Run: `pytest -m "not e2e" -v`
Expected: All pass

- [ ] **Step 6: Commit**

```bash
git add src/ibestat_mcp/server.py tests/test_server.py
git commit -m "feat: register list_datasets_by_topic as MCP tool"
```

---

### Task 6: Add E2E test

**Files:**
- Modify: `tests/test_e2e.py`

- [ ] **Step 1: Write the E2E test**

Add to `tests/test_e2e.py`:

```python
from ibestat_mcp.tools import list_datasets_by_topic


@pytest.mark.e2e
class TestListDatasetsByTopicE2E:
    @pytest.mark.asyncio
    async def test_returns_datasets_for_population_category(self) -> None:
        async with IbestatClient() as client:
            result = await list_datasets_by_topic(
                client, "010_010", lang="es", _cache=SemanticCache()
            )
        assert result.total > 0
        assert len(result.datasets) > 0
        assert result.category_id == "010_010"
        assert all(d.id for d in result.datasets)
        assert all(d.name for d in result.datasets)

    @pytest.mark.asyncio
    async def test_parent_category_aggregates_children(self) -> None:
        cache = SemanticCache()
        async with IbestatClient() as client:
            result = await list_datasets_by_topic(
                client, "010", lang="es", _cache=cache
            )
        assert result.total > 0
        assert result.category_name

    @pytest.mark.asyncio
    async def test_caching_works(self) -> None:
        cache = SemanticCache()
        async with IbestatClient() as client:
            result1 = await list_datasets_by_topic(
                client, "010_010", lang="ca", _cache=cache
            )
            result2 = await list_datasets_by_topic(
                client, "010_010", lang="ca", _cache=cache
            )
        assert result1.total == result2.total
        assert result1.datasets == result2.datasets
```

- [ ] **Step 2: Run E2E tests (optional, hits real API)**

Run: `pytest tests/test_e2e.py::TestListDatasetsByTopicE2E -v -m e2e`
Expected: All pass (requires network)

- [ ] **Step 3: Commit**

```bash
git add tests/test_e2e.py
git commit -m "test: add E2E tests for list_datasets_by_topic"
```

---

### Task 7: Update documentation and workflow

**Files:**
- Modify: `CLAUDE.md`
- Modify: `README.md`

- [ ] **Step 1: Update CLAUDE.md workflow**

In `CLAUDE.md`, update the "Recommended tool workflow" section to 6 steps:

```markdown
### Recommended tool workflow

1. **`browse_topics`** -- See all statistical domains IBESTAT covers (cached after first call)
2. **`list_datasets_by_topic`** -- List all datasets under a chosen category. First call fetches from multiple API endpoints and may take a few seconds; result is cached for instant subsequent calls.
3. **`search_datasets`** -- (Alternative) Free-text keyword search when you already know what to look for
4. **`get_dataset_info`** -- Inspect dataset dimensions; each dimension includes a `codelist_id` if a hierarchical codelist exists
5. **`get_codelist`** -- Use the `codelist_id` to explore valid filter values at all hierarchy levels (e.g., region > island > municipality)
6. **`get_data`** -- Query with valid filters discovered in step 5
```

Update the tool inventory table to include the new tool:

```markdown
### Tool inventory

| Tool | Purpose | Cached |
|------|---------|--------|
| `browse_topics` | Thematic topic tree (52 categories) | Yes -- fetched once per session |
| `list_datasets_by_topic` | All datasets under a category | Yes -- per category, first call may take a few seconds |
| `search_datasets` | Keyword search for datasets | No |
| `get_dataset_info` | Dataset dimensions + codelist references | DSD mapping cached per dataset |
| `get_codelist` | Hierarchical codes for a codelist | Yes -- per codelist |
| `get_data` | Fetch observation data with filters | No |
```

- [ ] **Step 2: Update README.md**

Update the tools table:

```markdown
## Tools

| Tool | Description |
|------|-------------|
| `browse_topics` | Browse IBESTAT's thematic catalog (Demographics, Economy, Tourism, Labour...) |
| `list_datasets_by_topic` | List all datasets under a category — no keyword guessing needed |
| `search_datasets` | Search datasets by keyword (e.g., "poblacio", "turisme") |
| `get_dataset_info` | Get dataset dimensions, filter values, and linked codelist IDs |
| `get_codelist` | Explore a codelist's hierarchical codes (e.g., Region > Island > Municipality) |
| `get_data` | Fetch data rows with optional dimension filters |
```

Update the Quick Start workflow to 6 steps:

```markdown
## Quick Start

Once configured, the LLM follows a six-step workflow:

1. **Browse topics** -- `browse_topics` shows IBESTAT's full thematic catalog so the LLM knows what domains exist.
2. **List datasets** -- `list_datasets_by_topic` shows all datasets under a chosen category. First call may take a few seconds (multiple API endpoints are queried and cached); subsequent calls are instant.
3. **Search** -- *(Alternative)* `search_datasets` finds datasets via free-text keyword search when you already know what to look for.
4. **Inspect** -- `get_dataset_info` reveals dimensions, their values, and a `codelist_id` for each dimension that has a hierarchical codelist. `codelist_id` allows to gather context for the dimension using the APIs internal semantic conventions.
5. **Explore codelists** -- `get_codelist` with the `codelist_id` shows the full hierarchy (e.g., Illes Balears > Mallorca > Palma) so the LLM can discover valid filter values at any level.
6. **Query** -- `get_data` fetches rows using the known-valid filter codes.
```

Update server.py module docstring from "five tools" to "six tools".

- [ ] **Step 3: Commit**

```bash
git add CLAUDE.md README.md src/ibestat_mcp/server.py
git commit -m "docs: update workflow to 6 steps with list_datasets_by_topic"
```

---

### Task 8: Final verification and PR

- [ ] **Step 1: Run full unit test suite**

Run: `pytest -m "not e2e" -v`
Expected: All pass, 0 warnings

- [ ] **Step 2: Create PR**

```bash
gh pr create --title "feat: add list_datasets_by_topic tool" --body "$(cat <<'EOF'
## Summary

- Adds `list_datasets_by_topic` MCP tool that deterministically lists all datasets under a given IBESTAT thematic category
- Bridges the discovery gap between `browse_topics` (shows categories) and `search_datasets` (requires keyword guessing)
- Uses the IBESTAT Operations API as intermediary: category → operations → datasets
- Results cached per (category_id, lang) — first call may take a few seconds, subsequent calls are instant
- Parent categories automatically aggregate all child category datasets

## Changes

- **client.py**: Added Operations API base URL and two new methods (`get_operations_by_subject`, `get_datasets_by_operation`)
- **models.py**: Added `nested_id` to `Category` (excluded from serialization), new `TopicDatasets` model
- **structural_parser.py**: Extracts `nestedId` from category entries
- **cache.py**: Added `topic_datasets` cache keyed by `(category_id, lang)`
- **tools.py**: New `list_datasets_by_topic` function with parent-category resolution and deduplication
- **server.py**: Registered as 6th MCP tool with verbose description about caching
- **CLAUDE.md / README.md**: Updated workflow from 5 to 6 steps

## Test plan

- [ ] `pytest -m "not e2e"` — all unit tests pass
- [ ] `pytest tests/test_e2e.py::TestListDatasetsByTopicE2E -m e2e` — E2E tests pass against real API
- [ ] Verify tool appears in `list_tools()` with correct description
- [ ] Verify first call for a category returns datasets and populates cache
- [ ] Verify second call for same category returns from cache (no API calls)
- [ ] Verify parent category aggregates all child category datasets

## Data decisions

Per Data Analyst: The Operations API only filters on leaf-level categories, not parent categories. For parent categories, the tool resolves all leaf children and queries each one, merging and deduplicating results.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```
