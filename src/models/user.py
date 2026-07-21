from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Column, DateTime, String, true
from sqlalchemy.orm import Mapped, relationship

from db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from models.refresh_token import RefreshToken
    from models.session import Session


class User(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "users"

    email = Column(String(320), unique=True, index=True)
    full_name = Column(String(200))
    password_hash = Column(String(255))
    is_active = Column(Boolean, server_default=true(), index=True)
    last_activity_at = Column(DateTime(timezone=True), default=None, index=True)

    sessions: Mapped[list[Session]] = relationship(
        back_populates="user", cascade="all, delete-orphan", passive_deletes=True
    )
    refresh_tokens: Mapped[list[RefreshToken]] = relationship(
        back_populates="user", cascade="all, delete-orphan", passive_deletes=True
    )
