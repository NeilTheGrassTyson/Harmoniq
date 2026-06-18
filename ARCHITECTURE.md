# Harmoniq — Architecture Overview

> **Status:** Phase 0 baseline — modular monolith.
> This document describes what the system *is* today. Evolutionary changes are recorded as ADRs in `docs/adr/`.

---

## Repository Layout

```
Harmoniq/
├── backend/              FastAPI application (Python 3.12+)
│   ├── app/
│   │   ├── api/v1/       HTTP route handlers (thin — no business logic)
│   │   ├── core/         Security, rate limiting, shared middleware
│   │   ├── models/       SQLAlchemy ORM models (database schema)
│   │   ├── schemas/      Pydantic request/response contracts
│   │   ├── services/     Business logic (one module per domain)
│   │   ├── main.py       App factory
│   │   ├── config.py     Settings (pydantic-settings, env-driven)
│   │   ├── database.py   Async SQLAlchemy engine + session factory
│   │   └── auth.py       Clerk JWT verification middleware
│   ├── alembic/          Database migrations
│   └── tests/            Pytest test suite
│
├── frontend/             Next.js 15 application (App Router, TypeScript)
│   ├── src/app/          Page routes and layouts (RSC by default)
│   ├── src/components/   Shared UI components
│   ├── src/lib/          Utility functions, API client, type helpers
│   └── src/types/        Shared TypeScript types
│
├── docs/
│   ├── adr/              Architecture Decision Records
│   ├── setup.md          Local development guide
│   └── deployment.md     Deployment guide
│
├── specs/                Feature specs (SPEC_TEMPLATE.md format)
└── .github/workflows/    CI pipelines
```

---

## System Overview

Harmoniq is a **modular monolith** in its initial phase. The goal is clarity
of internal boundaries within a single deployable unit — not premature
distribution.

```
┌─────────────────────────────────────────────────────────────────┐
│  Browser                                                        │
│  Next.js (Vercel)                                               │
│  ─ App Router, RSC, Tailwind CSS                                │
│  ─ Clerk <ClerkProvider> for session UI                         │
└──────────────────────────┬──────────────────────────────────────┘
                           │ HTTPS + JWT (Clerk session token)
┌──────────────────────────▼──────────────────────────────────────┐
│  FastAPI backend (Railway)                                      │
│  ─ auth middleware: verifies Clerk JWT on every protected route │
│  ─ api/v1/: route handlers                                      │
│  ─ services/: identity, social graph, catalog, melody, feed     │
│  ─ slowapi: rate limiting                                       │
└──────────────────────────┬──────────────────────────────────────┘
                           │ asyncpg
┌──────────────────────────▼──────────────────────────────────────┐
│  PostgreSQL (Neon)                                              │
│  ─ SQLAlchemy 2.0 async ORM                                     │
│  ─ Alembic migrations                                           │
└─────────────────────────────────────────────────────────────────┘
```

---

## Authentication Flow

1. User signs in via Clerk's prebuilt UI (hosted or embedded).
2. Clerk issues a **short-lived JWT** (session token) to the browser.
3. The Next.js frontend attaches `Authorization: Bearer <token>` to every
   API request.
4. The FastAPI `auth.py` middleware verifies the JWT against Clerk's JWKS
   endpoint on every protected route. No session state is stored in the
   backend.
