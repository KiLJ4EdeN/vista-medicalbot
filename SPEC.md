# Mudawi Medical Assistant

## Overview

Multilingual assistant, works in Persian, Arabic, Russian/Firousi and English+Turkish (4 languages).
Users can chat with a medical LLM, provided by dr7 openai completions, baichuan-m3.
There is also a VLM to analyze and OCR medical info when needed, or OCR PDFs etc.
There is also an option for user to start with speech-to-text instead of typing — model here is OpenRouter, google/gemini-3.5-flash, OpenAI-compatible style both for VLM and STT (frontend just calls this, gets text, and calls normal chat API; don't overthink it).
RAG/Knowledge is admin-only: admin uploads medical guidelines like ACR. Users only have images/files attached to a session at a time. No global or personal knowledge manipulation by users.
Admin also has a settings and monitoring panel.
Monitoring includes: seeing signed-up user changes, active users and their emails used for registration, full names, chats done today, chats done overall, active users, online users (via last-activity timestamp), and if possible recent topics marked by the system.

## Roles

For now we have 2:
- **User**: registers, chats, uploads files/images per session. No personal knowledge.
  Registration uses email, full name, and password. Password change must be supported.
- **Admin**: shared knowledge base CRUD, user management, usage stats, system settings.

## Architecture

FastAPI backend with PostgreSQL. Images/files can go to MinIO (S3-compatible).
Vector database: Qdrant (with hybrid search support for Persian/Arabic spelling variants).
Embedding model: bge-m3 with hybrid (dense + sparse). Vector DB handles the search implementation; we just call it (we call OpenRouter for the embedding — assumes we have the key).
Auth: OAuth2 register then JWT refresh for users. Admin uses x-api-key (over HTTPS, acceptable).
Code is fully agentic: LangChain agent with tool-calling, skill system, and RAG. The four prompt languages are driven entirely by prompt content.
Prefer more abstractions from well-known libraries rather than writing higher LOC ourselves.

## Structure

```
├── AGENTS.md
├── api/           # FastAPI routers
├── core/          # anything we implement
├── data/          # extra storage if needed
├── db/            # DB connectors
├── docker-compose.yml
├── Dockerfile
├── docs/          # extra markdown beyond prompts
├── models/        # SQLAlchemy/ORM models
├── opencode.json  # opencode config, restrict env vars, bash, etc.
├── prompts/       # prompt markdown files
├── pyproject.toml # uv-based
├── README.md
├── schemas/       # Pydantic models
├── scripts/       # utils, test helpers
├── services/      # controller layer: LLM calls, business logic
├── skills/        # skill markdown files
└── uv.lock
```

## Features

- Registration / login / profile management
- Chat sessions (create, list, history, soft-delete)
- AI agent with tools: RAG search (admin knowledge base), VLM image analysis, OCR (PDFs/images)
- File uploads to MinIO (per-session scope, user-level)
- STT (speech-to-text via OpenRouter)
- Per-session file attachments only — no persistent personal knowledge base
- Skills system (progressive-disclosure markdown files with YAML frontmatter)
- Admin: knowledge base CRUD, vector search testing, user management, usage analytics
- Admin: system settings (key-value config toggles)
- Multi-language prompts in all four languages

## Data Stores

- **PostgreSQL**: users, sessions, messages, uploads, knowledge entries, settings
- **MinIO (S3-compatible)**: uploaded files
- **Qdrant**: shared knowledge base chunks (admin-managed only)

## Endpoint Groups

- `/auth/*` — register, login
- `/profile` — view/update profile
- `/sessions/*` — session CRUD, messages (agent chat)
- `/chat/image`, `/stt`, `/tts` — media processing
- `/uploads/*` — file upload CRUD (scoped to session)
- `/knowledge/*` — admin knowledge base
- `/admin/*` — knowledge, users, stats, settings

## Key Design Points

- Tool errors returned as text (not exceptions) for agent self-correction
- Recursion limit on agent tool loops
- Prompts loaded from markdown files, cached in memory
- Skills with YAML frontmatter (frontmatter stripped before use)
- Tables created from ORM on startup; no migrations for now
- Online users determined by last-activity timestamp (no WebSockets)
