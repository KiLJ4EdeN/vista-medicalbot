import asyncio
from contextlib import suppress
from datetime import UTC, datetime, timedelta
from io import BytesIO
from uuid import UUID, uuid4

from fastapi import UploadFile
from langchain_text_splitters import RecursiveCharacterTextSplitter
from pypdf import PdfReader
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import get_settings
from core.exceptions import ExternalServiceError, InvalidInputError, NotFoundError
from db.session import async_session_factory
from models import KnowledgeEntry
from models.enums import ProcessingStatus
from services.documents import validate_document_upload
from services.storage import (
    get_object_bytes,
    presigned_download_url,
    put_object,
    remove_object,
)
from services.vector import KnowledgeChunk, delete_knowledge_vectors, index_chunks
from services.vlm import extract_text_with_vlm


async def create_knowledge_entry(
    db: AsyncSession,
    file: UploadFile,
    *,
    title: str,
) -> KnowledgeEntry:
    if not title.strip():
        raise InvalidInputError("Knowledge title cannot be blank")
    document = await validate_document_upload(file)
    entry_id = uuid4()
    object_key = f"knowledge/{entry_id}{document.suffix}"
    await put_object(
        object_key,
        BytesIO(document.data),
        length=document.size_bytes,
        content_type=document.content_type,
    )
    entry = KnowledgeEntry(
        id=entry_id,
        title=title.strip(),
        object_key=object_key,
        original_filename=document.original_filename,
        content_type=document.content_type,
        size_bytes=document.size_bytes,
        sha256=document.sha256,
        status=ProcessingStatus.PENDING,
    )
    db.add(entry)
    try:
        await db.commit()
    except Exception:
        await db.rollback()
        with suppress(ExternalServiceError):
            await remove_object(object_key)
        raise
    await db.refresh(entry)
    return entry


async def get_knowledge_entry(db: AsyncSession, entry_id: UUID) -> KnowledgeEntry:
    entry = await db.get(KnowledgeEntry, entry_id)
    if entry is None:
        raise NotFoundError("Knowledge entry not found")
    return entry


async def list_knowledge_entries(
    db: AsyncSession, *, offset: int, limit: int
) -> tuple[list[KnowledgeEntry], int]:
    total = await db.scalar(select(func.count()).select_from(KnowledgeEntry))
    entries = list(
        await db.scalars(
            select(KnowledgeEntry)
            .order_by(KnowledgeEntry.created_at.desc(), KnowledgeEntry.id.desc())
            .offset(offset)
            .limit(limit)
        )
    )
    return entries, total or 0


async def update_knowledge_entry(db: AsyncSession, entry_id: UUID, title: str) -> KnowledgeEntry:
    entry = await get_knowledge_entry(db, entry_id)
    normalized_title = title.strip()
    if not normalized_title:
        raise InvalidInputError("Knowledge title cannot be blank")
    entry.title = normalized_title
    entry.status = ProcessingStatus.PENDING
    entry.processing_error = None
    await db.commit()
    await db.refresh(entry)
    return entry


async def mark_knowledge_pending(db: AsyncSession, entry_id: UUID) -> KnowledgeEntry:
    entry = await get_knowledge_entry(db, entry_id)
    entry.status = ProcessingStatus.PENDING
    entry.processing_error = None
    await db.commit()
    await db.refresh(entry)
    return entry


async def delete_knowledge_entry(db: AsyncSession, entry_id: UUID) -> None:
    entry = await db.scalar(
        select(KnowledgeEntry).where(KnowledgeEntry.id == entry_id).with_for_update()
    )
    if entry is None:
        raise NotFoundError("Knowledge entry not found")
    await delete_knowledge_vectors(entry_id)
    await remove_object(entry.object_key)
    await db.delete(entry)
    await db.commit()


def _extract_pdf_text(data: bytes) -> str:
    reader = PdfReader(BytesIO(data), strict=False)
    return "\n\n".join(page.extract_text() or "" for page in reader.pages).strip()


async def _extract_text(entry: KnowledgeEntry, data: bytes) -> str:
    if entry.content_type == "application/pdf":
        text = await asyncio.to_thread(_extract_pdf_text, data)
        if len(text) >= 200:
            return text
    return await extract_text_with_vlm(data, entry.content_type, entry.original_filename)


def _split_text(text: str) -> list[str]:
    settings = get_settings()
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=settings.knowledge_chunk_size,
        chunk_overlap=settings.knowledge_chunk_overlap,
        separators=["\n\n", "\n", "。", "؟", ". ", " ", ""],
        length_function=len,
    )
    return [chunk.strip() for chunk in splitter.split_text(text) if chunk.strip()]


async def process_knowledge_entry(entry_id: UUID) -> None:
    async with async_session_factory() as db:
        entry = await db.scalar(
            select(KnowledgeEntry).where(KnowledgeEntry.id == entry_id).with_for_update()
        )
        if entry is None:
            return
        entry.processing_error = None
        await db.flush()

        try:
            data = await get_object_bytes(entry.object_key)
            text = await _extract_text(entry, data)
            chunks = _split_text(text)
            if not chunks:
                raise ExternalServiceError("No text could be extracted from the document")
            await delete_knowledge_vectors(entry.id)
            await index_chunks(
                [
                    KnowledgeChunk(
                        content=content,
                        title=entry.title,
                        knowledge_id=entry.id,
                        chunk_index=index,
                    )
                    for index, content in enumerate(chunks)
                ]
            )
            entry.status = ProcessingStatus.READY
            entry.chunk_count = len(chunks)
            entry.indexed_at = datetime.now(UTC)
            await db.commit()
        except Exception as error:
            await db.rollback()
            current = await db.get(KnowledgeEntry, entry_id)
            if current is not None:
                current.status = ProcessingStatus.FAILED
                current.processing_error = str(error)[:2000]
                await db.commit()


async def create_knowledge_download(db: AsyncSession, entry_id: UUID) -> tuple[str, datetime]:
    entry = await get_knowledge_entry(db, entry_id)
    settings = get_settings()
    expires = timedelta(minutes=settings.download_url_expire_minutes)
    url = await presigned_download_url(entry.object_key, expires=expires)
    return url, datetime.now(UTC) + expires
