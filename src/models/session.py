from sqlalchemy import Column, ForeignKey, String, Uuid

from db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Session(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "sessions"

    user_id = Column(Uuid, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    title = Column(String(200), nullable=True)
