from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class QueryRequest(BaseModel):
    content: str = Field(min_length=1, max_length=20_000)
    upload_ids: list[UUID] | None = Field(default=None, max_length=32)

    @field_validator("content", mode="after")
    @classmethod
    def normalize_content(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Message cannot be blank")
        return normalized
