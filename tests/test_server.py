"""Tests for the MCP server module."""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from ibestat_mcp.server import create_server


def _extract_text(result: Any) -> str:
    """Extract text from a call_tool result.

    FastMCP.call_tool may return either:
      - a tuple (content_blocks, structured_output)  -- mcp >= 1.20
      - a list of content blocks                     -- older versions

    This helper handles both cases.
    """
    if isinstance(result, tuple):
        content_blocks = result[0]
    else:
        content_blocks = result
    return content_blocks[0].text


def test_create_server_returns_fastmcp_instance():
    """create_server() should return a FastMCP server instance."""
    from mcp.server.fastmcp import FastMCP

    server = create_server()
    assert isinstance(server, FastMCP)


def test_server_has_expected_name():
    """The server should be named 'ibestat'."""
    server = create_server()
    assert server.name == "ibestat"


@pytest.mark.asyncio
async def test_server_has_three_tools():
    """The server should register exactly three tools."""
    server = create_server()
    tools = await server.list_tools()
    tool_names = {t.name for t in tools}
    assert tool_names == {"search_datasets", "get_dataset_info", "get_data"}


@pytest.mark.asyncio
async def test_search_datasets_tool_calls_client(search_datasets_response):
    """search_datasets tool should create a client and return JSON text."""
    server = create_server()

    mock_client = AsyncMock()
    mock_client.search_datasets = AsyncMock(return_value=search_datasets_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("ibestat_mcp.server.IbestatClient", return_value=mock_client):
        result = await server.call_tool(
            "search_datasets", {"query": "poblaci", "limit": 5}
        )

    text = _extract_text(result)
    data = json.loads(text)
    assert isinstance(data, list)
    assert len(data) > 0
    assert "id" in data[0]


@pytest.mark.asyncio
async def test_get_dataset_info_tool_calls_client(dataset_metadata_response):
    """get_dataset_info tool should return structured dataset info."""
    server = create_server()

    mock_client = AsyncMock()
    mock_client.get_dataset_metadata = AsyncMock(
        return_value=dataset_metadata_response
    )
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("ibestat_mcp.server.IbestatClient", return_value=mock_client):
        result = await server.call_tool(
            "get_dataset_info", {"dataset_id": "000001A_000001"}
        )

    text = _extract_text(result)
    data = json.loads(text)
    assert "name" in data
    assert "dimensions" in data


@pytest.mark.asyncio
async def test_get_data_tool_calls_client(dataset_metadata_response):
    """get_data tool should return observation rows as JSON."""
    server = create_server()

    mock_client = AsyncMock()
    mock_client.get_dataset_data = AsyncMock(
        return_value=dataset_metadata_response
    )
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("ibestat_mcp.server.IbestatClient", return_value=mock_client):
        result = await server.call_tool(
            "get_data", {"dataset_id": "000001A_000001"}
        )

    text = _extract_text(result)
    data = json.loads(text)
    assert isinstance(data, list)


@pytest.mark.asyncio
async def test_tool_returns_error_text_on_ibestat_error():
    """IbestatError should be returned as error text, not raised."""
    from ibestat_mcp.client import IbestatError

    server = create_server()

    mock_client = AsyncMock()
    mock_client.search_datasets = AsyncMock(
        side_effect=IbestatError("Dataset not found: test")
    )
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("ibestat_mcp.server.IbestatClient", return_value=mock_client):
        result = await server.call_tool(
            "search_datasets", {"query": "nonexistent"}
        )

    text = _extract_text(result)
    assert "Dataset not found" in text
