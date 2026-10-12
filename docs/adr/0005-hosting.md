# ADR 0005 — Hosting: Vercel (frontend) + Railway (backend)

**Date:** 2026-06-18
**Status:** Accepted
**Deciders:** Founder

---

## Context

Harmoniq has two deployable tiers: a Next.js frontend and a FastAPI backend.
These have different optimal runtime environments. The hosting strategy must
support a solo developer, minimize operational overhead, and provide
preview environments for feature review before merging.

## Decision

- **Frontend:** **Vercel** (Next.js)
- **Backend:** **Railway** (FastAPI)
- **Database:** **Neon** (see ADR 0003 — separate from compute hosting)

## Rationale

### Vercel (Frontend)

Vercel is the company that created and maintains Next.js. The integration is
zero-configuration:

- Push to `main` → automatic production deployment
- Push any branch → automatic preview URL
- Built-in image optimization, global CDN, and HTTPS
- Free Hobby tier is generous for development and early production

There is no meaningful alternative for Next.js hosting that provides the
same level of integration.

### Railway (Backend)

Railway is a PaaS optimized for Docker/Procfile-based services with a
simple GitHub integration:

- Push to `main` → automatic redeploy of the FastAPI service
- Environment variables managed per service in the Railway dashboard
- Supports release commands (e.g., `alembic upgrade head` before traffic
  shifts to new revision)
- Can host Redis, background workers, and additional services in the same
  project if needed in Phase NEXT
- Pricing: $5/mo Hobby plan covers early development

The separation of Railway (compute) from Neon (database) is intentional:
if the compute platform ever needs to change, the database migrates
independently.

### Why Not Render

Render is Railway's closest competitor. Rejected because:

- Free tier spins services down after 15 minutes of inactivity (30s cold
  start in development)
- Database hosting is more expensive than Neon
- Slightly less polished developer experience

### Why Not AWS/GCP/Azure

Excessive operational overhead for a solo developer project. Rejected.
HARMONIQ §4 (Simplicity Before Complexity) — if the benefit cannot be
explained in one sentence, the abstraction doesn't belong.

## Deployment Flow

```
Developer pushes to feature branch
  → Vercel: preview deployment with preview URL
  → (no Railway deploy on branches)

Developer merges to main via PR
  → Vercel: production deployment
  → Railway: release command (alembic upgrade head) → new revision deploys
```

## Consequences

- `Procfile` in `backend/` defines the start command:
  `web: uvicorn app.main:app --host 0.0.0.0 --port $PORT`
- Railway injects `PORT` automatically.
- `railway.json` in `backend/` configures the release command.
- CORS on the backend must explicitly allow the Vercel production domain
  and localhost for development.

---

## Addendum, 2026-10-02

The decision above stands; two of its consequences were not as written.

- **The "release command" was never configured.** `railway.json` declared
  `releaseCommand`, which is not a Railway config key; Railway's key is
  `preDeployCommand`, and an unrecognised key is silently ignored. No deploy ever
  ran a migration from it. Corrected on `dev` (`059331e`); production gets the
  fix with the next `dev → main` release. Details and the traps (a Redeploy
  does not run it) are in `docs/deployment.md`, "Migrations on deploy".
- **There is now a third environment.** `dev.harmoniq.live` — a Vercel branch
  domain, a Railway `dev` environment and a Neon `dev` branch — exists to test
  changes signed in before release. It does not alter the Vercel + Railway
  choice; see `docs/deployment.md`, "Dev environment".
