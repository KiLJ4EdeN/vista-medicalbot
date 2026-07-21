from collections.abc import Sequence
from typing import Any

import httpx

from core.config import get_settings
from core.exceptions import ExternalServiceError


async def embed_texts(texts: Sequence[str]) -> list[list[float]]:
    if not texts:
        return []

    settings = get_settings()
    headers = {
        "Authorization": f"Bearer {settings.embedding_api_key.get_secret_value()}",
        "Content-Type": "application/json",
    }
    try:
        async with httpx.AsyncClient(timeout=120) as client:
            response = await client.post(
                settings.embedding_api_url,
                headers=headers,
                json={"model": settings.embedding_model, "input": list(texts)},
            )
            response.raise_for_status()
            payload: dict[str, Any] = response.json()
            data = sorted(payload["data"], key=lambda item: item["index"])
            vectors = [item["embedding"] for item in data]
    except (httpx.HTTPError, KeyError, TypeError, ValueError) as error:
        raise ExternalServiceError("Embedding service request failed") from error

    if len(vectors) != len(texts) or any(not vector for vector in vectors):
        raise ExternalServiceError("Embedding service returned an invalid response")
    return vectors


async def embed_texts_batched(texts: Sequence[str]) -> list[list[float]]:
    batch_size = get_settings().embedding_batch_size
    vectors: list[list[float]] = []
    for start in range(0, len(texts), batch_size):
        vectors.extend(await embed_texts(texts[start : start + batch_size]))
    return vectors
