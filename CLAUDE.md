# ibestat-mcp

MCP server wrapping the IBESTAT eDades API (Balearic Islands public statistics). Python 3.10+, async, stdio transport.

## Team Workflow

This project uses a four-agent team. The **Project Manager (PM)** is the sole point of contact with the user and coordinates all work.

### Roles

| Role | Agent file | Responsibility |
|------|-----------|----------------|
| Project Manager | `pm.md` | User liaison, task breakdown, git/PR workflow, final sign-off before user review |
| MCP Engineer | `mcp-engineer.md` | Feature development, LLM/MCP expertise, implementation |
| Data Analyst | `data-analyst.md` | Data relevance, API coverage, feature prioritisation from a data perspective |
| Senior Reviewer | `senior-reviewer.md` | Code review, best practices, design patterns |

### Process

1. User requests go to the **PM**, who breaks them into tasks.
2. **PM** delegates implementation to the **MCP Engineer**, consulting the **Data Analyst** on data-related decisions.
3. **Senior Reviewer** reviews all code via PR reviews on GitHub.
4. **PM** ensures alignment across all members before presenting the result to the user.
5. **The user always performs the final merge.** No agent merges PRs.

### Git & PR Standards

- All work happens on feature branches, never directly on `main`.
- PRs are the primary communication channel between team members.
- PR descriptions must include: summary, test plan, and any data-related decisions noted by the analyst.
- The Senior Reviewer must approve before the PM presents to the user.
- Commit messages are concise and describe the "why".

## Tech Stack

- **Runtime**: Python 3.10+, async/await
- **MCP**: `mcp` SDK with `FastMCP`, stdio transport
- **HTTP**: `httpx` (async)
- **Models**: `pydantic` v2
- **Tests**: `pytest` + `pytest-asyncio` + `respx` (HTTP mocking)
- **Build**: `hatchling`

## Running Tests

```bash
pytest -m "not e2e"   # unit tests (fast, no network)
pytest -m e2e         # end-to-end (hits real API)
pytest                # all
```

## Project Structure

```
src/ibestat_mcp/
  server.py            — MCP server setup, tool registration, stdio entry point
  tools.py             — tool functions wiring client + parser + cache
  client.py            — async HTTP client for IBESTAT eDades API (statistical + structural)
  parser.py            — JSON-stat response parsing
  structural_parser.py — structural-resources API response parsing
  models.py            — Pydantic models (DatasetSummary, DatasetInfo, DataRow, TopicTree, CodelistResult)
  cache.py             — SemanticCache for structural metadata (topics, DSDs, codelists)
  _i18n.py             — shared i18n utilities (extract_localized_text, strip_accents)
tests/
  test_*.py   — unit + e2e tests
  fixtures/   — JSON response fixtures for mocking
```

## Semantic Layer & Recommended Workflow

The MCP server has a semantic layer powered by IBESTAT's structural-resources API.
Structural data (topics, codelists, DSDs) is cached in memory for the server session.

### Recommended tool workflow

1. **`browse_topics`** -- See all statistical domains IBESTAT covers (cached after first call)
2. **`list_datasets_by_topic`** -- List all datasets under a chosen category. First call fetches from multiple API endpoints and may take a few seconds; result is cached for instant subsequent calls.
3. **`search_datasets`** -- (Alternative) Free-text keyword search when you already know what to look for
4. **`get_dataset_info`** -- Inspect dataset dimensions; each dimension includes a `codelist_id` if a hierarchical codelist exists
5. **`get_codelist`** -- Use the `codelist_id` to explore valid filter values at all hierarchy levels (e.g., region > island > municipality)
6. **`get_data`** -- Query with valid filters discovered in step 5

### Tool inventory

| Tool | Purpose | Cached |
|------|---------|--------|
| `browse_topics` | Thematic topic tree (52 categories) | Yes -- fetched once per session |
| `list_datasets_by_topic` | All datasets under a category | Yes -- per category, first call may take a few seconds |
| `search_datasets` | Keyword search for datasets | No |
| `get_dataset_info` | Dataset dimensions + codelist references | DSD mapping cached per dataset |
| `get_codelist` | Hierarchical codes for a codelist | Yes -- per codelist |
| `get_data` | Fetch observation data with filters | No |
