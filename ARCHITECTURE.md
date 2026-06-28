# Harmoniq — Architecture Overview

> **Status:** Phase 1 (Music Catalog, User Accounts, Ratings, Follows, Home shipped) — modular monolith.
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
│  Next.js 16 (Vercel)                                            │
│  ─ App Router, RSC, Tailwind CSS v4 (@theme in globals.css)     │
│  ─ Clerk <ClerkProvider> for session UI; proxy.ts JWT gate      │
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
   Next.js `proxy.ts` (the Next.js 16 replacement for `middleware.ts`) reads
   this flag from the JWT on every request and redirects unonboarded users
   to `/onboarding`. Only private routes are gated — public browse routes
   (`/`, `/u/*`, `/artist/*`, etc.) are readable before onboarding completes,
   which also eliminates a JWT-propagation race after the onboarding form
   submits.
6. The decoded `clerk_id` (Clerk's `sub` claim) maps to an internal UUID in
   the `users` table. Internal joins always use the UUID; the `clerk_id` is
   only used for identity lookups.

---

## Frontend Layout Shell

`AppShell` (`frontend/src/components/AppShell.tsx`) is the single shared
layout for all authenticated and publicly-browsable pages. Every route that
renders content (Home, profile, artist, album, track, search, settings) wraps
its output in `AppShell`. The onboarding and auth pages (`/onboarding`,
`/sign-in`, `/sign-up`, `/sso-callback`) are the only exceptions — they
render without a shell.

AppShell owns:
- The collapsible sidebar (220px open, 0px collapsed, 200ms transition).
- The 3-column header grid (toggle + logo / search / NavAuth).
- The global sidebar navigation links: **Home** (`/`), **Search** (`/search`),
  **Profile** (`/u/[username]` — signed-in users only), **Settings**
  (`/settings`). Active state is derived from `usePathname()`.

No page file should render its own header, sidebar, or navigation — those
belong exclusively to AppShell.

---

## User Search

### Endpoint

`GET /api/v1/users/search?q={query}` — unauthenticated (optionally auth-aware in future).

- **Auth:** optional. Accepts a Clerk JWT if present, ignores absence. The endpoint is
  useful for logged-out browse flows and is therefore not protected.
- **Rate limit:** 20 requests/minute per IP (`slowapi`).
- **Min query length:** 2 characters. Returns `[]` immediately for shorter queries
  without hitting the database.
- **Matching:** case-insensitive `ILIKE` on `username` OR `display_name` (OR condition).
- **Response:** `list[UserSearchResult]` — only `username`, `display_name`, `avatar_url`.
  No `clerk_id`, no visibility fields, no internal IDs.
- **Route ordering:** registered before `GET /{username}` to prevent the catch-all
  from consuming `/search` as a username lookup.

### `filter_discoverable_users` stub

`services/user.py` contains a `filter_discoverable_users(query: Select) -> Select`
function that wraps every user search query. Today it is a pass-through (all users
are discoverable). When private profiles ship, visibility filtering is added here
rather than scattered across callers. The stub and its test harness are in place now
so the change surface is predictable. See `ENGINEERING_BIBLE.md §8.1`.

### Frontend

- `lib/users.ts:searchUsers(query)` calls this endpoint.
- `SearchBar` fetches both `searchCatalog` and `searchUsers` in parallel using
  `Promise.allSettled` — either fetch may fail independently without affecting the
  other's results.
- When on `/search`, `SearchBar` additionally calls `router.push("/search?q=…")`
  (debounced, 300ms) to keep the URL and the `/search` page body in sync.
- The `/search` page (`app/search/page.tsx`) reads `?q=` via `useSearchParams` and
  renders People + Music sections (up to 10 results each), or an empty state.

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
| `identity` (user.py) | ✅ Phase 1 | User records, profile, visibility settings, avatar, user search |
| `catalog` | ✅ Phase 1 | Music ingestion from MusicBrainz; track/album/artist entities |
| `storage` | ✅ Phase 1 | Cloudflare R2 avatar upload |
| `rating` | ✅ Phase 1 | Ratings and reviews; aggregate scores; reports |
| `follow` | ✅ Phase 1 | Follow graph (follower/followed relationships) |
| `home` | ✅ Phase 1 | Home surface: trending + friends' top songs |
| `melody` | Planned | Melody lifecycle state machine |
| `harmony` | Planned | Harmony score computation |
| `discovery` | Planned | Discovery surface (Harmonic Feed) composition |

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

ratings
  id            UUID PK
  user_id       UUID FK → users.id NOT NULL
  entity_type   VARCHAR NOT NULL               ← 'track' | 'album'
  entity_id     UUID NOT NULL                  ← internal PK of entity (no FK constraint — see below)
  score         INTEGER NOT NULL               CHECK (score >= 1 AND score <= 10)
  review_text   VARCHAR(2000) NOT NULL
  visibility    VARCHAR NOT NULL DEFAULT 'public'
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
  INDEX ix_ratings_user_id (user_id)
  INDEX ix_ratings_entity (entity_type, entity_id, created_at)
  INDEX ix_ratings_user_entity_created (user_id, entity_type, entity_id, created_at)

reports
  id            UUID PK
  reporter_id   UUID FK → users.id NOT NULL
  rating_id     UUID FK → ratings.id NOT NULL
  UNIQUE (reporter_id, rating_id)
  INDEX ix_reports_reporter_id (reporter_id)
  INDEX ix_reports_rating_id (rating_id)

follows
  follower_id   UUID FK → users.id NOT NULL (CASCADE)
  followed_id   UUID FK → users.id NOT NULL (CASCADE)
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
  PRIMARY KEY (follower_id, followed_id)
  CHECK ck_follows_no_self_follow (follower_id != followed_id)
  INDEX ix_follows_followed_id (followed_id)   ← who follows this user?
  INDEX ix_follows_follower_id (follower_id)   ← who does this user follow?
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

## Ratings & Reviews Architecture

### Polymorphic Entity Reference

The `ratings` table stores a `(entity_type, entity_id)` pair rather than two separate FK columns pointing at `tracks` and `albums`. There is no DB-level FK constraint on `entity_id` — it references different tables depending on `entity_type`. Referential integrity is enforced in `services/rating.py` via `resolve_entity(session, entity_type, entity_mbid)`: if the MBID cannot be found in the appropriate catalog table, the endpoint returns 404 before writing any row.

This pattern avoids schema duplication (separate `track_ratings` and `album_ratings` tables) and keeps query logic uniform across entity types. Future rating targets (artists, playlists) can be added by extending the `entity_type` enum without schema migrations.

### Aggregate Calculation

Aggregate scores are computed on read using a SQL window function — there is no denormalized "current score" column maintained on the entity tables. The query uses `ROW_NUMBER() OVER (PARTITION BY user_id ORDER BY created_at DESC)` in a subquery to select each user's most-recent rating, then applies `AVG()` to that set:

```sql
SELECT AVG(score) FROM (
  SELECT score,
    ROW_NUMBER() OVER (PARTITION BY user_id ORDER BY created_at DESC) AS rn
  FROM ratings
  WHERE entity_type = :et AND entity_id = :eid AND visibility = 'public'
) sub WHERE rn = 1
```

This correctly handles re-ratings (only the most recent counts) without requiring an `is_current` flag to be maintained across inserts and deletes.

### Visibility Default Exception

All other user-generated content in Harmoniq defaults to `private`. Ratings default to `public` — an explicit, approved exception. Ratings are the primary social signal of the product; a private-by-default system would be dark from launch. This exception is recorded in `specs/phase-1-ratings-reviews.md`.

### Report Duplicate Prevention

The UNIQUE constraint on `(reporter_id, rating_id)` in the `reports` table catches duplicate reports at the DB level. `services/rating.py` catches `IntegrityError`, rolls back, and returns a `(False, "duplicate")` tuple to the route handler. This is race-condition safe without a pre-flight SELECT.

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

The frontend design token reference is documented separately in
[DESIGN_SYSTEM.md](DESIGN_SYSTEM.md) — colors, typography,
spacing, motion, and component patterns.

**Outstanding:** Clerk's `appearance` prop for the sign-in and sign-up pages
has not yet been configured. The pages use Clerk's default dark theme until
this is wired up.

| # | Title |
|---|---|
| [0001](docs/adr/0001-backend-framework.md) | Backend framework: FastAPI |
| [0002](docs/adr/0002-frontend-framework.md) | Frontend framework: Next.js 16 |
| [0003](docs/adr/0003-database.md) | Database: PostgreSQL via Neon |
| [0004](docs/adr/0004-authentication.md) | Authentication: Clerk |
| [0005](docs/adr/0005-hosting.md) | Hosting: Vercel + Railway |
| [0006](docs/adr/0006-music-database.md) | Music catalog: MusicBrainz |
