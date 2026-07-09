# Visibility Audit — Live Production Deploy

**Date:** 2026-07-09
**Auditor:** Engineering (Claude), Founder-directed
**Target:** `https://harmoniq-production-ac1f.up.railway.app` (API) +
`https://harmoniq-two.vercel.app` (frontend)
**Closes:** ROADMAP.md Public Alpha Criteria, final checkbox ("Visibility
defaults confirmed working end to end — not assumed, checked") and NOW-tier
Remaining item 4.

This is the live-deploy counterpart to the code-level pass in
`security-review-2026-07-07.md`. Every check below was executed against
production data over the network — no localhost, no assumptions.

## Method

Three viewer tiers, per the visibility model in `app/core/visibility.py`:

1. **Anonymous** — raw `curl` against the API with no credentials.
2. **Authenticated non-owner** — the live site driven in a browser signed
   in as `user3`, viewing `testlistener` and `benjordan6848` (accounts
   user3 does not own and does not mutually follow).
3. **Structural** — route-level verification that owner-only surfaces
   (Melody inbox/sent, notifications, `/users/me`, moderation) take no
   username parameter, making cross-user reads impossible by construction.

The friends-scope admittance branch (mutual follow unlocking
`friends`-scoped items) was **not** exercised live — it would have required
mutating live accounts' follow state and settings. It is covered by the
integration suite (`test_follows.py`, `test_users.py`, `test_ratings.py`,
`test_spotify.py`) against a real Postgres container.

## Results

### Tier 1 — anonymous

| Check | Expected | Observed | Verdict |
|---|---|---|---|
| `GET /users/me`, `/melodies/inbox`, `/melodies/sent`, `/notifications`, `/notifications/unread-count`, `/home`, `/moderation/reports`, `/spotify/connection` | reject | all `403` | ✅ |
| `GET /users/search?q=…` | identity card only (ADR 0008) | exactly `username`, `display_name`, `avatar_url` | ✅ |
| `GET /users/{username}` | identity card + counts; scoped fields absent (not null) | bio/activity fields absent from JSON for private-scoped users | ✅ |
| `GET /ratings/user/{username}` | only `public`-scoped ratings | founder's two public ratings returned; others empty | ✅ |
| `GET /follows/{u}/followers`, `/following` | gated by `visibility_follows` | founder (non-public setting): `403 "This list is private."`; testlistener (public default): list returned | ✅ |
| `GET /spotify/listening/{u}` | gated by `visibility_activity` | `403 "Listening activity is private."` for private-scoped users | ✅ |
| Nonexistent username | 404, no existence oracle beyond that | `404` | ✅ |

Note: `visibility_ratings` and `visibility_follows` default to **public**
by documented constitutional exception (specs, Amendments 2026-07-04) —
testlistener's visible following list is that default working as ratified,
not a leak. `visibility_bio` and `visibility_activity` default private and
were observed enforced.

### Tier 2 — authenticated non-owner (user3 viewing others)

| Check | Observed | Verdict |
|---|---|---|
| `testlistener` profile | identity card + counts only; no bio, no listening section, no private surfaces | ✅ |
| `benjordan6848` profile | public ratings render (intended); no bio | ✅ |
| `benjordan6848/followers` page | "This list is private." — deny-branch enforced for authenticated non-friends, not just anonymous | ✅ |
| Own profile (`user3`) | owner sees own edit affordances; owner-always-allowed rule intact | ✅ |

### Tier 3 — structural

`/melodies/inbox`, `/melodies/sent`, `/notifications*`, `/users/me`,
`/home` have no username parameter — they resolve the subject from the
verified JWT. There is no API shape through which one user can request
another's inbox, notifications, or home feed. Moderation endpoints
additionally 404 (not 403) for authenticated non-moderators per
`CurrentModerator` (verified in `test_moderation.py`; anonymously they
403 identically to every other protected route, so no existence signal).

## Finding (non-visibility, fixed)

**`GET /spotify/listening/benjordan6848` returned `500 Internal Server
Error`** for all viewer tiers, instead of listening data. Not a
visibility failure — the visibility gate had legitimately admitted the
viewer; the crash was downstream in token handling.

Root cause: `app/core/crypto.py::_fernet()` raised a raw `ValueError`
when `TOKEN_ENCRYPTION_KEY` is set but malformed (Fernet requires 32
url-safe base64 bytes). Callers only handle `TokenCryptoError`, so the
error propagated as a 500. A *missing* key already degraded gracefully;
a *malformed* one did not. The founder's Railway env evidently carries a
malformed value.

Fix shipped in this audit: `_fernet()` now converts the `ValueError` to
`TokenCryptoError`, so the listening endpoint degrades to
`{"connected": false}` like every other credential failure. Unit test
added (`test_crypto.py::test_malformed_key_raises_token_crypto_error`).
The frontend already degraded gracefully (hides the listening section on
fetch error) — the page never broke.

**Operator action still required:** set a valid `TOKEN_ENCRYPTION_KEY` on
Railway (`python -c "from cryptography.fernet import Fernet;
print(Fernet.generate_key().decode())"`), then reconnect Spotify on the
founder account (the stored token was encrypted under whatever key
produced it and will be orphaned by a new key — reconnecting re-encrypts).

## Verdict

Visibility enforcement is confirmed working end to end on the live
deploy at the data-access layer, across all three viewer tiers. The one
defect found was a robustness bug adjacent to (not within) the
visibility model, fixed and regression-tested. The final Public Alpha
Criteria checkbox is closed by this audit.
