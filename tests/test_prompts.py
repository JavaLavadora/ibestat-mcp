"""Tests for MCP prompt registration and rendering."""

from __future__ import annotations

import pytest

from ibestat_mcp.server import create_server


@pytest.mark.asyncio
async def test_server_has_five_prompts():
    """The server should register exactly five prompts."""
    server = create_server()
    prompts = await server.list_prompts()
    prompt_names = {p.name for p in prompts}
    assert prompt_names == {
        "explore_topic",
        "query_dataset",
        "compare_municipalities",
        "time_series",
        "discover_available_data",
    }


@pytest.mark.asyncio
async def test_explore_topic_required_arg():
    """explore_topic should require 'topic' and make 'language' optional."""
    server = create_server()
    prompts = await server.list_prompts()
    prompt = next(p for p in prompts if p.name == "explore_topic")
    args = {a.name: a.required for a in prompt.arguments}
    assert args["topic"] is True
    assert args["language"] is False


@pytest.mark.asyncio
async def test_explore_topic_renders_with_defaults():
    """explore_topic should include the topic and default language in output."""
    server = create_server()
    result = await server.get_prompt("explore_topic", {"topic": "tourism"})
    text = result.messages[0].content.text
    assert "tourism" in text
    assert "language='ca'" in text
    assert "IBESTAT" in text
    assert "browse_topics" in text


@pytest.mark.asyncio
async def test_explore_topic_renders_with_language():
    """explore_topic should respect the language argument."""
    server = create_server()
    result = await server.get_prompt(
        "explore_topic", {"topic": "population", "language": "es"}
    )
    text = result.messages[0].content.text
    assert "population" in text
    assert "language='es'" in text


@pytest.mark.asyncio
async def test_query_dataset_renders():
    """query_dataset should mention the dataset ID and available tools."""
    server = create_server()
    result = await server.get_prompt(
        "query_dataset", {"dataset_id": "000001A_000001"}
    )
    text = result.messages[0].content.text
    assert "000001A_000001" in text
    assert "get_dataset_info" in text
    assert "get_codelist" in text
    assert "get_data" in text


@pytest.mark.asyncio
async def test_query_dataset_with_language():
    """query_dataset should forward language to the rendered prompt."""
    server = create_server()
    result = await server.get_prompt(
        "query_dataset", {"dataset_id": "DS_TEST", "language": "en"}
    )
    text = result.messages[0].content.text
    assert "language='en'" in text


@pytest.mark.asyncio
async def test_compare_municipalities_without_names():
    """compare_municipalities without municipality names should suggest choosing."""
    server = create_server()
    result = await server.get_prompt(
        "compare_municipalities", {"topic": "employment"}
    )
    text = result.messages[0].content.text
    assert "employment" in text
    assert "help them choose" in text
    assert "hierarchy" in text


@pytest.mark.asyncio
async def test_compare_municipalities_with_names():
    """compare_municipalities with names should include them in the prompt."""
    server = create_server()
    result = await server.get_prompt(
        "compare_municipalities",
        {"topic": "population", "municipalities": "Palma, Ibiza"},
    )
    text = result.messages[0].content.text
    assert "Palma, Ibiza" in text
    assert "population" in text
    assert "CL_AREA_ES53" in text


@pytest.mark.asyncio
async def test_time_series_without_years():
    """time_series without years should suggest discovering available periods."""
    server = create_server()
    result = await server.get_prompt(
        "time_series", {"topic": "housing prices"}
    )
    text = result.messages[0].content.text
    assert "housing prices" in text
    assert "discover what's available" in text.lower() or "discover what" in text.lower()
    assert "TIME_PERIOD" in text


@pytest.mark.asyncio
async def test_time_series_with_years():
    """time_series with years should include the range in the prompt."""
    server = create_server()
    result = await server.get_prompt(
        "time_series", {"topic": "tourism", "years": "2020-2024"}
    )
    text = result.messages[0].content.text
    assert "2020-2024" in text
    assert "tourism" in text


@pytest.mark.asyncio
async def test_discover_available_data_renders():
    """discover_available_data should describe IBESTAT and suggest browse_topics."""
    server = create_server()
    result = await server.get_prompt("discover_available_data", {})
    text = result.messages[0].content.text
    assert "IBESTAT" in text
    assert "Balearic Islands" in text
    assert "browse_topics" in text
    assert "3,700" in text


@pytest.mark.asyncio
async def test_discover_available_data_with_language():
    """discover_available_data should respect language parameter."""
    server = create_server()
    result = await server.get_prompt(
        "discover_available_data", {"language": "es"}
    )
    text = result.messages[0].content.text
    assert "language='es'" in text


@pytest.mark.asyncio
async def test_all_prompts_return_user_role():
    """All prompts should return messages with role='user'."""
    server = create_server()
    prompts = await server.list_prompts()
    test_args = {
        "explore_topic": {"topic": "test"},
        "query_dataset": {"dataset_id": "TEST_ID"},
        "compare_municipalities": {"topic": "test"},
        "time_series": {"topic": "test"},
        "discover_available_data": {},
    }
    for prompt in prompts:
        args = test_args[prompt.name]
        result = await server.get_prompt(prompt.name, args)
        assert len(result.messages) == 1
        assert result.messages[0].role == "user"


@pytest.mark.asyncio
async def test_all_prompts_have_descriptions():
    """All prompts should have non-empty descriptions."""
    server = create_server()
    prompts = await server.list_prompts()
    for prompt in prompts:
        assert prompt.description, f"Prompt '{prompt.name}' has no description"
        assert len(prompt.description) > 10
