"""Tests for ibestat_mcp.client module."""

from __future__ import annotations

import urllib.parse
from typing import Any

import httpx
import pytest
import respx

from ibestat_mcp.client import BASE_URL, STRUCTURAL_BASE_URL, IbestatClient, IbestatError


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def mock_search_response(search_datasets_response: dict[str, Any]) -> dict[str, Any]:
    return search_datasets_response


@pytest.fixture()
def mock_metadata_response(dataset_metadata_response: dict[str, Any]) -> dict[str, Any]:
    return dataset_metadata_response


@pytest.fixture()
def mock_data_response(dataset_data_response: dict[str, Any]) -> dict[str, Any]:
    return dataset_data_response


# ===========================================================================
# TestSearchDatasets
# ===========================================================================


class TestSearchDatasets:
    @pytest.mark.asyncio
    @respx.mock
    async def test_correct_url_and_params(
        self, mock_search_response: dict[str, Any]
    ) -> None:
        """search_datasets sends the correct URL, query and limit params."""
        route = respx.get(f"{BASE_URL}/datasets").mock(
            return_value=httpx.Response(200, json=mock_search_response)
        )
        async with IbestatClient() as client:
            result = await client.search_datasets("poblaci", limit=5)

        assert route.called
        request = route.calls[0].request
        url_decoded = urllib.parse.unquote_plus(str(request.url))
        assert "_type=json" in url_decoded
        assert "query=name ILIKE 'poblaci'" in url_decoded
        assert "limit=5" in url_decoded

    @pytest.mark.asyncio
    @respx.mock
    async def test_returns_raw_json(
        self, mock_search_response: dict[str, Any]
    ) -> None:
        """search_datasets returns the raw JSON dict from the API."""
        respx.get(f"{BASE_URL}/datasets").mock(
            return_value=httpx.Response(200, json=mock_search_response)
        )
        async with IbestatClient() as client:
            result = await client.search_datasets("poblaci", limit=5)

        assert result == mock_search_response
        assert "dataset" in result
        assert result["total"] == 183


# ===========================================================================
# TestGetDatasetMetadata
# ===========================================================================


class TestGetDatasetMetadata:
    @pytest.mark.asyncio
    @respx.mock
    async def test_correct_url(
        self, mock_metadata_response: dict[str, Any]
    ) -> None:
        """get_dataset_metadata uses the correct URL with dataset ID."""
        route = respx.get(
            f"{BASE_URL}/datasets/IBESTAT/000001A_000001/~latest"
        ).mock(return_value=httpx.Response(200, json=mock_metadata_response))

        async with IbestatClient() as client:
            result = await client.get_dataset_metadata("000001A_000001")

        assert route.called
        request = route.calls[0].request
        url_decoded = urllib.parse.unquote(str(request.url))
        assert "/datasets/IBESTAT/000001A_000001/~latest" in url_decoded
        assert "_type=json" in url_decoded

    @pytest.mark.asyncio
    @respx.mock
    async def test_returns_raw_json(
        self, mock_metadata_response: dict[str, Any]
    ) -> None:
        """get_dataset_metadata returns the raw JSON dict."""
        respx.get(
            f"{BASE_URL}/datasets/IBESTAT/000001A_000001/~latest"
        ).mock(return_value=httpx.Response(200, json=mock_metadata_response))

        async with IbestatClient() as client:
            result = await client.get_dataset_metadata("000001A_000001")

        assert result == mock_metadata_response
        assert result["id"] == "000001A_000001"


# ===========================================================================
# TestGetDatasetData
# ===========================================================================


