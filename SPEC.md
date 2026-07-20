# Mudawi Medical Assistant

## Overview

Mudawi is a backend-only multilingual medical assistant supporting Persian,
Arabic, Russian, English, and Turkish. Users chat with the `baichuan-m3`
medical LLM through the dr7 OpenAI-compatible chat completions API.

The agent can choose tools to analyze medical images, OCR PDFs and images, and
search administrator-managed medical guidelines. Users may also submit audio
to speech-to-text (STT), then send the resulting text through the normal chat
flow. There is no text-to-speech feature.

Users can attach files only to a chat session. They cannot create a global or
personal knowledge base. Administrators manage the shared medical knowledge
base, users, and usage monitoring. Deployment configuration is environment-only
and is not exposed through an admin settings panel.

## Roles

- **User**: registers with email, full name, and password; manages their
  profile and password; creates chat sessions; and uploads session-scoped files.
- **Admin**: authenticates with `x-api-key`, manages the shared knowledge base,
  activates or deactivates users, tests vector search, and views usage metrics.

Admin API-key principals are not user records and cannot log in through the
user authentication endpoints.

## Architecture

- Backend: FastAPI
- ORM: async SQLAlchemy 2 with `asyncpg`
- Relational database: PostgreSQL
- Object storage: MinIO (S3-compatible)
- Vector database: Qdrant
- Dense embeddings: hosted `bge-m3` through the OpenRouter
  OpenAI-compatible embeddings API
- Sparse retrieval: Qdrant lexical BM25 sparse vectors
- Agent: LangChain tool-calling agent with a recursion limit, skills, and RAG
- Authentication: short-lived access JWTs and rotating, revocable refresh JWTs
  for users; `x-api-key` over HTTPS for administrators

Hybrid search combines the hosted dense vectors with Qdrant BM25 sparse
vectors. It must account for Persian and Arabic spelling variants. Prompt
content, rather than hard-coded application branches, drives responses in all
five supported languages.

Prefer established, well-maintained libraries over custom implementations
where doing so reduces complexity.

## Structure

```text
├── AGENTS.md
├── api/           # FastAPI routers and dependencies
├── core/          # configuration, security, shared utilities
├── db/            # database and external-store connectors
├── docker-compose.yml
├── Dockerfile
├── docs/          # additional documentation
├── models/        # SQLAlchemy ORM models
├── prompts/       # prompt markdown files
├── pyproject.toml # uv-based Python project
├── README.md
├── schemas/       # Pydantic request/response schemas
├── scripts/       # operational utilities
├── services/      # integrations and business logic
├── skills/        # progressive-disclosure skill markdown files
└── uv.lock
```

## Features

- Registration, login, refresh-token rotation, logout, and profile management
- Password changes that revoke existing refresh tokens
- Chat sessions: create, list, history, and soft-delete
- SSE-streamed assistant responses, persisted after completion
- Agent-selected tools for shared RAG, VLM image analysis, and PDF/image OCR
- PDF, JPEG, PNG, and WebP uploads stored in MinIO and scoped to one session
- STT through the OpenRouter multimodal OpenAI-compatible API
- Skills loaded progressively from markdown with YAML frontmatter
- Admin knowledge CRUD, background ingestion, and vector search testing
- Original knowledge documents retained in MinIO
- Admin user listing, inspection, activation, and deactivation
- Usage analytics: registrations, active users, online users, and chat counts for
  today and all time

Recent topic generation is not included. Online users are determined from a
last-activity timestamp without WebSockets.

## Data Stores

- **PostgreSQL**: users, refresh tokens, chat sessions, messages, uploads, and
  knowledge-entry metadata
- **MinIO**: session uploads and original knowledge documents
- **Qdrant**: chunks from the administrator-managed shared knowledge base

Knowledge uploads create a pending PostgreSQL entry and retain the source in
MinIO. A FastAPI background task extracts, chunks, embeds, and indexes the
document, updating its ingestion status. This initial deployment does not
require an external job queue.

## Endpoint Groups

