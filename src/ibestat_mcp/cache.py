"""In-memory cache for IBESTAT structural metadata."""

from __future__ import annotations

from ibestat_mcp.models import CodelistResult, TopicTree


class SemanticCache:
    """Simple in-memory cache for structural metadata.

    Stores topic trees, DSD codelist mappings, and codelist results
    to avoid redundant API calls during a session.

    Topics and codelists are keyed by language since labels differ per
    language.  Codelists also include pagination parameters in the key
    so that different pages are cached independently.
    """

    def __init__(self) -> None:
        self._topics: dict[str, TopicTree] = {}
        self._dsd_maps: dict[str, dict[str, str]] = {}
        self._codelists: dict[tuple[str, int, int, str], CodelistResult] = {}

    def get_topics(self, lang: str) -> TopicTree | None:
        return self._topics.get(lang)

    def set_topics(self, lang: str, tree: TopicTree) -> None:
        self._topics[lang] = tree

    def get_dsd_codelist_map(self, dataset_id: str) -> dict[str, str] | None:
        return self._dsd_maps.get(dataset_id)

    def set_dsd_codelist_map(self, dataset_id: str, mapping: dict[str, str]) -> None:
        self._dsd_maps[dataset_id] = mapping

    def get_codelist(
        self, codelist_id: str, limit: int, offset: int, lang: str
    ) -> CodelistResult | None:
        return self._codelists.get((codelist_id, limit, offset, lang))

    def set_codelist(
        self, codelist_id: str, limit: int, offset: int, lang: str, result: CodelistResult
    ) -> None:
        self._codelists[(codelist_id, limit, offset, lang)] = result


cache = SemanticCache()
