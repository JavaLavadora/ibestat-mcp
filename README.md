# ibestat-mcp

MCP server for IBESTAT (Institut d'Estadistica de les Illes Balears) eDades API.

Allows LLMs to discover and explore Balearic Islands public statistical data through three tools:

- `search_datasets` — search datasets by keyword
- `get_dataset_info` — get dataset dimensions and available values
- `get_data` — fetch data with optional dimension filters

## Installation

```bash
pip install ibestat-mcp
```

## Usage

Add to your MCP client configuration:

```json
{
  "mcpServers": {
    "ibestat": {
      "command": "ibestat-mcp"
    }
  }
}
```

## Development

```bash
pip install -e ".[dev]"
pytest
```
