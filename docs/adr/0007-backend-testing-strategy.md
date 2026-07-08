# ADR 0007 — Backend Testing Strategy: Two-Tier with Testcontainers Postgres

**Date:** 2026-06-20
**Status:** Accepted
**Deciders:** Founder

---

## Context

As of the close of Feature 2 (User Accounts & Profiles), the backend on
`dev` contains substantial logic — on-demand MusicBrainz catalog ingestion,
the user service with data-access-layer visibility enforcement, Clerk
webhook sync, and two Alembic migrations — but the automated test suite
consists of a single endpoint test (`tests/test_health.py`) and an
in-process `httpx` client fixture. None of the data systems, persistence
behavior, or consent enforcement is covered.

This is a problem with constitutional weight, not merely a coverage gap.
HARMONIQ.md §6 (Consent Before Visibility) and ENGINEERING_BIBLE.md §8.1
require that visibility be enforced at the data-access layer. That
enforcement currently lives in `app/services/user.py::get_profile` and is
unverified — a regression there is a failure of a core principle, not a
cosmetic bug.

A decision is required on **what database tests run against**, because the
backend depends on PostgreSQL-specific behavior that a substitute engine
cannot faithfully reproduce:

- `User.id` uses `sqlalchemy.dialects.postgresql.UUID` (`PGUUID`).
- Timestamps use `server_default=func.now()` and timezone-aware `DateTime`.
- Uniqueness is enforced by DB constraints (`users.username`,
  `users.clerk_id`, `artists.mbid`, `albums.mbid`, `tracks.mbid`).
- Migrations run through an async Alembic env (`create_async_engine`).
- `get_db()` auto-commits on successful request completion.

SQLite — the usual fast in-memory choice — cannot represent `PGUUID`,
handles server-side defaults differently, and enforces constraints with
different semantics. A green SQLite suite would assert confidence about
precisely the guarantees most worth protecting, while testing a schema that
is not the real one.

## Decision

Adopt a **two-tier backend test strategy**:

1. **Unit tier** — fast, no database. Pure logic: schema validators,
   the visibility `can_see` decision logic, MusicBrainz response parsing.

2. **Integration tier** — runs against a **real PostgreSQL instance
   provisioned by Testcontainers**. A container starts once per test
   session; the project's Alembic migrations are applied to it; each test
   runs inside a transaction that is rolled back on completion for
   isolation. This tier covers persistence, real constraints, the
   auto-commit behavior of `get_db()`, and the data-access-layer visibility
   enforcement as it actually executes.

Docker is required both locally (Docker Desktop on the Windows dev machine)
and in CI (GitHub Actions service/daemon). Both were confirmed acceptable
by the Founder.

## Rationale

- **Faithfulness where it matters most.** The integration tier tests the
  real schema, real types, and real constraints. The consent enforcement
  that HARMONIQ.md §6 treats as non-negotiable is verified against the same
  engine production uses.
- **Migration correctness becomes testable.** Because the integration tier
  builds its schema by running Alembic migrations (not
  `Base.metadata.create_all`), a broken or non-additive migration fails CI.
  This directly supports WORKFLOW.md §1, which classifies non-additive
  schema changes as Tier 1.
- **Speed is preserved where faithfulness is not needed.** The unit tier
  keeps the fast feedback loop for pure logic; only tests that genuinely
  touch persistence pay the container cost.
- **Isolation without teardown cost.** Per-test transaction rollback avoids
  re-seeding or re-migrating between tests, keeping the integration tier
  fast after the one-time container start (~3–5s per session).

## Alternatives Considered

- **SQLite in-memory as primary store.** Fastest option. Rejected: cannot
  represent `PGUUID`, diverges on server-side defaults and constraint
  semantics, and does not exercise the migrations. Would require
  monkeypatching column types, at which point the schema under test is no
  longer the real schema.
- **Neon database branch per CI run.** Faithful (it _is_ Neon Postgres) and
  already supported by our tooling (see ADR 0003, which cites branching as
  a workflow benefit). Rejected as the _primary_ mechanism because it
  requires network access and Neon API credentials inside CI and local
  runs, ties the test loop to an external service's availability, and
  complicates parallelism. Retained as a documented fallback for
  environments where Docker is unavailable.
- **A shared dedicated test database.** Rejected: shared mutable state
  across runs breaks isolation and makes parallel/CI runs flaky.

## Consequences

- A new dev-dependency group is added: `testcontainers[postgresql]` (plus
  `psycopg`/driver as required by the container readiness check). These are
  dev-only and never ship to production.
- CI gains a Docker requirement. The GitHub Actions workflow must run on a
  runner with Docker available and may incur a few seconds of container
  startup per job.
- Local contributors must have Docker Desktop running to execute the
  integration tier. The unit tier remains runnable without Docker.
- Test selection is split by marker (e.g. `-m "not integration"` to run the
  fast tier alone). The default `pytest` run executes both.
- The Neon-branch approach remains documented as a fallback but is not the
  supported default path.

## Reevaluation condition

Revisit if container startup materially slows the development loop, if a CI
runner without Docker becomes necessary, or when a future phase introduces
database features (e.g. `pg_trgm` search, JSONB Melody metadata) that
warrant expanding the integration tier's scope.
