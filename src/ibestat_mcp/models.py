from typing import Any

from pydantic import BaseModel, Field


class DatasetSummary(BaseModel):
    id: str = Field(description="Dataset identifier (e.g., '000001A_000001')")
    name: str = Field(description="Dataset name (Catalan by default)")
    description: str | None = Field(
        default=None, description="Dataset description, if available (Catalan by default)"
    )
    link: str = Field(description="URL to the IBESTAT visualizer for this dataset")


class DimensionValue(BaseModel):
    code: str = Field(
        description="Dimension value code used in filters (e.g., '07040', '_T')"
    )
    label: str = Field(description="Human-readable label (Catalan by default)")


class DimensionInfo(BaseModel):
    id: str = Field(
        description="Dimension identifier used as filter key (e.g., 'TERRITORIO', 'TIME_PERIOD')"
    )
    name: str = Field(description="Dimension name (Catalan by default)")
    values: list[DimensionValue] = Field(
        description="Available values for this dimension"
    )
    codelist_id: str | None = Field(
        default=None,
        description="Codelist identifier for this dimension. Use with get_codelist to explore the full hierarchy of valid codes.",
    )


class DatasetInfo(BaseModel):
    name: str = Field(description="Dataset name (Catalan by default)")
    dimensions: list[DimensionInfo] = Field(
        description="Available dimensions and their values"
    )


DataRow = dict[str, Any]


class Category(BaseModel):
    id: str = Field(description="Category identifier (e.g., '010')")
    name: str = Field(description="Category name in the requested language")
    parent_id: str | None = Field(
        default=None, description="Parent category ID, None for top-level"
    )
    nested_id: str | None = Field(
        default=None,
        exclude=True,
        description="SDMX nested ID for URN construction (e.g., '010.010_010')",
    )


class TopicTree(BaseModel):
    name: str = Field(description="Category scheme name")
    categories: list[Category] = Field(
        description="Flat list of categories with parent references"
    )


class CodelistEntry(BaseModel):
    code: str = Field(description="Code identifier (e.g., '07040' for Palma)")
    label: str = Field(description="Human-readable label")
    parent_code: str | None = Field(
        default=None, description="Parent code for hierarchical codelists"
    )


class CodelistResult(BaseModel):
    id: str = Field(description="Codelist identifier (e.g., 'CL_AREA_ES53')")
    name: str = Field(description="Codelist name in the requested language")
    total: int = Field(description="Total number of codes in the full codelist")
    codes: list[CodelistEntry] = Field(description="Code entries (may be paginated)")


class TopicDatasets(BaseModel):
    category_id: str = Field(description="The category ID that was queried")
    category_name: str = Field(description="Category name in the requested language")
    datasets: list[DatasetSummary] = Field(
        description="All datasets under this category"
    )
    total: int = Field(description="Total number of datasets found")
    note: str = Field(
        description="Caching and performance note for the user"
    )
