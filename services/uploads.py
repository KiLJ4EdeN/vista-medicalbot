from contextlib import suppress
from datetime import UTC, datetime, timedelta
from io import BytesIO
from uuid import UUID, uuid4

from fastapi import UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import get_settings
from core.exceptions import ExternalServiceError, NotFoundError
from models import ChatSession, Upload
from models.enums import ProcessingStatus
from services.documents import validate_document_upload
from services.sessions import get_owned_session
from services.storage import presigned_download_url, put_object, remove_object


async def create_upload(
    db: AsyncSession, user_id: UUID, session_id: UUID, file: UploadFile
) -> Upload:
    chat_session = await get_owned_session(db, user_id, session_id)
    document = await validate_document_upload(file)
    object_key = f"sessions/{chat_session.user_id}/{session_id}/{uuid4()}{document.suffix}"

    await put_object(
        object_key,
        BytesIO(document.data),
        length=document.size_bytes,
        content_type=document.content_type,
    )
    upload = Upload(
        session_id=session_id,
        object_key=object_key,
        original_filename=document.original_filename,
        content_type=document.content_type,
        size_bytes=document.size_bytes,
        sha256=document.sha256,
        kind=document.kind,
        processing_status=ProcessingStatus.PENDING,
    )
    db.add(upload)
    try:
        await db.commit()
    except Exception:
        await db.rollback()
        with suppress(ExternalServiceError):
            await remove_object(object_key)
        raise
    await db.refresh(upload)
    return upload


async def get_owned_upload(db: AsyncSession, user_id: UUID, upload_id: UUID) -> Upload:
    upload = await db.scalar(
        select(Upload)
        .join(ChatSession, ChatSession.id == Upload.session_id)
        .where(
            Upload.id == upload_id,
            Upload.deleted_at.is_(None),
            ChatSession.user_id == user_id,
            ChatSession.deleted_at.is_(None),
        )
    )
    if upload is None:
        raise NotFoundError("Upload not found")
    return upload


async def list_session_uploads(db: AsyncSession, user_id: UUID, session_id: UUID) -> list[Upload]:
    await get_owned_session(db, user_id, session_id)
    return list(
        await db.scalars(
            select(Upload)
            .where(Upload.session_id == session_id, Upload.deleted_at.is_(None))
            .order_by(Upload.created_at.asc(), Upload.id.asc())
        )
    )


async def delete_upload(db: AsyncSession, user_id: UUID, upload_id: UUID) -> None:
    upload = await get_owned_upload(db, user_id, upload_id)
    await remove_object(upload.object_key)
    upload.deleted_at = datetime.now(UTC)
    await db.commit()


async def create_upload_download(
    db: AsyncSession, user_id: UUID, upload_id: UUID
) -> tuple[str, datetime]:
    upload = await get_owned_upload(db, user_id, upload_id)
    settings = get_settings()
    expires = timedelta(minutes=settings.download_url_expire_minutes)
    url = await presigned_download_url(upload.object_key, expires=expires)
    return url, datetime.now(UTC) + expires
