"""Tests for ibestat_mcp.cache module."""

from ibestat_mcp.cache import SemanticCache
from ibestat_mcp.models import TopicTree, Category, CodelistResult, CodelistEntry


class TestSemanticCache:
    def test_topics_initially_none(self) -> None:
        cache = SemanticCache()
        assert cache.topics is None

    def test_store_and_retrieve_topics(self) -> None:
        cache = SemanticCache()
        tree = TopicTree(name="TEST", categories=[Category(id="1", name="Test", parent_id=None)])
        cache.topics = tree
        assert cache.topics.name == "TEST"

    def test_dsd_map_initially_empty(self) -> None:
        cache = SemanticCache()
        assert cache.get_dsd_codelist_map("any") is None

    def test_store_and_retrieve_dsd_map(self) -> None:
        cache = SemanticCache()
        cache.set_dsd_codelist_map("DS1", {"TERRITORIO": "CL_AREA_ES53"})
        assert cache.get_dsd_codelist_map("DS1") == {"TERRITORIO": "CL_AREA_ES53"}

    def test_codelist_initially_empty(self) -> None:
        cache = SemanticCache()
        assert cache.get_codelist("CL_AREA_ES53") is None

    def test_store_and_retrieve_codelist(self) -> None:
        cache = SemanticCache()
        result = CodelistResult(
            id="CL_AREA_ES53", name="Test", total=1,
            codes=[CodelistEntry(code="ES53", label="Illes Balears", parent_code=None)],
        )
        cache.set_codelist("CL_AREA_ES53", result)
        assert cache.get_codelist("CL_AREA_ES53").id == "CL_AREA_ES53"
