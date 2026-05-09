"""Tests for ibestat_mcp.tools module."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

import pytest

from ibestat_mcp.models import DatasetInfo, DatasetSummary
from ibestat_mcp.tools import get_data, get_dataset_info, search_datasets


# ---------------------------------------------------------------------------
# Minimal fixtures that mirror real API structure
# ---------------------------------------------------------------------------


def _intl(ca: str, es: str = "") -> dict[str, Any]:
    """Build an InternationalString with Catalan (and optional Spanish)."""
    texts = [{"value": ca, "lang": "ca"}]
    if es:
        texts.append({"value": es, "lang": "es"})
    return {"text": texts}


def _make_search_response(datasets: list[dict[str, Any]]) -> dict[str, Any]:
    """Wrap dataset entries in a search-response envelope."""
    return {
        "kind": "statisticalResources#datasets",
        "dataset": datasets,
        "total": len(datasets),
        "limit": 10,
        "offset": 0,
        "selfLink": "https://example.com",
        "lastLink": "https://example.com",
    }


def _dataset_entry(
    ds_id: str,
    name_ca: str,
    version: str = "1.0",
    description: dict | None = None,
    visualizer_link: str | None = None,
) -> dict[str, Any]:
    """Build a single dataset entry as returned by search."""
    link = (
        visualizer_link
        or f"https://ibestat.es/edatos/apps/statistical-visualizer/visualizer/data.html"
        f"?resourceType=dataset&agencyId=IBESTAT&resourceId={ds_id}&version={version}"
    )
    entry: dict[str, Any] = {
        "id": ds_id,
        "kind": "statisticalResources#dataset",
        "name": _intl(name_ca),
        "selfLink": {
            "kind": "statisticalResources#dataset",
            "href": f"https://ibestat.es/edatos/apis/statistical-resources/v1.0/datasets/IBESTAT/{ds_id}/{version}",
        },
        "urn": f"urn:siemac:org.siemac.metamac.infomodel.statisticalresources.Dataset=IBESTAT:{ds_id}({version})",
        "visualizerHtmlLink": link,
    }
    if description is not None:
        entry["description"] = description
    return entry


def _make_metadata_response(
    ds_id: str = "TEST_001",
    name_ca: str = "Poblacio municipal",
    dims: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build a minimal dataset detail response with metadata section."""
    if dims is None:
        dims = [
            {
                "id": "TERRITORIO",
                "name": _intl("Territori"),
                "type": "GEOGRAPHIC_DIMENSION",
                "dimensionValues": {
                    "value": [
                        {"id": "07001", "name": _intl("Palma")},
                        {"id": "07002", "name": _intl("Inca")},
                    ],
                    "total": 2,
                },
            },
            {
                "id": "TIME_PERIOD",
                "name": _intl("Periode"),
                "type": "TIME_DIMENSION",
                "dimensionValues": {
                    "value": [
                        {"id": "2024", "name": _intl("2024")},
                    ],
                    "total": 1,
                },
            },
        ]
    return {
        "id": ds_id,
        "name": _intl(name_ca),
        "metadata": {
            "dimensions": {"dimension": dims},
        },
    }


