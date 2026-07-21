from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Column, DateTime, ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, relationship

from db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from models.user import User


class RefreshToken(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "refresh_tokens"

    user_id = Column(Uuid, ForeignKey("users.id", ondelete="CASCADE"), index=True)
    token_hash = Column(String(64), unique=True)
    family_id = Column(Uuid, index=True)
    expires_at = Column(DateTime(timezone=True), index=True)
    revoked_at = Column(DateTime(timezone=True), default=None)
    revoke_reason = Column(String(100), default=None)
    replaced_by_id = Column(
        Uuid, ForeignKey("refresh_tokens.id", ondelete="SET NULL"), default=None
    )

    user: Mapped[User] = relationship(back_populates="refresh_tokens")
