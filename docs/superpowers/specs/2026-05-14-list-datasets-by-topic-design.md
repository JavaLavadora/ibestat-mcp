# Design: `list_datasets_by_topic` Tool

**Date**: 2026-05-14
**Status**: Approved
**Problem**: `browse_topics` shows 52 thematic categories but provides no link to actual datasets. The LLM must guess keywords for `search_datasets`, leading to missed datasets and false negatives.

## Solution

A new MCP tool `list_datasets_by_topic` that deterministically lists all datasets under a given category by querying the IBESTAT Operations API as an intermediary.

### API Chain

```
Category (from browse_topics)
  → Operations API: GET /operations?query=SUBJECT_AREA_URN EQ "{category_urn}"
    → Statistical Resources API: GET /datasets?query=STATISTICAL_OPERATION_URN EQ "{operation_urn}"
      → list[DatasetSummary]
```

The Operations API lives at `https://ibestat.es/edatos/apis/operations/v1.0` — a third base URL alongside the existing statistical-resources and structural-resources APIs.

### URN Construction

The operations API requires a full SDMX URN for the category:
```
urn:sdmx:org.sdmx.infomodel.categoryscheme.Category=IBESTAT:TEMAS_BALEARS(03.000).{nested_id}
```

Where `nested_id` uses dot notation (e.g., `010.010_010`). This requires knowing the category's `nestedId` from the structural API — not the same as the `id` field we currently store.

The datasets API requires a SIEMAC URN for the operation:
```
urn:siemac:org.siemac.metamac.infomodel.statisticaloperations.Operation={operation_id}
```

### Filtering Behaviour

The operations API `SUBJECT_AREA_URN` filter only works with **leaf-level categories** (e.g., `010_010` "Poblacion"), not parent categories (e.g., `010` "Demografia"). When given a parent category, the tool must resolve all its leaf children from the topic tree and query each one, then merge results.

## Changes by Module

### 1. `models.py`

- **`Category`**: Add `nested_id: str | None = None` field. The structural API returns a `nestedId` (dot notation like `010.010_010`) needed for URN construction. Excluded from JSON serialization to avoid cluttering tool output.
- **`TopicDatasets`**: New model with fields:
  - `category_id: str` — the category queried
  - `category_name: str` — human-readable name
  - `datasets: list[DatasetSummary]` — all datasets under this category
  - `total: int` — total count
  - `note: str` — caching explanation for the LLM/user

### 2. `client.py`

- **`OPERATIONS_BASE_URL`**: New constant `https://ibestat.es/edatos/apis/operations/v1.0`
- **`__init__`**: Accept `operations_base_url` parameter
- **`get_operations_by_subject(nested_id, limit, offset)`**: Query operations filtered by `SUBJECT_AREA_URN EQ "urn:..."`. Returns raw JSON with `operation` list.
- **`get_datasets_by_operation(operation_id, limit)`**: Query datasets filtered by `STATISTICAL_OPERATION_URN EQ "urn:..."`. Returns raw JSON with `dataset` list.

### 3. `structural_parser.py`

- **`parse_categories`**: Extract `nestedId` from each category entry and populate `Category.nested_id`.

### 4. `cache.py`

- **`SemanticCache`**: Add `_topic_datasets: dict[tuple[str, str], TopicDatasets]` with `get_topic_datasets(category_id, lang)` / `set_topic_datasets(category_id, lang, result)`.

### 5. `tools.py`

- **`list_datasets_by_topic(client, category_id, lang, _cache)`**:
  1. Get topic tree from cache (or fetch via `browse_topics`)
  2. Find the category by `id`, get its `nested_id`
  3. If parent category → collect all leaf children's `nested_id`s
  4. For each nested_id → query operations → for each operation → query datasets
  5. Deduplicate by dataset ID
  6. Build `DatasetSummary` list and cache as `TopicDatasets`
  7. `note` field: `"First call fetches from the API and caches the result (~N operations queried). Subsequent calls for this category are instant."`

### 6. `server.py`

- Register `list_datasets_by_topic` as 6th MCP tool
- Tool description emphasizes: use after `browse_topics`, first call may be slower due to multi-endpoint fetch + caching, subsequent calls instant

### 7. Documentation

- **`CLAUDE.md`**: Update workflow from 5 to 6 steps. `list_datasets_by_topic` is step 2. `search_datasets` becomes an alternative/supplement.
- **`README.md`**: Update Quick Start workflow and tools table.

## Caching Strategy

Cached per `(category_id, lang)` in `SemanticCache`. Consistent with existing patterns for topics and codelists. The `note` field in the response explains caching to the user.

## Error Handling

- Category not found in topic tree → `IbestatError("Category '{id}' not found. Use browse_topics to see available categories.")`
- Operations API returns empty → Return `TopicDatasets` with empty `datasets` list and note explaining no datasets found
- Individual operation/dataset lookups fail → Log warning, skip, return partial results
- Operations API unavailable → `IbestatError` propagated as usual

## Testing

- **Unit tests** (`test_tools.py`): Mock the two-hop chain, test cache hit/miss, test parent-category resolution, test deduplication, test error cases
- **Unit tests** (`test_server.py`): Registration (6 tools), tool invocation, language forwarding
- **Unit tests** (`test_cache.py`): `topic_datasets` get/set with language keying
- **Unit tests** (`test_structural_parser.py`): `nested_id` extraction from category entries
- **E2E test** (`test_e2e.py`): Hit real API for one known leaf category, verify datasets returned
- **Fixtures**: Operations API response, datasets-by-operation response
