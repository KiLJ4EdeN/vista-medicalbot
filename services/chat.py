import asyncio
from collections.abc import AsyncIterator
from contextlib import suppress
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from langchain_core.callbacks import AsyncCallbackHandler
from langchain_core.messages import AIMessage
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import get_settings
from core.exceptions import ConflictError
from models import Message, User
from models.enums import MessageRole, MessageStatus
from services.agent import create_session_agent, load_chat_history
from services.sessions import get_owned_session


@dataclass(frozen=True, slots=True)
class AgentStreamEvent:
    event: str
    data: dict[str, Any]


class AgentEventHandler(AsyncCallbackHandler):
    def __init__(self, queue: asyncio.Queue[AgentStreamEvent]) -> None:
        self.queue = queue

    async def on_llm_new_token(
        self, token: str | list[str | dict[str, Any]], **kwargs: Any
    ) -> None:
        text = _content_text(token)
        if text:
            await self.queue.put(AgentStreamEvent("token", {"content": text}))

    async def on_tool_start(
        self, serialized: dict[str, Any], input_str: str, **kwargs: Any
    ) -> None:
        name = str(serialized.get("name", "tool"))
        await self.queue.put(AgentStreamEvent("tool_started", {"name": name}))

    async def on_tool_end(self, output: Any, **kwargs: Any) -> None:
        await self.queue.put(AgentStreamEvent("tool_finished", {}))


def _content_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(
            part if isinstance(part, str) else str(part.get("text", ""))
            for part in content
            if isinstance(part, (str, dict))
        )
    return ""


async def _prepare_messages(
    db: AsyncSession, user: User, session_id: UUID, content: str
) -> tuple[Message, Message]:
    chat_session = await get_owned_session(db, user.id, session_id, for_update=True)
    active_generation = await db.scalar(
        select(Message.id).where(
            Message.session_id == session_id,
            Message.role == MessageRole.ASSISTANT,
            Message.status == MessageStatus.PENDING,
        )
    )
    if active_generation is not None:
        raise ConflictError("A response is already being generated for this session")

    latest_sequence = await db.scalar(
        select(func.max(Message.sequence_number)).where(Message.session_id == session_id)
    )
    next_sequence = (latest_sequence or 0) + 1

    user_message = Message(
        session_id=session_id,
        role=MessageRole.USER,
        status=MessageStatus.COMPLETED,
        sequence_number=next_sequence,
        content=content,
    )
    assistant_message = Message(
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


def _final_content(result: dict[str, Any]) -> str:
    for message in reversed(result.get("messages", [])):
        if isinstance(message, AIMessage) and not getattr(message, "tool_calls", None):
            content = _content_text(message.content)
            if content:
                return content
    return ""


async def stream_agent_chat(
    db: AsyncSession, user: User, session_id: UUID, content: str
) -> AsyncIterator[AgentStreamEvent]:
    _, assistant_message = await _prepare_messages(db, user, session_id, content)
    queue: asyncio.Queue[AgentStreamEvent] = asyncio.Queue()
    callback = AgentEventHandler(queue)
    tools_used: list[str] = []
    streamed_content = ""
    task: asyncio.Task[None] | None = None

    yield AgentStreamEvent("message_started", {"message_id": str(assistant_message.id)})
    try:
        history = await load_chat_history(db, session_id)
        agent = await create_session_agent(db, user_id=user.id, session_id=session_id)

        async def invoke_agent() -> None:
            try:
                result = await agent.ainvoke(
                    {"messages": history},
                    config={
                        "callbacks": [callback],
                        "recursion_limit": get_settings().agent_recursion_limit,
                    },
                )
                await queue.put(AgentStreamEvent("agent_done", {"result": result}))
            except Exception as error:
                await queue.put(AgentStreamEvent("agent_error", {"error": str(error)}))

        task = asyncio.create_task(invoke_agent())
        while True:
            item = await queue.get()
            if item.event == "token":
                streamed_content += str(item.data["content"])
                yield item
            elif item.event == "tool_started":
                tools_used.append(str(item.data["name"]))
                yield item
            elif item.event == "tool_finished":
                yield item
            elif item.event == "agent_done":
                final_content = _final_content(item.data["result"])
                if not final_content:
                    raise RuntimeError("The language model returned an empty response")
                if not streamed_content:
                    yield AgentStreamEvent("token", {"content": final_content})
                elif final_content.startswith(streamed_content):
                    remainder = final_content[len(streamed_content) :]
                    if remainder:
                        yield AgentStreamEvent("token", {"content": remainder})
                assistant_message.content = final_content
                assistant_message.status = MessageStatus.COMPLETED
                assistant_message.extra_data = {"tools_used": tools_used}
                await db.commit()
                yield AgentStreamEvent(
                    "message_completed", {"message_id": str(assistant_message.id)}
                )
                return
            elif item.event == "agent_error":
                raise RuntimeError(str(item.data["error"]))
    except asyncio.CancelledError:
        if task is not None:
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task
        assistant_message.content = streamed_content
        assistant_message.status = MessageStatus.FAILED
        assistant_message.extra_data = {"tools_used": tools_used, "error": "client_disconnected"}
        with suppress(Exception):
            await db.commit()
        raise
    except Exception:
        assistant_message.content = streamed_content
        assistant_message.status = MessageStatus.FAILED
        assistant_message.extra_data = {"tools_used": tools_used, "error": "generation_failed"}
        await db.commit()
        yield AgentStreamEvent(
            "error",
            {
                "message_id": str(assistant_message.id),
                "detail": "The assistant response could not be completed.",
            },
        )
    finally:
        if task is not None and not task.done():
            task.cancel()
