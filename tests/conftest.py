import os
from collections.abc import AsyncIterator
from uuid import uuid4

import httpx
import pytest
import pytest_asyncio
from fastapi import FastAPI

from core.config import get_settings

_settings = get_settings()

ADMIN_API_KEY = os.environ.get("ADMIN_API_KEY", "test-admin-key-16+")
LLM_API_KEY = _settings.llm_api_key.get_secret_value()
MULTIMODAL_API_KEY = _settings.multimodal_api_key.get_secret_value()
CHAT_LANGUAGE = "arabic"

os.environ.setdefault("ADMIN_API_KEY", ADMIN_API_KEY)

skip_if_no_llm = pytest.mark.skipif(not LLM_API_KEY, reason="LLM_API_KEY not set")
skip_if_no_vlm = pytest.mark.skipif(not MULTIMODAL_API_KEY, reason="MULTIMODAL_API_KEY not set")


@pytest_asyncio.fixture(scope="function")
async def app() -> AsyncIterator[FastAPI]:
    from core.config import get_settings

    get_settings.cache_clear()

    from contextlib import suppress

    from qdrant_client import AsyncQdrantClient

    qdrant = AsyncQdrantClient(url=get_settings().qdrant_url)
    with suppress(Exception):
        await qdrant.delete_collection(get_settings().qdrant_collection)
    await qdrant.close()

    from api.main import app as fastapi_app
    from api.main import lifespan

    async with lifespan(fastapi_app):
        yield fastapi_app

    get_settings.cache_clear()


@pytest_asyncio.fixture(scope="function")
async def client(app: FastAPI) -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=True)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest_asyncio.fixture(scope="function")
async def user_token(client: httpx.AsyncClient) -> str:
    suffix = uuid4().hex[:8]
    email = f"test-{suffix}@example.com"
    r = await client.post(
        "/auth/register",
        json={"email": email, "full_name": "Test User", "password": "testpass123"},
    )
    assert r.status_code == 201, f"Registration failed: {r.text}"
    data = r.json()
    return data["token"]


@pytest_asyncio.fixture(scope="function")
async def user_id(client: httpx.AsyncClient, user_token: str) -> str:
    headers = {
        "Authorization": f"Bearer {user_token}",
        "X-Language": CHAT_LANGUAGE,
    }
    r = await client.get("/sessions", headers=headers)
    assert r.status_code == 200
    data = r.json()
    return str(data["items"][0]["user_id"]) if data["items"] else ""


@pytest_asyncio.fixture(scope="function")
async def session_id(client: httpx.AsyncClient, user_token: str) -> str:
    headers = {
        "Authorization": f"Bearer {user_token}",
        "X-Language": CHAT_LANGUAGE,
    }
    r = await client.post("/sessions", json={"title": "test session"}, headers=headers)
    assert r.status_code == 201, f"Session creation failed: {r.text}"
    return r.json()["id"]


@pytest_asyncio.fixture(scope="session")
def admin_headers() -> dict[str, str]:
    return {"x-api-key": ADMIN_API_KEY}


KNOWLEDGE_PDF = os.path.join(os.path.dirname(__file__), "..", "data", "NCCN.pdf")
