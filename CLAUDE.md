# Project overview

A social music discovery and rating platform: the critical/rating culture of RateYourMusic, the social graph and following/feed model of Spotify's social features, and user posts/reviews as a core feature (not an afterthought). A recommendation layer built from data collected directly in-app (ratings, reviews, follows, listens) is part of the long-term vision, but per HARMONIQ.md's "Humans Before Algorithms" principle and ROADMAP.md's LATER tier, it is deliberately deferred and gated behind its own plan-mode spec — not a pillar with equal billing to the human-originated mechanics above.

## Governing principles

This project is governed by HARMONIQ.md, the project constitution. Every
feature and technical decision should be weighed against it — imported
below so it's loaded automatically every session:

@HARMONIQ.md

@ENGINEERING_BIBLE.md

## Important context: Spotify API constraints

Spotify has significantly restricted third-party developer access:

- The Recommendations endpoint was removed from the Web API (Feb 2026).
- The audio-features and audio-analysis endpoints (tempo, key, danceability)
  have been removed since late 2024.
- New developer accounts are capped at 5 authorized users in "Development
  Mode." Reaching a real audience requires applying for extended access,
  which requires a registered business and 250,000+ monthly active users.
- Spotify's developer policy prohibits training ML models on Spotify content
  or metadata.

Implication: Spotify account-linking is a nice-to-have integration (show
what a user is currently playing, optionally import a starter library), NOT
the backbone of the recommendation engine or the core data model. The taste
graph and recommendation engine must be built from data we collect directly:
ratings, reviews, follows, and listens logged inside our own app.

## Plan mode vs. auto mode

This project uses a two-tier process for deciding what needs a spec and
approval before implementation, versus what can proceed directly. The full
breakdown lives in WORKFLOW.md, imported below:

@WORKFLOW.md

One project-specific note that feeds into the Tier 1 "data collection/
storage/sharing" rule above: anything touching the recommendation engine's
data pipeline is Tier 1 by default, given the Spotify ToS constraint on
training models on Spotify content described earlier in this file.

## Situational references (not auto-loaded)

These docs matter but don't need to sit in context for every session — open
them deliberately when the task calls for it, either by asking directly or
referencing the file by name in your prompt:

- **BRAND_BIBLE.md** — consult during design/UI/copy work, and during the
  Design Audit step of the Review Workflow.
- **SPEC_TEMPLATE.md** — use when starting any Tier 1 feature.
- **ROADMAP.md** — consult during planning/prioritization conversations,
  not implementation.

## Conventions

### Stack

| Layer          | Choice                                                                                  |
| -------------- | --------------------------------------------------------------------------------------- |
| Backend        | FastAPI, Python 3.12+                                                                   |
| Database       | PostgreSQL (Neon serverless) + asyncpg + SQLAlchemy 2.0 async + Alembic                 |
| Auth           | Clerk — `proxy.ts` gate in Next.js; Clerk Management API for `publicMetadata.onboarded` |
| Frontend       | Next.js 16 (App Router, RSC, TypeScript)                                                |
| Styling        | Tailwind v4 — `@theme` block in `globals.css`, no `tailwind.config.js`                  |
| Typography     | Space Grotesk (display) via `next/font/google`; system font stack (body)                |
| File storage   | Cloudflare R2 (S3-compatible via boto3)                                                 |
| Music database | MusicBrainz + Cover Art Archive — on-demand ingestion                                   |
| Hosting        | Frontend: Vercel; Backend: Railway                                                      |
| Mobile dev     | Tailscale + Windows OpenSSH Server + Tailscale Serve                                    |
| IDE            | VSCode + Claude Code extension                                                          |

### Backend tooling

- **Dependency management:** Poetry (`pyproject.toml`). Poetry not on PATH on Windows — invoke via `py -m poetry` or the full `.venv` path.
- **Lint/format:** Ruff (`ruff check`, `ruff format`). Config in `pyproject.toml`.
- **Type check:** `mypy` (or pyright — check `pyproject.toml`).
- **Tests:** `pytest`, `pytest-asyncio`, `pytest-cov`. Integration tests use Testcontainers (real PostgreSQL). `NullPool` required in test fixtures to avoid asyncpg connection conflicts.
- **Run tests:** `cd backend && python -m pytest`
- **Run dev server:** `cd backend && uvicorn app.main:app --reload`
- **Migrations:** `cd backend && alembic upgrade head`

### Frontend tooling

- **Lint:** ESLint (`npm run lint`). Two Dependabot PRs held pending `eslint-config-next` peer dep support for TypeScript 5→6 and ESLint 9→10.
- **Type check:** `npm run typecheck`
- **Format:** Prettier with `prettier-plugin-tailwindcss`
- **Run dev server:** `cd frontend && npm run dev`

### Skills

- `unslop-ui` at `.claude/skills/unslop-ui/` — `SKILL.md`, `references/`, and `scripts/devibe_scan.py` must be direct children of that folder.

### Folder structure

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

frontend/src/
├── app/            Next.js App Router pages
│   ├── album/[mbid]/
│   ├── artist/[mbid]/
│   ├── onboarding/
│   ├── settings/
│   ├── sign-in/[[...sign-in]]/
│   ├── sign-up/[[...sign-up]]/
│   ├── sso-callback/
│   ├── track/[mbid]/
│   └── u/[username]/
├── components/     Shared UI components
├── lib/            API client helpers (users, catalog, ratings, follows, home)
└── types/          Shared TypeScript types (index.ts)
```