5. The decoded `user_id` (Clerk's `sub` claim) is the canonical user
   identifier throughout the system. It is stored in the `users` table on
   first authenticated request.

---

## Frontend / Backend Contract

- The frontend **never** computes rankings, interprets trust, or talks to
  external music providers directly (Engineering Bible §7).
- All mutation and read operations go through the FastAPI backend.
- Pydantic schemas on the backend define the canonical shape of every
  request and response.
- TypeScript types on the frontend should match those schemas — shared type
  generation is deferred to Phase NEXT.

---

## Internal Backend Services

The backend is divided into logical service modules. They are co-deployed
but have explicit boundaries — no service imports from another's internal
modules, only from shared `models/` and `schemas/`.

| Service | Responsibility |
|---|---|
| `identity` | User records, profile, visibility settings |
| `social` | Follow graph, trust relationships |
| `catalog` | Music ingestion from MusicBrainz; track/album/artist entities |
| `melody` | Melody lifecycle state machine (send → received → opened/rejected) |
| `harmony` | Harmony score computation (computed component only) |
| `feed` | Home and Discovery surface composition |

---

## Database Architecture

- **Engine:** PostgreSQL 16 via Neon (serverless, connection pooling via PgBouncer).
- **ORM:** SQLAlchemy 2.0 with async `asyncpg` driver.
- **Migrations:** Alembic — every schema change is a versioned migration file.
- **Identifiers:** UUID primary keys throughout. Clerk's `sub` is stored as
  a string; internal joins use UUIDs.
- **Visibility enforcement:** Every query over user-generated data accepts a
  `requesting_user_id` parameter and applies visibility scope at the SQL
  level — never in application code after the fact.

---

## Music Catalog Architecture

- **Canonical source:** MusicBrainz (Phase 0/1 uses MetaBrainz API).
- **Identifiers:** MusicBrainz IDs (MBIDs) are stored as the canonical external
  key on every `track`, `album`, and `artist` record.
- **Artwork:** Cover Art Archive CDN URLs are stored; no binary assets are
  held in our database.
- **Ingestion:** On-demand: when a user searches for a track that doesn't
  exist in our catalog, the backend queries MusicBrainz, normalizes the
  response, and upserts into our catalog.
- **Audio previews:** Deezer API (supplementary, Phase NEXT — not present
  in Phase 0/1).

---

## Environment Variable Strategy

Three environments: `development`, `staging`, `production`. Secrets are
never committed — `.env.example` files document every required variable with
placeholder values.

| Variable | Where it lives |
|---|---|
| Database URL | Railway / Neon dashboard → env var injection |
| Clerk secret key | Railway env var |
| Clerk publishable key | Vercel env var (public, prefixed `NEXT_PUBLIC_`) |
| MusicBrainz API key | Railway env var |

---

## Deployment Flow

- **Frontend:** Push to `main` → Vercel auto-deploys. Feature branches get
  automatic preview URLs.
- **Backend:** Push to `main` → Railway auto-deploys via Procfile
  (`web: uvicorn app.main:app --host 0.0.0.0 --port $PORT`).
- **Database migrations:** Run `alembic upgrade head` as a Railway release
  command before the new backend revision receives traffic.

---

## Local Development Workflow

See [docs/setup.md](docs/setup.md) for the full walkthrough. The short version:

```bash
# Backend
cd backend
python -m venv .venv && source .venv/bin/activate   # or .venv\Scripts\activate on Windows
pip install -e ".[dev]"
alembic upgrade head
uvicorn app.main:app --reload

# Frontend (separate terminal)
cd frontend
npm install
npm run dev
```

---

## Testing Strategy

- **Backend:** pytest + httpx async client. Unit tests for services; integration
  tests for API endpoints against a real test database (Neon branch or local
  PostgreSQL). No mocking the database — see Engineering Bible §8.
- **Frontend:** Vitest + React Testing Library for component logic; Playwright
  for end-to-end flows (Phase NEXT).
- **CI:** Both suites run on every pull request via GitHub Actions.

---

## Branching Strategy

- `main` — production. Protected; requires passing CI.
- `feature/*` — feature branches. Each gets a Vercel preview URL and a Neon
  database branch automatically.
- Commits to `main` are squash-merged from feature branches.

---

## ADR Index

All significant architectural decisions are recorded in `docs/adr/`:

| # | Title |
|---|---|
| [0001](docs/adr/0001-backend-framework.md) | Backend framework: FastAPI |
| [0002](docs/adr/0002-frontend-framework.md) | Frontend framework: Next.js 15 |
| [0003](docs/adr/0003-database.md) | Database: PostgreSQL via Neon |
| [0004](docs/adr/0004-authentication.md) | Authentication: Clerk |
| [0005](docs/adr/0005-hosting.md) | Hosting: Vercel + Railway |
| [0006](docs/adr/0006-music-database.md) | Music catalog: MusicBrainz |
