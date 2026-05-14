# IBESTAT MCP Server — Design Spec

## Overview

An MCP (Model Context Protocol) server that exposes the IBESTAT (Institut d'Estadistica de les Illes Balears) eDades API to LLMs. Enables natural discovery and exploration of Balearic Islands public statistical data through a simple three-tool interface: search, understand, fetch.

## Goals

- Democratize access to IBESTAT public data via LLMs
- Support a natural workflow: discover datasets → understand their shape → fetch data
- Parse complex API responses (pipe-delimited observations, dimension index maps) into clean flat tables
- Default to Catalan for all user-facing data labels
- Keep code in English, product references in Catalan (eDades, not eDatos)
- Build on the eDades statistical-resources API, but architect for extensibility to other backends (PC-Axis, export API)

## Target Users

- **Non-technical users** asking natural language questions (e.g., "do we have population data by region?")
- **Data analysts/developers** who want efficient programmatic access to IBESTAT data

The tool design serves both: the LLM orchestrates the three-step workflow transparently for casual users, while power users can call tools directly with specific dataset IDs and filters.

## Architecture

### Project Structure

```
ibestat-mcp/
├── pyproject.toml              # Package config, entry point, dependencies
├── src/
│   └── ibestat_mcp/
│       ├── __init__.py
│       ├── server.py           # MCP server setup, tool registration
│       ├── tools.py            # Tool functions (search, info, data, topics, codelist)
│       ├── client.py           # HTTP client for IBESTAT eDades API (statistical + structural)
│       ├── parser.py           # Statistical-resources response parsing
│       ├── structural_parser.py # Structural-resources response parsing
│       ├── models.py           # Pydantic models for API responses
│       ├── cache.py            # SemanticCache for structural metadata
│       └── _i18n.py            # Shared i18n utilities
└── tests/
    └── ...
```

### Module Responsibilities

**`client.py`** — The only module that knows about IBESTAT API URLs and response shapes. Single class `IbestatClient` using `httpx.AsyncClient`. Six methods:

- `search_datasets(query, limit)` — keyword search across datasets
- `get_dataset_metadata(dataset_id)` — full dataset structure with dimensions
- `get_dataset_data(dataset_id, filters)` — observation data with optional dimension filters
- `get_categories()` — thematic category tree from structural-resources API
- `get_codelist_codes(codelist_id, limit, offset)` — codelist codes with hierarchy
- `get_data_structure(dsd_id)` — data structure definition

Base URLs: `statistical-resources/v1.0` and `structural-resources/v1.0`

Extensibility: adding PC-Axis or other backends means creating a new client class with the same interface, not changing tools.

**`parser.py`** — Converts raw API responses into clean tabular data:

1. Reads dimension representations (code to index mappings)
2. Reads dimension labels (code to Catalan name, preferring `lang=ca`)
3. Iterates the pipe-delimited observation string, mapping each value to its dimension combination
4. Strips accents/special characters from column names for safe encoding
5. Returns a list of flat dicts (rows)

**`models.py`** — Pydantic models for structured tool outputs:

- `DatasetSummary` — id, name, description, link
- `DatasetInfo` — name, dimensions (each with name + list of values)
- `DataRow` — a single observation row as a dict

**`tools.py`** — Tool function definitions that wire MCP tool calls to client + parser.

**`structural_parser.py`** — Parses structural-resources API responses: category schemes, codelist codes, DSD dimension-to-codelist mappings.

**`cache.py`** — `SemanticCache` class storing topic tree, DSD codelist maps, and codelist results in memory for the server session.

**`_i18n.py`** — Shared i18n utilities (`extract_localized_text`, `strip_accents`) used by both `parser.py` and `structural_parser.py`.

**`server.py`** — MCP server setup using the `mcp` Python SDK. Registers five tools, runs via stdio transport.

## MCP Tools

### Tool 1: `search_datasets`

Search IBESTAT datasets by keyword.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `query` | string | yes | Search term (e.g., "poblacio", "turisme") |
| `limit` | int | no | Max results (default: 10) |

**Returns:** List of matching datasets, each with:
- `id` — dataset identifier (e.g., "000001A_000001")
- `name` — dataset name in Catalan
- `description` — dataset description in Catalan (if available)
- `link` — URL to the IBESTAT visualizer for this dataset

**API call:** `GET /datasets?query=name ILIKE '{query}'&limit={limit}&_type=json`

**Deduplication:** The API can return multiple versions of the same dataset. The search tool deduplicates by dataset ID, keeping only the entry linking to `~latest`.

### Tool 2: `get_dataset_info`

Get the structure and available dimensions of a dataset.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `dataset_id` | string | yes | Dataset identifier (e.g., "000001A_000001") |

**Returns:** Dataset metadata with:
- `name` — dataset name in Catalan
- `dimensions` — list of dimensions, each with:
  - `id` — dimension code (e.g., "TERRITORIO", "TIME_PERIOD")
  - `name` — dimension name in Catalan
  - `values` — list of available values with their codes and Catalan labels

**API call:** `GET /datasets/IBESTAT/{id}/~latest?_type=json`

### Tool 3: `get_data`

Fetch actual data from a dataset, optionally filtered by dimensions.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `dataset_id` | string | yes | Dataset identifier |
| `filters` | object | no | Dimension filters. Values can be a single string or a list for multiple values (e.g., `{"TIME_PERIOD": ["2023", "2024"], "TERRITORIO": "07001"}`) |

**Returns:** Flat list of row dicts with Catalan column names (accents stripped). Example:

```json
[
  {
    "Territori": "Alaro",
    "Periode": "2024",
    "Sexe": "Total",
    "Poblacio padro": 2035,
    "Variacio anual": -20,
    "Taxa variacio": -0.97
  }
]
```

**API call:** `GET /datasets/IBESTAT/{id}/~latest?dim={filters}&_type=json&fields=-metadata`

## IBESTAT eDades API Details

### Base URL
`https://ibestat.es/edatos/apis/statistical-resources/v1.0`

### Key Behaviors

- **No authentication required** — public API
- **Multilingual responses** — names/labels available in Catalan (ca), Spanish (es), and English (en)
- **Pagination** — list endpoints return `total`, `limit`, `offset` with `nextLink`/`lastLink`
- **Search** — `query=name ILIKE '{term}'` for case-insensitive substring matching on dataset names
- **Filtering** — `dim=DIMENSION_ID:VALUE` query params to filter observations
- **Latest version** — `~latest` path segment to always get the most recent dataset version
- **Response format** — `_type=json` for JSON responses (default is XML)
- **Observations format** — pipe-delimited string of values, ordered by dimension index positions
- **Dimension representations** — each dimension includes `code` to `index` mappings and multilingual labels
- **Total datasets** — ~3,730 datasets available

### Structural Resources API

Base URL: `https://ibestat.es/edatos/apis/structural-resources/v1.0`

Endpoints used:
- `GET /categoryschemes/IBESTAT/TEMAS_BALEARS/~latest/categories` -- topic tree (52 categories)
- `GET /codelists/IBESTAT/{id}/~latest/codes` -- codelist codes with hierarchy
- `GET /datastructures/IBESTAT/{id}/~latest` -- DSD (dimension-to-codelist mapping)

## Dependencies

- `mcp` — MCP Python SDK (server framework)
- `httpx` — async HTTP client
- `pydantic` — data validation and serialization

Minimal footprint. No heavy data libraries — flat dict construction is sufficient for the tabular output.

## Packaging & Distribution

- pip-installable package via `pyproject.toml`
- Entry point: `ibestat-mcp` CLI command (stdio transport)
- Users add to their MCP client config pointing to the installed command

## Language & Encoding Policy

- Code identifiers (functions, variables, classes): English
- User-facing data labels (dataset names, dimension values): Catalan (`lang=ca`)
- Product/system references: Catalan (eDades, not eDatos)
- Column names in output: Catalan with accents stripped for safe encoding
- No special characters in code identifiers

## Error Handling

- **Dataset not found:** return a clear error message with the invalid ID
- **API unreachable / timeout:** return a message indicating the IBESTAT service is unavailable, suggest retrying
- **No results for search:** return an empty list with a message suggesting alternative search terms
- **Invalid filter dimension/value:** return an error listing the valid dimension IDs and their available values for that dataset

All errors are returned as MCP tool error responses, not exceptions — the LLM can read the error and adjust.

## Semantic Layer (Structural Resources)

### Caching

`SemanticCache` (in `cache.py`) stores structural data in memory for the server process lifetime. Topics, DSD mappings, and codelists are fetched once on first use.

### Key Concepts

- **Category scheme (TEMAS_BALEARS)**: 52 thematic categories in a parent-child tree
- **Codelist**: Hierarchical lookup table for a dimension's valid codes (e.g., geographic codes organized as region > island > municipality)
- **DSD (Data Structure Definition)**: Blueprint that maps each dataset dimension to its codelist
- **codelist_id**: Field on DimensionInfo returned by `get_dataset_info`, linking a dimension to its codelist for use with `get_codelist`

### New Tools

**`browse_topics`** -- Fetches the TEMAS_BALEARS category scheme and returns a flat list of categories with parent references. Cached after first call.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `language` | string | no | Language for labels: ca, es, en (default: ca) |

**`get_codelist`** -- Fetches codes from a codelist with hierarchical parent-child relationships. Cached per codelist.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `codelist_id` | string | yes | Codelist identifier from `get_dataset_info` (e.g., "CL_AREA_ES53") |
| `limit` | int | no | Max codes to return (default: 100) |
| `offset` | int | no | Pagination offset (default: 0) |
| `language` | string | no | Language for labels: ca, es, en (default: ca) |

### Enhanced Tool: `get_dataset_info`

Now returns `codelist_id` per dimension when a DSD mapping is available. The DSD is fetched from the structural-resources API and cached per dataset. Falls back gracefully (codelist_id = null) if the DSD is unavailable.

## Out of Scope

- PC-Axis repository API support
- Export API (Excel/image downloads)
- Authentication / rate limiting (API is public and no limits documented)