class TestGetDatasetData:
    @pytest.mark.asyncio
    @respx.mock
    async def test_with_filters_sends_dim_params(
        self, mock_metadata_response: dict[str, Any]
    ) -> None:
        """get_dataset_data with filters sends correct dim= query params."""
        route = respx.get(
            f"{BASE_URL}/datasets/IBESTAT/000001A_000001/~latest"
        ).mock(return_value=httpx.Response(200, json=mock_metadata_response))

        async with IbestatClient() as client:
            result = await client.get_dataset_data(
                "000001A_000001",
                filters={
                    "TIME_PERIOD": "2024",
                    "TERRITORIO": "07001",
                },
            )

        assert route.called
        request = route.calls[0].request
        url_decoded = urllib.parse.unquote(str(request.url))
        assert "dim=TIME_PERIOD:2024" in url_decoded
        assert "dim=TERRITORIO:07001" in url_decoded
        # Must NOT have fields=-metadata
        assert "fields=-metadata" not in url_decoded

    @pytest.mark.asyncio
    @respx.mock
    async def test_multi_value_filter_uses_pipe(
        self, mock_metadata_response: dict[str, Any]
    ) -> None:
        """Multi-value filters use pipe separator (dim=KEY:v1|v2)."""
        route = respx.get(
            f"{BASE_URL}/datasets/IBESTAT/000001A_000001/~latest"
        ).mock(return_value=httpx.Response(200, json=mock_metadata_response))

        async with IbestatClient() as client:
            result = await client.get_dataset_data(
                "000001A_000001",
                filters={"SEXO": ["_T", "M"]},
            )

        assert route.called
        request = route.calls[0].request
        url_decoded = urllib.parse.unquote(str(request.url))
        assert "dim=SEXO:_T|M" in url_decoded

    @pytest.mark.asyncio
    @respx.mock
    async def test_without_filters_no_dim_params(
        self, mock_metadata_response: dict[str, Any]
    ) -> None:
        """get_dataset_data without filters sends no dim= params."""
        route = respx.get(
            f"{BASE_URL}/datasets/IBESTAT/000001A_000001/~latest"
        ).mock(return_value=httpx.Response(200, json=mock_metadata_response))

        async with IbestatClient() as client:
            result = await client.get_dataset_data("000001A_000001")

        assert route.called
        request = route.calls[0].request
        url_decoded = urllib.parse.unquote(str(request.url))
        assert "dim=" not in url_decoded
        assert "_type=json" in url_decoded

    @pytest.mark.asyncio
    @respx.mock
    async def test_returns_full_response_with_metadata(
        self, mock_metadata_response: dict[str, Any]
    ) -> None:
        """get_dataset_data returns full response including metadata section."""
        respx.get(
            f"{BASE_URL}/datasets/IBESTAT/000001A_000001/~latest"
        ).mock(return_value=httpx.Response(200, json=mock_metadata_response))

        async with IbestatClient() as client:
            result = await client.get_dataset_data("000001A_000001")

        # Response must contain metadata for label resolution
        assert "metadata" in result
        assert "data" in result


# ===========================================================================
# TestErrorHandling
# ===========================================================================


class TestErrorHandling:
    @pytest.mark.asyncio
    @respx.mock
    async def test_404_raises_ibestat_error(self) -> None:
        """404 response raises IbestatError with 'not found' message."""
        respx.get(
            f"{BASE_URL}/datasets/IBESTAT/NONEXISTENT/~latest"
        ).mock(return_value=httpx.Response(404))

        async with IbestatClient() as client:
            with pytest.raises(IbestatError, match="not found"):
                await client.get_dataset_metadata("NONEXISTENT")

    @pytest.mark.asyncio
    @respx.mock
    async def test_timeout_raises_ibestat_error(self) -> None:
        """Connection timeout raises IbestatError with 'unavailable' message."""
        respx.get(
            f"{BASE_URL}/datasets/IBESTAT/000001A_000001/~latest"
        ).mock(side_effect=httpx.ConnectTimeout("connection timeout"))

        async with IbestatClient() as client:
            with pytest.raises(IbestatError, match="unavailable"):
                await client.get_dataset_metadata("000001A_000001")

    @pytest.mark.asyncio
    @respx.mock
    async def test_read_timeout_raises_ibestat_error(self) -> None:
        """Read timeout raises IbestatError with 'unavailable' message."""
        respx.get(
            f"{BASE_URL}/datasets/IBESTAT/000001A_000001/~latest"
        ).mock(side_effect=httpx.ReadTimeout("read timeout"))

        async with IbestatClient() as client:
            with pytest.raises(IbestatError, match="unavailable"):
                await client.get_dataset_metadata("000001A_000001")

    @pytest.mark.asyncio
    @respx.mock
    async def test_connect_error_raises_ibestat_error(self) -> None:
        """Connection error raises IbestatError with 'unavailable' message."""
        respx.get(
            f"{BASE_URL}/datasets/IBESTAT/000001A_000001/~latest"
        ).mock(side_effect=httpx.ConnectError("connection error"))

        async with IbestatClient() as client:
            with pytest.raises(IbestatError, match="unavailable"):
                await client.get_dataset_metadata("000001A_000001")

    @pytest.mark.asyncio
    @respx.mock
    async def test_raises_on_500(self) -> None:
        """500 response raises IbestatError with 'API error' message."""
        respx.get(url__startswith=f"{BASE_URL}/datasets").mock(
            return_value=httpx.Response(500)
        )
        async with IbestatClient() as client:
            with pytest.raises(IbestatError, match="API error"):
                await client.search_datasets("test")


