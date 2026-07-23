from sqlalchemy import BigInteger, Column, ForeignKey, String, Uuid

from db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Upload(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "uploads"

    session_id = Column(
        Uuid, ForeignKey("sessions.id", ondelete="CASCADE"), index=True, nullable=False
    )
    object_key = Column(String(1024), unique=True, nullable=False)
    original_filename = Column(String(255), nullable=False)
    content_type = Column(String(100), nullable=False)
    size_bytes = Column(BigInteger, nullable=False)
    sha256 = Column(String(64), index=True, nullable=False)
