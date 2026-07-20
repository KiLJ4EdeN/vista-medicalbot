from pydantic import BaseModel, Field, field_validator


class ChatRequest(BaseModel):
    content: str = Field(min_length=1, max_length=20_000)

    @field_validator("content", mode="after")
    @classmethod
    def normalize_content(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Message cannot be blank")
        return normalized
