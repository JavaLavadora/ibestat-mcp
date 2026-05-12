"""MCP server for the IBESTAT eDades statistical-resources API.

Registers three tools (search_datasets, get_dataset_info, get_data) and
exposes them via stdio transport.

Usage::

    # As a CLI entry point (configured in pyproject.toml):
    ibestat-mcp

    # Or directly:
    python -m ibestat_mcp.server
"""

from __future__ import annotations

import json
from typing import Annotated, Any

from mcp.server.fastmcp import FastMCP
from pydantic import Field

from ibestat_mcp.client import IbestatClient, IbestatError
from ibestat_mcp import tools as tool_functions


def create_server() -> FastMCP:
    """Create and configure the IBESTAT MCP server.

    Returns a fully configured FastMCP instance with all three tools
    registered.  This factory function exists for testability -- tests
    can call it directly without starting the stdio transport.
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
        query: str,
        limit: int = 10,
        language: Annotated[
            str,
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
            "Use this after search_datasets to understand a dataset's "
            "structure before requesting data. "
            "Supports Catalan (ca), Spanish (es), and English (en) labels "
            "via the language parameter. "
            "Example: dataset_id='000001A_000001' returns dimensions like "
            "TERRITORIO, TIME_PERIOD, SEXO, and MEDIDAS with all their codes "
            "and labels."
        ),
    )
    async def get_dataset_info(
        dataset_id: str,
        language: Annotated[
            str,
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
        dataset_id: str,
        filters: dict[str, Any] | None = None,
        language: Annotated[
            str,
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

    return mcp


def main() -> None:
    """Run the IBESTAT MCP server via stdio transport."""
    server = create_server()
    server.run(transport="stdio")


if __name__ == "__main__":
    main()
