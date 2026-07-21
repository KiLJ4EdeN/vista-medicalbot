# mudawi medical assistant

backend-only multilingual medical assistant. persian, arabic, russian, english, turkish. authenticated chat, document analysis, admin guideline retrieval, stt.

## stack

fastapi + async sqlalchemy 2 | postgres | minio | qdrant (dense+bm25 hybrid) | langchain react agent | dr7 chat | openrouter gemini

## quick start

```bash
cp .env.example .env
# fill in JWT_SECRET (>=32 chars), ADMIN_API_KEY (>=16 chars), and provider keys
docker compose up --build
```

open http://localhost:8000/docs

## local dev

python 3.12+, uv. infra first, then app:

```bash
docker compose up -d postgres minio qdrant
uv sync
uv run uvicorn api.main:app --reload
```

env vars from .env. swap between docker and local by changing POSTGRES_HOST, MINIO_HOST, QDRANT_HOST.

## migrations

```bash
alembic revision --autogenerate -m "what changed"
alembic upgrade head
alembic downgrade -1   # rollback
```

bootstrap uses create_all; prod should always use alembic upgrade head.

## validation

```bash
uvx ruff check api core db models schemas services
uvx ruff format --check api core db models schemas services
uvx ty check api core db models schemas services
```

provider calls need real credentials + infra.
