# mudawi medical assistant

backend-only multilingual medical assistant. persian, arabic, russian, english, turkish. authenticated chat, document analysis, admin guideline retrieval, stt.

## stack

fastapi + async sqlalchemy 2 | postgres | minio | qdrant (dense+bm25 hybrid) | custom react + langchain tools | dr7 chat | openrouter gemini

## quick start

```bash
cp .env.example .env
# fill in ADMIN_API_KEY (>=16 chars) and provider keys
docker compose up -d postgres minio qdrant
uv sync
uv run alembic upgrade head
uv run uvicorn api.main:app --reload
```

open http://localhost:8000/docs

Session, chat, and upload routes require `X-Language`: `arabic`, `persian`,
`russian`, or `turkish` (the bilingual English/Turkish DR ONLINE mode).

## local dev

python 3.12+, uv. python and tests run locally; compose provides postgres,
minio, and qdrant. postgres uses `POSTGRES_HOST`, `POSTGRES_PORT`,
`POSTGRES_USER`, `POSTGRES_PASSWORD`, and `POSTGRES_DB`. local endpoints use
`localhost`; compose overrides the app container's service hosts.

## migrations

```bash
uv run alembic revision --autogenerate -m "what changed"
uv run alembic upgrade head
uv run alembic downgrade -1   # rollback
```

bootstrap uses create_all; prod should always use alembic upgrade head.

## validation

```bash
uvx ruff check src
uvx ruff format --check src
uvx ty check src
```

provider calls need real credentials + infra.
