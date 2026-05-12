from typing import Any

from pydantic import BaseModel, Field


class DatasetSummary(BaseModel):
    id: str = Field(description="Dataset identifier (e.g., '000001A_000001')")
    name: str = Field(description="Dataset name in Catalan")
    description: str | None = Field(
        default=None, description="Dataset description in Catalan, if available"
    )
    link: str = Field(description="URL to the IBESTAT visualizer for this dataset")


class DimensionValue(BaseModel):
    code: str = Field(
        description="Dimension value code used in filters (e.g., '07040', '_T')"
    )
    label: str = Field(description="Human-readable label in Catalan")


class DimensionInfo(BaseModel):
    id: str = Field(
        description="Dimension identifier used as filter key (e.g., 'TERRITORIO', 'TIME_PERIOD')"
    )
    name: str = Field(description="Dimension name in Catalan")
    values: list[DimensionValue] = Field(
        description="Available values for this dimension"
    )


class DatasetInfo(BaseModel):
    name: str = Field(description="Dataset name in Catalan")
    dimensions: list[DimensionInfo] = Field(
        description="Available dimensions and their values"
    )


DataRow = dict[str, Any]
