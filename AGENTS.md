# Repository Guide

## Source of Truth

Read `docs/SPEC.md` before changing behavior. Update it whenever a product or
architecture decision changes. `README.md` is a terse dev-to-dev quick-start;
keep it minimal. AGENTS.md is the working reference.

## Architecture

- `src/api/`: FastAPI transport, dependencies, and HTTP contracts
- `src/core/`: settings, security, skill/prompt loading, and shared exceptions
- `src/db/`: PostgreSQL, MinIO, and Qdrant client construction
- `src/models/`: SQLAlchemy persistence models
- `src/schemas/`: Pydantic request and response models
- `src/services/`: business logic and provider integrations
- `src/prompts/`: cached agent prompt markdown
- `src/skills/`: progressive skill markdown with YAML frontmatter

Keep business rules out of routers. Services raise `ServiceError` subclasses;
the API maps them to HTTP responses. Agent tools catch failures and return text
so the model can recover without escaping the tool loop.

## Persistence Rules

- Use async SQLAlchemy sessions.
- Users own chat sessions; uploads derive ownership through their session.
- Sessions and uploads soft-delete.
- Only user and assistant message records persist; tool turns remain transient.
- User message payloads retain validated session-upload attachment IDs.
- Assistant records may be pending, completed, or failed and carry compact diagnostics.
- Message ordering uses `sequence_number`, not timestamps or UUIDs.
- Users have one opaque, non-expiring bearer token stored on their user row.
- User tokens do not rotate; admin account deactivation controls their access.
- Admins are API-key principals, not user rows.

## External Services

- MinIO calls are wrapped in `src/services/storage.py` and moved off the event loop.
- Qdrant uses named dense and BM25 sparse vectors with RRF fusion.
- OpenRouter endpoints are configured as full request URLs.
- The dr7 chat endpoint is called directly because it does not support native
  tool calls; the application owns the textual ReAct loop.
- Never log provider keys, admin keys, or user bearer tokens.

## Validation

Run before finishing a change:

```bash
uvx ruff check src
uvx ruff format --check src
uvx ty check src
```

Also generate OpenAPI and compile ORM metadata when routes or models change.
Provider calls cannot be considered validated without actual credentials.

## Constraints

- Python 3.12+
- ASCII by default in source files; multilingual content belongs in prompts or
  user/provider data.
- Alembic migrations live in `alembic/versions/`. Run `alembic upgrade head` before
  deploying; startup `create_all` is a dev convenience only.
- Tests cover authentication, chat, knowledge ingestion/search, and the textual
  ReAct event loop. Integration tests use local Python with configured Docker
  infrastructure and applicable provider credentials.
- Runtime configuration and secrets remain environment-only.

## Comments

- Code is self-documenting. No uppercase comments, section dividers, or
  decorative separators (`# FIXME`, `# TODO`, `# ── Section ──`, etc.).
