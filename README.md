# ibestat-mcp

MCP server for querying Balearic Islands public statistics via IBESTAT's eDades API.

## What is IBESTAT?

[IBESTAT](https://ibestat.es) (Institut d'Estadistica de les Illes Balears) is the official statistics office for the Balearic Islands (Mallorca, Menorca, Ibiza, Formentera). Their eDades API provides access to approximately 3,730 datasets covering population, tourism, employment, housing, economy, and more.

This MCP server gives LLMs direct access to search, explore, and query this data.

## Tools

| Tool | Description |
|------|-------------|
| `search_datasets` | Search datasets by keyword (e.g., "poblacio", "turisme") |
| `get_dataset_info` | Get dataset dimensions and available filter values |
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

Once configured, the LLM follows a natural three-step workflow:

1. **Search** -- "Find datasets about population" calls `search_datasets` to discover relevant datasets.
2. **Explore** -- The LLM picks a result and calls `get_dataset_info` to see its dimensions (territory, period, sex, age group, etc.) and the values available for each.
3. **Query** -- The LLM calls `get_data` with specific dimension filters to fetch the actual data rows.

Dimension filters require the actual codes returned by `get_dataset_info`, not human-readable labels. For example, Palma is `07040`, both sexes is `_T`, and a specific year might be `2024`. This is why the explore step matters -- it reveals the codes needed for precise queries.

### Example prompts

Try asking your LLM:

- "What was the population of Palma in 2024?"
- "Show me tourism statistics for the Balearic Islands"
- "Compare employment rates across Mallorca, Menorca, and Ibiza"
- "What are the latest housing price trends in the Balearic Islands?"
- "How many tourists visited Ibiza last year?"

## Data Language Note

Data labels are returned in Catalan by default (e.g., "Territori" for Territory, "Poblacio" for Population). The LLM handles this naturally in conversation.

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

**Column names and values are in Catalan**
This is expected — data labels come from the API in Catalan with accents stripped (e.g., "Territori", "Periode"). LLMs interpret these naturally. For programmatic use, `get_dataset_info` provides the full label mapping.

## Development

```bash
pip install -e ".[dev]"
pytest -m "not e2e"   # unit tests (fast, no network)
pytest -m e2e         # end-to-end (hits real API)
pytest                # all
```

## License

MIT -- see [LICENSE](LICENSE)
