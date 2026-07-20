import json
from collections.abc import AsyncIterator
from uuid import UUID

from fastapi import APIRouter
from sse_starlette import EventSourceResponse

from api.dependencies import CurrentUser, DatabaseSession
from schemas.chat import ChatRequest
from services.chat import stream_agent_chat

router = APIRouter(prefix="/sessions", tags=["chat"])


@router.post(
    "/{session_id}/messages",
    response_class=EventSourceResponse,
    responses={200: {"content": {"text/event-stream": {}}}},
)
async def chat(
    session_id: UUID, payload: ChatRequest, user: CurrentUser, db: DatabaseSession
) -> EventSourceResponse:
    stream = stream_agent_chat(db, user, session_id, payload.content)
    first_event = await anext(stream)

    async def events() -> AsyncIterator[dict[str, str]]:
        yield {
            "event": first_event.event,
            "data": json.dumps(first_event.data, ensure_ascii=False),
        }
        async for item in stream:
            yield {"event": item.event, "data": json.dumps(item.data, ensure_ascii=False)}

    return EventSourceResponse(events())
