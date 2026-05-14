"""Tests for ibestat_mcp.tools module."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

import pytest

from ibestat_mcp.cache import SemanticCache
from ibestat_mcp.models import CodelistResult, DatasetInfo, DatasetSummary, TopicDatasets, TopicTree
from ibestat_mcp.tools import browse_topics, get_codelist, get_data, get_dataset_info, list_datasets_by_topic, search_datasets


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


# ===========================================================================
# Language parameter threading tests
# ===========================================================================


def _intl_multilingual(ca: str, es: str, en: str = "") -> dict[str, Any]:
    """Build an InternationalString with all three languages."""
    texts = [{"value": ca, "lang": "ca"}, {"value": es, "lang": "es"}]
    if en:
        texts.append({"value": en, "lang": "en"})
    return {"text": texts}


def _make_multilingual_search_response() -> dict[str, Any]:
    """Build a search response with multilingual dataset names."""
    return {
        "kind": "statisticalResources#datasets",
        "dataset": [
            {
                "id": "DS_001",
                "kind": "statisticalResources#dataset",
                "name": _intl_multilingual(
                    "Poblacio total", "Poblacion total", "Total population"
                ),
                "description": _intl_multilingual(
                    "Dades de poblacio", "Datos de poblacion", "Population data"
                ),
                "selfLink": {
                    "kind": "statisticalResources#dataset",
                    "href": "https://example.com",
                },
                "urn": "urn:test",
                "visualizerHtmlLink": "https://example.com/viz",
            },
        ],
        "total": 1,
        "limit": 10,
        "offset": 0,
        "selfLink": "https://example.com",
        "lastLink": "https://example.com",
    }


def _make_multilingual_metadata_response() -> dict[str, Any]:
    """Build a metadata response with multilingual dimension labels."""
    return {
        "id": "TEST_LANG",
        "name": _intl_multilingual("Poblacio municipal", "Poblacion municipal", "Municipal population"),
        "metadata": {
            "dimensions": {
                "dimension": [
                    {
                        "id": "TERRITORIO",
                        "name": _intl_multilingual("Territori", "Territorio", "Reference area"),
                        "type": "GEOGRAPHIC_DIMENSION",
                        "dimensionValues": {
                            "value": [
                                {
                                    "id": "07001",
                                    "name": _intl_multilingual("Palma", "Palma", "Palma"),
                                },
                            ],
                            "total": 1,
                        },
                    },
                ]
            },
        },
    }


def _make_multilingual_data_response() -> dict[str, Any]:
    """Build a data response with multilingual labels."""
    return {
        "id": "TEST_LANG",
        "name": _intl_multilingual("Test CA", "Test ES", "Test EN"),
        "metadata": {
            "dimensions": {
                "dimension": [
                    {
                        "id": "TERRITORIO",
                        "name": _intl_multilingual("Territori", "Territorio", "Reference area"),
                        "type": "GEOGRAPHIC_DIMENSION",
                        "dimensionValues": {
                            "value": [
                                {
                                    "id": "07001",
                                    "name": _intl_multilingual("Palma", "Palma", "Palma"),
                                },
                            ],
                            "total": 1,
                        },
                    },
                    {
                        "id": "MEDIDAS",
                        "name": _intl_multilingual("Mesures", "Medidas", "Measures"),
                        "type": "MEASURE_DIMENSION",
                        "dimensionValues": {
                            "value": [
                                {
                                    "id": "POP",
                                    "name": _intl_multilingual("Poblacio", "Poblacion", "Population"),
                                },
                            ],
                            "total": 1,
                        },
                    },
                ]
            },
        },
        "data": {
            "dimensions": {
                "dimension": [
                    {
                        "dimensionId": "TERRITORIO",
                        "representations": {
                            "representation": [{"code": "07001", "index": 0}],
                            "total": 1,
                        },
                    },
                    {
                        "dimensionId": "MEDIDAS",
                        "representations": {
                            "representation": [{"code": "POP", "index": 0}],
                            "total": 1,
                        },
                    },
                ]
            },
            "observations": "500",
        },
    }


class TestSearchDatasetsLanguage:
    @pytest.mark.asyncio
    async def test_spanish_labels(self) -> None:
        """search_datasets with lang='es' returns Spanish names."""
        client = AsyncMock()
        client.search_datasets.return_value = _make_multilingual_search_response()

        result = await search_datasets(client, "poblaci", lang="es")

        assert result[0].name == "Poblacion total"
        assert result[0].description == "Datos de poblacion"

    @pytest.mark.asyncio
    async def test_english_labels(self) -> None:
        """search_datasets with lang='en' returns English names."""
        client = AsyncMock()
        client.search_datasets.return_value = _make_multilingual_search_response()

        result = await search_datasets(client, "poblaci", lang="en")

        assert result[0].name == "Total population"
        assert result[0].description == "Population data"

    @pytest.mark.asyncio
    async def test_catalan_default(self) -> None:
        """search_datasets defaults to Catalan labels."""
        client = AsyncMock()
        client.search_datasets.return_value = _make_multilingual_search_response()

        result = await search_datasets(client, "poblaci")

        assert result[0].name == "Poblacio total"


class TestGetDatasetInfoLanguage:
    @pytest.mark.asyncio
    async def test_spanish_labels(self) -> None:
        """get_dataset_info with lang='es' returns Spanish labels."""
        client = AsyncMock()
        client.get_dataset_metadata.return_value = _make_multilingual_metadata_response()

        result = await get_dataset_info(client, "TEST_LANG", lang="es")

        assert result.name == "Poblacion municipal"
        assert result.dimensions[0].name == "Territorio"

    @pytest.mark.asyncio
    async def test_english_labels(self) -> None:
        """get_dataset_info with lang='en' returns English labels."""
        client = AsyncMock()
        client.get_dataset_metadata.return_value = _make_multilingual_metadata_response()

        result = await get_dataset_info(client, "TEST_LANG", lang="en")

        assert result.name == "Municipal population"
        assert result.dimensions[0].name == "Reference area"


class TestGetDataLanguage:
    @pytest.mark.asyncio
    async def test_spanish_labels(self) -> None:
        """get_data with lang='es' returns rows with Spanish column names."""
        client = AsyncMock()
        client.get_dataset_data.return_value = _make_multilingual_data_response()

        result = await get_data(client, "TEST_LANG", lang="es")

        assert result[0] == {"Territorio": "Palma", "Poblacion": 500}

    @pytest.mark.asyncio
    async def test_english_labels(self) -> None:
        """get_data with lang='en' returns rows with English column names."""
        client = AsyncMock()
        client.get_dataset_data.return_value = _make_multilingual_data_response()

        result = await get_data(client, "TEST_LANG", lang="en")

        assert result[0] == {"Reference area": "Palma", "Population": 500}


# ===========================================================================
# TestBrowseTopics
# ===========================================================================


class TestBrowseTopics:
    @pytest.mark.asyncio
    async def test_returns_topic_tree(self, categories_response: dict[str, Any]) -> None:
        client = AsyncMock()
        client.get_categories.return_value = categories_response
        test_cache = SemanticCache()

        result = await browse_topics(client, lang="ca", _cache=test_cache)

        assert isinstance(result, TopicTree)
        assert result.name == "TEMAS_BALEARS"
        assert len(result.categories) == 4

    @pytest.mark.asyncio
    async def test_uses_cache_on_second_call(self, categories_response: dict[str, Any]) -> None:
        client = AsyncMock()
        client.get_categories.return_value = categories_response
        test_cache = SemanticCache()

        await browse_topics(client, lang="ca", _cache=test_cache)
        await browse_topics(client, lang="ca", _cache=test_cache)

        assert client.get_categories.call_count == 1

    @pytest.mark.asyncio
    async def test_different_language_refetches(self, categories_response: dict[str, Any]) -> None:
        client = AsyncMock()
        client.get_categories.return_value = categories_response
        test_cache = SemanticCache()

        await browse_topics(client, lang="ca", _cache=test_cache)
        await browse_topics(client, lang="es", _cache=test_cache)

        assert client.get_categories.call_count == 2


# ===========================================================================
# TestGetCodelist
# ===========================================================================


class TestGetCodelist:
    @pytest.mark.asyncio
    async def test_returns_codelist_result(self, codelist_codes_response: dict[str, Any]) -> None:
        client = AsyncMock()
        client.get_codelist_codes.return_value = codelist_codes_response
        test_cache = SemanticCache()

        result = await get_codelist(client, "CL_AREA_ES53", lang="ca", _cache=test_cache)

        assert isinstance(result, CodelistResult)
        assert result.id == "CL_AREA_ES53"
        assert result.total == 3

    @pytest.mark.asyncio
    async def test_uses_cache_on_second_call(self, codelist_codes_response: dict[str, Any]) -> None:
        client = AsyncMock()
        client.get_codelist_codes.return_value = codelist_codes_response
        test_cache = SemanticCache()

        await get_codelist(client, "CL_AREA_ES53", lang="ca", _cache=test_cache)
        await get_codelist(client, "CL_AREA_ES53", lang="ca", _cache=test_cache)

        assert client.get_codelist_codes.call_count == 1

    @pytest.mark.asyncio
    async def test_different_pagination_refetches(self, codelist_codes_response: dict[str, Any]) -> None:
        client = AsyncMock()
        client.get_codelist_codes.return_value = codelist_codes_response
        test_cache = SemanticCache()

        await get_codelist(client, "CL_AREA_ES53", limit=100, offset=0, lang="ca", _cache=test_cache)
        await get_codelist(client, "CL_AREA_ES53", limit=100, offset=100, lang="ca", _cache=test_cache)

        assert client.get_codelist_codes.call_count == 2

    @pytest.mark.asyncio
    async def test_hierarchy_preserved(self, codelist_codes_response: dict[str, Any]) -> None:
        client = AsyncMock()
        client.get_codelist_codes.return_value = codelist_codes_response
        test_cache = SemanticCache()

        result = await get_codelist(client, "CL_AREA_ES53", lang="ca", _cache=test_cache)

        palma = next(c for c in result.codes if c.code == "07040")
        assert palma.parent_code == "07"


# ===========================================================================
# TestGetDatasetInfoCodelistId
# ===========================================================================


class TestGetDatasetInfoCodelistId:
    @pytest.mark.asyncio
    async def test_includes_codelist_id(
        self,
        dataset_metadata_response: dict[str, Any],
        data_structure_response: dict[str, Any],
    ) -> None:
        client = AsyncMock()
        client.get_dataset_metadata.return_value = dataset_metadata_response
        client.get_data_structure.return_value = data_structure_response
        test_cache = SemanticCache()

        result = await get_dataset_info(client, "000001A_000001", lang="ca", _cache=test_cache)

        territorio = next(d for d in result.dimensions if d.id == "TERRITORIO")
        assert territorio.codelist_id == "CL_AREA_ES53"

    @pytest.mark.asyncio
    async def test_no_codelist_for_time(
        self,
        dataset_metadata_response: dict[str, Any],
        data_structure_response: dict[str, Any],
    ) -> None:
        client = AsyncMock()
        client.get_dataset_metadata.return_value = dataset_metadata_response
        client.get_data_structure.return_value = data_structure_response
        test_cache = SemanticCache()

        result = await get_dataset_info(client, "000001A_000001", lang="ca", _cache=test_cache)

        time_dim = next(d for d in result.dimensions if d.id == "TIME_PERIOD")
        assert time_dim.codelist_id is None

    @pytest.mark.asyncio
    async def test_caches_dsd_map(
        self,
        dataset_metadata_response: dict[str, Any],
        data_structure_response: dict[str, Any],
    ) -> None:
        client = AsyncMock()
        client.get_dataset_metadata.return_value = dataset_metadata_response
        client.get_data_structure.return_value = data_structure_response
        test_cache = SemanticCache()

        await get_dataset_info(client, "000001A_000001", lang="ca", _cache=test_cache)
        await get_dataset_info(client, "000001A_000001", lang="ca", _cache=test_cache)

        assert client.get_data_structure.call_count == 1

    @pytest.mark.asyncio
    async def test_graceful_fallback_on_dsd_error(self) -> None:
        client = AsyncMock()
        client.get_dataset_metadata.return_value = _make_metadata_response(
            name_ca="Test dataset"
        )
        client.get_data_structure.side_effect = Exception("not found")
        test_cache = SemanticCache()

        result = await get_dataset_info(client, "TEST_001", lang="ca", _cache=test_cache)

        assert len(result.dimensions) > 0
        assert all(d.codelist_id is None for d in result.dimensions)


# ===========================================================================
# TestListDatasetsByTopic
# ===========================================================================


class TestListDatasetsByTopic:
    def _make_topic_tree(self) -> TopicTree:
        from ibestat_mcp.models import Category
        return TopicTree(
            name="TEMAS_BALEARS",
            categories=[
                Category(id="010", name="Demografia", parent_id=None, nested_id="010"),
                Category(id="010_010", name="Poblacio", parent_id="010", nested_id="010.010_010"),
                Category(id="010_020", name="Natalitat", parent_id="010", nested_id="010.010_020"),
                Category(id="020", name="Economia", parent_id=None, nested_id="020"),
                Category(id="020_010", name="Mercat de treball", parent_id="020", nested_id="020.020_010"),
            ],
        )

    def _make_operations_response(self, op_ids: list[str]) -> dict[str, Any]:
        return {
            "operation": [
                {
                    "id": op_id,
                    "urn": f"urn:siemac:org.siemac.metamac.infomodel.statisticaloperations.Operation={op_id}",
                }
                for op_id in op_ids
            ],
            "total": len(op_ids),
        }

    def _make_datasets_response(self, datasets: list[tuple[str, str]]) -> dict[str, Any]:
        return {
            "dataset": [
                {
                    "id": ds_id,
                    "name": {"text": [{"value": name, "lang": "ca"}]},
                    "visualizerHtmlLink": f"https://ibestat.es/viz/{ds_id}",
                }
                for ds_id, name in datasets
            ],
            "total": len(datasets),
        }

    @pytest.mark.asyncio
    async def test_returns_datasets_for_leaf_category(self) -> None:
        client = AsyncMock()
        client.get_categories.return_value = {"category": []}
        client.get_operations_by_subject.return_value = self._make_operations_response(["OP1"])
        client.get_datasets_by_operation.return_value = self._make_datasets_response([
            ("DS1", "Dataset uno"),
            ("DS2", "Dataset dos"),
        ])
        test_cache = SemanticCache()
        test_cache.set_topics("ca", self._make_topic_tree())

        result = await list_datasets_by_topic(client, "010_010", lang="ca", _cache=test_cache)

        assert isinstance(result, TopicDatasets)
        assert result.category_id == "010_010"
        assert result.total == 2
        assert result.datasets[0].id == "DS1"
        assert result.datasets[1].id == "DS2"

    @pytest.mark.asyncio
    async def test_parent_category_queries_all_children(self) -> None:
        client = AsyncMock()
        client.get_categories.return_value = {"category": []}
        client.get_operations_by_subject.return_value = self._make_operations_response(["OP1"])
        client.get_datasets_by_operation.return_value = self._make_datasets_response([
            ("DS1", "Dataset uno"),
        ])
        test_cache = SemanticCache()
        test_cache.set_topics("ca", self._make_topic_tree())

        result = await list_datasets_by_topic(client, "010", lang="ca", _cache=test_cache)

        assert client.get_operations_by_subject.call_count == 2
        call_args = [c.args[0] for c in client.get_operations_by_subject.call_args_list]
        assert "010.010_010" in call_args
        assert "010.010_020" in call_args

    @pytest.mark.asyncio
    async def test_deduplicates_datasets(self) -> None:
        client = AsyncMock()
        client.get_categories.return_value = {"category": []}
        client.get_operations_by_subject.return_value = self._make_operations_response(["OP1", "OP2"])
        client.get_datasets_by_operation.side_effect = [
            self._make_datasets_response([("DS1", "Dataset uno")]),
            self._make_datasets_response([("DS1", "Dataset uno"), ("DS2", "Dataset dos")]),
        ]
        test_cache = SemanticCache()
        test_cache.set_topics("ca", self._make_topic_tree())

        result = await list_datasets_by_topic(client, "010_010", lang="ca", _cache=test_cache)

        assert result.total == 2
        ids = [d.id for d in result.datasets]
        assert ids == ["DS1", "DS2"]

    @pytest.mark.asyncio
    async def test_uses_cache_on_second_call(self) -> None:
        client = AsyncMock()
        client.get_categories.return_value = {"category": []}
        client.get_operations_by_subject.return_value = self._make_operations_response(["OP1"])
        client.get_datasets_by_operation.return_value = self._make_datasets_response([
            ("DS1", "Dataset uno"),
        ])
        test_cache = SemanticCache()
        test_cache.set_topics("ca", self._make_topic_tree())

        await list_datasets_by_topic(client, "010_010", lang="ca", _cache=test_cache)
        await list_datasets_by_topic(client, "010_010", lang="ca", _cache=test_cache)

        assert client.get_operations_by_subject.call_count == 1

    @pytest.mark.asyncio
    async def test_category_not_found_raises(self) -> None:
        from ibestat_mcp.client import IbestatError

        client = AsyncMock()
        client.get_categories.return_value = {"category": []}
        test_cache = SemanticCache()
        test_cache.set_topics("ca", self._make_topic_tree())

        with pytest.raises(IbestatError, match="Category 'INVALID' not found"):
            await list_datasets_by_topic(client, "INVALID", lang="ca", _cache=test_cache)

    @pytest.mark.asyncio
    async def test_empty_operations_returns_empty(self) -> None:
        client = AsyncMock()
        client.get_categories.return_value = {"category": []}
        client.get_operations_by_subject.return_value = self._make_operations_response([])
        test_cache = SemanticCache()
        test_cache.set_topics("ca", self._make_topic_tree())

        result = await list_datasets_by_topic(client, "010_010", lang="ca", _cache=test_cache)

        assert result.total == 0
        assert result.datasets == []

    @pytest.mark.asyncio
    async def test_note_field_present(self) -> None:
        client = AsyncMock()
        client.get_categories.return_value = {"category": []}
        client.get_operations_by_subject.return_value = self._make_operations_response(["OP1"])
        client.get_datasets_by_operation.return_value = self._make_datasets_response([
            ("DS1", "Dataset uno"),
        ])
        test_cache = SemanticCache()
        test_cache.set_topics("ca", self._make_topic_tree())

        result = await list_datasets_by_topic(client, "010_010", lang="ca", _cache=test_cache)

        assert "cache" in result.note.lower() or "first call" in result.note.lower()
