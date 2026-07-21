from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from models.enums import MessageRole, MessageStatus


class ImageAttachment(BaseModel):
    id: UUID
    original_filename: str
    content_type: str
    size_bytes: int
    download_url: str | None = None


class ChatMessage(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    role: MessageRole
    status: MessageStatus
    sequence_number: int
    content: str
    payload: dict[str, Any]
    created_at: datetime
    attachments: list[ImageAttachment] = []


class ChatMessageList(BaseModel):
    items: list[ChatMessage]
    total: int
    offset: int
    limit: int
