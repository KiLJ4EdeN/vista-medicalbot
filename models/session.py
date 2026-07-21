from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Column, ForeignKey, Index, String, Uuid
from sqlalchemy.orm import Mapped, relationship

from db.base import Base, SoftDeleteMixin, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from models.chat_message import ChatMessage
    from models.upload import Upload
    from models.user import User


class Session(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "sessions"
    __table_args__ = (Index("ix_sessions_user_deleted", "user_id", "deleted_at"),)

    user_id = Column(Uuid, ForeignKey("users.id", ondelete="CASCADE"), index=True)
    title = Column(String(200), default=None)

    user: Mapped[User] = relationship(back_populates="sessions")
    messages: Mapped[list[ChatMessage]] = relationship(
        back_populates="session", cascade="all, delete-orphan", passive_deletes=True
    )
    uploads: Mapped[list[Upload]] = relationship(
        back_populates="session", cascade="all, delete-orphan", passive_deletes=True
    )
