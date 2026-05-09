from typing import Any

from pydantic import BaseModel


class DatasetSummary(BaseModel):
    id: str
    name: str
    description: str | None = None
    link: str


class DimensionValue(BaseModel):
    code: str
    label: str


class DimensionInfo(BaseModel):
    id: str
    name: str
    values: list[DimensionValue]


class DatasetInfo(BaseModel):
    name: str
    dimensions: list[DimensionInfo]


DataRow = dict[str, Any]
