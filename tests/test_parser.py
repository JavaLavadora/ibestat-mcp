"""Tests for ibestat_mcp.parser module."""

from __future__ import annotations

from typing import Any

import pytest

from ibestat_mcp.parser import (
    extract_localized_text,
    parse_dimensions,
    parse_observations,
    strip_accents,
)


# ---------------------------------------------------------------------------
# Helpers to build realistic API structures
# ---------------------------------------------------------------------------


def _intl(ca: str, es: str = "", en: str = "") -> dict[str, Any]:
    """Build an InternationalString matching the real API format."""
    texts = []
    if en:
        texts.append({"value": en, "lang": "en"})
    if es:
        texts.append({"value": es, "lang": "es"})
    if ca:
        texts.append({"value": ca, "lang": "ca"})
    return {"text": texts}


def _dim_value(id_: str, name_ca: str, name_es: str = "", name_en: str = "") -> dict:
    """Build a dimensionValues.value entry."""
    return {"id": id_, "name": _intl(name_ca, name_es, name_en)}


def _meta_dimension(
    dim_id: str,
    name_ca: str,
    values: list[dict],
    dim_type: str = "DIMENSION",
) -> dict:
    """Build a metadata dimension entry."""
    return {
        "id": dim_id,
        "name": _intl(name_ca),
        "type": dim_type,
        "dimensionValues": {"value": values, "total": len(values)},
    }


def _data_dimension(dim_id: str, codes: list[str]) -> dict:
    """Build a data dimension entry with code-to-index mapping."""
    return {
        "dimensionId": dim_id,
        "representations": {
            "representation": [
                {"code": code, "index": idx} for idx, code in enumerate(codes)
            ],
            "total": len(codes),
        },
    }


def _build_response(
    meta_dims: list[dict],
    data_dims: list[dict],
    observations: str,
) -> dict[str, Any]:
    """Build a full dataset response with metadata and data sections."""
    return {
        "id": "TEST_DS",
        "name": _intl("Test Dataset"),
        "metadata": {
            "dimensions": {"dimension": meta_dims, "total": len(meta_dims)},
        },
        "data": {
            "dimensions": {"dimension": data_dims, "total": len(data_dims)},
            "observations": observations,
        },
    }


# ===========================================================================
# TestStripAccents
# ===========================================================================


class TestStripAccents:
    def test_strips_catalan_accents(self):
        assert strip_accents("Alaró") == "Alaro"

    def test_strips_multiple_accents(self):
        assert strip_accents("Població empadronada") == "Poblacio empadronada"

    def test_preserves_ascii(self):
        assert strip_accents("Total") == "Total"

    def test_handles_empty(self):
        assert strip_accents("") == ""

    def test_strips_cedilla(self):
        assert strip_accents("Peça") == "Peca"

    def test_strips_umlaut(self):
        assert strip_accents("über") == "uber"

    def test_strips_tilde(self):
        assert strip_accents("España") == "Espana"


# ===========================================================================
# TestExtractLocalizedText
# ===========================================================================


class TestExtractLocalizedText:
    def test_extracts_catalan(self):
        intl = _intl("Territori", "Territorio", "Reference area")
        assert extract_localized_text(intl, "ca") == "Territori"

    def test_extracts_spanish(self):
        intl = _intl("Territori", "Territorio", "Reference area")
        assert extract_localized_text(intl, "es") == "Territorio"

    def test_extracts_english(self):
        intl = _intl("Territori", "Territorio", "Reference area")
        assert extract_localized_text(intl, "en") == "Reference area"

    def test_falls_back_to_first_available(self):
        intl = {"text": [{"value": "Territorio", "lang": "es"}]}
        assert extract_localized_text(intl, "ca") == "Territorio"

    def test_handles_none(self):
        assert extract_localized_text(None) == ""

    def test_handles_empty_dict(self):
        assert extract_localized_text({}) == ""

    def test_handles_empty_text_list(self):
        assert extract_localized_text({"text": []}) == ""

    def test_default_lang_is_catalan(self):
        intl = _intl("Territori", "Territorio")
        assert extract_localized_text(intl) == "Territori"


