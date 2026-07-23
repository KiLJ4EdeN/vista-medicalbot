from sqlalchemy import Column, ForeignKey, Index, String, Uuid

from db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from models.enums import ChatLanguage, enum_type


class Session(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "sessions"
    __table_args__ = (Index("ix_sessions_user_language", "user_id", "language"),)

    user_id = Column(Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    language = Column(enum_type(ChatLanguage), nullable=False)
    title = Column(String(200), nullable=True)
