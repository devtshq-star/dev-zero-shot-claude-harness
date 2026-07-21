from datetime import datetime

from pydantic import BaseModel


class ColumnProfile(BaseModel):
    name: str
    dtype: str
    null_count: int
    distinct_count: int
    min: str | None = None
    max: str | None = None


class DatasetProfile(BaseModel):
    columns: list[ColumnProfile]
    duplicate_row_count: int


class DatasetResponse(BaseModel):
    id: str
    name: str
    row_count: int
    column_count: int
    profile: DatasetProfile
    data_quality_flags: list[str] = []
    uploaded_at: datetime
