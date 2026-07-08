# Harmoniq

> A social music discovery network built around trust and musical identity.

Harmoniq is not a streaming platform, a content feed, or a recommendation engine. It is a system where music is transmitted between people as a signal of taste and identity — discovered through trusted people, not algorithms.

---

## What this repository is

This is the Harmoniq monorepo. It contains everything needed to build, run, and deploy the product:

```
Harmoniq/
├── backend/          FastAPI application (Python) — API, business logic, database
├── frontend/         Next.js application — UI, routing, Clerk session handling
├── docs/
│   ├── adr/          Architecture Decision Records — why major decisions were made
│   ├── setup.md      Local development guide
│   └── deployment.md Deployment guide (Vercel + Railway + Neon)
├── specs/            Feature specifications (written before implementation)
├── ARCHITECTURE.md   System overview, data flow, deployment diagram
├── HARMONIQ.md       Project constitution — principles that govern every decision
├── BRAND_BIBLE.md    Product identity, naming, tone, interaction philosophy
├── ENGINEERING_BIBLE.md  Technical architecture and domain model
├── ROADMAP.md        Feature roadmap — NOW / NEXT / LATER
└── WORKFLOW.md       How features move from idea to shipped
```

---

## Current status

**Phase 0 complete** — infrastructure and stack decisions are finalized and committed.

**Phase 1 (NOW) has not started.** Feature development begins after reviewing [ROADMAP.md](ROADMAP.md) and writing a spec for each Tier 1 feature per [WORKFLOW.md](WORKFLOW.md).

---

## Stack

| Layer            | Technology                                                                                |
| ---------------- | ----------------------------------------------------------------------------------------- |
| Backend          | Python 3.12+, FastAPI, SQLAlchemy 2.0 (async), Alembic                                    |
| Frontend         | Next.js 16 (App Router), TypeScript (strict), Tailwind CSS 4                              |
| Database         | PostgreSQL 16 via [Neon](https://neon.tech) (serverless)                                  |
| Auth             | [Clerk](https://clerk.com)                                                                |
| Frontend hosting | [Vercel](https://vercel.com)                                                              |
| Backend hosting  | [Railway](https://railway.app)                                                            |
| Music catalog    | [MusicBrainz](https://musicbrainz.org) + [Cover Art Archive](https://coverartarchive.org) |

Full rationale for every decision is in [`docs/adr/`](docs/adr/).

---

## Quick start

You need accounts on [Neon](https://neon.tech) and [Clerk](https://clerk.com) before the app will run. See [docs/setup.md](docs/setup.md) for the full walkthrough.

**Backend (terminal 1):**

```bash
cd backend
python -m venv .venv && source .venv/bin/activate   # .venv\Scripts\activate on Windows
pip install poetry && poetry install
cp .env.example .env   # fill in DATABASE_URL, CLERK_JWKS_URL, MUSICBRAINZ_USER_AGENT
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

**Frontend (terminal 2):**

```bash
cd frontend
npm install
cp .env.local.example .env.local   # fill in Clerk keys and NEXT_PUBLIC_API_URL
npm run dev
```

Health check: `curl http://localhost:8000/api/v1/health`

---

## Governance

This project is governed by [HARMONIQ.md](HARMONIQ.md). Every feature and technical decision is weighed against its eight principles. Before starting any work, read:

1. [HARMONIQ.md](HARMONIQ.md) — the constitution
2. [WORKFLOW.md](WORKFLOW.md) — how work gets approved and reviewed
3. [ROADMAP.md](ROADMAP.md) — what's being built and in what order

The `specs/` directory holds feature specifications written using [SPEC_TEMPLATE.md](SPEC_TEMPLATE.md). A spec must be approved before any Tier 1 feature is implemented.

---

## Key commands

| Where       | Command                    | What it does           |
| ----------- | -------------------------- | ---------------------- |
| `backend/`  | `poetry run ruff check .`  | Lint                   |
| `backend/`  | `poetry run ruff format .` | Format                 |
| `backend/`  | `poetry run mypy app`      | Type check             |
| `backend/`  | `poetry run pytest`        | Test suite             |
| `backend/`  | `alembic upgrade head`     | Run pending migrations |
| `frontend/` | `npm run dev`              | Start dev server       |
| `frontend/` | `npm run typecheck`        | TypeScript check       |
| `frontend/` | `npm run lint`             | ESLint                 |
| `frontend/` | `npm run format`           | Prettier (auto-fix)    |
| `frontend/` | `npm run build`            | Production build       |