def _make_data_response() -> dict[str, Any]:
    """Build a minimal data response with metadata + data sections.

    Layout: TERRITORIO(2) x MEDIDAS(2), row-major.
    Observations: "100 | 5.0 | 200 | 3.2"
    Expected flat rows (MEDIDAS pivoted):
        {"Territori": "Palma", "Poblacio": 100, "Variacio": 5.0}
        {"Territori": "Inca",  "Poblacio": 200, "Variacio": 3.2}
    """
    return {
        "id": "TEST_001",
        "name": _intl("Test dataset"),
        "metadata": {
            "dimensions": {
                "dimension": [
                    {
                        "id": "TERRITORIO",
                        "name": _intl("Territori"),
                        "type": "GEOGRAPHIC_DIMENSION",
                        "dimensionValues": {
                            "value": [
                                {"id": "07001", "name": _intl("Palma")},
                                {"id": "07002", "name": _intl("Inca")},
                            ],
                            "total": 2,
                        },
                    },
                    {
                        "id": "MEDIDAS",
                        "name": _intl("Mesures"),
                        "type": "MEASURE_DIMENSION",
                        "dimensionValues": {
                            "value": [
                                {"id": "POBLACION", "name": _intl("Poblacio")},
                                {"id": "VARIACION", "name": _intl("Variacio")},
                            ],
                            "total": 2,
                        },
                    },
                ]
            }
        },
        "data": {
            "dimensions": {
                "dimension": [
                    {
                        "dimensionId": "TERRITORIO",
                        "representations": {
                            "representation": [
                                {"code": "07001", "index": 0},
                                {"code": "07002", "index": 1},
                            ],
                            "total": 2,
                        },
                    },
                    {
                        "dimensionId": "MEDIDAS",
                        "representations": {
                            "representation": [
                                {"code": "POBLACION", "index": 0},
                                {"code": "VARIACION", "index": 1},
                            ],
                            "total": 2,
                        },
                    },
                ]
            },
            "observations": "100 | 5.0 | 200 | 3.2",
        },
    }


# ===========================================================================
# TestSearchDatasets
# ===========================================================================


class TestSearchDatasets:
    @pytest.mark.asyncio
    async def test_returns_dataset_summaries(self) -> None:
        """search_datasets returns a list of DatasetSummary objects."""
        client = AsyncMock()
        client.search_datasets.return_value = _make_search_response(
            [
                _dataset_entry("DS_001", "Poblacio total"),
                _dataset_entry("DS_002", "Poblacio per edat"),
            ]
        )

        result = await search_datasets(client, "poblaci", limit=10)

        client.search_datasets.assert_awaited_once_with("poblaci", 10)
        assert len(result) == 2
        assert all(isinstance(r, DatasetSummary) for r in result)
        assert result[0].id == "DS_001"
        assert result[0].name == "Poblacio total"
        assert result[1].id == "DS_002"

    @pytest.mark.asyncio
    async def test_deduplicates_by_id(self) -> None:
        """Duplicate dataset IDs (different versions) are deduplicated."""
        client = AsyncMock()
        client.search_datasets.return_value = _make_search_response(
            [
                _dataset_entry("DS_001", "Poblacio total", version="1.0"),
                _dataset_entry("DS_001", "Poblacio total", version="1.1"),
                _dataset_entry("DS_002", "Altra dataset", version="1.0"),
            ]
        )

        result = await search_datasets(client, "poblaci")

        assert len(result) == 2
        ids = [r.id for r in result]
        assert ids == ["DS_001", "DS_002"]

    @pytest.mark.asyncio
    async def test_empty_results(self) -> None:
        """Empty dataset list returns empty list."""
        client = AsyncMock()
        client.search_datasets.return_value = _make_search_response([])

        result = await search_datasets(client, "nonexistent")

        assert result == []

    @pytest.mark.asyncio
    async def test_extracts_description_when_present(self) -> None:
        """Description is extracted from the dataset entry when available."""
        client = AsyncMock()
        client.search_datasets.return_value = _make_search_response(
            [
                _dataset_entry(
                    "DS_001",
                    "Poblacio total",
                    description=_intl("Una descripcio de la dataset"),
                ),
            ]
        )

        result = await search_datasets(client, "poblaci")

        assert result[0].description == "Una descripcio de la dataset"

    @pytest.mark.asyncio
    async def test_description_none_when_absent(self) -> None:
        """Description is None when not present in the dataset entry."""
        client = AsyncMock()
        client.search_datasets.return_value = _make_search_response(
            [_dataset_entry("DS_001", "Poblacio total")]
        )

        result = await search_datasets(client, "poblaci")

        assert result[0].description is None

    @pytest.mark.asyncio
    async def test_visualizer_link_extracted(self) -> None:
        """The visualizerHtmlLink is used as the link field."""
        client = AsyncMock()
        link = "https://ibestat.es/edatos/apps/statistical-visualizer/visualizer/data.html?resourceType=dataset&agencyId=IBESTAT&resourceId=DS_001&version=1.0"
        client.search_datasets.return_value = _make_search_response(
            [_dataset_entry("DS_001", "Poblacio total", visualizer_link=link)]
        )

        result = await search_datasets(client, "poblaci")

        assert result[0].link == link


