"""MCP tool functions that wire the IBESTAT client and parser together.

Each function takes an ``IbestatClient`` as its first argument and returns
parsed, structured data ready for MCP server responses.  All functions accept
a ``lang`` parameter to select the language for data labels (``"ca"``,
``"es"``, or ``"en"``).
"""

from __future__ import annotations

from ibestat_mcp.client import IbestatClient
from ibestat_mcp.models import DataRow, DatasetInfo, DatasetSummary
from ibestat_mcp.parser import extract_localized_text, parse_dimensions, parse_observations


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

    Returns
    -------
    DatasetInfo
        Dataset name and parsed dimension information in the requested language.
    """
    response = await client.get_dataset_metadata(dataset_id)
    name = extract_localized_text(response.get("name"), lang)
    dimensions = parse_dimensions(response, lang)

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
    return parse_observations(response, lang)