- `/auth/*`: register, login, refresh, and logout
- `/profile`: view/update profile and change password
- `/sessions/*`: session CRUD, history, and SSE agent chat
- `/uploads/*`: session-scoped file upload, listing, and deletion
- `/stt`: audio-to-text processing
- `/knowledge/*`: admin knowledge CRUD and search testing
- `/admin/users/*`: user monitoring and activation/deactivation
- `/admin/stats/*`: usage and activity analytics

## Environment Contract

```dotenv
# infra
POSTGRES_PASSWORD=
MINIO_ROOT_USER=
MINIO_ROOT_PASSWORD=
MINIO_BUCKET=files

# db and stores
DATABASE_URL=postgresql+asyncpg://postgres:${POSTGRES_PASSWORD}@postgres:5432/postgres
MINIO_ENDPOINT=minio:9000
MINIO_PUBLIC_ENDPOINT=localhost:9000
MINIO_PUBLIC_SECURE=false
MINIO_ACCESS_KEY=${MINIO_ROOT_USER}
MINIO_SECRET_KEY=${MINIO_ROOT_PASSWORD}
MINIO_SECURE=false
MAX_UPLOAD_BYTES=26214400
MAX_AUDIO_BYTES=26214400
MAX_PDF_PAGES=100
DOWNLOAD_URL_EXPIRE_MINUTES=15
QDRANT_URL=http://qdrant:6333
QDRANT_COLLECTION=medical_knowledge
QDRANT_BM25_MODEL=Qdrant/bm25
KNOWLEDGE_CHUNK_SIZE=1200
KNOWLEDGE_CHUNK_OVERLAP=200
EMBEDDING_BATCH_SIZE=32
RAG_RESULT_LIMIT=6
AGENT_RECURSION_LIMIT=12
CHAT_HISTORY_LIMIT=50
ONLINE_WINDOW_MINUTES=15

# auth
JWT_SECRET=
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=15
REFRESH_TOKEN_EXPIRE_DAYS=30
ADMIN_API_KEY=

# llm
LLM_API_URL=https://dr7.ai/api/v1/medical/chat/completions
LLM_MODEL=baichuan-m3
LLM_PROVIDER_TYPE=openai
LLM_API_KEY=

# multimodal / vlm / stt
MULTIMODAL_API_URL=https://openrouter.ai/api/v1/chat/completions
MULTIMODAL_MODEL=google/gemini-3.5-flash
MULTIMODAL_PROVIDER_TYPE=openai
MULTIMODAL_API_KEY=

# embeddings
EMBEDDING_API_URL=https://openrouter.ai/api/v1/embeddings
EMBEDDING_MODEL=baai/bge-m3
EMBEDDING_API_KEY=
```

Secrets and operational configuration remain environment-only. There is no
fixed bypass token and no runtime settings table.

## Key Design Points

- Tool failures are returned to the agent as text so it can self-correct.
- Agent tool loops have a configurable recursion limit.
- Prompts are markdown files cached in memory.
- Skill frontmatter is parsed for discovery and excluded from prompt content.
- Refresh tokens are stored as hashes, rotated on use, and revocable by token
  family, logout, account deactivation, or password change.
- Chat sessions and user uploads use soft deletion. Knowledge deletion removes
  corresponding vectors and its MinIO object as background work.
- Only user and assistant messages are persisted. Tool execution remains
  transient, with compact diagnostic metadata allowed on assistant messages.
- Messages have a per-session sequence number so streamed conversations retain
  deterministic ordering. Only one assistant generation may run per session.
- Chat streams use `message_started`, `token`, `tool_started`, `tool_finished`,
  `message_completed`, and `error` SSE events.
- The agent chooses among progressive skill loading, shared guideline hybrid
  search, and current-session file OCR/VLM analysis. Tool failures are returned
  as text rather than escaping into the agent loop.
- Knowledge entries include issuing source, publication year, and tags for
  retrieval filtering and citations.
- Database tables are created from ORM metadata at startup. Alembic migrations
  are deferred for the initial greenfield version.
- Automated tests remain deferred by the current product decision. Docker
  Compose provides the application, PostgreSQL, MinIO, and Qdrant stack.
