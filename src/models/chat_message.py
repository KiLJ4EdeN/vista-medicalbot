from sqlalchemy import Column, ForeignKey, Integer, Text, UniqueConstraint, Uuid
from sqlalchemy.dialects.postgresql import JSONB

from db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from models.enums import MessageRole, MessageStatus, enum_type


class ChatMessage(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "chat_messages"
    __table_args__ = (UniqueConstraint("session_id", "sequence_number"),)

    session_id = Column(Uuid, ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False)
    role = Column(enum_type(MessageRole), nullable=False)
    status = Column(enum_type(MessageStatus), default=MessageStatus.COMPLETED, nullable=False)
    sequence_number = Column(Integer, nullable=False)
    content = Column(Text, default="", nullable=False)
    payload = Column(JSONB, default=dict, nullable=False)
