"""Parse IBESTAT eDades API responses into clean flat tables with localized labels.

Converts the nested, multilingual, multi-dimensional API response format into
simple lists of flat dictionaries suitable for tabular display. The MEDIDAS
(measures) dimension is pivoted so that each measure becomes a column rather
than a row value. Labels can be returned in Catalan (ca), Spanish (es), or
English (en).
"""

from __future__ import annotations

from typing import Any

from ibestat_mcp._i18n import extract_localized_text, strip_accents
from ibestat_mcp.models import DimensionInfo, DimensionValue


def parse_dimensions(
    metadata_response: dict[str, Any], lang: str = "ca"
) -> list[DimensionInfo]:
    """Extract dimension info with localized labels from an API response.

    Parameters
    ----------
    metadata_response:
        A full dataset response that contains a ``metadata`` section.
    lang:
        Language code for labels (``"ca"``, ``"es"``, or ``"en"``).

    Returns
    -------
    list[DimensionInfo]
        One entry per dimension, with accent-stripped localized labels.
    """
    raw_dims = metadata_response["metadata"]["dimensions"]["dimension"]
    result: list[DimensionInfo] = []
    for dim in raw_dims:
        dim_name = strip_accents(extract_localized_text(dim["name"], lang))
        values: list[DimensionValue] = []
        for val in dim["dimensionValues"]["value"]:
            val_label = strip_accents(extract_localized_text(val["name"], lang))
            values.append(DimensionValue(code=val["id"], label=val_label))
        result.append(DimensionInfo(id=dim["id"], name=dim_name, values=values))
    return result


def _parse_observation_value(raw: str) -> int | float | None:
    """Convert a single pipe-separated observation string to a number or None."""
    stripped = raw.strip()
    if not stripped:
        return None
    try:
        f = float(stripped)
    except ValueError:
        return None
    # Return int when the value is a whole number (e.g. "6121" -> 6121)
    if f == int(f) and "." not in stripped:
        return int(f)
    return f


