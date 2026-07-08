# Security Review — Pre-Friends-Test Pass

**Date:** 2026-07-07
**Scope:** WORKFLOW.md §2.5 Security Audit, one-time pass ahead of inviting
CS-student friends to test. Code-level review with file:line citations, not
live penetration testing.

---

## 1. Auth — Clerk JWT verification / JWKS

**File:** `backend/app/auth.py`

- Verification is stateless against Clerk's JWKS endpoint, correct
  algorithm pinning (`RS256` only, no `alg: none` acceptance), `kid`-based
  key selection, expiry checked (`ExpiredSignatureError` → 401).
- **Finding (accept-as-is, documented):** `_fetch_jwks` (`auth.py:27-36`) is
  `@lru_cache(maxsize=1)` for the process lifetime — a comment already
  acknowledges Clerk key rotation would require a process restart to pick
  up new keys. At friend-test scale with Railway's auto-redeploy-on-push
  cadence, the process restarts often enough that this is low risk. **Not
  a blocker**, but worth a TTL cache (e.g. re-fetch every 24h) before any
  larger/longer-lived deployment — track as a backlog item, not urgent.
- `verify_aud` is explicitly disabled (`auth.py:54`) — standard for Clerk's
  session tokens, which don't set a fixed `aud`; not a gap.

## 2. Rate limiting

**Files:** `backend/app/core/rate_limit.py`, `backend/app/main.py:26`

- A global default of `100/minute` per remote address applies to every
  route automatically via `app.state.limiter` + slowapi's middleware —
  **no endpoint is actually unlimited**, contrary to an earlier
  impression. Endpoints without an explicit `@limiter.limit(...)`
  decorator (`ratings.py` PATCH/DELETE, `notifications.py` mark-read/
  read-all, `users.py` POST `/` account creation, `spotify.py` DELETE
  `/connection`) fall back to that 100/minute default rather than being
  open.
- Sensitive write paths already carry tighter explicit limits: rating
  submit `10/minute`, avatar upload `5/minute`, Melody send
  `10/minute;60/day`, follow/unfollow `30/minute`, moderation actions
  `30/minute`.
- **Recommendation (non-blocking):** account creation (`users.py:67`,
  `POST /`) has no explicit tighter limit. It's gated behind a valid Clerk
  JWT, which is the real cost barrier, so the global 100/minute is
  acceptable for now — flag for a tighter explicit limit only if invite
  scale grows past a trusted friend cohort.

## 3. CORS

**File:** `backend/app/config.py:28`

- `cors_allowed_origins` defaults to `http://localhost:3000` only — safe
  default, not a wildcard. Production value is env-driven
  (`CORS_ALLOWED_ORIGINS` on Railway per `docs/deployment.md`).
- **Action required before any real deploy (not yet verifiable from code
  alone):** confirm the actual Railway env var is set to the real Vercel
  origin(s) only, never `*`. This is a deploy-time config check, not a
  code fix — carried into the pre-invite checklist.

## 4. Secrets handling

- `.gitignore:7-12` correctly excludes `.env`/`.env.*` while carving out
  `!.env.example`/`!.env.*.example` — but **neither example file actually
  exists** in `backend/` or `frontend/`, despite `docs/setup.md` referring
  to `cp .env.example .env` and `.env.local.example` in its quick-start
  steps. This is a real onboarding gap for a friend helping debug, not a
  secrets leak (no secrets are exposed by the _absence_ of the file) —
  carried into the pre-invite checklist as a concrete fix.
- No committed secrets found in tracked source (config values are all
  `str | None` env-driven with no hardcoded defaults for keys/tokens).
- `TOKEN_ENCRYPTION_KEY` (Fernet) correctly encrypts Spotify refresh
  tokens at rest (`spotify.py`/models) — confirmed no plaintext token
  column.

## 5. Avatar upload

**Files:** `backend/app/services/storage.py`, `backend/app/api/v1/users.py:189-224`

- **Verified safe — not a gap.** The upload path never decodes image
  pixel data at all (no Pillow/`Image.open` call anywhere in the flow):
  it reads at most `MAX_AVATAR_BYTES + 1` bytes (`users.py:199`, hard
  413 above 5MB), validates via magic-byte sniffing
  (`storage.py:33-45`, independent of client-supplied `Content-Type`),
  and uploads the raw validated bytes directly to R2. With no decode
  step, there is no decompression-bomb surface to guard against.

## 6. Injection surfaces

- Grepped `backend/app/services/` for raw SQL interpolation
  (`f"SELECT..."`, `.format()` used in query text, `%`-formatting into
  SQL). The only `.format()` usages are non-SQL URL construction
  (`catalog.py:242,479`, Cover Art Archive URLs keyed on MusicBrainz IDs
  already validated as UUIDs by the catalog layer). The only `text()`
  calls are static `index_where` predicates on `ON CONFLICT` clauses
  (`notification.py:66,88`) — fixed strings, no user input interpolated.
  All data access goes through SQLAlchemy's parameterized ORM query
  builder. **No injection surface found.**

## 7. Data exposure

- `NotificationItem`/`NotificationMelodyRef` (`schemas/notification.py:12-23`)
  embed only actor summary (`UserSummary`) and track summary
  (`TrackSummary`) — confirmed no rating/review content, no visibility-
  scoped fields leak through a notification.
- `CurrentModerator` (`deps.py:59-67`) returns 404 for non-moderators —
  existence-hiding pattern applied consistently across all four
  moderation endpoints.
- Hidden-rating filtering (`_can_view` in `rating.py`, trending/friends
  SQL in `home.py`) was already verified during feature implementation
  and re-confirmed here by inspection — `hidden_at IS NULL` (or owner
  check) present in every read path.

## 8. Consent / visibility (HARMONIQ §6)

- `melody_accept_scope` is checked before every send (`services/melody.py`)
  with uniformly neutral rejection copy regardless of which specific rule
  blocked it (confirmed the error-status mapping in `melodies.py:26-34`
  doesn't leak which scope failed).
- Rejected-Melody state is never surfaced to anyone but the sender (state
  machine + no notification created on reject — confirmed in
  `notification.py`'s call sites: only `send_melody` and `follow` create
  notifications, `respond()` never does).
- No new visibility scope was skipped in this feature set — Melody and
  Notification are the only two new shareable-ish entities, and neither
  introduces a scope field beyond `melody_accept_scope`, which is
  correctly a consent gate (who may send), not a visibility scope (who
  may see), and is documented as such in `models/user.py:43-45`.

## 9. Logging / auditability (ENGINEERING_BIBLE §8)

- Follow mutations logged (`follow.py:54,74` — follower/followed IDs
  only).
- Moderation actions logged (`moderation.py:174-178, 212-217, 240-244` —
  dismiss/hide/suspend, all logging IDs only, never rating text or user
  PII beyond username).
- No log statement found anywhere in the reviewed services that includes
  `review_text`, email, or token values — logging is consistently
  ID-scoped.

---

## Summary

No blocking findings. Two concrete action items carried into the
pre-invite checklist (both non-code, both already tracked there):
create `.env.example` files, and verify the live `CORS_ALLOWED_ORIGINS`
value once a deploy target exists. One backlog item (JWKS TTL cache) noted
for later, not blocking a small closed friend cohort.
