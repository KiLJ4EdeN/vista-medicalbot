from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query, Response, status

from api.dependencies import CurrentUser, DatabaseSession
from schemas.message import MessageListResponse, MessageResponse
from schemas.session import (
    SessionCreateRequest,
    SessionListResponse,
    SessionResponse,
    SessionUpdateRequest,
)
from services.sessions import (
    create_chat_session,
    delete_chat_session,
    get_owned_session,
    list_chat_sessions,
    list_session_messages,
    update_chat_session,
)

router = APIRouter(prefix="/sessions", tags=["sessions"])


@router.post("", response_model=SessionResponse, status_code=status.HTTP_201_CREATED)
async def create_session(
    payload: SessionCreateRequest, user: CurrentUser, db: DatabaseSession
) -> SessionResponse:
    chat_session = await create_chat_session(db, user, title=payload.title)
    return SessionResponse.model_validate(chat_session)


@router.get("", response_model=SessionListResponse)
async def get_sessions(
    user: CurrentUser,
    db: DatabaseSession,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> SessionListResponse:
    items, total = await list_chat_sessions(db, user.id, offset=offset, limit=limit)
    return SessionListResponse(items=items, total=total, offset=offset, limit=limit)


@router.get("/{session_id}", response_model=SessionResponse)
async def get_session(session_id: UUID, user: CurrentUser, db: DatabaseSession) -> SessionResponse:
    chat_session = await get_owned_session(db, user.id, session_id)
    return SessionResponse.model_validate(chat_session)


@router.patch("/{session_id}", response_model=SessionResponse)
async def patch_session(
    session_id: UUID,
    payload: SessionUpdateRequest,
    user: CurrentUser,
    db: DatabaseSession,
) -> SessionResponse:
    chat_session = await update_chat_session(db, user.id, session_id, title=payload.title)
    return SessionResponse.model_validate(chat_session)


@router.delete("/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_session(session_id: UUID, user: CurrentUser, db: DatabaseSession) -> Response:
    await delete_chat_session(db, user.id, session_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{session_id}/messages", response_model=MessageListResponse)
async def get_messages(
    session_id: UUID,
    user: CurrentUser,
    db: DatabaseSession,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
) -> MessageListResponse:
    items, total = await list_session_messages(db, user.id, session_id, offset=offset, limit=limit)
    return MessageListResponse(
        items=[MessageResponse.model_validate(item) for item in items],
        total=total,
        offset=offset,
        limit=limit,
    )
