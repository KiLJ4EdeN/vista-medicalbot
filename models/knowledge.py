from datetime import datetime

from sqlalchemy import ARRAY, BigInteger, DateTime, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base, SoftDeleteMixin, TimestampMixin, UUIDPrimaryKeyMixin
from models.enums import ProcessingStatus, enum_type


class KnowledgeEntry(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "knowledge_entries"
    __table_args__ = (Index("ix_knowledge_status_deleted", "status", "deleted_at"),)

    title: Mapped[str] = mapped_column(String(300))
    description: Mapped[str | None] = mapped_column(Text, default=None)
    source: Mapped[str] = mapped_column(String(300))
    publication_year: Mapped[int | None] = mapped_column(Integer, default=None, index=True)
    tags: Mapped[list[str]] = mapped_column(ARRAY(String(100)), default=list)
    object_key: Mapped[str] = mapped_column(String(1024), unique=True)
    original_filename: Mapped[str] = mapped_column(String(255))
    content_type: Mapped[str] = mapped_column(String(100))
    size_bytes: Mapped[int] = mapped_column(BigInteger)
    sha256: Mapped[str] = mapped_column(String(64), index=True)
    status: Mapped[ProcessingStatus] = mapped_column(
        enum_type(ProcessingStatus), default=ProcessingStatus.PENDING, index=True
    )
    chunk_count: Mapped[int] = mapped_column(Integer, default=0)
    processing_error: Mapped[str | None] = mapped_column(Text, default=None)
    indexed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
