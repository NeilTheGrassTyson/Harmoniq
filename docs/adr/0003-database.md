# ADR 0003 — Database: PostgreSQL via Neon

**Date:** 2026-06-18
**Status:** Accepted
**Deciders:** Founder

---

## Context

Harmoniq's data model is deeply relational: users, social graph edges (follows,
trust relationships), Melody state machines, visibility scopes per row, and
eventually the Harmony computation over aggregated signals. Complex joins,
foreign key integrity, and transactional guarantees are required.

A managed service is preferred — database operations (backups, patching,
connection pooling) should not require solo-developer attention.

## Decision

**PostgreSQL 16** as the database engine, hosted on **Neon** (serverless
managed PostgreSQL). ORM: **SQLAlchemy 2.0 (async)** with **Alembic** for
migrations.

## Rationale

### PostgreSQL

No meaningful alternative for this data model. PostgreSQL offers:
- Full relational integrity with foreign keys and check constraints
- JSONB for semi-structured data (Melody metadata, visibility scope maps)
- Window functions for feed ranking and Harmony score computation
- Row-level security (available as a future hardening layer)
- `pg_trgm` and full-text search for catalog queries (Phase 1+)

MySQL/MariaDB were not evaluated. PlanetScale (MySQL-based) was rejected
because it does not enforce foreign keys — an unacceptable tradeoff for a
system where referential integrity is a security property.

### Neon

- **Serverless / scale-to-zero:** Development databases cost nothing when
  idle. Production scales on demand.
- **Database branching:** Each git feature branch can have a corresponding
  database branch — isolated schema state for testing migrations without
  affecting the main database. Directly supports WORKFLOW.md's review
  requirements.
- **Connection pooling:** PgBouncer-compatible built-in pooler handles
  FastAPI's async connection pattern without requiring a separate
  connection pooler service.
- **Pricing:** Free tier (10 GB) covers Phase 0 and Phase 1 comfortably.

### SQLAlchemy 2.0 + asyncpg

- SQLAlchemy is the de facto Python ORM. The 2.0 API is cleaner than 1.x
  and has first-class async support via `asyncpg`.
- Alembic (same author as SQLAlchemy) handles schema migrations as versioned
  Python scripts. Every schema change is a migration — no hand-edited SQL.

## Alternatives Considered

- **Supabase (PostgreSQL + extras):** Bundles auth, a REST API, and
  real-time subscriptions. Rejected because those extras conflict with
  our dedicated auth provider (Clerk) and the FastAPI backend. The
  bundled PostgREST API would create a second, uncontrolled API surface.
- **Railway PostgreSQL:** Simpler but lacks database branching. Rejected
  in favor of Neon's development workflow benefits.
- **MongoDB / document stores:** No foreign keys, no joins. Rejected.
  Harmoniq's social graph and visibility enforcement require relational
  integrity.

## Consequences

- PostgreSQL is the only supported database engine — no abstraction is
  built to support others.
- All schema changes must be expressed as Alembic migrations. Direct DDL
  is forbidden in production.
- Connection string format: `postgresql+asyncpg://user:pass@host/db`
- The `DATABASE_URL` environment variable must never appear in version
  control. See `.env.example` for the required variable name.
