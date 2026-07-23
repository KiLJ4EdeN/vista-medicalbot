from sqlalchemy import Boolean, Column, DateTime, String, true

from db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class User(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "users"

    email = Column(String(320), unique=True, index=True, nullable=False)
    full_name = Column(String(200), nullable=False)
    password_hash = Column(String(255), nullable=False)
    api_token = Column(String(64), unique=True, index=True, nullable=False)
    is_active = Column(Boolean, server_default=true(), index=True, nullable=False)
    last_activity_at = Column(DateTime(timezone=True), nullable=True, index=True)
