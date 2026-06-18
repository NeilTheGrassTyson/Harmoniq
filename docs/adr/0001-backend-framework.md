# ADR 0001 — Backend Framework: FastAPI

**Date:** 2026-06-18
**Status:** Accepted
**Deciders:** Founder

---

## Context

Harmoniq requires a backend capable of serving a social graph, enforcing
per-row visibility rules, processing Melody state transitions, and
eventually supporting limited real-time presence (currently-listening
indicators). The backend must be maintainable by a solo developer using
AI tooling, with a minimal and auditable dependency surface.

An earlier prototype used Flask. It was discarded — Flask's synchronous
model and the prototype's Spotify-only design did not match the product
direction established in HARMONIQ.md.

## Decision

Use **FastAPI (Python 3.12+)** as the backend web framework.

## Rationale

- **Async-first:** FastAPI is built on Starlette and supports async request
  handlers natively. The social graph queries (trust scores, feed
  composition) benefit from concurrent I/O without thread overhead.
- **Type safety via Pydantic:** Request validation and response serialization
  are defined as typed Python classes. This eliminates a category of runtime
  errors at the API boundary and makes AI-assisted development more reliable.
- **OpenAPI generation:** Automatic `/docs` and `/redoc` endpoints are
  generated from route definitions — no separate API documentation step.
- **Explicit over magic:** FastAPI's dependency injection pattern makes
  auth, DB session access, and rate limiting explicit per-route rather than
  hidden in global middleware (as with Flask/Django).
- **Supply-chain risk reduction (Engineering Bible §8):** Moving the backend
  to Python avoids the npm ecosystem's historically higher vulnerability rate.
  Python dependencies are pinned via Poetry's lock file.
- **AI tooling support:** FastAPI has extensive training data in all major
  LLMs. Code generation is reliable; errors are well-understood.

## Alternatives Considered

- **Flask** — synchronous, no Pydantic, lower performance for I/O-bound
  workloads. Rejected. The earlier prototype used it; it was inadequate.
- **Django + DRF** — higher magic, heavier framework, ORM conflicts with
  SQLAlchemy. Rejected. Complexity conflicts with HARMONIQ §4 (Simplicity).
- **Node.js (Express/NestJS)** — rejected explicitly in Engineering Bible §8
  due to npm supply-chain risk on the most security-critical tier.

## Consequences

- All backend code is Python 3.12+.
- SQLAlchemy 2.0 (async) is the ORM; Alembic handles migrations.
- Dependencies are managed via Poetry and pinned in `poetry.lock`.
