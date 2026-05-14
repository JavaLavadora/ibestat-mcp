"""Async HTTP client for the IBESTAT eDades statistical-resources API.

Provides ``IbestatClient``, a thin async wrapper around the IBESTAT eDades
API that returns raw JSON responses for downstream parsing.

Usage::

    async with IbestatClient() as client:
        datasets = await client.search_datasets("poblaci")
        data = await client.get_dataset_data("000001A_000001",
                                              filters={"TIME_PERIOD": "2024"})
"""

from __future__ import annotations

from typing import Any

import httpx

BASE_URL = "https://ibestat.es/edatos/apis/statistical-resources/v1.0"
STRUCTURAL_BASE_URL = "https://ibestat.es/edatos/apis/structural-resources/v1.0"
TIMEOUT = 30.0


class IbestatError(Exception):
    """Raised for IBESTAT API errors (not-found, timeouts, connectivity)."""


class IbestatClient:
    """Async client for the IBESTAT eDades statistical-resources API.

    Must be used as an async context manager::

        async with IbestatClient() as client:
            result = await client.search_datasets("poblaci")
    """

    def __init__(
        self,
        base_url: str = BASE_URL,
        structural_base_url: str = STRUCTURAL_BASE_URL,
    ) -> None:
        self._base_url = base_url
        self._structural_base_url = structural_base_url
        self._http: httpx.AsyncClient | None = None

    async def __aenter__(self) -> IbestatClient:
        self._http = httpx.AsyncClient(timeout=TIMEOUT)
        return self

    async def __aexit__(self, *args: Any) -> None:
        if self._http:
            await self._http.aclose()
            self._http = None

    def _client(self) -> httpx.AsyncClient:
        if self._http is None:
            raise RuntimeError("Use IbestatClient as an async context manager")
        return self._http

    async def _get(
        self, url: str, params: list[tuple[str, str]] | None = None
    ) -> dict[str, Any]:
        """Send a GET request, always appending ``_type=json``.

        Parameters
        ----------
        url:
            The full URL to request.
        params:
            Optional query parameters as a list of (key, value) tuples.
            A list is used (rather than a dict) to support repeated keys
            such as ``dim=...``.

        Returns
        -------
        dict[str, Any]
            The parsed JSON response body.

        Raises
        ------
        IbestatError
            On 404, connection timeout, read timeout, or connection error.
        """
        all_params: list[tuple[str, str]] = [("_type", "json")]
        if params:
            all_params.extend(params)
        try:
            response = await self._client().get(url, params=all_params)
        except (httpx.TimeoutException, httpx.NetworkError):
            raise IbestatError(
                "IBESTAT service is unavailable. Please try again later."
            )
        if response.status_code == 404:
            raise IbestatError(f"Dataset not found: {url}")
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as e:
            raise IbestatError(f"IBESTAT API error ({response.status_code}): {e}") from e
        return response.json()

    async def search_datasets(self, query: str, limit: int = 10) -> dict[str, Any]:
        """Search for datasets by name.

        Parameters
        ----------
        query:
            Search term applied with ``ILIKE`` matching against dataset names.
        limit:
            Maximum number of results to return (default 10).

        Returns
        -------
        dict[str, Any]
            Raw API response containing ``dataset`` list, ``total``, etc.
        """
        return await self._get(
            f"{self._base_url}/datasets",
            params=[
                ("query", f"name ILIKE '{query}'"),
                ("limit", str(limit)),
            ],
        )

    async def get_dataset_metadata(self, dataset_id: str) -> dict[str, Any]:
        """Fetch full dataset response (metadata + data) for a given ID.

        Parameters
        ----------
        dataset_id:
            The dataset identifier (e.g. ``"000001A_000001"``).

        Returns
        -------
        dict[str, Any]
            Raw API response including ``metadata`` and ``data`` sections.
        """
        return await self._get(
            f"{self._base_url}/datasets/IBESTAT/{dataset_id}/~latest",
        )

    async def get_dataset_data(
        self,
        dataset_id: str,
        filters: dict[str, str | list[str]] | None = None,
    ) -> dict[str, Any]:
        """Fetch dataset data, optionally filtered by dimension values.

        Does NOT strip metadata (``fields=-metadata``) because dimension
        labels only exist in the metadata section and are needed for the
        parser to resolve human-readable names.

        Parameters
        ----------
        dataset_id:
            The dataset identifier (e.g. ``"000001A_000001"``).
        filters:
            Optional dimension filters as ``{dim_id: value_or_values}``.
            A single string value or a list of string values can be provided
            per dimension.  Lists are joined with ``|`` (pipe) to match the
            API's multi-value syntax.

        Returns
        -------
        dict[str, Any]
            Raw API response including ``metadata`` and ``data`` sections.
        """
        params: list[tuple[str, str]] = []
        if filters:
            for dim_id, values in filters.items():
                if isinstance(values, list):
                    joined = "|".join(values)
                    params.append(("dim", f"{dim_id}:{joined}"))
                else:
                    params.append(("dim", f"{dim_id}:{values}"))
        # Do NOT use fields=-metadata — we need metadata for dimension labels
        return await self._get(
            f"{self._base_url}/datasets/IBESTAT/{dataset_id}/~latest",
            params=params,
        )

    # ------------------------------------------------------------------
    # Structural-resources API
    # ------------------------------------------------------------------

    async def get_categories(self) -> dict[str, Any]:
        """Fetch the IBESTAT thematic category tree.

        Returns the full list of categories from the TEMAS_BALEARS
        category scheme.

        Returns
        -------
        dict[str, Any]
            Raw API response containing ``category`` list, ``total``, etc.
        """
        return await self._get(
            f"{self._structural_base_url}/categoryschemes/IBESTAT/TEMAS_BALEARS/~latest/categories",
        )

    async def get_codelist_codes(
        self, codelist_id: str, limit: int = 100, offset: int = 0
    ) -> dict[str, Any]:
        """Fetch codes from a given codelist.

        Parameters
        ----------
        codelist_id:
            The codelist identifier (e.g. ``"CL_AREA_ES53"``).
        limit:
            Maximum number of codes to return (default 100).
        offset:
            Pagination offset (default 0).

        Returns
        -------
        dict[str, Any]
            Raw API response containing ``code`` list, ``total``, etc.
        """
        return await self._get(
            f"{self._structural_base_url}/codelists/IBESTAT/{codelist_id}/~latest/codes",
            params=[("limit", str(limit)), ("offset", str(offset))],
        )

    async def get_data_structure(self, dsd_id: str) -> dict[str, Any]:
        """Fetch a Data Structure Definition (DSD).

        Parameters
        ----------
        dsd_id:
            The DSD identifier (e.g. ``"DSD_000001A_00001"``).

        Returns
        -------
        dict[str, Any]
            Raw API response with ``dataStructureComponents``, dimensions, etc.
        """
        return await self._get(
            f"{self._structural_base_url}/datastructures/IBESTAT/{dsd_id}/~latest",
        )
