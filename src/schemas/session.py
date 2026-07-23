from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from models.enums import ChatLanguage


class CreateSessionRequest(BaseModel):
    title: str | None = Field(default=None, max_length=200)

    @field_validator("title", mode="after")
    @classmethod
    def normalize_title(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None


class RenameSessionRequest(BaseModel):
    title: str = Field(min_length=1, max_length=200)

    @field_validator("title", mode="after")
    @classmethod
    def normalize_title(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Title cannot be blank")
        return normalized


class SessionInfo(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    language: ChatLanguage
    title: str | None
    created_at: datetime
    updated_at: datetime


class SessionList(BaseModel):
    items: list[SessionInfo]
    total: int
    offset: int
    limit: int