# ===========================================================================
# TestParseDimensions
# ===========================================================================


class TestParseDimensions:
    def test_parses_simple_dimensions(self):
        response = {
            "metadata": {
                "dimensions": {
                    "dimension": [
                        _meta_dimension(
                            "SEXO",
                            "Sexe",
                            [
                                _dim_value("_T", "Ambdós sexes"),
                                _dim_value("M", "Homes"),
                                _dim_value("F", "Dones"),
                            ],
                        ),
                    ],
                    "total": 1,
                },
            },
        }
        dims = parse_dimensions(response)
        assert len(dims) == 1
        assert dims[0].id == "SEXO"
        assert dims[0].name == "Sexe"
        assert len(dims[0].values) == 3
        assert dims[0].values[0].code == "_T"
        assert dims[0].values[0].label == "Ambdos sexes"  # accent stripped

    def test_parses_multiple_dimensions(self):
        response = {
            "metadata": {
                "dimensions": {
                    "dimension": [
                        _meta_dimension(
                            "TERRITORIO",
                            "Territori",
                            [_dim_value("07001", "Alaró")],
                            dim_type="GEOGRAPHIC_DIMENSION",
                        ),
                        _meta_dimension(
                            "TIME_PERIOD",
                            "Període",
                            [_dim_value("2024", "2024"), _dim_value("2023", "2023")],
                            dim_type="TIME_DIMENSION",
                        ),
                    ],
                    "total": 2,
                },
            },
        }
        dims = parse_dimensions(response)
        assert len(dims) == 2
        assert dims[0].id == "TERRITORIO"
        assert dims[0].name == "Territori"
        assert dims[0].values[0].label == "Alaro"  # accent stripped
        assert dims[1].id == "TIME_PERIOD"
        assert dims[1].name == "Periode"  # accent stripped

    def test_with_real_fixture(self, dataset_metadata_response):
        dims = parse_dimensions(dataset_metadata_response)
        assert len(dims) == 4
        dim_ids = [d.id for d in dims]
        assert "TERRITORIO" in dim_ids
        assert "TIME_PERIOD" in dim_ids
        assert "SEXO" in dim_ids
        assert "MEDIDAS" in dim_ids

        # Check TERRITORIO dimension
        terr = next(d for d in dims if d.id == "TERRITORIO")
        assert terr.name == "Territori"
        assert len(terr.values) == 67
        # Check accent is stripped
        alaro = next(v for v in terr.values if v.code == "07001")
        assert alaro.label == "Alaro"


# ===========================================================================
# TestParseObservations
# ===========================================================================


