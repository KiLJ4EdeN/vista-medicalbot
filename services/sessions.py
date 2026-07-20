from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from core.exceptions import NotFoundError
from models import ChatSession, Message, Upload, User


async def get_owned_session(
    db: AsyncSession, user_id: UUID, session_id: UUID, *, for_update: bool = False
) -> ChatSession:
    query = select(ChatSession).where(
        ChatSession.id == session_id,
        ChatSession.user_id == user_id,
        ChatSession.deleted_at.is_(None),
    )
    if for_update:
        query = query.with_for_update()
    chat_session = await db.scalar(query)
    if chat_session is None:
        raise NotFoundError("Chat session not found")
    return chat_session


async def create_chat_session(db: AsyncSession, user: User, *, title: str | None) -> ChatSession:
    chat_session = ChatSession(user_id=user.id, title=title)
    db.add(chat_session)
    await db.commit()
    return chat_session


async def list_chat_sessions(
    db: AsyncSession, user_id: UUID, *, offset: int, limit: int
) -> tuple[list[ChatSession], int]:
    filters = (ChatSession.user_id == user_id, ChatSession.deleted_at.is_(None))
    total = await db.scalar(select(func.count()).select_from(ChatSession).where(*filters))
    items = list(
        await db.scalars(
            select(ChatSession)
            .where(*filters)
            .order_by(ChatSession.updated_at.desc(), ChatSession.id.desc())
            .offset(offset)
            .limit(limit)
        )
    )
    return items, total or 0


async def update_chat_session(
    db: AsyncSession, user_id: UUID, session_id: UUID, *, title: str
) -> ChatSession:
    chat_session = await get_owned_session(db, user_id, session_id, for_update=True)
    chat_session.title = title
    await db.commit()
    return chat_session


async def delete_chat_session(db: AsyncSession, user_id: UUID, session_id: UUID) -> None:
    chat_session = await get_owned_session(db, user_id, session_id, for_update=True)
    deleted_at = datetime.now(UTC)
    chat_session.deleted_at = deleted_at
    await db.execute(
        update(Upload)
        .where(Upload.session_id == session_id, Upload.deleted_at.is_(None))
        .values(deleted_at=deleted_at)
    )
    await db.commit()


async def list_session_messages(
    db: AsyncSession, user_id: UUID, session_id: UUID, *, offset: int, limit: int
) -> tuple[list[Message], int]:
    await get_owned_session(db, user_id, session_id)
    total = await db.scalar(
        select(func.count()).select_from(Message).where(Message.session_id == session_id)
    )
    messages = list(
        await db.scalars(
            select(Message)
            .where(Message.session_id == session_id)
            .order_by(Message.sequence_number.asc())
            .offset(offset)
            .limit(limit)
        )
    )
    return messages, total or 0
