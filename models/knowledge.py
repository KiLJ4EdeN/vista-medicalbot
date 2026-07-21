from sqlalchemy import ARRAY, BigInteger, Column, DateTime, Index, Integer, String, Text

from db.base import Base, SoftDeleteMixin, TimestampMixin, UUIDPrimaryKeyMixin
from models.enums import ProcessingStatus, enum_type


class KnowledgeEntry(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "knowledge_entries"
    __table_args__ = (Index("ix_knowledge_status_deleted", "status", "deleted_at"),)

    title = Column(String(300))
    description = Column(Text, default=None)
    source = Column(String(300))
    publication_year = Column(Integer, default=None, index=True)
    tags = Column(ARRAY(String(100)), default=list)
    object_key = Column(String(1024), unique=True)
    original_filename = Column(String(255))
    content_type = Column(String(100))
    size_bytes = Column(BigInteger)
    sha256 = Column(String(64), index=True)
    status = Column(enum_type(ProcessingStatus), default=ProcessingStatus.PENDING, index=True)
    chunk_count = Column(Integer, default=0)
    processing_error = Column(Text, default=None)
    indexed_at = Column(DateTime(timezone=True), default=None)
