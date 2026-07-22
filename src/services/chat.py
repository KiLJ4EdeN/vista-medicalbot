import asyncio
from collections.abc import AsyncIterator
from contextlib import suppress
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import get_settings
from core.exceptions import ConflictError
from models import ChatMessage, Upload, User
from models.enums import MessageRole, MessageStatus
from services.agent import create_session_agent, load_chat_history
from services.sessions import get_session


@dataclass(frozen=True, slots=True)
class AgentStreamEvent:
    event: str
    data: dict[str, Any]


async def _prepare_messages(
    db: AsyncSession,
    user: User,
    session_id: UUID,
    content: str,
    upload_ids: list[UUID] | None = None,
) -> tuple[ChatMessage, ChatMessage]:
    chat_session = await get_session(db, user.id, session_id, for_update=True)
    active_generation = await db.scalar(
        select(ChatMessage.id).where(
            ChatMessage.session_id == session_id,
            ChatMessage.role == MessageRole.ASSISTANT,
            ChatMessage.status == MessageStatus.PENDING,
        )
    )
    if active_generation is not None:
        raise ConflictError("A response is already being generated for this session")

    latest_sequence = await db.scalar(
        select(func.max(ChatMessage.sequence_number)).where(ChatMessage.session_id == session_id)
    )
    next_sequence = (latest_sequence or 0) + 1

    extra: dict[str, Any] = {}
    if upload_ids:
        validated: list[str] = []
        for uid in upload_ids:
            upload = await db.scalar(
                select(Upload).where(
                    Upload.id == uid,
                    Upload.session_id == session_id,
                    Upload.deleted_at.is_(None),
                )
            )
            if upload is not None:
                validated.append(str(upload.id))
        if validated:
            extra["attachments"] = validated

    user_message = ChatMessage(
        session_id=session_id,
        role=MessageRole.USER,
        status=MessageStatus.COMPLETED,
        sequence_number=next_sequence,
        content=content,
        payload=extra,
    )
    assistant_message = ChatMessage(
        session_id=session_id,
        role=MessageRole.ASSISTANT,
        status=MessageStatus.PENDING,
        sequence_number=next_sequence + 1,
        content="",
    )
    if chat_session.title is None:
        chat_session.title = content[:200]
    chat_session.updated_at = datetime.now(UTC)
    db.add_all([user_message, assistant_message])
    await db.commit()
    await db.refresh(user_message)
    await db.refresh(assistant_message)
    return user_message, assistant_message


async def stream_query(
    db: AsyncSession,
    user: User,
    session_id: UUID,
    content: str,
    upload_ids: list[UUID] | None = None,
) -> AsyncIterator[AgentStreamEvent]:
    _, assistant_message = await _prepare_messages(
        db, user, session_id, content, upload_ids=upload_ids
    )
    tools_used: list[str] = []
    streamed_content = ""

    yield AgentStreamEvent("message_started", {"message_id": str(assistant_message.id)})
    try:
        history = await load_chat_history(db, session_id)
        agent = await create_session_agent(db, user_id=user.id, session_id=session_id)
        async for item in agent.astream(
            history, recursion_limit=get_settings().agent_recursion_limit
        ):
            if item.event == "tool_started":
                tools_used.append(item.content)
                yield AgentStreamEvent("tool_started", {"name": item.content})
            elif item.event == "tool_finished":
                yield AgentStreamEvent("tool_finished", {})
            elif item.event == "final":
                final_content = item.content
                if not final_content:
                    raise RuntimeError("The language model returned an empty response")
                streamed_content = final_content
                yield AgentStreamEvent("token", {"content": final_content})
                assistant_message.content = final_content
                assistant_message.status = MessageStatus.COMPLETED
                assistant_message.payload = {"tools_used": tools_used}
                await db.commit()
                yield AgentStreamEvent(
                    "message_completed", {"message_id": str(assistant_message.id)}
                )
                return
    except asyncio.CancelledError:
        assistant_message.content = streamed_content
        assistant_message.status = MessageStatus.FAILED
        assistant_message.payload = {"tools_used": tools_used, "error": "client_disconnected"}
        with suppress(Exception):
            await db.commit()
        raise
    except Exception:
        assistant_message.content = streamed_content
        assistant_message.status = MessageStatus.FAILED
        assistant_message.payload = {"tools_used": tools_used, "error": "generation_failed"}
        await db.commit()
        yield AgentStreamEvent(
            "error",
            {
                "message_id": str(assistant_message.id),
                "detail": "The assistant response could not be completed.",
            },
        )
