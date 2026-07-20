from __future__ import annotations

from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy import ForeignKey, Index, Integer, Text, UniqueConstraint, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from models.enums import MessageRole, MessageStatus, enum_type

if TYPE_CHECKING:
    from models.chat_session import ChatSession


class Message(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "messages"
    __table_args__ = (
        UniqueConstraint("session_id", "sequence_number"),
        Index("ix_messages_session_sequence", "session_id", "sequence_number"),
    )

    session_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("chat_sessions.id", ondelete="CASCADE"), index=True
    )
    role: Mapped[MessageRole] = mapped_column(enum_type(MessageRole))
    status: Mapped[MessageStatus] = mapped_column(
        enum_type(MessageStatus), default=MessageStatus.COMPLETED
    )
    sequence_number: Mapped[int] = mapped_column(Integer)
    content: Mapped[str] = mapped_column(Text, default="")
    extra_data: Mapped[dict[str, Any]] = mapped_column("metadata", JSONB, default=dict)

    session: Mapped[ChatSession] = relationship(back_populates="messages")
