"""MCP server for the IBESTAT eDades statistical-resources API.

Registers six tools and five prompts, exposed via stdio transport.

Usage::

    # As a CLI entry point (configured in pyproject.toml):
    ibestat-mcp

    # Or directly:
    python -m ibestat_mcp.server
"""

from __future__ import annotations

import json
from typing import Annotated, Any, Literal

from mcp.server.fastmcp import FastMCP
from pydantic import Field

from ibestat_mcp.client import IbestatClient, IbestatError
from ibestat_mcp import prompts as prompt_functions
from ibestat_mcp import tools as tool_functions


def create_server() -> FastMCP:
    """Create and configure the IBESTAT MCP server.

    Returns a fully configured FastMCP instance with six tools and five
    prompts registered.  This factory function exists for testability --
    tests can call it directly without starting the stdio transport.
    """
    mcp = FastMCP("ibestat")

    @mcp.tool(
        description=(
            "Search for IBESTAT statistical datasets by keyword. "
            "Returns a list of matching datasets with their IDs, names, "
            "and links. Use this to discover available datasets before "
            "fetching details or data. "
            "Supports Catalan (ca), Spanish (es), and English (en) labels "
            "via the language parameter. "
            "Example: query='poblaci' finds population-related datasets. "
            "Example: query='turisme' finds tourism-related datasets."
        ),
    )
    async def search_datasets(
        query: Annotated[
            str,
            Field(
                description=(
                    "Search term. Works best in Catalan or Spanish "
                    "(e.g., 'poblacio' for population, 'turisme' for tourism)."
                )
            ),
        ],
        limit: Annotated[
            int,
            Field(description="Maximum number of results to return (default: 10)."),
        ] = 10,
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
        """Search IBESTAT datasets by keyword."""
        try:
            async with IbestatClient() as client:
                results = await tool_functions.search_datasets(
                    client, query, limit, lang=language
                )
            return json.dumps(
                [r.model_dump() for r in results], ensure_ascii=False
            )
        except IbestatError as e:
            return json.dumps({"error": str(e)}, ensure_ascii=False)

    @mcp.tool(
        description=(
            "Get detailed metadata for an IBESTAT dataset, including its "
            "name and all available dimensions with their possible values. "
            "Each dimension includes a codelist_id when available — use it "
            "with get_codelist to explore the full hierarchy of valid codes. "
            "Use this after search_datasets to understand a dataset's "
            "structure before requesting data. "
            "Supports Catalan (ca), Spanish (es), and English (en) labels "
            "via the language parameter. "
            "Example: dataset_id='000001A_000001' returns dimensions like "
            "TERRITORIO (codelist_id='CL_AREA_ES53'), TIME_PERIOD, SEXO, "
            "and MEDIDAS with all their codes and labels."
        ),
    )
    async def get_dataset_info(
        dataset_id: Annotated[
            str,
            Field(
                description=(
                    "Dataset identifier from search_datasets results "
                    "(e.g., '000001A_000001')."
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
        """Get metadata and dimensions for an IBESTAT dataset."""
        try:
            async with IbestatClient() as client:
                info = await tool_functions.get_dataset_info(
                    client, dataset_id, lang=language
                )
            return json.dumps(info.model_dump(), ensure_ascii=False)
        except IbestatError as e:
            return json.dumps({"error": str(e)}, ensure_ascii=False)

    @mcp.tool(
        description=(
            "Fetch observation data from an IBESTAT dataset, optionally "
            "filtered by dimension values. Returns rows as flat JSON objects "
            "with human-readable labels. Use get_dataset_info first to "
            "discover available dimension codes for filtering. "
            "Supports Catalan (ca), Spanish (es), and English (en) labels "
            "via the language parameter. "
            "Example: dataset_id='000001A_000001', "
            "filters={'TIME_PERIOD': '2024', 'SEXO': '_T'} returns total "
            "population for all municipalities in 2024."
        ),
    )
    async def get_data(
        dataset_id: Annotated[
            str,
            Field(
                description=(
                    "Dataset identifier from search_datasets results "
                    "(e.g., '000001A_000001')."
                )
            ),
        ],
        filters: Annotated[
            dict[str, Any] | None,
            Field(
                description=(
                    "Optional dimension filters using codes from get_dataset_info. "
                    "Keys are dimension IDs (e.g., 'TIME_PERIOD', 'TERRITORIO'), "
                    "values are codes (e.g., '2024', '07040' for Palma). "
                    "Example: {'TIME_PERIOD': '2024', 'SEXO': '_T'}"
                )
            ),
        ] = None,
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
        """Fetch observation data from an IBESTAT dataset."""
        try:
            async with IbestatClient() as client:
                rows = await tool_functions.get_data(
                    client, dataset_id, filters, lang=language
                )
            return json.dumps(rows, ensure_ascii=False)
        except IbestatError as e:
            return json.dumps({"error": str(e)}, ensure_ascii=False)

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
        """Browse IBESTAT's thematic topic tree."""
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
        """Get hierarchical codes from an IBESTAT codelist."""
        try:
            async with IbestatClient() as client:
                result = await tool_functions.get_codelist(
                    client, codelist_id, limit=limit, offset=offset, lang=language
                )
            return json.dumps(result.model_dump(), ensure_ascii=False)
        except IbestatError as e:
            return json.dumps({"error": str(e)}, ensure_ascii=False)

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

    # -----------------------------------------------------------------
    # Prompt registration
    # -----------------------------------------------------------------

    @mcp.prompt(
        name="explore_topic",
        description=(
            "Explore a statistical topic from IBESTAT's catalogue. "
            "Seeds a full discovery workflow: browse topics, list datasets, "
            "inspect dimensions, explore codelists, and fetch data."
        ),
    )
    def explore_topic(
        topic: Annotated[
            str,
            Field(description="Statistical topic to explore (e.g. 'tourism', 'population')."),
        ],
        language: Annotated[
            Literal["ca", "es", "en"],
            Field(description="Language for data labels. Default: 'ca'."),
        ] = "ca",
    ) -> str:
        return prompt_functions.explore_topic(topic, language)

    @mcp.prompt(
        name="query_dataset",
        description=(
            "Query a specific IBESTAT dataset by its ID. "
            "For users who already know which dataset they want. "
            "Guides inspection of dimensions, codelist lookup, and data retrieval."
        ),
    )
    def query_dataset(
        dataset_id: Annotated[
            str,
            Field(description="Dataset identifier (e.g. '000001A_000001')."),
        ],
        language: Annotated[
            Literal["ca", "es", "en"],
            Field(description="Language for data labels. Default: 'ca'."),
        ] = "ca",
    ) -> str:
        return prompt_functions.query_dataset(dataset_id, language)

    @mcp.prompt(
        name="compare_municipalities",
        description=(
            "Compare data across Balearic Islands municipalities. "
            "Provides context about IBESTAT's geographic codelist hierarchy "
            "(region > island > municipality) and how to resolve place names to codes."
        ),
    )
    def compare_municipalities(
        topic: Annotated[
            str,
            Field(description="Statistical topic to compare (e.g. 'population', 'employment')."),
        ],
        municipalities: Annotated[
            str | None,
            Field(description="Comma-separated municipality names (e.g. 'Palma, Ibiza'). Optional."),
        ] = None,
        language: Annotated[
            Literal["ca", "es", "en"],
            Field(description="Language for data labels. Default: 'ca'."),
        ] = "ca",
    ) -> str:
        return prompt_functions.compare_municipalities(topic, municipalities, language)

    @mcp.prompt(
        name="time_series",
        description=(
            "Show trends over time for an IBESTAT statistical topic. "
            "Provides context about the TIME_PERIOD dimension and how to "
            "filter by year ranges."
        ),
    )
    def time_series(
        topic: Annotated[
            str,
            Field(description="Statistical topic to analyse over time (e.g. 'tourism', 'housing prices')."),
        ],
        years: Annotated[
            str | None,
            Field(description="Year range (e.g. '2020-2024'). Optional."),
        ] = None,
        language: Annotated[
            Literal["ca", "es", "en"],
            Field(description="Language for data labels. Default: 'ca'."),
        ] = "ca",
    ) -> str:
        return prompt_functions.time_series(topic, years, language)

    @mcp.prompt(
        name="discover_available_data",
        description=(
            "Discover what data IBESTAT has available. "
            "Onboarding prompt for first-time users who want to learn what "
            "statistical data the Balearic Islands statistics office publishes."
        ),
    )
    def discover_available_data(
        language: Annotated[
            Literal["ca", "es", "en"],
            Field(description="Language for data labels. Default: 'ca'."),
        ] = "ca",
    ) -> str:
        return prompt_functions.discover_available_data(language)

    return mcp


def main() -> None:
    """Run the IBESTAT MCP server via stdio transport."""
    server = create_server()
    server.run(transport="stdio")


if __name__ == "__main__":
    main()
