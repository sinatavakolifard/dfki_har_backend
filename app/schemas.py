from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class UserIn(BaseModel):
    age: int | None = Field(default=None, ge=0, le=150)
    height_cm: int | None = Field(default=None, ge=0, le=300)
    weight_kg: int | None = Field(default=None, ge=0, le=500)
    gender: str | None = Field(default=None, max_length=32)


class UserOut(UserIn):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    created_at: datetime
    updated_at: datetime


class SessionMetadataIn(BaseModel):
    """Metadata part of the multipart upload."""

    id: UUID
    user_id: UUID
    started_at: datetime
    duration_ms: int = Field(ge=0)
    sample_count: int = Field(ge=0)
    target_hz: int = Field(gt=0, le=10_000)
    description: str | None = None
    csv_uncompressed_bytes: int = Field(ge=0)
    csv_sha256: str = Field(min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$")


class SessionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    started_at: datetime
    duration_ms: int
    sample_count: int
    target_hz: int
    description: str | None
    csv_compression: str
    csv_uncompressed_bytes: int
    csv_sha256: str
    uploaded_at: datetime
