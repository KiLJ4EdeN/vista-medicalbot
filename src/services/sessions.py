import asyncio
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.exceptions import NotFoundError
from models import ChatMessage, Session, Upload, User
from services.storage import remove_object


async def get_session(
    db: AsyncSession, user_id: UUID, session_id: UUID, *, for_update: bool = False
) -> Session:
    query = select(Session).where(
        Session.id == session_id,
        Session.user_id == user_id,
    )
    if for_update:
        query = query.with_for_update()
    chat_session = await db.scalar(query)
    if chat_session is None:
        raise NotFoundError("Chat session not found")
    return chat_session


async def create_session(db: AsyncSession, user: User, *, title: str | None) -> Session:
    chat_session = Session(user_id=user.id, title=title)
    db.add(chat_session)
    await db.commit()
    await db.refresh(chat_session)
    return chat_session


async def list_sessions(
    db: AsyncSession, user_id: UUID, *, offset: int, limit: int
) -> tuple[list[Session], int]:
    filters = (Session.user_id == user_id,)
    total = await db.scalar(select(func.count()).select_from(Session).where(*filters))
    items = list(
        await db.scalars(
            select(Session)
            .where(*filters)
            .order_by(Session.updated_at.desc(), Session.id.desc())
            .offset(offset)
            .limit(limit)
        )
    )
    return items, total or 0


async def rename_session(
    db: AsyncSession, user_id: UUID, session_id: UUID, *, title: str
) -> Session:
    chat_session = await get_session(db, user_id, session_id, for_update=True)
    chat_session.title = title
    await db.commit()
    await db.refresh(chat_session)
    return chat_session


async def delete_session(db: AsyncSession, user_id: UUID, session_id: UUID) -> None:
    chat_session = await get_session(db, user_id, session_id, for_update=True)
    object_keys = list(
        await db.scalars(select(Upload.object_key).where(Upload.session_id == session_id))
    )
    await asyncio.gather(*(remove_object(object_key) for object_key in object_keys))
    await db.delete(chat_session)
    await db.commit()


async def load_messages(
    db: AsyncSession, user_id: UUID, session_id: UUID, *, offset: int, limit: int
) -> tuple[list[ChatMessage], int]:
    await get_session(db, user_id, session_id)
    total = await db.scalar(
        select(func.count()).select_from(ChatMessage).where(ChatMessage.session_id == session_id)
    )
    messages = list(
        await db.scalars(
            select(ChatMessage)
            .where(ChatMessage.session_id == session_id)
            .order_by(ChatMessage.sequence_number.asc())
            .offset(offset)
            .limit(limit)
        )
    )
    return messages, total or 0
