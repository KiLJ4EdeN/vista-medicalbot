from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class UploadResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    session_id: UUID
    original_filename: str
    content_type: str
    size_bytes: int
    sha256: str
    created_at: datetime


class UploadListResponse(BaseModel):
    items: list[UploadResponse]


class UploadDownloadResponse(BaseModel):
    url: str
    expires_at: datetime
