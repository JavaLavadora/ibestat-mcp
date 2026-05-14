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
async def test_server_has_six_tools():
    """The server should register exactly six tools."""
    server = create_server()
    tools = await server.list_tools()
    tool_names = {t.name for t in tools}
    assert tool_names == {
        "search_datasets", "get_dataset_info", "get_data",
        "browse_topics", "get_codelist", "list_datasets_by_topic",
    }


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
async def test_get_dataset_info_tool_calls_client(
    dataset_metadata_response, data_structure_response
):
    """get_dataset_info tool should return structured dataset info."""
    server = create_server()

    mock_client = AsyncMock()
    mock_client.get_dataset_metadata = AsyncMock(
        return_value=dataset_metadata_response
    )
    mock_client.get_data_structure = AsyncMock(
        return_value=data_structure_response
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


# ===========================================================================
# Language parameter tests
# ===========================================================================


@pytest.mark.asyncio
async def test_tools_expose_language_parameter():
    """All three tools should include a 'language' parameter."""
    server = create_server()
    tools = await server.list_tools()
    for tool in tools:
        param_names = list(tool.inputSchema.get("properties", {}).keys())
        assert "language" in param_names, (
            f"Tool '{tool.name}' is missing the 'language' parameter"
        )


@pytest.mark.asyncio
async def test_search_datasets_passes_language(search_datasets_response):
    """search_datasets tool should forward language to tool_functions."""
    server = create_server()

    mock_client = AsyncMock()
    mock_client.search_datasets = AsyncMock(return_value=search_datasets_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("ibestat_mcp.server.IbestatClient", return_value=mock_client):
        with patch("ibestat_mcp.server.tool_functions") as mock_tools:
            mock_tools.search_datasets = AsyncMock(return_value=[])
            await server.call_tool(
                "search_datasets", {"query": "test", "language": "es"}
            )
            mock_tools.search_datasets.assert_awaited_once()
            call_kwargs = mock_tools.search_datasets.call_args
            assert call_kwargs.kwargs.get("lang") == "es" or (
                len(call_kwargs.args) >= 4 and call_kwargs.args[3] == "es"
            )


@pytest.mark.asyncio
async def test_get_dataset_info_passes_language(dataset_metadata_response):
    """get_dataset_info tool should forward language to tool_functions."""
    server = create_server()

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("ibestat_mcp.server.IbestatClient", return_value=mock_client):
        with patch("ibestat_mcp.server.tool_functions") as mock_tools:
            from ibestat_mcp.models import DatasetInfo
            mock_tools.get_dataset_info = AsyncMock(
                return_value=DatasetInfo(name="Test", dimensions=[])
            )
            await server.call_tool(
                "get_dataset_info",
                {"dataset_id": "000001A_000001", "language": "en"},
            )
            mock_tools.get_dataset_info.assert_awaited_once()
            call_kwargs = mock_tools.get_dataset_info.call_args
            assert call_kwargs.kwargs.get("lang") == "en"


@pytest.mark.asyncio
async def test_get_data_passes_language(dataset_metadata_response):
    """get_data tool should forward language to tool_functions."""
    server = create_server()

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("ibestat_mcp.server.IbestatClient", return_value=mock_client):
        with patch("ibestat_mcp.server.tool_functions") as mock_tools:
            mock_tools.get_data = AsyncMock(return_value=[])
            await server.call_tool(
                "get_data",
                {"dataset_id": "000001A_000001", "language": "es"},
            )
            mock_tools.get_data.assert_awaited_once()
            call_kwargs = mock_tools.get_data.call_args
            assert call_kwargs.kwargs.get("lang") == "es"


# ===========================================================================
# New tool registration tests
# ===========================================================================


@pytest.mark.asyncio
async def test_browse_topics_tool_registered():
    """browse_topics tool should be registered."""
    server = create_server()
    tool_names = [t.name for t in await server.list_tools()]
    assert "browse_topics" in tool_names


@pytest.mark.asyncio
async def test_get_codelist_tool_registered():
    """get_codelist tool should be registered."""
    server = create_server()
    tool_names = [t.name for t in await server.list_tools()]
    assert "get_codelist" in tool_names


@pytest.mark.asyncio
async def test_browse_topics_tool_calls_client():
    """browse_topics tool should create a client and return JSON text."""
    from ibestat_mcp.models import TopicTree, Category

    server = create_server()
    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("ibestat_mcp.server.IbestatClient", return_value=mock_client):
        with patch("ibestat_mcp.server.tool_functions") as mock_tools:
            mock_tools.browse_topics = AsyncMock(
                return_value=TopicTree(
                    name="TEMAS_BALEARS",
                    categories=[Category(id="010", name="Test", parent_id=None)],
                )
            )
            result = await server.call_tool("browse_topics", {})

    text = _extract_text(result)
    data = json.loads(text)
    assert data["name"] == "TEMAS_BALEARS"
    assert len(data["categories"]) == 1


@pytest.mark.asyncio
async def test_get_codelist_tool_calls_client():
    """get_codelist tool should create a client and return JSON text."""
    from ibestat_mcp.models import CodelistResult, CodelistEntry

    server = create_server()
    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("ibestat_mcp.server.IbestatClient", return_value=mock_client):
        with patch("ibestat_mcp.server.tool_functions") as mock_tools:
            mock_tools.get_codelist = AsyncMock(
                return_value=CodelistResult(
                    id="CL_AREA_ES53",
                    name="CL_AREA_ES53",
                    total=1,
                    codes=[CodelistEntry(code="ES53", label="Illes Balears", parent_code=None)],
                )
            )
            result = await server.call_tool(
                "get_codelist", {"codelist_id": "CL_AREA_ES53"}
            )

    text = _extract_text(result)
    data = json.loads(text)
    assert data["id"] == "CL_AREA_ES53"
    assert len(data["codes"]) == 1


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
