"""Tests for ibestat_mcp.client module."""

from __future__ import annotations

import ssl
import urllib.parse
from typing import Any

import httpx
import pytest
import respx

from ibestat_mcp.client import BASE_URL, STRUCTURAL_BASE_URL, OPERATIONS_BASE_URL, IbestatClient, IbestatError


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
# TestResolveSslVerify
# ===========================================================================


class TestResolveSslVerify:
    """_resolve_ssl_verify lets a custom CA bundle be configured via env vars.

    Behind a TLS-inspecting corporate proxy (or a sandboxed dev environment
    with its own intercepting root CA), httpx's default certifi bundle
    fails verification even though curl/OpenSSL accept the connection via
    the system trust store. These tests guard the env-var override that
    fixes that without changing default behaviour.
    """

    @pytest.mark.parametrize(
        "env_var",
        ["SSL_CERT_FILE", "REQUESTS_CA_BUNDLE", "CURL_CA_BUNDLE", "NODE_EXTRA_CA_CERTS"],
    )
    def test_returns_ssl_context_when_env_var_set(
        self, monkeypatch: pytest.MonkeyPatch, env_var: str
    ) -> None:
        """Each supported env var, if set, yields an SSLContext (not a bare str)."""
        from ibestat_mcp.client import _resolve_ssl_verify

        monkeypatch.setenv(env_var, certifi_bundle_path())
        result = _resolve_ssl_verify()
        assert isinstance(result, ssl.SSLContext)

    def test_returns_true_when_no_env_var_set(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """With none of the supported env vars set, default certifi verification applies."""
        from ibestat_mcp.client import _resolve_ssl_verify

        for env_var in (
            "SSL_CERT_FILE",
            "REQUESTS_CA_BUNDLE",
            "CURL_CA_BUNDLE",
            "NODE_EXTRA_CA_CERTS",
        ):
            monkeypatch.delenv(env_var, raising=False)
        assert _resolve_ssl_verify() is True

    def test_priority_order(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """SSL_CERT_FILE takes priority over the other env vars."""
        from ibestat_mcp.client import _resolve_ssl_verify

        bundle = certifi_bundle_path()
        monkeypatch.setenv("SSL_CERT_FILE", bundle)
        monkeypatch.setenv("NODE_EXTRA_CA_CERTS", "/does/not/exist.pem")
        # Should not raise even though NODE_EXTRA_CA_CERTS points nowhere,
        # because SSL_CERT_FILE (a valid file) is checked first.
        result = _resolve_ssl_verify()
        assert isinstance(result, ssl.SSLContext)


def certifi_bundle_path() -> str:
    """Return a real, existing PEM file path to use as a stand-in CA bundle."""
    import certifi

    return certifi.where()


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


# ===========================================================================
# TestGetOperationsBySubject
# ===========================================================================


class TestGetOperationsBySubject:
    @pytest.mark.asyncio
    @respx.mock
    async def test_queries_operations_api(self, operations_response: dict[str, Any]) -> None:
        route = respx.get(f"{OPERATIONS_BASE_URL}/operations").respond(
            json=operations_response
        )

        async with IbestatClient() as client:
            result = await client.get_operations_by_subject("010.010_010")

        assert route.called
        request = route.calls[0].request
        assert "SUBJECT_AREA_URN" in str(request.url)
        assert "010.010_010" in str(request.url)
        assert len(result["operation"]) == 2

    @pytest.mark.asyncio
    @respx.mock
    async def test_pagination_params(self, operations_response: dict[str, Any]) -> None:
        route = respx.get(f"{OPERATIONS_BASE_URL}/operations").respond(
            json=operations_response
        )

        async with IbestatClient() as client:
            await client.get_operations_by_subject("010.010_010", limit=5, offset=10)

        request = route.calls[0].request
        assert "limit=5" in str(request.url)
        assert "offset=10" in str(request.url)


# ===========================================================================
# TestGetDatasetsByOperation
# ===========================================================================


class TestGetDatasetsByOperation:
    @pytest.mark.asyncio
    @respx.mock
    async def test_queries_datasets_with_operation_urn(
        self, datasets_by_operation_response: dict[str, Any]
    ) -> None:
        route = respx.get(f"{BASE_URL}/datasets").respond(
            json=datasets_by_operation_response
        )

        async with IbestatClient() as client:
            result = await client.get_datasets_by_operation("000001A")

        assert route.called
        request = route.calls[0].request
        assert "STATISTICAL_OPERATION_URN" in str(request.url)
        assert "000001A" in str(request.url)
        assert len(result["dataset"]) == 2

    @pytest.mark.asyncio
    @respx.mock
    async def test_limit_param(self, datasets_by_operation_response: dict[str, Any]) -> None:
        route = respx.get(f"{BASE_URL}/datasets").respond(
            json=datasets_by_operation_response
        )

        async with IbestatClient() as client:
            await client.get_datasets_by_operation("000001A", limit=50)

        request = route.calls[0].request
        assert "limit=50" in str(request.url)
