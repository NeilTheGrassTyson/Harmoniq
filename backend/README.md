# Harmoniq — Backend

FastAPI application serving the Harmoniq API. Handles authentication verification, business logic, database access, and music catalog ingestion.

---

## Tech stack

- **Python 3.12+** with **Poetry** for dependency management
- **FastAPI** — async web framework, Pydantic v2 for validation
- **SQLAlchemy 2.0** (async, asyncpg driver) — ORM
- **Alembic** — database migrations
- **Neon** — managed PostgreSQL (serverless)
- **Clerk** — JWT-based authentication (verified here, not issued here)
- **slowapi** — rate limiting
- **ruff** — linting and formatting
- **mypy** — static type checking
- **pytest** — test suite

---

## Directory structure

```
backend/
├── app/
│   ├── main.py          App factory — registers middleware, routes
│   ├── config.py        Settings (pydantic-settings, reads from .env)
│   ├── database.py      Async SQLAlchemy engine + session dependency
│   ├── auth.py          Clerk JWT verification — get_current_user dependency
│   ├── api/v1/          One route module per domain, registered in router.py
│   │                    (prefix /api/v1). Thin — no business logic.
│   ├── core/            Enums, CORS, token crypto, rate limiting, security
│   │                    headers, and the shared visibility check (visibility.py)
│   ├── models/          SQLAlchemy ORM models. __init__.py re-exports every
│   │                    model — required for Alembic autogenerate.
│   ├── schemas/         Pydantic request/response contracts, per domain
│   └── services/        Business logic, one module per domain. musicbrainz.py
│                        is the rate-limited MusicBrainz client.
├── alembic/
│   ├── env.py           Migration environment (reads settings, imports models)
│   ├── script.py.mako   Migration file template
│   └── versions/        Generated migration files
├── scripts/             One-off operational scripts (e.g. seed_catalog.py)
├── tests/
│   ├── conftest.py      Shared fixtures
│   ├── unit/            No external dependencies
│   └── integration/     Real PostgreSQL via Testcontainers — needs Docker (ADR 0007)
├── .env.example         Required environment variables (no secrets)
├── alembic.ini          Alembic configuration
├── pyproject.toml       Dependencies + tool config (ruff, mypy, pytest)
├── Procfile             Railway start command
└── railway.json         Railway build + release configuration
```

---

## Setup

```bash
# From the backend/ directory:

# Don't create or activate a venv yourself — docs/setup.md §2 explains why.
poetry env use 3.12
poetry install

cp .env.example .env
# Edit .env — the three variables below are the core set; the rest enable
# individual integrations and features (see "Required environment variables")
```

### Required environment variables

| Variable                 | Description                                                                                        |
| ------------------------ | -------------------------------------------------------------------------------------------------- |
| `DATABASE_URL`           | `postgresql+asyncpg://user:pass@host/db?sslmode=require`                                           |
| `CLERK_JWKS_URL`         | From Clerk dashboard → API Keys (e.g. `https://your-app.clerk.accounts.dev/.well-known/jwks.json`) |
| `MUSICBRAINZ_USER_AGENT` | Required by MetaBrainz API: `"AppName/Version (email@example.com)"`                                |

These three are the core. `.env.example` lists every other variable — Clerk
secret and webhook, CORS origins, Spotify credentials, `TOKEN_ENCRYPTION_KEY`,
R2, and the per-feature flags (`SEARCH_LOCAL_FIRST`, `HARMONY_ENABLED`,
`MELODY_REACTIONS_ENABLED`, `STREAMING_LINKS_ENABLED`) — and
`docs/setup.md` §4 explains each one.

---

## Running locally

```bash
# Run pending migrations first
alembic upgrade head

# Start the development server (auto-reloads on file changes)
uvicorn app.main:app --reload --port 8000
```

API base: `http://localhost:8000`  
Interactive docs (dev only): `http://localhost:8000/docs`

---

## Development commands

```bash
# Lint
poetry run ruff check .

# Format (auto-fix)
poetry run ruff format .

# Type check
poetry run mypy app

# Run tests
poetry run pytest

# Run tests with coverage
poetry run pytest --cov=app
```

All four must pass before a PR can merge (enforced by CI).

---

## Adding a new feature

1. **Model** — add a SQLAlchemy model in `app/models/<domain>.py`, import it in `app/models/__init__.py`
2. **Migration** — run `alembic revision --autogenerate -m "describe the change"`, review the generated file
3. **Schema** — add Pydantic request/response models in `app/schemas/<domain>.py`
4. **Service** — add business logic in `app/services/<domain>.py`
5. **Route** — add route handlers in `app/api/v1/<domain>.py`, register in `app/api/v1/router.py`
6. **Tests** — add tests in `tests/test_<domain>.py`

Each service module is logically separated — no service imports from another service's internal modules. Shared access goes through `models/` and `schemas/` only.

---

## Authentication

Protected routes use the `get_current_user` dependency from `app/auth.py`:

```python
from typing import Annotated
from fastapi import Depends
from app.auth import get_current_user

@router.get("/me")
async def get_profile(user_id: Annotated[str, Depends(get_current_user)]):
    # user_id is the Clerk `sub` claim (e.g. "user_2abc...")
    ...
```

The backend never issues or stores sessions. It verifies Clerk JWTs against Clerk's JWKS endpoint.

---

## Migrations

```bash
# Apply all pending migrations
alembic upgrade head

# Create a new migration (review the generated file before committing)
alembic revision --autogenerate -m "add users table"

# Downgrade one step
alembic downgrade -1

# Show migration history
alembic history
```

Migrations run automatically as Railway's `preDeployCommand` (`railway.json`) before each new release starts; a failing migration fails the deploy and the previous release keeps serving. This was misnamed `releaseCommand`, which Railway ignores, until 2026-10-02, and **production only gets the fix with the next `dev → main` release** — see [docs/deployment.md](../docs/deployment.md#migrations-on-deploy). Always run `alembic upgrade head` locally after pulling changes that include new migration files.
