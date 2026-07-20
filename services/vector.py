import asyncio
import re
from dataclasses import dataclass
from functools import lru_cache
from typing import Any
from uuid import UUID, uuid4

from fastembed import SparseTextEmbedding
from qdrant_client import models

from core.config import get_settings
from core.exceptions import ExternalServiceError
from db.vector import get_qdrant_client
from services.embeddings import embed_texts, embed_texts_batched

DENSE_VECTOR = "dense"
SPARSE_VECTOR = "bm25"
ARABIC_DIACRITICS = re.compile(r"[\u0610-\u061a\u064b-\u065f\u0670\u06d6-\u06ed]")


@dataclass(frozen=True, slots=True)
class KnowledgeChunk:
    content: str
    title: str
    source: str
    publication_year: int | None
    tags: list[str]
    knowledge_id: UUID
    chunk_index: int


@dataclass(frozen=True, slots=True)
class SearchHit:
    content: str
    title: str
    source: str
    publication_year: int | None
    tags: list[str]
    knowledge_id: UUID
    chunk_index: int
    score: float


def normalize_lexical_text(text: str) -> str:
    normalized = text.translate(
        str.maketrans(
            {
                "ي": "ی",
                "ى": "ی",
                "ك": "ک",
                "ۀ": "ه",
                "ة": "ه",
                "ؤ": "و",
                "إ": "ا",
                "أ": "ا",
                "ٱ": "ا",
                "ـ": "",
            }
        )
    )
    return ARABIC_DIACRITICS.sub("", normalized).lower()


@lru_cache
def _sparse_model() -> SparseTextEmbedding:
    return SparseTextEmbedding(model_name=get_settings().qdrant_bm25_model)


def _embed_sparse_sync(texts: list[str]) -> list[models.SparseVector]:
    embeddings = _sparse_model().embed(texts, batch_size=get_settings().embedding_batch_size)
    return [
        models.SparseVector(indices=embedding.indices.tolist(), values=embedding.values.tolist())
        for embedding in embeddings
    ]


async def embed_sparse(texts: list[str]) -> list[models.SparseVector]:
    normalized = [normalize_lexical_text(text) for text in texts]
    return await asyncio.to_thread(_embed_sparse_sync, normalized)


async def _ensure_collection(dense_size: int) -> None:
    client = get_qdrant_client()
    settings = get_settings()
    try:
        if await client.collection_exists(settings.qdrant_collection):
            return
        await client.create_collection(
            collection_name=settings.qdrant_collection,
            vectors_config={
                DENSE_VECTOR: models.VectorParams(size=dense_size, distance=models.Distance.COSINE)
            },
            sparse_vectors_config={
                SPARSE_VECTOR: models.SparseVectorParams(modifier=models.Modifier.IDF)
            },
        )
        await client.create_payload_index(
            collection_name=settings.qdrant_collection,
            field_name="knowledge_id",
            field_schema=models.PayloadSchemaType.KEYWORD,
            wait=True,
        )
        await client.create_payload_index(
            collection_name=settings.qdrant_collection,
            field_name="source",
            field_schema=models.PayloadSchemaType.KEYWORD,
            wait=True,
        )
        await client.create_payload_index(
            collection_name=settings.qdrant_collection,
            field_name="tags",
            field_schema=models.PayloadSchemaType.KEYWORD,
            wait=True,
        )
        await client.create_payload_index(
            collection_name=settings.qdrant_collection,
            field_name="publication_year",
            field_schema=models.PayloadSchemaType.INTEGER,
            wait=True,
        )
    except Exception as error:
        try:
            if await client.collection_exists(settings.qdrant_collection):
                return
        except Exception:
            pass
        raise ExternalServiceError("Qdrant collection setup failed") from error


