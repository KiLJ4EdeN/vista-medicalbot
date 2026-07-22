from sqlalchemy import Column, ForeignKey, Integer, Text, UniqueConstraint, Uuid
from sqlalchemy.dialects.postgresql import JSONB

from db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from models.enums import MessageRole, MessageStatus, enum_type


class ChatMessage(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "chat_messages"
    __table_args__ = (UniqueConstraint("session_id", "sequence_number"),)

    session_id = Column(Uuid, ForeignKey("sessions.id", ondelete="CASCADE"))
    role = Column(enum_type(MessageRole))
    status = Column(enum_type(MessageStatus), default=MessageStatus.COMPLETED)
    sequence_number = Column(Integer)
    content = Column(Text, default="")
    payload = Column(JSONB, default=dict)
