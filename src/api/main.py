from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from api.admin import router as admin_router
from api.auth import router as auth_router
from api.chat import router as chat_router
from api.errors import service_error_handler
from api.knowledge import router as knowledge_router
from api.profile import router as profile_router
from api.sessions import router as sessions_router
from api.stt import router as stt_router
from api.uploads import router as uploads_router
from core.config import validate_runtime_settings
from core.exceptions import ServiceError
from db.session import create_tables, engine


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    validate_runtime_settings()
    await create_tables()
    yield
    await engine.dispose()


app = FastAPI(title="Mudawi Medical Assistant", version="0.1.0", lifespan=lifespan)
app.add_exception_handler(ServiceError, service_error_handler)
app.include_router(auth_router)
app.include_router(profile_router)
app.include_router(sessions_router)
app.include_router(uploads_router)
app.include_router(knowledge_router)
app.include_router(chat_router)
app.include_router(stt_router)
app.include_router(admin_router)


@app.get("/health", tags=["system"])
async def health() -> dict[str, str]:
    return {"status": "ok"}