async def index_chunks(chunks: list[KnowledgeChunk]) -> None:
    if not chunks:
        return
    texts = [chunk.content for chunk in chunks]
    dense_vectors, sparse_vectors = await asyncio.gather(
        embed_texts_batched(texts), embed_sparse(texts)
    )
    if len(dense_vectors) != len(chunks) or len(sparse_vectors) != len(chunks):
        raise ExternalServiceError("Embedding count does not match knowledge chunks")

    await _ensure_collection(len(dense_vectors[0]))
    points = [
        models.PointStruct(
            id=uuid4(),
            vector={DENSE_VECTOR: dense, SPARSE_VECTOR: sparse},
            payload={
                "content": chunk.content,
                "title": chunk.title,
                "source": chunk.source,
                "publication_year": chunk.publication_year,
                "tags": chunk.tags,
                "knowledge_id": str(chunk.knowledge_id),
                "chunk_index": chunk.chunk_index,
            },
        )
        for chunk, dense, sparse in zip(chunks, dense_vectors, sparse_vectors, strict=True)
    ]
    try:
        await get_qdrant_client().upsert(
            collection_name=get_settings().qdrant_collection, points=points, wait=True
        )
    except Exception as error:
        raise ExternalServiceError("Failed to index knowledge chunks") from error


async def delete_knowledge_vectors(knowledge_id: UUID) -> None:
    client = get_qdrant_client()
    settings = get_settings()
    try:
        if not await client.collection_exists(settings.qdrant_collection):
            return
        await client.delete(
            collection_name=settings.qdrant_collection,
            points_selector=models.FilterSelector(
                filter=models.Filter(
                    must=[
                        models.FieldCondition(
                            key="knowledge_id", match=models.MatchValue(value=str(knowledge_id))
                        )
                    ]
                )
            ),
            wait=True,
        )
    except Exception as error:
        raise ExternalServiceError("Failed to delete knowledge vectors") from error


def _payload_value(payload: dict[str, Any], key: str, expected_type: type) -> Any:
    value = payload.get(key)
    if not isinstance(value, expected_type):
        raise ExternalServiceError("Qdrant returned invalid knowledge payload")
    return value


async def hybrid_search(
    query: str,
    *,
    limit: int | None = None,
    source: str | None = None,
    publication_year: int | None = None,
    tags: list[str] | None = None,
) -> list[SearchHit]:
    settings = get_settings()
    result_limit = limit or settings.rag_result_limit
    dense_vectors, sparse_vectors = await asyncio.gather(
        embed_texts([query]), embed_sparse([query])
    )
    client = get_qdrant_client()
    conditions: list[models.Condition] = []
    if source is not None:
        conditions.append(
            models.FieldCondition(key="source", match=models.MatchValue(value=source))
        )
    if publication_year is not None:
        conditions.append(
            models.FieldCondition(
                key="publication_year", match=models.MatchValue(value=publication_year)
            )
        )
    conditions.extend(
        models.FieldCondition(key="tags", match=models.MatchValue(value=tag))
        for raw_tag in tags or []
        if (tag := raw_tag.strip().lower())
    )
    query_filter = models.Filter(must=conditions) if conditions else None
    try:
        if not await client.collection_exists(settings.qdrant_collection):
            return []
        response = await client.query_points(
            collection_name=settings.qdrant_collection,
            prefetch=[
                models.Prefetch(query=dense_vectors[0], using=DENSE_VECTOR, limit=result_limit * 3),
                models.Prefetch(
                    query=sparse_vectors[0], using=SPARSE_VECTOR, limit=result_limit * 3
                ),
            ],
            query=models.FusionQuery(fusion=models.Fusion.RRF),
            query_filter=query_filter,
            limit=result_limit,
            with_payload=True,
        )
    except Exception as error:
        raise ExternalServiceError("Qdrant hybrid search failed") from error

    hits: list[SearchHit] = []
    for point in response.points:
        payload = point.payload or {}
        try:
            hits.append(
                SearchHit(
                    content=_payload_value(payload, "content", str),
                    title=_payload_value(payload, "title", str),
                    source=_payload_value(payload, "source", str),
                    publication_year=payload.get("publication_year"),
                    tags=_payload_value(payload, "tags", list),
                    knowledge_id=UUID(_payload_value(payload, "knowledge_id", str)),
                    chunk_index=_payload_value(payload, "chunk_index", int),
                    score=point.score,
                )
            )
        except (TypeError, ValueError) as error:
            raise ExternalServiceError("Qdrant returned invalid knowledge payload") from error
    return hits
