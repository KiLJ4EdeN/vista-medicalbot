from sqlalchemy import BigInteger, Column, ForeignKey, Index, String, Uuid

from db.base import Base, SoftDeleteMixin, TimestampMixin, UUIDPrimaryKeyMixin


class Upload(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "uploads"
    __table_args__ = (Index("ix_uploads_session_deleted", "session_id", "deleted_at"),)

    session_id = Column(Uuid, ForeignKey("sessions.id", ondelete="CASCADE"))
    object_key = Column(String(1024), unique=True)
    original_filename = Column(String(255))
    content_type = Column(String(100))
    size_bytes = Column(BigInteger)
    sha256 = Column(String(64), index=True)
