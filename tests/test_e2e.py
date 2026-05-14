"""End-to-end smoke tests that hit the real IBESTAT API.

These tests verify the full discover -> understand -> fetch pipeline
against the live eDades API. They are marked with ``@pytest.mark.e2e``
so they can be excluded from fast unit-test runs::

    pytest -m "not e2e"
"""

from __future__ import annotations

import pytest

from ibestat_mcp.cache import SemanticCache
from ibestat_mcp.client import IbestatClient
from ibestat_mcp.tools import browse_topics, get_codelist, get_data, get_dataset_info, list_datasets_by_topic, search_datasets


@pytest.mark.e2e
class TestEndToEnd:
    @pytest.mark.asyncio
    async def test_full_workflow(self) -> None:
        """Test the complete discover -> understand -> fetch workflow."""
        async with IbestatClient() as client:
            # Step 1: Search for population datasets
            results = await search_datasets(client, "poblaci", limit=3)
            assert len(results) > 0, "Search should return at least one dataset"
            dataset_id = results[0].id
            assert dataset_id, "Dataset should have an ID"

            # Step 2: Get dataset info
            info = await get_dataset_info(client, dataset_id)
            assert info.name, "Dataset should have a name"
            assert len(info.dimensions) > 0, "Dataset should have at least one dimension"

            # Verify dimensions have values
            for dim in info.dimensions:
                assert dim.id, "Dimension should have an ID"
                assert dim.name, "Dimension should have a name"
                assert len(dim.values) > 0, f"Dimension {dim.id} should have values"

            # Step 3: Get data with filters (small slice)
            filters = {}
            for dim in info.dimensions:
                if len(dim.values) > 2:
                    filters[dim.id] = dim.values[0].code

            rows = await get_data(client, dataset_id, filters=filters)
            assert len(rows) > 0, "Should return at least one data row"

            first_row = rows[0]
            assert len(first_row) > 1, "Row should have multiple columns"
            # Verify no accent characters in column names
            for key in first_row.keys():
                assert key.isascii(), f"Column name '{key}' should be ASCII (accents stripped)"


@pytest.mark.e2e
class TestBrowseTopicsE2E:
    @pytest.mark.asyncio
    async def test_returns_categories(self) -> None:
        async with IbestatClient() as client:
            result = await browse_topics(client, lang="es", _cache=SemanticCache())
        assert len(result.categories) > 0
        top_level = [c for c in result.categories if c.parent_id is None]
        assert len(top_level) > 0


@pytest.mark.e2e
class TestGetCodelistE2E:
    @pytest.mark.asyncio
    async def test_geographic_codelist(self) -> None:
        async with IbestatClient() as client:
            result = await get_codelist(client, "CL_AREA_ES53", limit=10, lang="es", _cache=SemanticCache())
        assert result.total > 0
        assert len(result.codes) <= 10

    @pytest.mark.asyncio
    async def test_hierarchy_present(self) -> None:
        async with IbestatClient() as client:
            result = await get_codelist(client, "CL_AREA_ES53", limit=100, lang="ca", _cache=SemanticCache())
        codes_with_parents = [c for c in result.codes if c.parent_code is not None]
        assert len(codes_with_parents) > 0


@pytest.mark.e2e
class TestGetDatasetInfoCodelistIdE2E:
    @pytest.mark.asyncio
    async def test_includes_codelist_id(self) -> None:
        async with IbestatClient() as client:
            result = await get_dataset_info(client, "000001A_000001", lang="ca", _cache=SemanticCache())
        territorio = next((d for d in result.dimensions if d.id == "TERRITORIO"), None)
        assert territorio is not None
        assert territorio.codelist_id is not None


@pytest.mark.e2e
class TestListDatasetsByTopicE2E:
    @pytest.mark.asyncio
    async def test_returns_datasets_for_population_category(self) -> None:
        async with IbestatClient() as client:
            result = await list_datasets_by_topic(
                client, "010_010", lang="es", _cache=SemanticCache()
            )
        assert result.total > 0
        assert len(result.datasets) > 0
        assert result.category_id == "010_010"
        assert all(d.id for d in result.datasets)
        assert all(d.name for d in result.datasets)

    @pytest.mark.asyncio
    async def test_parent_category_aggregates_children(self) -> None:
        cache = SemanticCache()
        async with IbestatClient() as client:
            result = await list_datasets_by_topic(
                client, "010", lang="es", _cache=cache
            )
        assert result.total > 0
        assert result.category_name

    @pytest.mark.asyncio
    async def test_caching_works(self) -> None:
        cache = SemanticCache()
        async with IbestatClient() as client:
            result1 = await list_datasets_by_topic(
                client, "010_010", lang="ca", _cache=cache
            )
            result2 = await list_datasets_by_topic(
                client, "010_010", lang="ca", _cache=cache
            )
        assert result1.total == result2.total
        assert result1.datasets == result2.datasets
