from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, File, Response, UploadFile, status

from api.dependencies import ChatLanguageHeader, CurrentUser, DatabaseSession
from schemas.upload import UploadDownloadResponse, UploadListResponse, UploadResponse
from services.uploads import (
    create_upload,
    create_upload_download,
    delete_upload,
    get_owned_upload,
    list_session_uploads,
)

router = APIRouter(prefix="/uploads", tags=["uploads"])


@router.post(
    "/sessions/{session_id}",
    response_model=UploadResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_session_file(
    session_id: UUID,
    file: Annotated[UploadFile, File()],
    language: ChatLanguageHeader,
    user: CurrentUser,
    db: DatabaseSession,
) -> UploadResponse:
    upload = await create_upload(db, user.id, session_id, language, file)
    return UploadResponse.model_validate(upload)


@router.get("/sessions/{session_id}", response_model=UploadListResponse)
async def get_session_uploads(
    session_id: UUID,
    language: ChatLanguageHeader,
    user: CurrentUser,
    db: DatabaseSession,
) -> UploadListResponse:
    uploads = await list_session_uploads(db, user.id, session_id, language)
    return UploadListResponse(items=uploads)


@router.get("/{upload_id}", response_model=UploadResponse)
async def get_upload(
    upload_id: UUID,
    language: ChatLanguageHeader,
    user: CurrentUser,
    db: DatabaseSession,
) -> UploadResponse:
    upload = await get_owned_upload(db, user.id, upload_id, language)
    return UploadResponse.model_validate(upload)


@router.post("/{upload_id}/download", response_model=UploadDownloadResponse)
async def download_upload(
    upload_id: UUID,
    language: ChatLanguageHeader,
    user: CurrentUser,
    db: DatabaseSession,
) -> UploadDownloadResponse:
    url, expires_at = await create_upload_download(db, user.id, upload_id, language)
    return UploadDownloadResponse(url=url, expires_at=expires_at)


@router.delete("/{upload_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_upload(
    upload_id: UUID,
    language: ChatLanguageHeader,
    user: CurrentUser,
    db: DatabaseSession,
) -> Response:
    await delete_upload(db, user.id, upload_id, language)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
