from dataclasses import dataclass
from datetime import UTC, datetime, time, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement

from core.config import get_settings
from core.exceptions import NotFoundError
from models import ChatMessage, Session, User
from models.enums import MessageRole


@dataclass(frozen=True, slots=True)
class DashboardStats:
    total_users: int
    registrations_today: int
    active_users: int
    online_users: int
    sessions_total: int
    sessions_today: int
    chats_total: int
    chats_today: int
    generated_at: datetime


async def list_users(
    db: AsyncSession,
    *,
    offset: int,
    limit: int,
    search: str | None,
    is_active: bool | None,
) -> tuple[list[User], int]:
    conditions = []
    if search:
        term = f"%{search.strip()}%"
        conditions.append(or_(User.email.ilike(term), User.full_name.ilike(term)))
    if is_active is not None:
        conditions.append(User.is_active.is_(is_active))

    total = await db.scalar(select(func.count()).select_from(User).where(*conditions))
    users = list(
        await db.scalars(
            select(User)
            .where(*conditions)
            .order_by(User.created_at.desc(), User.id.desc())
            .offset(offset)
            .limit(limit)
        )
    )
    return users, total or 0


async def get_user(db: AsyncSession, user_id: UUID, *, for_update: bool = False) -> User:
    query = select(User).where(User.id == user_id)
    if for_update:
        query = query.with_for_update()
    user = await db.scalar(query)
    if user is None:
        raise NotFoundError("User not found")
    return user


async def set_user_active(db: AsyncSession, user_id: UUID, *, is_active: bool) -> User:
    user = await get_user(db, user_id, for_update=True)
    if user.is_active == is_active:
        await db.rollback()
        await db.refresh(user)
        return user

    user.is_active = is_active
    await db.commit()
    await db.refresh(user)
    return user


async def dashboard_stats(db: AsyncSession) -> DashboardStats:
    now = datetime.now(UTC)
    today = datetime.combine(now.date(), time.min, tzinfo=UTC)
    online_since = now - timedelta(minutes=get_settings().online_window_minutes)

    async def count(model: Any, *conditions: ColumnElement[bool]) -> int:
        value = await db.scalar(select(func.count()).select_from(model).where(*conditions))
        return value or 0

    return DashboardStats(
        total_users=await count(User),
        registrations_today=await count(User, User.created_at >= today),
        active_users=await count(User, User.is_active.is_(True)),
        online_users=await count(
            User,
            User.is_active.is_(True),
            User.last_activity_at.is_not(None),
            User.last_activity_at >= online_since,
        ),
        sessions_total=await count(Session),
        sessions_today=await count(Session, Session.created_at >= today),
        chats_total=await count(ChatMessage, ChatMessage.role == MessageRole.USER),
        chats_today=await count(
            ChatMessage,
            ChatMessage.role == MessageRole.USER,
            ChatMessage.created_at >= today,
        ),
        generated_at=now,
    )