# ===========================================================================
# TestContextManager
# ===========================================================================


class TestContextManager:
    @pytest.mark.asyncio
    async def test_client_requires_context_manager(self) -> None:
        """Using the client outside async context manager raises RuntimeError."""
        client = IbestatClient()
        with pytest.raises(RuntimeError, match="async context manager"):
            await client.search_datasets("test")

    @pytest.mark.asyncio
    async def test_custom_base_url(self) -> None:
        """Client accepts a custom base_url."""
        custom_url = "https://custom.example.com/api/v1"
        client = IbestatClient(base_url=custom_url)
        assert client._base_url == custom_url


# ===========================================================================
# TestGetCategories
# ===========================================================================


class TestGetCategories:
    @pytest.mark.asyncio
    @respx.mock
    async def test_correct_url(self, categories_response: dict[str, Any]) -> None:
        """get_categories sends the correct URL for the TEMAS_BALEARS category scheme."""
        route = respx.get(
            f"{STRUCTURAL_BASE_URL}/categoryschemes/IBESTAT/TEMAS_BALEARS/~latest/categories"
        ).mock(return_value=httpx.Response(200, json=categories_response))

        async with IbestatClient() as client:
            result = await client.get_categories()

        assert route.called
        assert result["total"] == 4


# ===========================================================================
# TestGetCodelistCodes
# ===========================================================================


class TestGetCodelistCodes:
    @pytest.mark.asyncio
    @respx.mock
    async def test_correct_url_and_pagination(
        self, codelist_codes_response: dict[str, Any]
    ) -> None:
        """get_codelist_codes sends the correct URL with limit/offset params."""
        route = respx.get(
            f"{STRUCTURAL_BASE_URL}/codelists/IBESTAT/CL_AREA_ES53/~latest/codes"
        ).mock(return_value=httpx.Response(200, json=codelist_codes_response))

        async with IbestatClient() as client:
            result = await client.get_codelist_codes("CL_AREA_ES53", limit=50, offset=10)

        assert route.called
        request = route.calls[0].request
        url_decoded = urllib.parse.unquote_plus(str(request.url))
        assert "limit=50" in url_decoded
        assert "offset=10" in url_decoded


# ===========================================================================
# TestGetDataStructure
# ===========================================================================


class TestGetDataStructure:
    @pytest.mark.asyncio
    @respx.mock
    async def test_correct_url(self, data_structure_response: dict[str, Any]) -> None:
        """get_data_structure sends the correct URL for a DSD."""
        route = respx.get(
            f"{STRUCTURAL_BASE_URL}/datastructures/IBESTAT/DSD_000001A_000001/~latest"
        ).mock(return_value=httpx.Response(200, json=data_structure_response))

        async with IbestatClient() as client:
            result = await client.get_data_structure("DSD_000001A_000001")

        assert route.called
        assert result["id"] == "DSD_000001A_000001"
