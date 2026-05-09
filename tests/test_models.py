from ibestat_mcp.models import DatasetSummary, DimensionValue, DimensionInfo, DatasetInfo


class TestDatasetSummary:
    def test_create_with_all_fields(self):
        ds = DatasetSummary(
            id="000001A_000001",
            name="Poblacio municipal empadronada segons el sexe",
            description="Municipis de les Illes Balears per anys",
            link="https://ibestat.es/edatos/apps/statistical-visualizer/visualizer/data.html?resourceType=dataset&agencyId=IBESTAT&resourceId=000001A_000001",
        )
        assert ds.id == "000001A_000001"
        assert ds.name == "Poblacio municipal empadronada segons el sexe"
        assert ds.description == "Municipis de les Illes Balears per anys"
        assert ds.link.startswith("https://")

    def test_description_is_optional(self):
        ds = DatasetSummary(
            id="000001A_000001",
            name="Poblacio municipal",
            link="https://example.com",
        )
        assert ds.description is None


class TestDimensionValue:
    def test_create(self):
        dv = DimensionValue(code="07001", label="Alaro")
        assert dv.code == "07001"
        assert dv.label == "Alaro"


class TestDimensionInfo:
    def test_create_with_values(self):
        dim = DimensionInfo(
            id="TERRITORIO",
            name="Territori",
            values=[
                DimensionValue(code="07001", label="Alaro"),
                DimensionValue(code="07002", label="Alcudia"),
            ],
        )
        assert dim.id == "TERRITORIO"
        assert len(dim.values) == 2
        assert dim.values[0].label == "Alaro"


class TestDatasetInfo:
    def test_create(self):
        info = DatasetInfo(
            name="Poblacio municipal empadronada segons el sexe",
            dimensions=[
                DimensionInfo(
                    id="TERRITORIO",
                    name="Territori",
                    values=[DimensionValue(code="07001", label="Alaro")],
                ),
            ],
        )
        assert info.name == "Poblacio municipal empadronada segons el sexe"
        assert len(info.dimensions) == 1


class TestDataRow:
    def test_data_row_is_dict(self):
        from ibestat_mcp.models import DataRow
        row: DataRow = {"Territori": "Alaro", "Poblacio padro": 2035, "Taxa variacio": -0.97}
        assert isinstance(row, dict)
        assert row["Territori"] == "Alaro"
