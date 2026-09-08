# AGENTS.md

This is Codex's (and any Codex-family agent's, operating in this project as
**astra**) onboarding file for Harmoniq. It is the equivalent of `CLAUDE.md`
for Claude Code — same project, same rules, different tool. `AGENTS.md` has
no import mechanism, so unlike `CLAUDE.md` this file restates the essentials
inline rather than pulling them in. See ADR `docs/adr/0013-astra-second-engineer.md`
for why this file exists and how astra fits alongside Claude Code.

**Astra is an equal Engineering contributor, not an advisory or junior
role.** Same authority, same constraints as Claude Code — see
HARMONIQ.md's Governance section.

**Read these in order before doing anything non-trivial:**

1. `HARMONIQ.md` — the project constitution. Highest authority in the repo.
   Every feature and technical decision is weighed against it.
2. `ENGINEERING_BIBLE.md` — the architecture this constitution implies:
   domain model, the Home/Discovery split, Melody/Harmony semantics,
   security and consent requirements.
3. `WORKFLOW.md` — process: which work needs a spec and Founder approval
   before implementation, and which can proceed directly.

Situational docs (`BRAND_BIBLE.md`, `SPEC_TEMPLATE.md`, `ROADMAP.md`) are
read on demand for the task at hand, not on every session — same as for
Claude Code.

## Project overview

A social music discovery and rating platform: RateYourMusic's critical/
rating culture, Spotify's social-graph/feed model, and user posts/reviews
as a core mechanic. A recommendation layer built from in-app data (ratings,
reviews, follows, listens) is the long-term vision but is deliberately
deferred per HARMONIQ.md's "Humans Before Algorithms" principle — it is not
a peer feature to the human-originated mechanics above.

### Spotify API constraints (read before touching anything Spotify-related)

- The Recommendations endpoint and the audio-features/audio-analysis
  endpoints are gone from the Web API.
- New developer accounts are capped at 5 users in Development Mode.
- Spotify's developer policy **prohibits training ML models on Spotify
  content or metadata.** This is not just a privacy constraint — it's a
  hard ToS boundary. Spotify-derived data may be displayed; it may never
  be training input for the recommendation engine.
- Implication: Spotify account-linking is a nice-to-have (show what's
  currently playing, optional starter-library import), never the backbone
  of the recommendation engine or core data model.

## Plan mode vs. auto mode — the gate that matters most

Full breakdown: `WORKFLOW.md` §1. The short version, because getting this
wrong is the costliest mistake available in this repo:

**Tier 1 (spec + Founder approval required before writing code):**
net-new user-facing features; stack/auth/hosting changes; new paid
third-party services; non-additive schema changes (renames, drops, type
changes); anything touching real payments; anything irreversible (deleting
data, dropping tables, force-push, rewriting history); **any change to how
user data is collected, stored, or shared — including anything touching
the recommendation engine's data pipeline** (this last one exists because
of the Spotify ToS constraint above).

**Tier 2 (proceed directly):** implementing an already-approved plan,
tests, behavior-preserving refactors, bug fixes, UI work within the
existing design system, routine CRUD following an established pattern.

**When in doubt, treat it as Tier 1.** A spec is cheap; an unreviewed
irreversible decision is not.

All Tier 1 and Tier 2 work still passes through the Review Workflow in
`WORKFLOW.md` §2 (static analysis, optimization/design/security audits,
documentation, architecture review) before it's considered done.

## Branch flow

One direction only: feature branches → `dev` → `main` via a single PR.
Never merge `main → dev` and `dev → main` for the same changes — it
replays identical commits through both paths and produces confusing
"N ahead / N behind" states on byte-identical trees. Mechanics (naming,
PR conventions, CI triggers) are in `docs/GITHUB_WORKFLOW.md`.

## Conventions

### Stack

| Layer          | Choice                                                                    |
| -------------- | -------------------------------------------------------------------------- |
| Backend        | FastAPI, Python 3.12+                                                      |
| Database       | PostgreSQL (Neon serverless) + asyncpg + SQLAlchemy 2.0 async + Alembic    |
| Auth           | Clerk                                                                      |
| Frontend       | Next.js 16 (App Router, RSC, TypeScript)                                  |
| Styling        | Tailwind v4 — `@theme` block in `globals.css`, no `tailwind.config.js`     |
| File storage   | Cloudflare R2 (S3-compatible via boto3)                                   |
| Music database | MusicBrainz + Cover Art Archive — on-demand ingestion                     |
| Hosting        | Frontend: Vercel; Backend: Railway                                        |

### Backend — before pushing, run what CI runs

```
poetry run ruff check . && poetry run ruff format --check . \
  && poetry run mypy app && poetry run bandit -r app -c pyproject.toml \
  && poetry run pytest -q
```

`ruff` runs over all of `backend/`, not just `app tests`. Bandit needs
`-c pyproject.toml` — it does not auto-discover it.

Windows/Poetry gotchas that have already cost sessions (full detail in
`CLAUDE.md` and `docs/setup.md` §2/§10):

- Poetry is on PATH as its own executable — call it as plain `poetry`,
  never `py -m poetry` (resolves to a Python with no Poetry installed).
- Virtualenv is in-project at `backend/.venv`. Never activate a venv
  before `poetry run` — an active `VIRTUAL_ENV` overrides Poetry's own env
  and a declared dependency then looks missing.
- A stale `.venv` (from a moved/renamed project folder, or leftover from
  before a dependency change) has to be **deleted**, not just
  deactivated — `python.exe` keeps working off the baked-in interpreter
  path while `pip.exe` dies with `Fatal error in launcher`. Delete
  `backend/.venv` and re-run `poetry install`.

### Frontend — before pushing, run what CI runs

```
cd frontend && npm run verify
```

Runs typecheck, lint, format:check, tests, build — in that order, matching
`.github/workflows/frontend-ci.yml`. A hand-picked subset of these has
missed the format step before and turned CI red.

Line endings are normalized to LF repo-wide via `.gitattributes` — this is
enforced automatically on checkout/commit, not something to hand-manage.

## Keeping this file honest

`AGENTS.md` and `CLAUDE.md` cover the same ground for two different tools
and there is no mechanism that keeps them in sync automatically. If a
decision changes something stated in one, check whether the other needs
the same update — don't let them drift.

## Multi-agent coordination

Astra and Claude Code both operate in this repo. To avoid both mutating
the same branch at once: work in git worktrees (this project's existing
pattern) with an explicit branch/lane assigned per task, and don't push to
a branch another agent is actively working on without checking first.
Attribute commits with a `Co-Authored-By: Astra <noreply@openai.com>`
trailer, mirroring the existing Claude convention, so provenance stays
traceable per ENGINEERING_BIBLE.md §8.
