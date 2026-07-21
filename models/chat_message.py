from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Column, ForeignKey, Index, Integer, Text, UniqueConstraint, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, relationship

from db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from models.enums import MessageRole, MessageStatus, enum_type

if TYPE_CHECKING:
    from models.session import Session


class ChatMessage(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "chat_messages"
    __table_args__ = (
        UniqueConstraint("session_id", "sequence_number"),
        Index("ix_chat_messages_session_sequence", "session_id", "sequence_number"),
    )

    session_id = Column(Uuid, ForeignKey("sessions.id", ondelete="CASCADE"), index=True)
    role = Column(enum_type(MessageRole))
    status = Column(enum_type(MessageStatus), default=MessageStatus.COMPLETED)
    sequence_number = Column(Integer)
    content = Column(Text, default="")
    payload = Column(JSONB, default=dict)

    session: Mapped[Session] = relationship(back_populates="messages")
