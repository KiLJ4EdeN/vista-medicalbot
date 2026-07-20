from functools import lru_cache

from qdrant_client import AsyncQdrantClient

from core.config import get_settings


@lru_cache
def get_qdrant_client() -> AsyncQdrantClient:
    return AsyncQdrantClient(url=get_settings().qdrant_url)
