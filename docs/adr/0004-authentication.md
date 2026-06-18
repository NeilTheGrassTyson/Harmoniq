# ADR 0004 — Authentication: Clerk

**Date:** 2026-06-18
**Status:** Accepted
**Deciders:** Founder

---

## Context

Authentication is the hardest infrastructure decision to walk back — migrating
auth means migrating every user account and every session. The provider must
support: email/password, OAuth social login, JWT-based session verification in
FastAPI, email verification, brute-force protection, and a UI that can match
Harmoniq's brand.

HARMONIQ §5 (Security Is Foundational) requires that auth be treated as a
design constraint, not a review step. Building custom JWT auth from scratch
in a solo project introduces surface area for subtle vulnerabilities.

## Decision

Use **Clerk** as the authentication and user management provider.

## Rationale

- **Security completeness out of the box:** Clerk handles email verification,
  password hashing (bcrypt), brute-force rate limiting, bot detection, and
  session management. A solo developer implementing these from scratch is
  more likely to introduce a vulnerability than a security-focused product.
- **FastAPI integration:** Clerk issues short-lived JWTs (session tokens)
  that are verified in FastAPI using Clerk's public JWKS endpoint. The
  Python `jwt` library decodes and validates the token; no Clerk SDK is
  required on the backend, just JWKS verification.
- **Embeddable UI components:** Clerk's `<SignIn />`, `<SignUp />`, and
  `<UserProfile />` components can be styled to approximate Harmoniq's brand.
  This eliminates weeks of auth UI implementation time.
- **Social OAuth:** Google, Apple, and GitHub OAuth are configuration options,
  not code changes.
- **Developer experience:** Clerk is well-documented, has extensive examples
  for Next.js + FastAPI, and generates reliable AI-assisted code.
- **Pricing:** Free tier includes 10,000 MAU — more than sufficient through
  early development and initial public alpha.

## Authentication Contract

- The **user identifier** throughout Harmoniq is the Clerk `sub` claim from
  the JWT. On first authenticated request, the backend creates a row in the
  `users` table with `clerk_user_id = sub`.
- The backend **never stores passwords** — Clerk owns credential management.
- **Visibility and consent rules** (HARMONIQ §6) are implemented in
  Harmoniq's own data layer, not in Clerk. Clerk only answers "who is
  this person?" — it has no knowledge of Harmoniq's permission model.

## Alternatives Considered

- **Custom JWT (PyJWT + bcrypt):** Full control, no cost. Rejected because
  it requires implementing email verification, token refresh, brute-force
  protection, and social OAuth from scratch — each a potential vulnerability.
  Violates HARMONIQ §5.
- **Auth0:** Mature but more complex dashboard UX, higher pricing at scale,
  and notably worse developer experience than Clerk. No clear advantage.
- **Supabase Auth:** Requires using Supabase as the database too; creates
  two competing identity systems if combined with a separate Postgres.
  Rejected.

## Consequences

- `CLERK_SECRET_KEY` is a Railway environment variable (never committed).
- `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` is a Vercel environment variable.
- The backend `auth.py` module verifies JWTs against Clerk's JWKS endpoint
  (`https://api.clerk.com/v1/jwks`). The JWKS URL changes per Clerk app
  instance and is set via `CLERK_JWKS_URL` env var.
- Clerk's user ID format is `user_<alphanumeric>` — store as `VARCHAR(64)`.
