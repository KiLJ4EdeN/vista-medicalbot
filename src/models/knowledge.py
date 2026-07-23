from sqlalchemy import BigInteger, Column, DateTime, Integer, String, Text

from db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from models.enums import ProcessingStatus, enum_type


class KnowledgeEntry(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "knowledge_entries"

    title = Column(String(300), nullable=False)
    object_key = Column(String(1024), unique=True, nullable=False)
    original_filename = Column(String(255), nullable=False)
    content_type = Column(String(100), nullable=False)
    size_bytes = Column(BigInteger, nullable=False)
    sha256 = Column(String(64), index=True, nullable=False)
    status = Column(
        enum_type(ProcessingStatus),
        default=ProcessingStatus.PENDING,
        index=True,
        nullable=False,
    )
    chunk_count = Column(Integer, default=0, nullable=False)
    processing_error = Column(Text, nullable=True)
    indexed_at = Column(DateTime(timezone=True), nullable=True)
