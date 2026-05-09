"""End-to-end smoke tests that hit the real IBESTAT API.

These tests verify the full discover -> understand -> fetch pipeline
against the live eDades API. They are marked with ``@pytest.mark.e2e``
so they can be excluded from fast unit-test runs::

    pytest -m "not e2e"
"""

from __future__ import annotations

import pytest

from ibestat_mcp.client import IbestatClient
from ibestat_mcp.tools import get_data, get_dataset_info, search_datasets


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