class TestParseObservations:
    def test_simple_2d(self):
        """Two non-MEDIDAS dimensions plus MEDIDAS with 1 measure."""
        response = _build_response(
            meta_dims=[
                _meta_dimension(
                    "TERRITORIO",
                    "Territori",
                    [_dim_value("07001", "Alaró"), _dim_value("07003", "Alcúdia")],
                    dim_type="GEOGRAPHIC_DIMENSION",
                ),
                _meta_dimension(
                    "MEDIDAS",
                    "Indicador",
                    [_dim_value("POP", "Població")],
                    dim_type="MEASURE_DIMENSION",
                ),
            ],
            data_dims=[
                _data_dimension("TERRITORIO", ["07001", "07003"]),
                _data_dimension("MEDIDAS", ["POP"]),
            ],
            observations="100 | 200",
        )
        rows = parse_observations(response)
        assert len(rows) == 2
        assert rows[0] == {"Territori": "Alaro", "Poblacio": 100}
        assert rows[1] == {"Territori": "Alcudia", "Poblacio": 200}

    def test_medidas_pivoted(self):
        """MEDIDAS values become column names, not row values."""
        response = _build_response(
            meta_dims=[
                _meta_dimension(
                    "TERRITORIO",
                    "Territori",
                    [_dim_value("07001", "Alaró")],
                    dim_type="GEOGRAPHIC_DIMENSION",
                ),
                _meta_dimension(
                    "MEDIDAS",
                    "Indicador",
                    [
                        _dim_value("POP", "Població"),
                        _dim_value("VAR", "Variació"),
                    ],
                    dim_type="MEASURE_DIMENSION",
                ),
            ],
            data_dims=[
                _data_dimension("TERRITORIO", ["07001"]),
                _data_dimension("MEDIDAS", ["POP", "VAR"]),
            ],
            observations="100 | 5",
        )
        rows = parse_observations(response)
        assert len(rows) == 1
        assert rows[0] == {"Territori": "Alaro", "Poblacio": 100, "Variacio": 5}

    def test_multi_dimensional_with_medidas(self):
        """3 dimensions: TERRITORIO(2) x SEXO(2) x MEDIDAS(2)."""
        response = _build_response(
            meta_dims=[
                _meta_dimension(
                    "TERRITORIO",
                    "Territori",
                    [_dim_value("07001", "Alaró"), _dim_value("07003", "Alcúdia")],
                    dim_type="GEOGRAPHIC_DIMENSION",
                ),
                _meta_dimension(
                    "SEXO",
                    "Sexe",
                    [_dim_value("_T", "Total"), _dim_value("F", "Dones")],
                ),
                _meta_dimension(
                    "MEDIDAS",
                    "Indicador",
                    [
                        _dim_value("POP", "Població"),
                        _dim_value("VAR", "Variació"),
                    ],
                    dim_type="MEASURE_DIMENSION",
                ),
            ],
            data_dims=[
                _data_dimension("TERRITORIO", ["07001", "07003"]),
                _data_dimension("SEXO", ["_T", "F"]),
                _data_dimension("MEDIDAS", ["POP", "VAR"]),
            ],
            # Row-major: last dim (MEDIDAS) varies fastest
            # Alaró/Total/POP, Alaró/Total/VAR, Alaró/Dones/POP, Alaró/Dones/VAR,
            # Alcúdia/Total/POP, Alcúdia/Total/VAR, Alcúdia/Dones/POP, Alcúdia/Dones/VAR
            observations="100 | 5 | 60 | 3 | 200 | 10 | 110 | 6",
        )
        rows = parse_observations(response)
        assert len(rows) == 4  # 2 territories x 2 sexes
        assert rows[0] == {"Territori": "Alaro", "Sexe": "Total", "Poblacio": 100, "Variacio": 5}
        assert rows[1] == {"Territori": "Alaro", "Sexe": "Dones", "Poblacio": 60, "Variacio": 3}
        assert rows[2] == {"Territori": "Alcudia", "Sexe": "Total", "Poblacio": 200, "Variacio": 10}
        assert rows[3] == {"Territori": "Alcudia", "Sexe": "Dones", "Poblacio": 110, "Variacio": 6}

    def test_null_observations(self):
        """Empty observation values should become None."""
        response = _build_response(
            meta_dims=[
                _meta_dimension(
                    "TERRITORIO",
                    "Territori",
                    [_dim_value("07001", "Alaró")],
                    dim_type="GEOGRAPHIC_DIMENSION",
                ),
                _meta_dimension(
                    "MEDIDAS",
                    "Indicador",
                    [
                        _dim_value("POP", "Població"),
                        _dim_value("VAR", "Variació"),
                    ],
                    dim_type="MEASURE_DIMENSION",
                ),
            ],
            data_dims=[
                _data_dimension("TERRITORIO", ["07001"]),
                _data_dimension("MEDIDAS", ["POP", "VAR"]),
            ],
            observations="100 | ",
        )
        rows = parse_observations(response)
        assert len(rows) == 1
        assert rows[0]["Poblacio"] == 100
        assert rows[0]["Variacio"] is None

    def test_with_real_fixture(self, dataset_metadata_response):
        """Parse the real fixture and spot-check values."""
        rows = parse_observations(dataset_metadata_response)

        # 67 territories x 28 years x 3 sexes = 5628 rows (MEDIDAS pivoted into columns)
        assert len(rows) == 67 * 28 * 3

        # Check a specific known data point from conftest docs:
        # Alaró (index 0 in data), 2025 (index 0), Ambdós sexes (index 0)
        # MEDIDAS at indices 0,1,2 => TVA, PADRON, VA
        # First 3 observations: '1.39', '6121', '84'
        first_row = rows[0]
        assert first_row["Territori"] == "Alaro"

        # MEDIDAS are pivoted: check the measure columns exist
        assert "Poblacio empadronada" in first_row
        assert "Poblacio empadronada. Taxa de variacio anual" in first_row
        assert "Poblacio empadronada. Variacio anual" in first_row

    def test_medidas_index_ordering(self):
        """Data section index ordering may differ from metadata order."""
        response = _build_response(
            meta_dims=[
                _meta_dimension(
                    "TERRITORIO",
                    "Territori",
                    [_dim_value("07001", "Alaró")],
                    dim_type="GEOGRAPHIC_DIMENSION",
                ),
                _meta_dimension(
                    "MEDIDAS",
                    "Indicador",
                    [
                        _dim_value("POP", "Població"),
                        _dim_value("VAR", "Variació"),
                    ],
                    dim_type="MEASURE_DIMENSION",
                ),
            ],
            data_dims=[
                _data_dimension("TERRITORIO", ["07001"]),
                # NOTE: data section has VAR at index 0, POP at index 1
                {
                    "dimensionId": "MEDIDAS",
                    "representations": {
                        "representation": [
                            {"code": "VAR", "index": 0},
                            {"code": "POP", "index": 1},
                        ],
                        "total": 2,
                    },
                },
            ],
            observations="5 | 100",
        )
        rows = parse_observations(response)
        assert len(rows) == 1
        # VAR is at index 0 so value 5, POP at index 1 so value 100
        assert rows[0]["Variacio"] == 5
        assert rows[0]["Poblacio"] == 100

    def test_no_medidas_dimension(self):
        """Datasets without MEDIDAS should produce a generic 'value' column."""
        response = {
            "metadata": {
                "dimensions": {
                    "dimension": [
                        {
                            "id": "TERRITORIO",
                            "name": {"text": [{"value": "Territori", "lang": "ca"}]},
                            "type": "GEOGRAPHIC_DIMENSION",
                            "dimensionValues": {
                                "value": [
                                    {"id": "07001", "name": {"text": [{"value": "Alaro", "lang": "ca"}]}},
                                    {"id": "07002", "name": {"text": [{"value": "Alcudia", "lang": "ca"}]}},
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
                            "type": "GEOGRAPHIC_DIMENSION",
                            "representations": {
                                "representation": [
                                    {"code": "07001", "index": 0},
                                    {"code": "07002", "index": 1},
                                ],
                                "total": 2,
                            },
                        },
                    ]
                },
                "observations": "500 | 1000",
            },
        }
        rows = parse_observations(response)
        assert len(rows) == 2
        assert "value" in rows[0]
        assert rows[0]["Territori"] == "Alaro"
        assert rows[0]["value"] == 500
        assert rows[1]["Territori"] == "Alcudia"
        assert rows[1]["value"] == 1000

    def test_integer_and_float_values(self):
        """Integer observation values should be returned as int, floats as float."""
        response = _build_response(
            meta_dims=[
                _meta_dimension(
                    "TERRITORIO",
                    "Territori",
                    [_dim_value("07001", "Alaró")],
                    dim_type="GEOGRAPHIC_DIMENSION",
                ),
                _meta_dimension(
                    "MEDIDAS",
                    "Indicador",
                    [
                        _dim_value("POP", "Població"),
                        _dim_value("RATE", "Taxa"),
                    ],
                    dim_type="MEASURE_DIMENSION",
                ),
            ],
            data_dims=[
                _data_dimension("TERRITORIO", ["07001"]),
                _data_dimension("MEDIDAS", ["POP", "RATE"]),
            ],
            observations="6121 | -0.97",
        )
        rows = parse_observations(response)
        assert rows[0]["Poblacio"] == 6121
        assert isinstance(rows[0]["Poblacio"], (int, float))
        assert rows[0]["Taxa"] == -0.97


class TestParseObservationsFilters:
    """The eDades API only honours the first `dim` filter server-side, so
    parse_observations must re-apply the full requested filter set against
    the raw (unlocalized) codes to correctly narrow down any dimensions the
    API silently ignored.
    """

    def _build_ignored_second_filter_response(self) -> dict[str, Any]:
        """TERRITORIO(2) x SEXO(3) x MEDIDAS(1), simulating the server
        having honoured only the TERRITORIO filter and ignored SEXO -- the
        raw data section contains the full cartesian product for both.
        """
        return _build_response(
            meta_dims=[
                _meta_dimension(
                    "TERRITORIO",
                    "Territori",
                    [_dim_value("ES53", "Illes Balears"), _dim_value("ES52", "Comunitat Valenciana")],
                    dim_type="GEOGRAPHIC_DIMENSION",
                ),
                _meta_dimension(
                    "SEXO",
                    "Sexe",
                    [
                        _dim_value("_T", "Total"),
                        _dim_value("H", "Homes"),
                        _dim_value("M", "Dones"),
                    ],
                ),
                _meta_dimension(
                    "MEDIDAS",
                    "Indicador",
                    [_dim_value("POP", "Poblacio")],
                    dim_type="MEASURE_DIMENSION",
                ),
            ],
            data_dims=[
                _data_dimension("TERRITORIO", ["ES53", "ES52"]),
                _data_dimension("SEXO", ["_T", "H", "M"]),
                _data_dimension("MEDIDAS", ["POP"]),
            ],
            # Row-major, MEDIDAS varies fastest (only 1 value here), then SEXO,
            # then TERRITORIO:
            # ES53/_T, ES53/H, ES53/M, ES52/_T, ES52/H, ES52/M
            observations="100 | 50 | 50 | 900 | 450 | 450",
        )

    def test_single_value_filters_narrow_down_ignored_dimensions(self):
        response = self._build_ignored_second_filter_response()
        rows = parse_observations(
            response, lang="ca", filters={"TERRITORIO": "ES53", "SEXO": "_T"}
        )
        assert len(rows) == 1
        assert rows[0] == {"Territori": "Illes Balears", "Sexe": "Total", "Poblacio": 100}

    def test_no_filters_returns_full_unfiltered_set(self):
        """Backward compatibility: callers that don't pass filters still get
        every row the API returned."""
        response = self._build_ignored_second_filter_response()
        rows = parse_observations(response, lang="ca")
        assert len(rows) == 6

    def test_list_valued_filter_matches_any_of_the_values(self):
        response = self._build_ignored_second_filter_response()
        rows = parse_observations(
            response,
            lang="ca",
            filters={"TERRITORIO": "ES53", "SEXO": ["_T", "H"]},
        )
        assert len(rows) == 2
        sexes = {row["Sexe"] for row in rows}
        assert sexes == {"Total", "Homes"}
        assert all(row["Territori"] == "Illes Balears" for row in rows)

    def test_filters_apply_without_medidas_dimension(self):
        """Same re-narrowing logic must also work for datasets with no
        MEDIDAS dimension (the plain 'value' column branch)."""
        response = {
            "metadata": {
                "dimensions": {
                    "dimension": [
                        {
                            "id": "TERRITORIO",
                            "name": {"text": [{"value": "Territori", "lang": "ca"}]},
                            "type": "GEOGRAPHIC_DIMENSION",
                            "dimensionValues": {
                                "value": [
                                    {"id": "07001", "name": {"text": [{"value": "Alaro", "lang": "ca"}]}},
                                    {"id": "07002", "name": {"text": [{"value": "Alcudia", "lang": "ca"}]}},
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
                            "type": "GEOGRAPHIC_DIMENSION",
                            "representations": {
                                "representation": [
                                    {"code": "07001", "index": 0},
                                    {"code": "07002", "index": 1},
                                ],
                                "total": 2,
                            },
                        },
                    ]
                },
                "observations": "500 | 1000",
            },
        }
        rows = parse_observations(response, filters={"TERRITORIO": "07001"})
        assert len(rows) == 1
        assert rows[0] == {"Territori": "Alaro", "value": 500}


# ===========================================================================
# TestLanguageSelection -- lang parameter threading
# ===========================================================================


def _intl_multilingual(ca: str, es: str, en: str) -> dict[str, Any]:
    """Build an InternationalString with all three languages."""
    return {
        "text": [
            {"value": en, "lang": "en"},
            {"value": es, "lang": "es"},
            {"value": ca, "lang": "ca"},
        ]
    }


def _multilingual_meta_dimension(
    dim_id: str,
    name_ca: str,
    name_es: str,
    name_en: str,
    values: list[dict],
    dim_type: str = "DIMENSION",
) -> dict:
    """Build a metadata dimension with multilingual name."""
    return {
        "id": dim_id,
        "name": _intl_multilingual(name_ca, name_es, name_en),
        "type": dim_type,
        "dimensionValues": {"value": values, "total": len(values)},
    }


def _multilingual_dim_value(
    id_: str, name_ca: str, name_es: str, name_en: str
) -> dict:
    """Build a dimensionValues.value entry with multilingual names."""
    return {"id": id_, "name": _intl_multilingual(name_ca, name_es, name_en)}


class TestParseDimensionsLanguage:
    """Verify parse_dimensions respects the lang parameter."""

    def _build_response(self) -> dict:
        return {
            "metadata": {
                "dimensions": {
                    "dimension": [
                        _multilingual_meta_dimension(
                            "SEXO",
                            "Sexe",
                            "Sexo",
                            "Sex",
                            [
                                _multilingual_dim_value(
                                    "_T", "Ambdos sexes", "Ambos sexos", "Both sexes"
                                ),
                                _multilingual_dim_value(
                                    "M", "Homes", "Hombres", "Males"
                                ),
                            ],
                        ),
                    ],
                    "total": 1,
                },
            },
        }

    def test_catalan_default(self):
        dims = parse_dimensions(self._build_response())
        assert dims[0].name == "Sexe"
        assert dims[0].values[0].label == "Ambdos sexes"

    def test_spanish(self):
        dims = parse_dimensions(self._build_response(), lang="es")
        assert dims[0].name == "Sexo"
        assert dims[0].values[0].label == "Ambos sexos"
        assert dims[0].values[1].label == "Hombres"

    def test_english(self):
        dims = parse_dimensions(self._build_response(), lang="en")
        assert dims[0].name == "Sex"
        assert dims[0].values[0].label == "Both sexes"
        assert dims[0].values[1].label == "Males"


class TestParseObservationsLanguage:
    """Verify parse_observations respects the lang parameter."""

    def _build_response(self) -> dict:
        return {
            "id": "TEST_LANG",
            "name": _intl_multilingual("Test CA", "Test ES", "Test EN"),
            "metadata": {
                "dimensions": {
                    "dimension": [
                        _multilingual_meta_dimension(
                            "TERRITORIO",
                            "Territori",
                            "Territorio",
                            "Reference area",
                            [
                                _multilingual_dim_value(
                                    "07001", "Alaro", "Alaro", "Alaro"
                                ),
                            ],
                            dim_type="GEOGRAPHIC_DIMENSION",
                        ),
                        _multilingual_meta_dimension(
                            "MEDIDAS",
                            "Indicador",
                            "Indicador",
                            "Indicator",
                            [
                                _multilingual_dim_value(
                                    "POP", "Poblacio", "Poblacion", "Population"
                                ),
                            ],
                            dim_type="MEASURE_DIMENSION",
                        ),
                    ],
                    "total": 2,
                },
            },
            "data": {
                "dimensions": {
                    "dimension": [
                        _data_dimension("TERRITORIO", ["07001"]),
                        _data_dimension("MEDIDAS", ["POP"]),
                    ],
                    "total": 2,
                },
                "observations": "100",
            },
        }

    def test_catalan_default(self):
        rows = parse_observations(self._build_response())
        assert rows[0] == {"Territori": "Alaro", "Poblacio": 100}

    def test_spanish(self):
        rows = parse_observations(self._build_response(), lang="es")
        assert rows[0] == {"Territorio": "Alaro", "Poblacion": 100}

    def test_english(self):
        rows = parse_observations(self._build_response(), lang="en")
        assert rows[0] == {"Reference area": "Alaro", "Population": 100}
