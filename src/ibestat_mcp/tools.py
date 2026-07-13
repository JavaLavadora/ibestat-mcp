"""MCP tool functions that wire the IBESTAT client and parser together.

Each function takes an ``IbestatClient`` as its first argument and returns
parsed, structured data ready for MCP server responses.  All functions accept
a ``lang`` parameter to select the language for data labels (``"ca"``,
``"es"``, or ``"en"``).
"""

from __future__ import annotations

import logging

from ibestat_mcp.cache import SemanticCache, cache as _default_cache
from ibestat_mcp.client import IbestatClient
from ibestat_mcp.models import (
    CodelistResult, DataRow, DatasetInfo, DatasetSummary,
    TopicDatasets, TopicTree,
)
from ibestat_mcp.parser import extract_localized_text, parse_dimensions, parse_observations
from ibestat_mcp.structural_parser import (
    extract_codelist_ids_from_dsd,
    parse_categories,
    parse_codelist_codes,
)

logger = logging.getLogger(__name__)


async def search_datasets(
    client: IbestatClient,
    query: str,
    limit: int = 10,
    lang: str = "ca",
) -> list[DatasetSummary]:
    """Search for datasets by name and return deduplicated summaries.

    Parameters
    ----------
    client:
        An initialised IBESTAT API client.
    query:
        Search term applied against dataset names.
    limit:
        Maximum number of results to return.
    lang:
        Language code for labels (``"ca"``, ``"es"``, or ``"en"``).

    Returns
    -------
    list[DatasetSummary]
        Deduplicated list of dataset summaries with localized names.
    """
    response = await client.search_datasets(query, limit)
    entries = response.get("dataset", [])

    seen: set[str] = set()
    results: list[DatasetSummary] = []

    for entry in entries:
        ds_id = entry["id"]
        if ds_id in seen:
            continue
        seen.add(ds_id)

        name = extract_localized_text(entry.get("name"), lang)
        description_field = entry.get("description")
        description_raw = (
            extract_localized_text(description_field, lang)
            if description_field is not None
            else None
        )
        description = description_raw or None
        link = entry.get("visualizerHtmlLink", "")

        results.append(
            DatasetSummary(
                id=ds_id,
                name=name,
                description=description,
                link=link,
            )
        )

    return results


async def get_dataset_info(
    client: IbestatClient,
    dataset_id: str,
    lang: str = "ca",
    _cache: SemanticCache | None = None,
) -> DatasetInfo:
    """Fetch dataset metadata and return structured dimension info.

    Parameters
    ----------
    client:
        An initialised IBESTAT API client.
    dataset_id:
        The dataset identifier (e.g. ``"000001A_000001"``).
    lang:
        Language code for labels (``"ca"``, ``"es"``, or ``"en"``).
    _cache:
        Optional cache override for testing.

    Returns
    -------
    DatasetInfo
        Dataset name and parsed dimension information in the requested language.
        Each dimension includes ``codelist_id`` when a DSD mapping is available.
    """
    c = _cache or _default_cache
    response = await client.get_dataset_metadata(dataset_id)
    name = extract_localized_text(response.get("name"), lang)
    dimensions = parse_dimensions(response, lang)

    codelist_map = c.get_dsd_codelist_map(dataset_id)
    if codelist_map is None:
        try:
            related_dsd = response.get("metadata", {}).get("relatedDsd", {})
            dsd_id = related_dsd.get("id")
            if dsd_id:
                dsd_response = await client.get_data_structure(dsd_id)
                codelist_map = extract_codelist_ids_from_dsd(dsd_response)
                c.set_dsd_codelist_map(dataset_id, codelist_map)
        except Exception:
            logger.debug("DSD lookup failed for %s", dataset_id, exc_info=True)
            codelist_map = {}

    if codelist_map is None:
        codelist_map = {}

    for dim in dimensions:
        dim.codelist_id = codelist_map.get(dim.id)

    return DatasetInfo(name=name, dimensions=dimensions)


async def get_data(
    client: IbestatClient,
    dataset_id: str,
    filters: dict[str, str | list[str]] | None = None,
    lang: str = "ca",
) -> list[DataRow]:
    """Fetch dataset observations and return flat row dictionaries.

    Parameters
    ----------
    client:
        An initialised IBESTAT API client.
    dataset_id:
        The dataset identifier (e.g. ``"000001A_000001"``).
    filters:
        Optional dimension filters as ``{dim_id: value_or_values}``.
    lang:
        Language code for labels (``"ca"``, ``"es"``, or ``"en"``).

    Returns
    -------
    list[DataRow]
        Flat row dictionaries with localized labels, MEDIDAS pivoted into
        columns.
    """
    response = await client.get_dataset_data(dataset_id, filters=filters)
    return parse_observations(response, lang, filters=filters)


async def browse_topics(
    client: IbestatClient,
    lang: str = "ca",
    _cache: SemanticCache | None = None,
) -> TopicTree:
    """Fetch the IBESTAT thematic topic tree.

    Returns a flat list of categories with parent references, representing
    the TEMAS_BALEARS category scheme.  Cached after first call.

    Parameters
    ----------
    client:
        An initialised IBESTAT API client.
    lang:
        Language code for labels (``"ca"``, ``"es"``, or ``"en"``).
    _cache:
        Optional cache override for testing.

    Returns
    -------
    TopicTree
        Category scheme name and flat list of categories.
    """
    c = _cache or _default_cache
    cached = c.get_topics(lang)
    if cached is not None:
        return cached
    response = await client.get_categories()
    categories = parse_categories(response, lang)
    tree = TopicTree(name="TEMAS_BALEARS", categories=categories)
    c.set_topics(lang, tree)
    return tree


