from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, File, Form, Query, Response, UploadFile, status

from api.dependencies import AdminAccess, DatabaseSession
from schemas.knowledge import (
    KnowledgeListResponse,
    KnowledgeResponse,
    KnowledgeSearchHit,
    KnowledgeSearchRequest,
    KnowledgeSearchResponse,
    KnowledgeUpdateRequest,
)
from schemas.upload import UploadDownloadResponse
from services.knowledge import (
    cleanup_knowledge_entry,
    create_knowledge_download,
    create_knowledge_entry,
    get_knowledge_entry,
    list_knowledge_entries,
    mark_knowledge_deleted,
    mark_knowledge_pending,
    process_knowledge_entry,
    update_knowledge_entry,
)
from services.vector import hybrid_search

router = APIRouter(prefix="/knowledge", tags=["admin knowledge"])


@router.post("", response_model=KnowledgeResponse, status_code=status.HTTP_202_ACCEPTED)
async def upload_knowledge(
    background_tasks: BackgroundTasks,
    file: Annotated[UploadFile, File()],
    title: Annotated[str, Form(min_length=1, max_length=300)],
    source: Annotated[str, Form(min_length=1, max_length=300)],
    db: DatabaseSession,
    _admin: AdminAccess,
    description: Annotated[str | None, Form(max_length=5000)] = None,
    publication_year: Annotated[int | None, Form(ge=1800, le=2200)] = None,
    tags: Annotated[str, Form(description="Comma-separated tags")] = "",
) -> KnowledgeResponse:
    entry = await create_knowledge_entry(
        db,
        file,
        title=title,
        description=description,
        source=source,
        publication_year=publication_year,
        tags=tags.split(","),
    )
    background_tasks.add_task(process_knowledge_entry, entry.id)
    return KnowledgeResponse.model_validate(entry)


@router.get("", response_model=KnowledgeListResponse)
async def get_knowledge_entries(
    db: DatabaseSession,
    _admin: AdminAccess,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> KnowledgeListResponse:
    items, total = await list_knowledge_entries(db, offset=offset, limit=limit)
    return KnowledgeListResponse(items=items, total=total, offset=offset, limit=limit)


@router.post("/search/test", response_model=KnowledgeSearchResponse)
async def test_knowledge_search(
    payload: KnowledgeSearchRequest, _admin: AdminAccess
) -> KnowledgeSearchResponse:
    hits = await hybrid_search(
        payload.query,
        limit=payload.limit,
        source=payload.source,
        publication_year=payload.publication_year,
        tags=payload.tags,
    )
    return KnowledgeSearchResponse(
        items=[
            KnowledgeSearchHit(
                knowledge_id=hit.knowledge_id,
                title=hit.title,
                source=hit.source,
                publication_year=hit.publication_year,
                tags=hit.tags,
                chunk_index=hit.chunk_index,
                content=hit.content,
                score=hit.score,
            )
            for hit in hits
        ]
    )


@router.get("/{entry_id}", response_model=KnowledgeResponse)
async def get_knowledge(
    entry_id: UUID, db: DatabaseSession, _admin: AdminAccess
) -> KnowledgeResponse:
    return KnowledgeResponse.model_validate(await get_knowledge_entry(db, entry_id))


@router.patch("/{entry_id}", response_model=KnowledgeResponse)
async def patch_knowledge(
    entry_id: UUID,
    payload: KnowledgeUpdateRequest,
    background_tasks: BackgroundTasks,
    db: DatabaseSession,
    _admin: AdminAccess,
) -> KnowledgeResponse:
    entry = await update_knowledge_entry(db, entry_id, payload.model_dump(exclude_unset=True))
    background_tasks.add_task(process_knowledge_entry, entry.id)
    return KnowledgeResponse.model_validate(entry)


@router.post("/{entry_id}/reindex", response_model=KnowledgeResponse, status_code=202)
async def reindex_knowledge(
    entry_id: UUID,
    background_tasks: BackgroundTasks,
    db: DatabaseSession,
    _admin: AdminAccess,
) -> KnowledgeResponse:
    entry = await mark_knowledge_pending(db, entry_id)
    background_tasks.add_task(process_knowledge_entry, entry.id)
    return KnowledgeResponse.model_validate(entry)


@router.post("/{entry_id}/download", response_model=UploadDownloadResponse)
async def download_knowledge(
    entry_id: UUID, db: DatabaseSession, _admin: AdminAccess
) -> UploadDownloadResponse:
    url, expires_at = await create_knowledge_download(db, entry_id)
    return UploadDownloadResponse(url=url, expires_at=expires_at)


@router.delete("/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_knowledge(
    entry_id: UUID,
    background_tasks: BackgroundTasks,
    db: DatabaseSession,
    _admin: AdminAccess,
) -> Response:
    entry = await mark_knowledge_deleted(db, entry_id)
    background_tasks.add_task(cleanup_knowledge_entry, entry.id, entry.object_key)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
