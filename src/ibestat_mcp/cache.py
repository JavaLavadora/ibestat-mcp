"""In-memory cache for IBESTAT structural metadata."""

from __future__ import annotations

from ibestat_mcp.models import CodelistResult, TopicTree


class SemanticCache:
    """Simple in-memory cache for structural metadata.

    Stores topic trees, DSD codelist mappings, and codelist results
    to avoid redundant API calls during a session.
    """

    def __init__(self) -> None:
        self.topics: TopicTree | None = None
        self._dsd_maps: dict[str, dict[str, str]] = {}
        self._codelists: dict[str, CodelistResult] = {}

    def get_dsd_codelist_map(self, dataset_id: str) -> dict[str, str] | None:
        """Return the dimension-to-codelist mapping for *dataset_id*, or None."""
        return self._dsd_maps.get(dataset_id)

    def set_dsd_codelist_map(self, dataset_id: str, mapping: dict[str, str]) -> None:
        """Store the dimension-to-codelist mapping for *dataset_id*."""
        self._dsd_maps[dataset_id] = mapping

    def get_codelist(self, codelist_id: str) -> CodelistResult | None:
        """Return the cached codelist for *codelist_id*, or None."""
        return self._codelists.get(codelist_id)

    def set_codelist(self, codelist_id: str, result: CodelistResult) -> None:
        """Cache the codelist *result* under *codelist_id*."""
        self._codelists[codelist_id] = result


cache = SemanticCache()
