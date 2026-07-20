from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from models.enums import MessageRole, MessageStatus


class MessageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    role: MessageRole
    status: MessageStatus
    sequence_number: int
    content: str
    extra_data: dict[str, Any]
    created_at: datetime


class MessageListResponse(BaseModel):
    items: list[MessageResponse]
    total: int
    offset: int
    limit: int
