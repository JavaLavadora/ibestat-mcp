"""Tests for ibestat_mcp.cache module."""

from ibestat_mcp.cache import SemanticCache
from ibestat_mcp.models import TopicTree, Category, CodelistResult, CodelistEntry


class TestSemanticCache:
    def test_topics_initially_none(self) -> None:
        cache = SemanticCache()
        assert cache.get_topics("ca") is None

    def test_store_and_retrieve_topics(self) -> None:
        cache = SemanticCache()
        tree = TopicTree(name="TEST", categories=[Category(id="1", name="Test", parent_id=None)])
        cache.set_topics("ca", tree)
        assert cache.get_topics("ca").name == "TEST"

    def test_topics_keyed_by_language(self) -> None:
        cache = SemanticCache()
        tree_ca = TopicTree(name="CA", categories=[])
        tree_es = TopicTree(name="ES", categories=[])
        cache.set_topics("ca", tree_ca)
        cache.set_topics("es", tree_es)
        assert cache.get_topics("ca").name == "CA"
        assert cache.get_topics("es").name == "ES"
        assert cache.get_topics("en") is None

    def test_dsd_map_initially_empty(self) -> None:
        cache = SemanticCache()
        assert cache.get_dsd_codelist_map("any") is None

    def test_store_and_retrieve_dsd_map(self) -> None:
        cache = SemanticCache()
        cache.set_dsd_codelist_map("DS1", {"TERRITORIO": "CL_AREA_ES53"})
        assert cache.get_dsd_codelist_map("DS1") == {"TERRITORIO": "CL_AREA_ES53"}

    def test_codelist_initially_empty(self) -> None:
        cache = SemanticCache()
        assert cache.get_codelist("CL_AREA_ES53", 100, 0, "ca") is None

    def test_store_and_retrieve_codelist(self) -> None:
        cache = SemanticCache()
        result = CodelistResult(
            id="CL_AREA_ES53", name="Test", total=1,
            codes=[CodelistEntry(code="ES53", label="Illes Balears", parent_code=None)],
        )
        cache.set_codelist("CL_AREA_ES53", 100, 0, "ca", result)
        assert cache.get_codelist("CL_AREA_ES53", 100, 0, "ca").id == "CL_AREA_ES53"

    def test_codelist_keyed_by_pagination(self) -> None:
        cache = SemanticCache()
        page1 = CodelistResult(id="CL", name="CL", total=200, codes=[
            CodelistEntry(code="A", label="Page 1", parent_code=None),
        ])
        page2 = CodelistResult(id="CL", name="CL", total=200, codes=[
            CodelistEntry(code="B", label="Page 2", parent_code=None),
        ])
        cache.set_codelist("CL", 100, 0, "ca", page1)
        cache.set_codelist("CL", 100, 100, "ca", page2)
        assert cache.get_codelist("CL", 100, 0, "ca").codes[0].code == "A"
        assert cache.get_codelist("CL", 100, 100, "ca").codes[0].code == "B"

    def test_codelist_keyed_by_language(self) -> None:
        cache = SemanticCache()
        result_ca = CodelistResult(id="CL", name="CL", total=1, codes=[
            CodelistEntry(code="X", label="Catala", parent_code=None),
        ])
        result_es = CodelistResult(id="CL", name="CL", total=1, codes=[
            CodelistEntry(code="X", label="Espanol", parent_code=None),
        ])
        cache.set_codelist("CL", 100, 0, "ca", result_ca)
        cache.set_codelist("CL", 100, 0, "es", result_es)
        assert cache.get_codelist("CL", 100, 0, "ca").codes[0].label == "Catala"
        assert cache.get_codelist("CL", 100, 0, "es").codes[0].label == "Espanol"
