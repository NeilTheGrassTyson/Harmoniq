# Harmoniq — Architecture Overview

> **Status:** Phase 1 (Feature 2 shipped) — modular monolith.
> This document describes what the system *is* today. Evolutionary changes are recorded as ADRs in `docs/adr/`.

---

## Repository Layout

```
Harmoniq/
├── backend/              FastAPI application (Python 3.12+)
│   ├── app/
│   │   ├── api/v1/       HTTP route handlers (thin — no business logic)
│   │   ├── core/         Enums, rate limiting, security helpers
│   │   ├── models/       SQLAlchemy ORM models (database schema)
│   │   ├── schemas/      Pydantic request/response contracts
│   │   ├── services/     Business logic (one module per domain)
│   │   ├── main.py       App factory
│   │   ├── config.py     Settings (pydantic-settings, env-driven)
│   │   ├── database.py   Async SQLAlchemy engine + session factory
│   │   └── auth.py       Clerk JWT verification + optional auth helper
│   ├── alembic/          Database migrations
│   └── tests/            Pytest test suite
│
├── frontend/             Next.js 16 application (App Router, TypeScript)
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
│  ─ Clerk <ClerkProvider> for session UI + JWT gate              │
└──────────────────────────┬──────────────────────────────────────┘
                           │ HTTPS + JWT (Clerk session token)
┌──────────────────────────▼──────────────────────────────────────┐
│  FastAPI backend (Railway)                                      │
│  ─ auth middleware: verifies Clerk JWT on every protected route │
│  ─ api/v1/: route handlers                                      │
│  ─ services/: identity, social graph, catalog, melody, feed     │
│  ─ slowapi: rate limiting                                       │
└──────────┬───────────────┴──────────────────────────────────────┘
           │ boto3 (S3-compatible)          │ asyncpg
           ▼                               ▼
┌──────────────────────┐    ┌──────────────────────────────────────┐
│  Cloudflare R2       │    │  PostgreSQL (Neon)                   │
│  ─ Avatar storage    │    │  ─ SQLAlchemy 2.0 async ORM          │
│  ─ Public CDN URL    │    │  ─ Alembic migrations                │
└──────────────────────┘    └──────────────────────────────────────┘
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
5. On first sign-in the user is routed to `/onboarding` to choose a username.
   After the Harmoniq user record is created, the backend sets
   `publicMetadata.onboarded = true` in Clerk via the Management API. The
   Next.js middleware reads this flag from the JWT on every request and
   redirects unonboarded users to `/onboarding`.
6. The decoded `clerk_id` (Clerk's `sub` claim) maps to an internal UUID in
   the `users` table. Internal joins always use the UUID; the `clerk_id` is
   only used for identity lookups.

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

| Service | Status | Responsibility |
|---|---|---|
| `identity` (user.py) | ✅ Phase 1 | User records, profile, visibility settings, avatar |
| `catalog` | ✅ Phase 1 | Music ingestion from MusicBrainz; track/album/artist entities |
| `storage` | ✅ Phase 1 | Cloudflare R2 avatar upload |
| `social` | Planned | Follow graph, trust relationships |
| `melody` | Planned | Melody lifecycle state machine |
| `harmony` | Planned | Harmony score computation |
| `feed` | Planned | Home and Discovery surface composition |

---

## Database Architecture

- **Engine:** PostgreSQL 16 via Neon (serverless, connection pooling via PgBouncer).
- **ORM:** SQLAlchemy 2.0 with async `asyncpg` driver.
- **Migrations:** Alembic — every schema change is a versioned migration file.
- **Identifiers:** UUID primary keys throughout. Clerk's `sub` is stored as
  a `clerk_id` string column; internal joins use UUIDs.
- **Visibility enforcement:** Performed at the service layer (`services/user.py`)
  using a `VisibilityScope` enum (`private` / `friends` / `public`). Fields
  excluded by scope are absent from the JSON response (not null) — achieved via
  Pydantic's `model_construct` + `exclude_unset`. Never enforced in route
  handlers or on the frontend.

### Tables (current)

```
users
  id                UUID PK
  clerk_id          VARCHAR UNIQUE NOT NULL   ← Clerk sub claim
  username          VARCHAR UNIQUE NOT NULL   ← chosen at onboarding
  display_name      VARCHAR(50) NOT NULL
  avatar_url        VARCHAR                   ← public R2 URL
  bio               VARCHAR(280)
  visibility_bio    VARCHAR NOT NULL DEFAULT 'private'
  visibility_activity VARCHAR NOT NULL DEFAULT 'private'
  visibility_ratings  VARCHAR NOT NULL DEFAULT 'private'
  created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
  updated_at        TIMESTAMPTZ NOT NULL DEFAULT now()

artists
  id            UUID PK
  mbid          VARCHAR UNIQUE NOT NULL
  name          VARCHAR NOT NULL
  sort_name     VARCHAR
  disambiguation VARCHAR
  image_url     VARCHAR
  last_fetched_at TIMESTAMPTZ NOT NULL

albums (release groups)
  id            UUID PK
  mbid          VARCHAR UNIQUE NOT NULL
  title         VARCHAR NOT NULL
  artist_id     UUID FK → artists.id
  release_year  INTEGER
  album_type    VARCHAR
  cover_art_url VARCHAR
  last_fetched_at TIMESTAMPTZ NOT NULL

tracks (recordings)
  id            UUID PK
  mbid          VARCHAR UNIQUE NOT NULL
  title         VARCHAR NOT NULL
  artist_id     UUID FK → artists.id
  album_id      UUID FK → albums.id   ← nullable
  duration_ms   INTEGER
  track_number  INTEGER
  disc_number   INTEGER
  last_fetched_at TIMESTAMPTZ NOT NULL
```

---

## Media Storage

Avatars are stored in **Cloudflare R2** (S3-compatible object storage).

- The backend receives the uploaded file, validates content type via magic bytes
  (JPEG `\xff\xd8\xff`, PNG `\x89PNG\r\n\x1a\n`, WebP `RIFF…WEBP`), and uploads
  via `boto3` in a thread-pool executor.
- The public CDN URL (`R2_PUBLIC_URL/avatars/{uuid}.{ext}`) is stored in the DB.
  Raw bytes never touch Postgres.
- Maximum file size: 5 MB. Supported types: JPEG, PNG, WebP.
- R2 requires a public bucket or custom domain; configure in Cloudflare Dashboard.

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

| Variable | Where it lives | Required for |
|---|---|---|
| `DATABASE_URL` | Railway / Neon dashboard | All server ops |
| `CLERK_JWKS_URL` | Railway env var | JWT verification |
| `CLERK_SECRET_KEY` | Railway env var | Onboarding flag sync |
| `CLERK_WEBHOOK_SECRET` | Railway env var | Webhook signature verification |
| `CLERK_PUBLISHABLE_KEY` | Vercel env var (public) | Frontend Clerk UI |
| `MUSICBRAINZ_USER_AGENT` | Railway env var | MusicBrainz API |
| `R2_ACCOUNT_ID` | Railway env var | Avatar upload |
| `R2_ACCESS_KEY_ID` | Railway env var | Avatar upload |
| `R2_SECRET_ACCESS_KEY` | Railway env var | Avatar upload |
| `R2_BUCKET_NAME` | Railway env var | Avatar upload |
| `R2_PUBLIC_URL` | Railway env var | Avatar URL generation |

R2 and Clerk SK/webhook credentials are optional at import time and
validated at their call sites — Alembic migrations can run with only
`DATABASE_URL` and `CLERK_JWKS_URL` set.

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