# ===========================================================================
# TestGetDatasetInfo
# ===========================================================================


class TestGetDatasetInfo:
    @pytest.mark.asyncio
    async def test_returns_dataset_info(self) -> None:
        """get_dataset_info returns a DatasetInfo with name and dimensions."""
        client = AsyncMock()
        client.get_dataset_metadata.return_value = _make_metadata_response(
            name_ca="Poblacio municipal"
        )

        result = await get_dataset_info(client, "TEST_001")

        client.get_dataset_metadata.assert_awaited_once_with("TEST_001")
        assert isinstance(result, DatasetInfo)
        assert result.name == "Poblacio municipal"
        assert len(result.dimensions) == 2
        assert result.dimensions[0].id == "TERRITORIO"
        assert result.dimensions[0].name == "Territori"
        assert len(result.dimensions[0].values) == 2
        assert result.dimensions[0].values[0].code == "07001"
        assert result.dimensions[0].values[0].label == "Palma"

    @pytest.mark.asyncio
    async def test_accent_stripping(self) -> None:
        """Names with accents are stripped for safe encoding."""
        client = AsyncMock()
        dims = [
            {
                "id": "PERIODO",
                "name": _intl("Període"),
                "type": "TIME_DIMENSION",
                "dimensionValues": {
                    "value": [
                        {"id": "2024", "name": _intl("Any 2024")},
                    ],
                    "total": 1,
                },
            },
        ]
        client.get_dataset_metadata.return_value = _make_metadata_response(
            name_ca="Poblacio amb accents: es",
            dims=dims,
        )

        result = await get_dataset_info(client, "TEST_002")

        assert result.dimensions[0].name == "Periode"


# ===========================================================================
# TestGetData
# ===========================================================================


class TestGetData:
    @pytest.mark.asyncio
    async def test_returns_flat_rows(self) -> None:
        """get_data returns a list of flat dictionaries."""
        client = AsyncMock()
        client.get_dataset_data.return_value = _make_data_response()

        result = await get_data(client, "TEST_001")

        client.get_dataset_data.assert_awaited_once_with(
            "TEST_001", filters=None
        )
        assert len(result) == 2
        assert isinstance(result[0], dict)
        # MEDIDAS pivoted: Poblacio and Variacio are column names
        assert result[0]["Territori"] == "Palma"
        assert result[0]["Poblacio"] == 100
        assert result[0]["Variacio"] == 5.0
        assert result[1]["Territori"] == "Inca"
        assert result[1]["Poblacio"] == 200
        assert result[1]["Variacio"] == 3.2

    @pytest.mark.asyncio
    async def test_passes_filters_to_client(self) -> None:
        """Filters are forwarded to the client's get_dataset_data call."""
        client = AsyncMock()
        client.get_dataset_data.return_value = _make_data_response()
        filters = {"TIME_PERIOD": "2024", "TERRITORIO": "07001"}

        await get_data(client, "TEST_001", filters=filters)

        client.get_dataset_data.assert_awaited_once_with(
            "TEST_001", filters=filters
        )

    @pytest.mark.asyncio
    async def test_no_filters_default(self) -> None:
        """When no filters provided, None is passed to client."""
        client = AsyncMock()
        client.get_dataset_data.return_value = _make_data_response()

        await get_data(client, "TEST_001")

        client.get_dataset_data.assert_awaited_once_with(
            "TEST_001", filters=None
        )
