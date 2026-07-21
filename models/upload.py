from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, Column, ForeignKey, Index, String, Text, Uuid
from sqlalchemy.orm import Mapped, relationship

from db.base import Base, SoftDeleteMixin, TimestampMixin, UUIDPrimaryKeyMixin
from models.enums import ProcessingStatus, UploadKind, enum_type

if TYPE_CHECKING:
    from models.session import Session


class Upload(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "uploads"
    __table_args__ = (Index("ix_uploads_session_deleted", "session_id", "deleted_at"),)

    session_id = Column(Uuid, ForeignKey("sessions.id", ondelete="CASCADE"), index=True)
    object_key = Column(String(1024), unique=True)
    original_filename = Column(String(255))
    content_type = Column(String(100))
    size_bytes = Column(BigInteger)
    sha256 = Column(String(64), index=True)
    kind = Column(enum_type(UploadKind))
    processing_status = Column(enum_type(ProcessingStatus), default=ProcessingStatus.PENDING)
    extracted_text = Column(Text, default=None)
    processing_error = Column(Text, default=None)

    session: Mapped[Session] = relationship(back_populates="uploads")
