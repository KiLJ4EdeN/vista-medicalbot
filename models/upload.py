from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import BigInteger, ForeignKey, Index, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.base import Base, SoftDeleteMixin, TimestampMixin, UUIDPrimaryKeyMixin
from models.enums import ProcessingStatus, UploadKind, enum_type

if TYPE_CHECKING:
    from models.chat_session import ChatSession


class Upload(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "uploads"
    __table_args__ = (Index("ix_uploads_session_deleted", "session_id", "deleted_at"),)

    session_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("chat_sessions.id", ondelete="CASCADE"), index=True
    )
    object_key: Mapped[str] = mapped_column(String(1024), unique=True)
    original_filename: Mapped[str] = mapped_column(String(255))
    content_type: Mapped[str] = mapped_column(String(100))
    size_bytes: Mapped[int] = mapped_column(BigInteger)
    sha256: Mapped[str] = mapped_column(String(64), index=True)
    kind: Mapped[UploadKind] = mapped_column(enum_type(UploadKind))
    processing_status: Mapped[ProcessingStatus] = mapped_column(
        enum_type(ProcessingStatus), default=ProcessingStatus.PENDING
    )
    extracted_text: Mapped[str | None] = mapped_column(Text, default=None)
    processing_error: Mapped[str | None] = mapped_column(Text, default=None)

    session: Mapped[ChatSession] = relationship(back_populates="uploads")
