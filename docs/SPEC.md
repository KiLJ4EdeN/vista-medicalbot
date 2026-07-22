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

- **User**: registers with email, full name, and password; receives one
  non-expiring bearer token; manages their profile and password; creates chat
  sessions; and uploads session-scoped files.
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
- Agent: custom textual ReAct loop using LangChain tool abstractions, with a
  recursion limit, skills, and RAG; dr7 does not provide native tool calls
- Authentication: one opaque, non-expiring bearer token per user; `x-api-key`
  over HTTPS for administrators

Hybrid search combines the hosted dense vectors with Qdrant BM25 sparse
vectors. It must account for Persian and Arabic spelling variants. Prompt
content, rather than hard-coded application branches, drives responses in all
five supported languages.

Prefer established, well-maintained libraries over custom implementations
where doing so reduces complexity.

## Structure

```text
├── AGENTS.md
├── alembic/       # database migrations
├── docker-compose.yml
├── Dockerfile
├── docs/          # additional documentation
├── pyproject.toml # uv-based Python project
├── README.md
├── src/
│   ├── api/       # FastAPI routers and dependencies
│   ├── core/      # configuration, security, shared utilities
│   ├── db/        # database and external-store connectors
│   ├── models/    # SQLAlchemy ORM models
│   ├── prompts/   # prompt markdown files
│   ├── schemas/   # Pydantic request/response schemas
│   ├── services/  # integrations and business logic
│   └── skills/    # progressive-disclosure skill markdown files
├── tests/         # integration and isolated agent tests
└── uv.lock
```

## Features

- Registration and login that return the user's permanent bearer token
- Profile and password management without token rotation
- Chat sessions: create, list, history, and soft-delete
- SSE-delivered lifecycle, tool, and final-answer events, with completed or
  failed assistant records persisted
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

- **PostgreSQL**: users and their permanent tokens, chat sessions, messages,
  uploads, and knowledge-entry metadata
- **MinIO**: session uploads and original knowledge documents
- **Qdrant**: chunks from the administrator-managed shared knowledge base

Knowledge uploads create a pending PostgreSQL entry and retain the source in
MinIO. A FastAPI background task extracts, chunks, embeds, and indexes the
document, updating its ingestion status. This initial deployment does not
require an external job queue.

## Endpoint Groups

- `/auth/*`: register and login
- `/profile`: view/update profile and change password
- `/sessions/*`: session CRUD, history, and SSE agent chat
- `/uploads/*`: session-scoped file upload, listing, and deletion
- `/stt`: audio-to-text processing
- `/knowledge/*`: admin knowledge CRUD and search testing
- `/admin/users/*`: user monitoring and activation/deactivation
- `/admin/stats/*`: usage and activity analytics

## Environment Contract

```dotenv
# postgres
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_USER=postgres
POSTGRES_PASSWORD=
POSTGRES_DB=postgres

# object and vector stores
MINIO_ROOT_USER=
MINIO_ROOT_PASSWORD=
MINIO_BUCKET=files
MINIO_ENDPOINT=localhost:9000
MINIO_PUBLIC_ENDPOINT=localhost:9000
MINIO_PUBLIC_SECURE=false
MINIO_ACCESS_KEY=${MINIO_ROOT_USER}
MINIO_SECRET_KEY=${MINIO_ROOT_PASSWORD}
MINIO_SECURE=false
MAX_UPLOAD_BYTES=26214400
MAX_AUDIO_BYTES=26214400
MAX_PDF_PAGES=100
DOWNLOAD_URL_EXPIRE_MINUTES=15
QDRANT_URL=http://localhost:6333
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
ADMIN_API_KEY=

# llm
LLM_API_URL=https://dr7.ai/api/v1/medical/chat/completions
LLM_MODEL=baichuan-m3
LLM_API_KEY=

# multimodal / vlm / stt
MULTIMODAL_API_URL=https://openrouter.ai/api/v1/chat/completions
MULTIMODAL_MODEL=google/gemini-3.5-flash
MULTIMODAL_API_KEY=

# embeddings
EMBEDDING_API_URL=https://openrouter.ai/api/v1/embeddings
EMBEDDING_MODEL=baai/bge-m3
EMBEDDING_API_KEY=
```

For containerized application runs, Compose overrides `POSTGRES_HOST`,
`MINIO_ENDPOINT`, and `QDRANT_URL` with Docker service hostnames.

Secrets and operational configuration remain environment-only. There is no
fixed bypass token and no runtime settings table.

## Key Design Points

- Tool failures are returned to the agent as text so it can self-correct.
- Agent tool loops have a configurable recursion limit.
- The agent emits tool and final-answer events directly; SSE does not use a
  callback queue because dr7 currently returns complete responses.
- Prompts are markdown files cached in memory.
- Skill frontmatter is parsed for discovery and excluded from prompt content.
- Each user has one opaque bearer token that does not expire or rotate. Both
  registration and credential login return the same token. The token remains
  stored with the user so it can be returned on later login.
- Admin account deactivation immediately blocks the user's bearer token;
  reactivation restores access with the same token. Password changes do not
  change the token. There is no user logout or token refresh endpoint.
- Chat sessions and user uploads use soft deletion. Knowledge deletion removes
  corresponding vectors and its MinIO object as background work.
- Only user and assistant message records are persisted; tool execution remains
  transient. User payloads retain validated session-upload attachment IDs so
  history can return attachment metadata and download URLs. Assistant records
  may retain compact diagnostic metadata.
- Messages have a per-session sequence number so streamed conversations retain
  deterministic ordering. Only one assistant generation may run per session.
- Chat streams use `message_started`, `token`, `tool_started`, `tool_finished`,
  `message_completed`, and `error` SSE events.
- The agent chooses among progressive skill loading, shared guideline hybrid
  search, and current-session file OCR/VLM analysis. Tool failures are returned
  as text rather than escaping into the agent loop.
- Knowledge entries currently include a title and source-document metadata.
  Retrieved citations expose title and chunk number; source, publication-year,
  and tag filtering are not implemented.
- Database tables are created from ORM metadata at startup as a development
  convenience. Existing databases are upgraded with Alembic migrations.
- Tests cover authentication, chat, knowledge ingestion/search, and the textual
  ReAct event loop. Local development runs Python directly while Docker Compose
  provides PostgreSQL, MinIO, and Qdrant.
