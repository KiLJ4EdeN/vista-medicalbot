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
from models.enums import ProcessingStatus, UploadKind
from services.documents import ValidatedDocument, validate_document_upload
from services.storage import (
    get_object_bytes,
    presigned_download_url,
    put_object,
    remove_object,
)
from services.vector import KnowledgeChunk, delete_knowledge_vectors, index_chunks
from services.vlm import extract_text_with_vlm


def normalize_tags(tags: list[str]) -> list[str]:
    return list(dict.fromkeys(tag.strip().lower() for tag in tags if tag.strip()))[:50]


async def create_knowledge_entry(
    db: AsyncSession,
    file: UploadFile,
    *,
    title: str,
    description: str | None,
    source: str,
    publication_year: int | None,
    tags: list[str],
) -> KnowledgeEntry:
    if not title.strip() or not source.strip():
        raise InvalidInputError("Knowledge title and source cannot be blank")
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
        description=description.strip() if description else None,
        source=source.strip(),
        publication_year=publication_year,
        tags=normalize_tags(tags),
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
    entry = await db.scalar(
        select(KnowledgeEntry).where(
            KnowledgeEntry.id == entry_id, KnowledgeEntry.deleted_at.is_(None)
        )
    )
    if entry is None:
        raise NotFoundError("Knowledge entry not found")
    return entry


async def list_knowledge_entries(
    db: AsyncSession, *, offset: int, limit: int
) -> tuple[list[KnowledgeEntry], int]:
    active = KnowledgeEntry.deleted_at.is_(None)
    total = await db.scalar(select(func.count()).select_from(KnowledgeEntry).where(active))
    entries = list(
        await db.scalars(
            select(KnowledgeEntry)
            .where(active)
            .order_by(KnowledgeEntry.created_at.desc(), KnowledgeEntry.id.desc())
            .offset(offset)
            .limit(limit)
        )
    )
    return entries, total or 0


async def update_knowledge_entry(
    db: AsyncSession, entry_id: UUID, changes: dict[str, object]
) -> KnowledgeEntry:
    entry = await get_knowledge_entry(db, entry_id)
    for field, value in changes.items():
        if field in {"title", "source"} and isinstance(value, str):
            value = value.strip()
            if not value:
                raise InvalidInputError(f"Knowledge {field} cannot be blank")
        elif field == "description" and isinstance(value, str):
            value = value.strip() or None
        elif field == "tags" and isinstance(value, list):
            value = normalize_tags([tag for tag in value if isinstance(tag, str)])
        setattr(entry, field, value)
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


async def mark_knowledge_deleted(db: AsyncSession, entry_id: UUID) -> KnowledgeEntry:
    entry = await get_knowledge_entry(db, entry_id)
    entry.deleted_at = datetime.now(UTC)
    await db.commit()
    await db.refresh(entry)
    return entry


def _extract_pdf_text(document: ValidatedDocument) -> str:
    reader = PdfReader(BytesIO(document.data), strict=False)
    return "\n\n".join(page.extract_text() or "" for page in reader.pages).strip()


async def _extract_text(entry: KnowledgeEntry, data: bytes) -> str:
    if entry.content_type == "application/pdf":
        document = ValidatedDocument(
            data=data,
            original_filename=entry.original_filename,
            content_type=entry.content_type,
            suffix=".pdf",
            size_bytes=entry.size_bytes,
            sha256=entry.sha256,
            kind=UploadKind.PDF,
        )
        text = await asyncio.to_thread(_extract_pdf_text, document)
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
            select(KnowledgeEntry).where(
                KnowledgeEntry.id == entry_id, KnowledgeEntry.deleted_at.is_(None)
            )
        )
        if entry is None:
            return
        entry.status = ProcessingStatus.PROCESSING
        entry.processing_error = None
        await db.commit()

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
                        source=entry.source,
                        publication_year=entry.publication_year,
                        tags=entry.tags,
                        knowledge_id=entry.id,
                        chunk_index=index,
                    )
                    for index, content in enumerate(chunks)
                ]
            )
            await db.refresh(entry)
            if entry.deleted_at is not None:
                await delete_knowledge_vectors(entry.id)
                return
            entry.status = ProcessingStatus.READY
            entry.chunk_count = len(chunks)
            entry.indexed_at = datetime.now(UTC)
            await db.commit()
        except Exception as error:
            await db.rollback()
            current = await db.get(KnowledgeEntry, entry_id)
            if current is not None and current.deleted_at is None:
                current.status = ProcessingStatus.FAILED
                current.processing_error = str(error)[:2000]
                await db.commit()


async def cleanup_knowledge_entry(entry_id: UUID, object_key: str) -> None:
    await delete_knowledge_vectors(entry_id)
    await remove_object(object_key)


async def create_knowledge_download(db: AsyncSession, entry_id: UUID) -> tuple[str, datetime]:
    entry = await get_knowledge_entry(db, entry_id)
    settings = get_settings()
    expires = timedelta(minutes=settings.download_url_expire_minutes)
    url = await presigned_download_url(entry.object_key, expires=expires)
    return url, datetime.now(UTC) + expires
