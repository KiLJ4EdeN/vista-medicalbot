from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from models.enums import ProcessingStatus


class KnowledgeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    original_filename: str
    content_type: str
    size_bytes: int
    sha256: str
    status: ProcessingStatus
    chunk_count: int
    processing_error: str | None
    indexed_at: datetime | None
    created_at: datetime
    updated_at: datetime


class KnowledgeListResponse(BaseModel):
    items: list[KnowledgeResponse]
    total: int
    offset: int
    limit: int


class KnowledgeUpdateRequest(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=300)

    @model_validator(mode="after")
    def require_change(self) -> "KnowledgeUpdateRequest":
        if not self.model_fields_set:
            raise ValueError("At least one knowledge field is required")
        return self


class KnowledgeSearchRequest(BaseModel):
    query: str = Field(min_length=2, max_length=4000)
    limit: int = Field(default=6, ge=1, le=50)


class KnowledgeSearchHit(BaseModel):
    knowledge_id: UUID
    title: str
    chunk_index: int
    content: str
    score: float


class KnowledgeSearchResponse(BaseModel):
    items: list[KnowledgeSearchHit]
