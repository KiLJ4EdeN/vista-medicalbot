# Repository Guide

## Source of Truth

Read `SPEC.md` before changing behavior. Update it whenever a product or
architecture decision changes. `README.md` describes operation and public API
usage; it must remain consistent with the spec.

## Architecture

- `api/`: FastAPI transport, dependencies, and HTTP contracts
- `core/`: settings, security, skill/prompt loading, and shared exceptions
- `db/`: PostgreSQL, MinIO, and Qdrant client construction
- `models/`: SQLAlchemy persistence models
- `schemas/`: Pydantic request and response models
- `services/`: business logic and provider integrations
- `prompts/`: cached agent prompt markdown
- `skills/`: progressive skill markdown with YAML frontmatter

Keep business rules out of routers. Services raise `ServiceError` subclasses;
the API maps them to HTTP responses. Agent tools catch failures and return text
so the model can recover without escaping the tool loop.

## Persistence Rules

- Use async SQLAlchemy sessions.
- Users own chat sessions; uploads derive ownership through their session.
- Sessions and uploads soft-delete.
- Only user and final assistant messages persist.
- Message ordering uses `sequence_number`, not timestamps or UUIDs.
- Refresh tokens are stored as hashes and rotate under row locks.
- Admins are API-key principals, not user rows.

## External Services

- MinIO calls are wrapped in `services/storage.py` and moved off the event loop.
- Qdrant uses named dense and BM25 sparse vectors with RRF fusion.
- OpenRouter endpoints are configured as full request URLs.
- The dr7 chat URL is converted to an OpenAI base URL only in the LangChain
  model factory.
- Never persist or log provider keys, JWT secrets, admin keys, or raw tokens.

## Validation

Run before finishing a change:

```bash
uvx ruff check api core db models schemas services
uvx ruff format --check api core db models schemas services
uvx ty check api core db models schemas services
```

Also generate OpenAPI and compile ORM metadata when routes or models change.
Provider calls cannot be considered validated without actual credentials.

## Constraints

- Python 3.12+
- ASCII by default in source files; multilingual content belongs in prompts or
  user/provider data.
- Alembic migrations live in `alembic/versions/`. Run `alembic upgrade head` before
  deploying; startup `create_all` is a dev convenience only.
- Tests are deferred by current product decision; 3 integration tests exist
  in tests/ and require docker-compose infra + env vars to run.
- Runtime configuration and secrets remain environment-only.

## Comments

- Code is self-documenting. No uppercase comments, section dividers, or
  decorative separators (`# FIXME`, `# TODO`, `# ── Section ──`, etc.).
