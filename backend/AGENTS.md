# AGENTS.md — backend

Read the root `AGENTS.md` first — this file only adds backend-specific
detail, it doesn't restate the project-wide rules (Tier 1/Tier 2 gate,
Spotify ToS constraint, branch flow).

## Folder structure

```
backend/app/
├── api/v1/         Route handlers (thin — no business logic)
├── core/           Enums, rate limiting, security helpers
├── models/         SQLAlchemy ORM models
├── schemas/        Pydantic request/response contracts
├── services/       Business logic (one module per domain)
├── main.py         App factory
├── config.py       pydantic-settings, env-driven
├── database.py     Async engine + session factory
└── auth.py         Clerk JWT verification
```

Route handlers stay thin. Business logic belongs in `services/`, one module
per domain — don't let it creep into `api/v1/`.

## Commands

- Dependency management: Poetry, run from `backend/` (`backend/pyproject.toml`
  is the only one in the repo).
- Run dev server: `cd backend && uvicorn app.main:app --reload`
- Run tests: `cd backend && python -m pytest -m "not integration"` for the
  unit tier (no external dependencies, runs anywhere). The integration
  tier (`-m "integration"`, or no `-m` filter for the full suite) needs a
  Docker daemon — Testcontainers spins up real Postgres. If Docker isn't
  available in your environment, stick to the unit-tier command; don't
  read a Docker-dependent failure as a broken test. `docs/setup.md` §8 has
  the full breakdown.
- Migrations: `cd backend && alembic upgrade head`
- Full CI-equivalent gate before pushing: see root `AGENTS.md`'s backend
  command block.

## Testing

`pytest`, `pytest-asyncio`, `pytest-cov`. Integration tests use
Testcontainers (real PostgreSQL) — `NullPool` is required in test fixtures
to avoid asyncpg connection conflicts; dropping it reintroduces connection
errors that look unrelated to the change that caused them.

## Data access and visibility (ENGINEERING_BIBLE.md §8.1)

Every shareable entity (highlight, listening activity, Melody history,
Harmony detail) carries an explicit visibility scope, defaulting to the
most private option. **Enforcement happens at the data-access layer, not
the presentation layer** — a query for another user's data must itself
respect visibility scope. It is never acceptable to return private data
from an endpoint and rely on the frontend to hide it. This is the single
most re-checked rule in this codebase (see `ROADMAP.md`'s closing note) —
treat any new query touching user-generated data as visibility-scoped by
default, not as an afterthought pass.