async def get_codelist(
    client: IbestatClient,
    codelist_id: str,
    limit: int = 100,
    offset: int = 0,
    lang: str = "ca",
    _cache: SemanticCache | None = None,
) -> CodelistResult:
    """Fetch codes from a codelist with hierarchical parent-child relationships.

    Use the ``codelist_id`` from ``get_dataset_info`` to explore valid filter
    values at all hierarchy levels.  Cached after first call per codelist.

    Parameters
    ----------
    client:
        An initialised IBESTAT API client.
    codelist_id:
        Codelist identifier (e.g. ``"CL_AREA_ES53"``).
    limit:
        Maximum number of codes to return.
    offset:
        Pagination offset.
    lang:
        Language code for labels (``"ca"``, ``"es"``, or ``"en"``).
    _cache:
        Optional cache override for testing.

    Returns
    -------
    CodelistResult
        Codelist ID, name, total count, and list of code entries.
    """
    c = _cache or _default_cache
    cached = c.get_codelist(codelist_id, limit, offset, lang)
    if cached is not None:
        return cached
    response = await client.get_codelist_codes(codelist_id, limit=limit, offset=offset)
    codes = parse_codelist_codes(response, lang)
    total = response.get("total", len(codes))
    name = extract_localized_text(response.get("name"), lang) or codelist_id
    result = CodelistResult(id=codelist_id, name=name, total=total, codes=codes)
    c.set_codelist(codelist_id, limit, offset, lang, result)
    return result


async def list_datasets_by_topic(
    client: IbestatClient,
    category_id: str,
    lang: str = "ca",
    _cache: SemanticCache | None = None,
) -> TopicDatasets:
    """List all datasets under an IBESTAT thematic category.

    Resolves category -> operations -> datasets via the IBESTAT Operations
    API.  For parent categories, all leaf children are queried and results
    are merged.  Results are cached per ``(category_id, lang)``.

    Parameters
    ----------
    client:
        An initialised IBESTAT API client.
    category_id:
        Category ID from ``browse_topics`` (e.g. ``"010_010"``).
    lang:
        Language code for labels (``"ca"``, ``"es"``, or ``"en"``).
    _cache:
        Optional cache override for testing.

    Returns
    -------
    TopicDatasets
        Category info, dataset list, and a caching note.

    Raises
    ------
    IbestatError
        If the category is not found in the topic tree.
    """
    from ibestat_mcp.client import IbestatError

    c = _cache or _default_cache
    cached = c.get_topic_datasets(category_id, lang)
    if cached is not None:
        return cached

    topic_tree = c.get_topics(lang)
    if topic_tree is None:
        topic_tree = await browse_topics(client, lang=lang, _cache=c)

    category = next((cat for cat in topic_tree.categories if cat.id == category_id), None)
    if category is None:
        raise IbestatError(
            f"Category '{category_id}' not found. "
            "Use browse_topics to see available categories."
        )

    children = [
        cat for cat in topic_tree.categories if cat.parent_id == category_id
    ]
    is_parent = len(children) > 0

    if is_parent:
        nested_ids = [cat.nested_id for cat in children if cat.nested_id]
        category_name = category.name
    else:
        nested_ids = [category.nested_id] if category.nested_id else []
        category_name = category.name

    seen: set[str] = set()
    datasets: list[DatasetSummary] = []
    total_operations = 0

    for nested_id in nested_ids:
        try:
            ops_response = await client.get_operations_by_subject(nested_id)
        except Exception:
            logger.debug("Operations lookup failed for %s", nested_id, exc_info=True)
            continue

        operations = ops_response.get("operation", [])
        total_operations += len(operations)

        for op in operations:
            op_id = op["id"]
            try:
                ds_response = await client.get_datasets_by_operation(op_id)
            except Exception:
                logger.debug("Datasets lookup failed for operation %s", op_id, exc_info=True)
                continue

            for entry in ds_response.get("dataset", []):
                ds_id = entry["id"]
                if ds_id in seen:
                    continue
                seen.add(ds_id)
                name = extract_localized_text(entry.get("name"), lang)
                description_field = entry.get("description")
                description_raw = (
                    extract_localized_text(description_field, lang)
                    if description_field is not None
                    else None
                )
                description = description_raw or None
                link = entry.get("visualizerHtmlLink", "")
                datasets.append(DatasetSummary(
                    id=ds_id, name=name, description=description, link=link,
                ))

    note = (
        f"First call fetched from the API and cached the result "
        f"({total_operations} operations queried). "
        f"Subsequent calls for category '{category_id}' in '{lang}' are instant."
    )

    result = TopicDatasets(
        category_id=category_id,
        category_name=category_name,
        datasets=datasets,
        total=len(datasets),
        note=note,
    )
    c.set_topic_datasets(category_id, lang, result)
    return result
