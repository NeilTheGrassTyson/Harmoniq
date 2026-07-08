# Spotify Account Linking & Listening Display

> Feature Spec — Phase 1 / NOW tier (pulled forward from NEXT by Founder
> decision, 2026-07-04 — see ROADMAP.md)
> Status: Approved 2026-07-04 (approved via plan-mode session; this spec
> records the approved plan)

---

# Purpose

The profile's "Listening activity" section has been a placeholder since
User Accounts shipped. Musical identity — the product's primary data type —
is thin when a profile shows only ratings. Linking a Spotify account lets a
user's profile reflect what they actually listen to: a "now playing" row
and a recently-played list.

Core principle strengthened: **Musical Identity** (BRAND_BIBLE §3.1). What
a user listens to, surfaced on their own profile under their own
visibility control, is identity expression — not content, not a feed.

This is a *supplementary display integration*, per ENGINEERING_BIBLE §11
and the Spotify API constraints in CLAUDE.md. Spotify is not the data
backbone and never feeds the future recommendation layer.

---

# Scope

### In Scope

* OAuth account linking (Authorization Code flow) from the settings page:
  Connect, connection status, Disconnect.
* Encrypted-at-rest storage of the Spotify refresh token (Fernet; key from
  env). The only Spotify data persisted is the connection record itself
  (spotify user id, encrypted refresh token, granted scopes, connected_at).
* Display-only listening data on the profile page: current track (when
  playing) + up to 20 recently-played tracks, fetched live from Spotify
  with a short (60s) in-process cache of the raw payload.
* Visibility enforcement at the service layer using the **existing**
  `visibility_activity` profile setting (default private): owner always
  sees their own listening; others per scope.
* Spotify Development Mode app (5-user allowlist) — sufficient for the
  Founder's personal account at this stage.

### Out of Scope

* Persisting listens (no `listens` table; no scrobbling). Listening-history
  persistence is the recommendation pipeline's front door and requires its
  own Tier 1 spec (WORKFLOW.md §1, CLAUDE.md data-pipeline rule).
* Any use of Spotify data beyond display: no recommendation input, no
  similarity modeling, no training data (Spotify ToS; ENGINEERING_BIBLE
  §13).
* Starter-library import, playlists, playback control.
* Multiple provider abstraction (provider interface arrives with a second
  provider, not before — Simplicity Before Complexity).
* Extended-quota access / production Spotify app.

---

# Non-Goals

* This does not make Spotify the canonical music source — MusicBrainz
  remains canonical (ADR 0006). Listening rows are rendered from Spotify
  metadata directly and are not matched into the local catalog in this
  phase.
* This does not implement real-time push; "now playing" is fetch-on-view
  with a short cache (ENGINEERING_BIBLE §9's calm-behavior constraint).

---

# User Experience

**Connecting (settings page):**
1. Settings shows a "Connected accounts" section. Not connected → a
   "Connect Spotify" button.
2. Click → redirect to Spotify's consent screen → approve → return to
   Harmoniq (`/spotify-callback`) → automatic redirect back to settings,
   which now shows "Connected as {spotify username} · since {date}" and a
   Disconnect button.
3. A quiet caption notes that listening activity appears on the profile
   according to the existing "Listening activity" visibility setting.

**Viewing (profile page):**
* The Listening section (visible per `visibility_activity`) shows a "Now
  playing" row when a track is playing, and a recently-played list (album
  art, title, artist, relative time).
* Owner not connected → quiet empty state: "No listening activity yet."
* Denied by visibility → the section is absent entirely (existing
  key-omission pattern).

**Error states:** Spotify unreachable → section renders nothing (section
independence, same philosophy as Home). Revoked/expired grant → treated as
not connected; settings shows Connect again.

**Edge cases:** user denies consent on Spotify's screen → returned to
settings with no change; connecting a second time replaces the existing
connection (upsert).

---

# Functional Requirements

* User can initiate Spotify OAuth from settings; the authorize URL is
  built server-side (client id/secret never reach the frontend).
* The OAuth `state` parameter must be HMAC-signed, time-limited (10 min),
  and bound to the initiating Harmoniq user; the callback must reject a
  state whose signature, expiry, or user binding fails.
* System must store the refresh token encrypted (Fernet). The plaintext
  token must never be logged or returned by any API.
* Access tokens live only in process memory, refreshed ~60s before expiry;
  a rotated refresh token returned by Spotify must be persisted.
* A refresh failure with `invalid_grant` (revoked) must delete the
  connection and surface "not connected."
* Listening data must be fetched live (60s payload cache) and never
  written to the database.
* Visibility must be enforced in the service layer on every request; the
  cache stores the raw Spotify payload per user, and the visibility
  decision is applied after cache retrieval, never cached itself.
* Feature should never send Spotify data to any other subsystem.
* Disconnect must delete the connection row and drop in-memory tokens and
  cached payloads immediately (revocable consent, ENGINEERING_BIBLE §8.1).

---

# Acceptance Criteria

* [ ] Founder can connect their personal Spotify account from settings and
      see "Connected as …".
* [ ] With a track playing on Spotify, the Founder's profile shows Now
      playing + recently played within ~60s.
* [ ] With `visibility_activity=private`, a signed-out viewer sees no
      Listening section; the owner still sees it. Setting it to `public`
      makes it visible; the change takes effect immediately.
* [ ] `spotify_connections.refresh_token_encrypted` contains Fernet
      ciphertext, not a plaintext token.
* [ ] Callback with a tampered/expired/foreign `state` returns 400 and
      creates no connection.
* [ ] Disconnect removes the row; the profile shows the quiet empty state.
* [ ] No new table stores track/listen data; grep confirms Spotify data
      flows only to the listening response schema.
