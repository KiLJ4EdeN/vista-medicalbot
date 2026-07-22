from sqlalchemy import Column, ForeignKey, Index, String, Uuid

from db.base import Base, SoftDeleteMixin, TimestampMixin, UUIDPrimaryKeyMixin


class Session(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "sessions"
    __table_args__ = (Index("ix_sessions_user_deleted", "user_id", "deleted_at"),)

    user_id = Column(Uuid, ForeignKey("users.id", ondelete="CASCADE"))
    title = Column(String(200), default=None)