def parse_observations(
    response: dict[str, Any],
    lang: str = "ca",
    filters: dict[str, str | list[str]] | None = None,
) -> list[dict[str, Any]]:
    """Flatten a dataset response into a list of row dictionaries.

    The MEDIDAS dimension is pivoted: its values become column names instead
    of appearing as row values.  All column names and labels are accent-
    stripped localized text.

    IBESTAT's eDades API only honours the *first* ``dim=<id>:<value>`` query
    parameter server-side: any additional requested filter dimensions are
    silently ignored and the response comes back with the full code range
    for those dimensions instead of just the requested value. Since this
    function already walks every dimension combination and has access to
    each dimension's raw (unlocalized) code, ``filters`` lets it re-apply the
    originally-requested filter set against those raw codes, dropping rows
    for any dimension the API failed to narrow down.

    Parameters
    ----------
    response:
        A full dataset response with both ``metadata`` and ``data`` sections.
    lang:
        Language code for labels (``"ca"``, ``"es"``, or ``"en"``).
    filters:
        Optional ``{dim_id: value_or_values}`` filters that were requested
        when fetching ``response``. Rows whose raw dimension code doesn't
        match are dropped client-side, to work around the API only honouring
        the first ``dim`` filter it receives. ``None`` (the default)
        preserves the old behaviour of returning every row in the response.

    Returns
    -------
    list[dict[str, Any]]
        Flat row dictionaries ready for tabular display.
    """
    normalized_filters: dict[str, set[str]] = {
        dim_id: (set(v) if isinstance(v, list) else {v})
        for dim_id, v in (filters or {}).items()
    }

    # ------------------------------------------------------------------
    # 1. Build label lookup from metadata
    # ------------------------------------------------------------------
    meta_dims = response["metadata"]["dimensions"]["dimension"]

    # Map: dim_id -> {value_id -> localized_label}
    label_lookup: dict[str, dict[str, str]] = {}
    # Map: dim_id -> localized dimension name
    dim_name_lookup: dict[str, str] = {}
    # Identify the MEDIDAS dimension
    medidas_dim_id: str | None = None

    for dim in meta_dims:
        dim_id = dim["id"]
        dim_name_lookup[dim_id] = strip_accents(extract_localized_text(dim["name"], lang))
        if dim.get("type") == "MEASURE_DIMENSION":
            medidas_dim_id = dim_id
        val_map: dict[str, str] = {}
        for val in dim["dimensionValues"]["value"]:
            val_map[val["id"]] = strip_accents(extract_localized_text(val["name"], lang))
        label_lookup[dim_id] = val_map

    # ------------------------------------------------------------------
    # 2. Get dimension order, sizes, and code arrays from data section
    # ------------------------------------------------------------------
    data_dims = response["data"]["dimensions"]["dimension"]

    # For each data dimension, build an ordered list of codes (by index)
    dim_ids: list[str] = []
    dim_codes: list[list[str]] = []  # codes ordered by their data index
    dim_sizes: list[int] = []

    for ddim in data_dims:
        dim_id = ddim["dimensionId"]
        dim_ids.append(dim_id)
        reps = ddim["representations"]["representation"]
        # Sort by index to get correct order
        sorted_reps = sorted(reps, key=lambda r: r["index"])
        codes = [r["code"] for r in sorted_reps]
        dim_codes.append(codes)
        dim_sizes.append(len(codes))

    # ------------------------------------------------------------------
    # 3. Parse observations
    # ------------------------------------------------------------------
    raw_obs = response["data"]["observations"]
    obs_values = [_parse_observation_value(v) for v in raw_obs.split(" | ")]

    # ------------------------------------------------------------------
    # 4. Find MEDIDAS dimension position (if any)
    # ------------------------------------------------------------------
    medidas_idx: int | None = None
    if medidas_dim_id is not None:
        for i, did in enumerate(dim_ids):
            if did == medidas_dim_id:
                medidas_idx = i
                break

    # ------------------------------------------------------------------
    # 5. Iterate all dimension combinations in row-major order
    # ------------------------------------------------------------------
    # We need to compute the total number of combinations and map
    # multi-dimensional indices to the flat observation index.
    total = 1
    for s in dim_sizes:
        total *= s

    # Build strides for row-major indexing
    # stride[i] = product of sizes of all dimensions after i
    n_dims = len(dim_sizes)
    strides = [1] * n_dims
    for i in range(n_dims - 2, -1, -1):
        strides[i] = strides[i + 1] * dim_sizes[i + 1]

    # If MEDIDAS exists, we group by all non-MEDIDAS dimensions
    # and collect MEDIDAS values into columns.
    if medidas_idx is not None:
        medidas_codes = dim_codes[medidas_idx]
        medidas_labels = [
            label_lookup.get(medidas_dim_id, {}).get(code, code)
            for code in medidas_codes
        ]
        medidas_size = dim_sizes[medidas_idx]

        # Non-MEDIDAS dimensions
        non_medidas_indices = [i for i in range(n_dims) if i != medidas_idx]
        non_medidas_sizes = [dim_sizes[i] for i in non_medidas_indices]

        # Total rows = product of non-MEDIDAS sizes
        total_rows = 1
        for s in non_medidas_sizes:
            total_rows *= s

        rows: list[dict[str, Any]] = []
        for row_flat in range(total_rows):
            # Compute multi-index for non-MEDIDAS dimensions
            multi_idx_non_medidas: list[int] = []
            remaining = row_flat
            for k, s in enumerate(non_medidas_sizes):
                # stride for this position = product of remaining non-medidas sizes
                stride_k = 1
                for s2 in non_medidas_sizes[k + 1 :]:
                    stride_k *= s2
                idx = remaining // stride_k
                remaining %= stride_k
                multi_idx_non_medidas.append(idx)

            # Build the row dict with dimension labels
            row: dict[str, Any] = {}
            skip_row = False
            for k, nm_idx in enumerate(non_medidas_indices):
                dim_id = dim_ids[nm_idx]
                code = dim_codes[nm_idx][multi_idx_non_medidas[k]]
                if dim_id in normalized_filters and code not in normalized_filters[dim_id]:
                    skip_row = True
                    break
                col_name = dim_name_lookup.get(dim_id, dim_id)
                val_label = label_lookup.get(dim_id, {}).get(code, code)
                row[col_name] = val_label

            if skip_row:
                continue

            # Now add MEDIDAS columns
            for m_local_idx in range(medidas_size):
                # Build full multi-index for observation lookup
                full_idx = [0] * n_dims
                for k, nm_pos in enumerate(non_medidas_indices):
                    full_idx[nm_pos] = multi_idx_non_medidas[k]
                full_idx[medidas_idx] = m_local_idx

                # Compute flat index
                flat = 0
                for i in range(n_dims):
                    flat += full_idx[i] * strides[i]

                row[medidas_labels[m_local_idx]] = obs_values[flat]

            rows.append(row)

        return rows

    else:
        # No MEDIDAS dimension: each combination is a row with a single value column
        rows = []
        for flat_idx in range(total):
            remaining = flat_idx
            row = {}
            skip_row = False
            for i in range(n_dims):
                idx = remaining // strides[i]
                remaining %= strides[i]
                dim_id = dim_ids[i]
                code = dim_codes[i][idx]
                if dim_id in normalized_filters and code not in normalized_filters[dim_id]:
                    skip_row = True
                    break
                col_name = dim_name_lookup.get(dim_id, dim_id)
                val_label = label_lookup.get(dim_id, {}).get(code, code)
                row[col_name] = val_label
            if skip_row:
                continue
            row["value"] = obs_values[flat_idx]
            rows.append(row)
        return rows
