from datetime import timedelta
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query, Response, status
from sqlalchemy import select

from api.dependencies import ChatLanguageHeader, CurrentUser, DatabaseSession
from models import Upload
from schemas.message import ChatMessage as ChatMessageSchema
from schemas.message import ChatMessageList, ImageAttachment
from schemas.session import (
    CreateSessionRequest,
    RenameSessionRequest,
    SessionInfo,
    SessionList,
)
from services.sessions import (
    create_session as create_session_service,
)
from services.sessions import (
    delete_session,
    get_session,
    list_sessions,
    load_messages,
    rename_session,
)
from services.storage import presigned_download_url

router = APIRouter(prefix="/sessions", tags=["sessions"])


@router.post("", response_model=SessionInfo, status_code=status.HTTP_201_CREATED)
async def create_session(
    payload: CreateSessionRequest,
    language: ChatLanguageHeader,
    user: CurrentUser,
    db: DatabaseSession,
) -> SessionInfo:
    chat_session = await create_session_service(db, user, language, title=payload.title)
    return SessionInfo.model_validate(chat_session)


@router.get("", response_model=SessionList)
async def get_sessions(
    user: CurrentUser,
    db: DatabaseSession,
    language: ChatLanguageHeader,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> SessionList:
    items, total = await list_sessions(db, user.id, language, offset=offset, limit=limit)
    return SessionList(items=items, total=total, offset=offset, limit=limit)


@router.get("/{session_id}", response_model=SessionInfo)
async def get_session_endpoint(
    session_id: UUID,
    language: ChatLanguageHeader,
    user: CurrentUser,
    db: DatabaseSession,
) -> SessionInfo:
    chat_session = await get_session(db, user.id, session_id, language)
    return SessionInfo.model_validate(chat_session)


@router.patch("/{session_id}", response_model=SessionInfo)
async def patch_session(
    session_id: UUID,
    payload: RenameSessionRequest,
    language: ChatLanguageHeader,
    user: CurrentUser,
    db: DatabaseSession,
) -> SessionInfo:
    chat_session = await rename_session(db, user.id, session_id, language, title=payload.title)
    return SessionInfo.model_validate(chat_session)


@router.delete("/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_session(
    session_id: UUID,
    language: ChatLanguageHeader,
    user: CurrentUser,
    db: DatabaseSession,
) -> Response:
    await delete_session(db, user.id, session_id, language)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{session_id}/messages", response_model=ChatMessageList)
async def get_messages(
    session_id: UUID,
    language: ChatLanguageHeader,
    user: CurrentUser,
    db: DatabaseSession,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
) -> ChatMessageList:
    items, total = await load_messages(
        db, user.id, session_id, language, offset=offset, limit=limit
    )
    enriched: list[ChatMessageSchema] = []
    for msg in items:
        attachment_ids = msg.payload.get("attachments", [])
        atts: list[ImageAttachment] = []
        if attachment_ids:
            uploads = await db.scalars(
                select(Upload).where(Upload.id.in_([UUID(a) for a in attachment_ids]))
            )
            for upload in uploads:
                url = await presigned_download_url(upload.object_key, expires=timedelta(hours=1))
                atts.append(
                    ImageAttachment(
                        id=upload.id,
                        original_filename=upload.original_filename,
                        content_type=upload.content_type,
                        size_bytes=upload.size_bytes,
                        download_url=url,
                    )
                )
        resp = ChatMessageSchema.model_validate(msg)
        resp.attachments = atts
        enriched.append(resp)
    return ChatMessageList(items=enriched, total=total, offset=offset, limit=limit)