* [ ] Static analysis passes: ruff, mypy (backend); tsc, eslint (frontend).

---

# Design Requirements

* Calm and minimal per BRAND_BIBLE §7/§8: the Listening section uses the
  existing SectionLabel style; "Now playing" is a quiet row, not a badge or
  animation. No prompts to connect on other users' profiles.
* Copy follows §10: "No listening activity yet.", "Connected as …",
  "Listening activity is shown on your profile according to your Listening
  activity visibility setting." No hype, no exclamation marks.
* Spotify branding kept minimal (name only) — this is Harmoniq's surface.

---

# Technical Notes

* **New backend modules:** `app/core/crypto.py` (Fernet helpers),
  `app/models/spotify.py` (`SpotifyConnection`), `app/schemas/spotify.py`,
  `app/services/spotify.py`, `app/api/v1/spotify.py`.
* **Endpoints:** `GET /api/v1/spotify/connect-url` (auth),
  `POST /api/v1/spotify/callback` (auth, 10/min),
  `GET|DELETE /api/v1/spotify/connection` (auth),
  `GET /api/v1/spotify/listening/{username}` (optional auth).
* **Schema:** `spotify_connections(id, user_id unique FK CASCADE,
  spotify_user_id, refresh_token_encrypted, scopes, connected_at)` —
  additive migration.
* **Config:** `SPOTIFY_CLIENT_ID`, `SPOTIFY_CLIENT_SECRET`,
  `SPOTIFY_REDIRECT_URI`, `TOKEN_ENCRYPTION_KEY` — all optional-at-import,
  validated at call site (house pattern). `TOKEN_ENCRYPTION_KEY` doubles as
  the OAuth-state HMAC key (documented dual use).
* **New dependency:** `cryptography` (direct); `respx` (dev, httpx
  mocking).
* **Spotify endpoints used:** `/authorize`, `/api/token`, `/v1/me`,
  `/v1/me/player/currently-playing`, `/v1/me/player/recently-played`.
  Scopes: `user-read-recently-played user-read-currently-playing`.
* **Redirect URI:** loopback IP literal `http://127.0.0.1:3000/spotify-callback`
  (Spotify's 2025 policy rejects `localhost` for new apps). Clerk dev
  sessions are pinned to the `localhost` origin, so the callback page is
  public in the route proxy and forwards itself from 127.0.0.1 to
  localhost (query string intact) before performing the authed exchange —
  users browse on localhost throughout. Security is unaffected: the
  exchange endpoint requires auth plus the user-bound signed state.
* **Known limitation (accepted):** the 60s payload cache and access-token
  cache are in-process — correct for single-worker local dev; a shared
  cache is required before multi-worker deployment. Losing/rotating
  `TOKEN_ENCRYPTION_KEY` orphans stored refresh tokens (users reconnect).

---

# Rollback Plan

* Feature is disabled by removing the spotify router from
  `app/api/v1/router.py` (frontend degrades to the quiet empty state) or
  simply by unsetting the Spotify env vars (endpoints return 503).
* The `spotify_connections` table is additive; the migration is reversible
  via `alembic downgrade`. Dropping it destroys only connection records —
  users reconnect; no user content is lost.

---

# Open Questions

- None blocking. Deferred deliberately: listen persistence (own spec),
  matching Spotify tracks to MusicBrainz catalog entries, extended-quota
  application timing.

---

*Approved 2026-07-04. Implementation proceeds under the standard Review
Workflow in WORKFLOW.md.*

---

# Amendments — 2026-07-05 (Founder-approved)

## B1. Client-side polling while the page is open

Supersedes the Non-Goals line "This does not implement real-time push;
'now playing' is fetch-on-view with a short cache." The backend model is
unchanged — still fetch-on-view, still the 60-second per-user cache
(`app/services/spotify.py::_LISTENING_CACHE_TTL`), still not server push.
What changes is the client: `frontend/src/hooks/usePolledListening.ts`
polls `GET /spotify/listening/{username}` on a ~25-second interval for as
long as the profile page is open, so the Listening section updates without
a manual reload.

Polling pauses via the Page Visibility API when the browser tab isn't
visible, and does one immediate refetch on becoming visible again — no
requests are made for a page nobody is looking at. A failed poll silently
retains the last known-good data rather than clearing the section or
surfacing an error (the same section-independence philosophy already used
elsewhere, e.g. Home's `_safe_section`).

This is a direct application of ENGINEERING_BIBLE §9, which already
enumerates "currently listening" indicators as one of the only two
permitted real-time/ephemeral-presence features — this amendment doesn't
carve out a new exception, it exercises the one already granted.

No backend change was needed: the existing 60-second cache already absorbs
repeated client polling regardless of how many viewers a profile has.

## B2. Now-playing gets a quiet visual distinction

Supersedes the Design Requirements line "'Now playing' is a quiet row, not
a badge or animation." The now-playing row now carries a subtle,
accent-tinted background and left border, plus the app's existing
three-bar `EqualizerGlyph` brand mark animated with a slow, staggered
pulse (`.eq-bar` / `.listening-now-row` in `globals.css`) — deliberately
not a new icon, not a loud or flashing badge, and disabled entirely under
`prefers-reduced-motion`. The intent is still "quiet" per BRAND_BIBLE's
emotional tone system; this amendment just gives "now playing" one
tasteful, on-brand cue rather than none.

## B3. Known limitations — unaffected

The "in-process, single-worker" caching limitation noted above is
unchanged by this amendment; polling is purely a client-side behavior
change and does not alter the backend's caching or deployment model.
