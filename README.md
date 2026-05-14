# ibestat-mcp

MCP server for querying Balearic Islands public statistics via IBESTAT's eDades API.

## What is IBESTAT?

[IBESTAT](https://ibestat.es) (Institut d'Estadistica de les Illes Balears) is the official statistics office for the Balearic Islands (Mallorca, Menorca, Ibiza, Formentera). Their eDades API provides access to approximately 3,730 datasets covering population, tourism, employment, housing, economy, and more.

This MCP server gives LLMs direct access to search, explore, and query this data.

## Tools

| Tool | Description |
|------|-------------|
| `browse_topics` | Browse IBESTAT's thematic catalog (Demographics, Economy, Tourism, Labour...) |
| `list_datasets_by_topic` | List all datasets under a category — no keyword guessing needed |
| `search_datasets` | Search datasets by keyword (e.g., "poblacio", "turisme") |
| `get_dataset_info` | Get dataset dimensions, filter values, and linked codelist IDs |
| `get_codelist` | Explore a codelist's hierarchical codes (e.g., Region > Island > Municipality) |
| `get_data` | Fetch data rows with optional dimension filters |

## Installation

The package is not yet published on PyPI. Install directly from GitHub:

```bash
pip install git+https://github.com/JavaLavadora/ibestat-mcp.git
```

Or for local development:

```bash
git clone https://github.com/JavaLavadora/ibestat-mcp.git
cd ibestat-mcp
pip install -e ".[dev]"
```

## Configuration (Claude Desktop)

Add this to your Claude Desktop configuration file (`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "ibestat": {
      "command": "ibestat-mcp"
    }
  }
}
```

On macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`

On Linux: `~/.config/Claude/claude_desktop_config.json`

On Windows: `%APPDATA%\Claude\claude_desktop_config.json`

## Quick Start

Once configured, the LLM follows a six-step workflow:

1. **Browse topics** -- `browse_topics` shows IBESTAT's full thematic catalog so the LLM knows what domains exist.
2. **List datasets** -- `list_datasets_by_topic` shows all datasets under a chosen category. First call may take a few seconds (multiple API endpoints are queried and cached); subsequent calls are instant.
3. **Search** -- *(Alternative)* `search_datasets` finds datasets via free-text keyword search when you already know what to look for.
4. **Inspect** -- `get_dataset_info` reveals dimensions, their values, and a `codelist_id` for each dimension that has a hierarchical codelist. `codelist_id` allows to gather context for the dimension using the APIs internal semantic conventions.
5. **Explore codelists** -- `get_codelist` with the `codelist_id` shows the full hierarchy (e.g., Illes Balears > Mallorca > Palma) so the LLM can discover valid filter values at any level.
6. **Query** -- `get_data` fetches rows using the known-valid filter codes.

Dimension filters require the actual codes returned by `get_dataset_info` or `get_codelist`, not human-readable labels. For example, Palma is `07040`, both sexes is `_T`, and a specific year might be `2024`. Steps 3-4 reveal the codes needed for precise queries.

Structural metadata (topics, codelists, DSDs) is cached in memory for the server session, so repeated calls are fast.

### Example prompts

Try asking your LLM:

- "What was the population of Palma in 2024?"
- "Show me tourism statistics for the Balearic Islands"
- "Compare employment rates across Mallorca, Menorca, and Ibiza"
- "What are the latest housing price trends in the Balearic Islands?"
- "How many tourists visited Ibiza last year?"

## Data Language Note

All three tools accept a `language` parameter that controls the language of returned data labels. Supported values:

- `ca` -- Catalan (default). Labels like "Territori", "Poblacio".
- `es` -- Spanish. Labels like "Territorio", "Poblacion".
- `en` -- English. Labels like "Reference area", "Population".

The LLM will typically pick the right language based on the user's conversation language.

Search queries work best in Catalan or Spanish since dataset names are stored in those languages. For example, use "poblacio" (not "population"), "turisme" (not "tourism"), "ocupacio" (not "employment").

## Troubleshooting

**Search returns no results for English terms**
Dataset names are indexed in Catalan/Spanish. Use Catalan stems: `poblaci` (population), `turisme` (tourism), `atur` (unemployment), `habitatge` (housing). Partial matches work.

**`get_data` is slow or returns too much data**
Without filters, all observations are fetched — some datasets have hundreds of thousands of rows. Always call `get_dataset_info` first, then pass `filters` to narrow by time period, territory, etc.

**"IBESTAT service is unavailable" error**
The IBESTAT API is a public government service with no SLA. Wait a few minutes and retry. If persistent, check that `https://ibestat.es` is reachable from your network.

**"Dataset not found" error**
The dataset ID may be wrong or the dataset may have been retired. Use `search_datasets` to find the current valid ID — copy the `id` field exactly as returned.

**Filter keys seem to be ignored (unfiltered data returned)**
Filters require dimension IDs (`TIME_PERIOD`, `TERRITORIO`) and value codes (`07040`, `_T`), not human-readable labels. Use the `id` and `code` fields from `get_dataset_info`, not `name` or `label`.

**Column names and values are not in English**
The server returns labels in Catalan by default (e.g., "Territori", "Periode"). Set the `language` parameter to `es` for Spanish or `en` for English. LLMs interpret these labels naturally in conversation.

## Development

```bash
pip install -e ".[dev]"
pytest -m "not e2e"   # unit tests (fast, no network)
pytest -m e2e         # end-to-end (hits real API)
pytest                # all
```

## License

MIT -- see [LICENSE](LICENSE)
