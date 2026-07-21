# Mudawi Medical Assistant

Mudawi is a backend-only multilingual medical assistant for Persian, Arabic,
Russian, English, and Turkish. It provides authenticated chat, session-scoped
medical document analysis, administrator-managed guideline retrieval, and
speech-to-text.

`SPEC.md` is the authoritative product and architecture specification.

## Stack

- FastAPI and async SQLAlchemy 2
- PostgreSQL for users, chat history, uploads, and knowledge metadata
- MinIO for session files and original knowledge documents
- Qdrant hybrid retrieval
- Hosted `bge-m3` dense embeddings plus local `Qdrant/bm25` sparse embeddings
- LangChain tool-calling agent
- dr7 `baichuan-m3` chat completions
- OpenRouter Gemini multimodal OCR/VLM/STT

## Quick Start

1. Create the environment file:

   ```bash
   cp .env.example .env
   ```

2. Set at least these secrets in `.env`:

   ```dotenv
   POSTGRES_PASSWORD=change-me        # postgres root password
   MINIO_ROOT_PASSWORD=change-me      # docker-compose minio admin
   MINIO_SECRET_KEY=change-me         # local-dev minio secret
   JWT_SECRET=use-a-long-random-secret
   ADMIN_API_KEY=use-a-long-random-admin-key
   LLM_API_KEY=
   MULTIMODAL_API_KEY=
   EMBEDDING_API_KEY=
   ```

   `JWT_SECRET` must contain at least 32 characters and `ADMIN_API_KEY` at
   least 16 characters. Provider keys may be omitted while validating local
   infrastructure, but their corresponding features will not work.

3. Start the complete stack:

   ```bash
   docker compose up --build
   ```

4. Open the API documentation at `http://localhost:8000/docs` or check
   `http://localhost:8000/health`.

The first BM25 use downloads the small FastEmbed model. Its cache is persisted
by Docker Compose.

## Local Development

Python 3.12 or newer and `uv` are required. Run infra services first:

```bash
docker compose up -d postgres minio qdrant
```

Then start the app locally:

```bash
uv sync
uv run uvicorn api.main:app --reload
```

Environment variables read from `.env`. Service URLs auto-construct from
component vars — to switch between Docker and local dev just change three
values:

| Var | Docker | Local |
|-----|--------|-------|
| `POSTGRES_HOST` | `postgres` | `localhost` |
| `MINIO_HOST` | `minio` | `localhost` |
| `QDRANT_HOST` | `qdrant` | `localhost` |

Set `DATABASE_URL` / `MINIO_ENDPOINT` / `QDRANT_URL` directly to bypass
auto-construction entirely.

`MINIO_PUBLIC_ENDPOINT` is the browser-reachable host used when signing
download URLs; set it and `MINIO_PUBLIC_SECURE` to the deployed MinIO domain
and HTTPS behavior outside local Docker.

## Database Migrations

Schema changes are managed with Alembic. After modifying a model, generate a
migration:

```bash
alembic revision --autogenerate -m "description of change"
```

Review the generated file, then apply it:

```bash
alembic upgrade head
```

To roll back the last migration:

```bash
alembic downgrade -1
```

The initial migration (`482a5632357e`) creates all tables. In development,
startup auto-creates tables via ORM metadata for convenience; in production
always use `alembic upgrade head`.

Static validation commands:

```bash
uvx ruff check api core db models schemas services
uvx ruff format --check api core db models schemas services
uvx ty check api core db models schemas services
```

## Authentication

Users register with email, full name, and password. Login uses the OAuth2
password form where `username` is the email. Access tokens are short-lived;
refresh tokens rotate and are revoked on reuse, logout, password change, or
account deactivation.

Administrators authenticate with `x-api-key`. The current design uses one
shared trusted-admin key. A browser admin can inspect any key it sends, so this
model must be replaced with server-side admin sessions if multiple or
untrusted administrators are introduced.

## Main APIs

- `/auth/*`: register, login, refresh, logout
- `/profile`: profile and password management
- `/sessions/*`: session CRUD, history, and SSE agent chat
- `/uploads/*`: session PDF/image storage and presigned downloads
- `/stt`: authenticated audio transcription
- `/knowledge/*`: admin-only knowledge CRUD, reindexing, and search testing
- `/admin/users/*`: admin-only user listing and activation controls
- `/admin/stats`: admin-only dashboard metrics

Chat requests use `POST /sessions/{session_id}/messages`. The stream emits:

- `message_started`
- `token`
- `tool_started`
- `tool_finished`
- `message_completed`
- `error`

Only visible user and assistant messages are persisted. Tool traces are
transient, with compact tool names and failure state stored as assistant
message metadata.

## Knowledge Retrieval

Only administrators can upload shared knowledge. Sources are retained in
MinIO, processed in a FastAPI background task, and indexed in Qdrant. Native
PDF text is extracted locally; scanned PDFs and images fall back to Gemini OCR.

Retrieval combines hosted `bge-m3` dense vectors and local BM25 sparse vectors
with reciprocal-rank fusion. Conservative Persian/Arabic character and
diacritic normalization is applied to the lexical path. Hazm is intentionally
not used because aggressive token normalization can alter medical terms.

## Admin Metrics

- `active_users`: enabled accounts
- `online_users`: enabled accounts active within `ONLINE_WINDOW_MINUTES`
- `chats_*`: user message turns, excluding assistant and tool activity
- Daily values use UTC

## Current Validation Boundary

ORM mappings, PostgreSQL DDL compilation, schemas, OpenAPI security contracts,
LangChain construction, BM25 inference, linting, formatting, and static typing
are validated locally. Live dr7, OpenRouter, PostgreSQL, MinIO, and Qdrant
end-to-end calls require deployment credentials and running infrastructure.
