# User Accounts & Profiles

> Feature Spec — Phase 1 / NOW tier
> Status: Approved 2026-06-18 — Implementation complete 2026-06-18

---

# Purpose

Harmoniq's core identity proposition is that musical discovery happens through
people — but without user accounts and public profiles, there are no people.
This feature establishes the foundation: a user is someone with a username, a
display name, an optional bio, and control over what others can see about them.

Every subsequent social feature (follows, Melodies, ratings, the Discovery feed)
depends on the primitives introduced here. Without a stable user record tied to
Clerk authentication, none of those features can ship.

The principle it strengthens is **Identity Before Engagement**: profiles are
expressive, not metric-driven. Visibility controls exist from day one because
musical taste is personal, and HARMONIQ.md §6 (Consent Before Visibility)
requires that what others see must always be something the user intentionally
chose to share.

---

# Scope

### In Scope

- Clerk authentication integration: users authenticated by Clerk receive a
  Harmoniq user record on first sign-in.
- Onboarding flow: new users must choose a username and confirm a display name
  before accessing the app. The gate enforces this via JWT public metadata.
- User record: `username`, `display_name`, `avatar_url`, `bio`, three
  `visibility_*` fields, `created_at`, `updated_at`.
- Public profile page (`/u/<username>`): displays fields based on the viewer's
  visibility permissions.
- Settings page: edit display name, username, bio, avatar, and all three
  visibility scopes.
- Avatar upload: JPEG/PNG/WebP up to 5 MB, stored in Cloudflare R2, served
  from a public CDN URL.
- Visibility scopes: `private` (owner only), `friends` (mutual followers —
  stub returning false until follows ships), `public` (everyone).
  Applied per-field for bio, listening activity, and ratings count.
- Username availability check endpoint (debounced in the UI).
- Clerk webhook handler: syncs `display_name` and `avatar_url` from `user.updated`
  events.
- Reserved username list: `me`, `admin`, `api`, `settings`, `onboarding`,
  `check-username`, `staff`, `support`, `help`, `about`, `terms`, `privacy`.

### Out of Scope

- Account deletion — `user.deleted` webhook handling deferred. See Known
  Limitations.
- Follows / friends graph — the `_is_friend` stub always returns `False` until
  the follows table ships. FRIENDS-scoped fields behave as PRIVATE for
  non-owners in the interim.
- User search / discovery of other users.
- Email or notification preferences.
- Blocking or muting other users.
- OAuth social login beyond Clerk (Spotify, Google, etc.).

---

# Non-Goals

This feature is not intended to:

- Build the social graph (follows, trust scores, mutual connections).
- Implement any recommendation or discovery surface.
- Collect or store listening history (the `activity_placeholder` field is a
  sentinel; real data comes in a later feature).

---

# User Lifecycle

1. **New user signs in via Clerk** — Clerk issues a JWT. The Next.js middleware
   reads `sessionClaims.metadata.onboarded`. If absent or false, the user is
   redirected to `/onboarding`.
2. **Onboarding** — User chooses a username and confirms a display name (pre-
   populated from Clerk's `firstName + lastName`). On submit, the backend
   creates the user record and calls Clerk's Management API to set
   `publicMetadata.onboarded = true`. The frontend forces a Clerk session
   reload (`user.reload()`) to refresh the JWT, then redirects to the profile
   page.
3. **Returning user on a new device** — The JWT may not yet include
   `onboarded = true` (token hasn't refreshed). The onboarding page checks the
   backend `/api/v1/users/me` on mount; if the record already exists, it
   redirects to the profile instead of attempting a duplicate create.
4. **Profile updates** — Settings page calls `PATCH /api/v1/users/me`. Username
   changes are checked for availability server-side before accepting.
5. **Avatar changes** — `POST /api/v1/users/me/avatar`. Content validated server-
   side via magic bytes; file never touches the DB — only the R2 URL is stored.
6. **Clerk profile sync** — If the user changes their name or avatar in Clerk,
   the `user.updated` webhook fires and the backend syncs those fields. This is
   a one-way push from Clerk; Harmoniq is always the source of truth for
   `username`, `bio`, and visibility settings.

---

# User Experience

**Onboarding (`/onboarding`)**
Username field with real-time availability feedback (debounced 300ms). Display
name field pre-populated from Clerk. Clear error states: taken, invalid format,
server error. Back button returns to sign-in (hard replace, not push). On
success, redirect to `/u/<username>`.

**Profile page (`/u/<username>`)**
Avatar (initials fallback with deterministic colour if none set), display name,
@username. Bio shown if visible and set; "Add a bio" link if own profile and
bio not yet set. Activity section and ratings count shown only if visible
(fields absent from response when scoped out). "Edit profile" button for own
profile.

**Settings page (`/settings`)**
Avatar: click to upload, client-side type/size validation before sending.
Display name: text input, 50-char limit. Username: real-time availability check
(shows "unchanged" if current username re-typed). Bio: textarea, 280-char
counter, empty value cleared to null on save. Visibility controls: one select
per field (bio, listening activity, ratings count). Save button disabled while
not ready.

---

# Functional Requirements

**User creation**

- `POST /api/v1/users` creates a user record, enforcing username format
  (`[a-zA-Z0-9_-]{3,30}`) and reserved-name list server-side.
- On successful creation, the backend sets `publicMetadata.onboarded = true`
  in Clerk via the Management API. This is non-fatal: if it fails, the user
  record still exists; the flag will be set on the next Clerk token refresh or
  can be retried manually.
- A race condition on duplicate username (between check and write) is handled
  with an `IntegrityError` catch on commit, returning a 409.

**Username check**

- `GET /api/v1/users/check-username?q=<value>` returns `{"available": bool}`.
- Rate-limited to 20 requests/minute per IP to limit enumeration.
- Returns `available: false` for invalid format or reserved names without
  querying the DB.

**Profile retrieval**

- `GET /api/v1/users/me` — always returns full own profile including visibility
  settings (`OwnProfileResponse`).
- `GET /api/v1/users/<username>` — returns `ProfileResponse`. Fields gated by
  visibility are **absent** from the JSON (not null). Enforced at the service
  layer; route handler uses `JSONResponse(model.model_dump(exclude_unset=True))`.

**Profile update**

- `PATCH /api/v1/users/me` — rate-limited to 10/minute. Distinguishes `bio`
  explicitly set to `null` (clear it) from `bio` absent from payload (leave
  unchanged) via `model_fields_set`.

**Avatar upload**

- `POST /api/v1/users/me/avatar` — multipart/form-data. Rate-limited to 5/minute.
- Server-side magic byte validation: JPEG (`\xff\xd8\xff`), PNG
  (`\x89PNG\r\n\x1a\n`), WebP (`RIFF…WEBP`). Content-Type header not trusted.
- Maximum: 5 MB. Returns 413 if exceeded.
- Uploads via boto3 in `run_in_executor` (non-blocking).

**Webhook**

- `POST /api/v1/webhooks/clerk` — validates Svix HMAC-SHA256 signature with
  5-minute timestamp tolerance. Handles `user.updated` → sync `display_name`
  and `avatar_url`. Unknown event types are silently accepted (200) without
  processing.

---

# Acceptance Criteria

- [ ] New Clerk user is redirected to `/onboarding` on first sign-in.
- [ ] Onboarding form rejects reserved usernames and invalid formats inline.
- [ ] On submit, a user record is created in the DB and the user lands on
      their profile page.
- [ ] Returning user on a new device is not re-onboarded; they are redirected
      from `/onboarding` to their profile.
- [ ] `GET /api/v1/users/<username>` returns bio only when `visibility_bio` is
      `public` (or `friends` if viewer is a friend, or owner). Bio is absent
      (not null) when not visible.
- [ ] Changing `visibility_bio` to `private` on settings page causes bio to
      disappear from a different-user's profile view.
- [ ] Avatar upload with a valid JPEG/PNG/WebP under 5 MB succeeds and the
      new avatar appears on the profile.
- [ ] Avatar upload with an oversized file returns a clear error message.
- [ ] Avatar upload with a file whose extension was renamed but content is not
      an image returns a clear error message (magic-byte enforcement).
- [ ] Webhook with invalid signature returns 400.
- [ ] All backend static analysis passes (ruff, mypy).
- [ ] All frontend static analysis passes (tsc, eslint).
- [ ] Migration applies cleanly via `alembic upgrade head` on a fresh schema.

---

# Design Requirements

Onboarding and settings pages must follow the minimalist visual language
established in the catalog feature: `text-xs font-medium uppercase tracking-widest`
labels, `border border-neutral-200` inputs, `rounded bg-neutral-900` submit
buttons, neutral/muted feedback states. No modal dialogs, no toast notifications —
inline feedback states only.

Avatar placeholder: deterministic initials with `hsl(hash-derived-hue, 35%, 55%)`
background. Never a broken image icon. The placeholder must be visually
consistent across refreshes for the same username.

Visibility copy: "Only you" / "Friends — People you both follow" / "Everyone".
Not "Private" / "Friends" / "Public" — the plain English copies are more
informative to users who haven't read documentation.

---

# Technical Notes

**Onboarding gate (Option B — approved)**
JWT public metadata approach: backend calls `PATCH /v1/users/{clerk_id}` on
Clerk Management API to set `publicMetadata.onboarded = true` after creating
the Harmoniq record. Middleware reads `sessionClaims?.metadata?.onboarded`.
Requires the Clerk JWT template to include `"metadata": "{{ user.public_metadata }}"`.

**Cloudflare R2 (approved)**
S3-compatible; no egress fee on bandwidth from R2 to Cloudflare CDN. Used over
AWS S3 for cost predictability. Bucket must have public access enabled; store
the public CDN URL (`R2_PUBLIC_URL/avatars/{uuid}.{ext}`), not the internal
S3 URL.

**Visibility enforcement pattern**
`services/user.py → get_profile()` uses `model_construct()` to set only
visible fields on the `ProfileResponse` instance. Fields not set by
`model_construct` are treated as unset by Pydantic. The route handler serializes
with `model_dump(exclude_unset=True)` so absent fields never appear as null.

**Route ordering**
`/check-username` and `/me` must be registered before `/{username}` on the
FastAPI router. FastAPI resolves static path segments before dynamic ones, but
only when registered first.

**`updated_at` column**
No DB trigger. The service layer explicitly sets `user.updated_at = _now()` on
every mutation. This is deliberate — SQLAlchemy's `onupdate` is complex in
async context and the explicit call is more readable.

---

# Observability

- User creation logged at info level with internal UUID only (never `clerk_id`
  or username in info-level logs in production).
- Visibility scope changes logged at info level with internal UUID and
  before/after values.
- Username changes logged at info level with internal UUID.
- Avatar upload failures logged at error level with internal UUID and exception.
- Clerk Management API failures (onboarding flag) logged at error level; not
  re-raised.
- Webhook events logged at info level with `event_type` only.
- Webhook signature failures logged at warning level with reason.

---

# Rollback Plan

The `users` table is additive — no existing tables are modified. The migration
is reversible via `alembic downgrade`. Removing the `users` and `webhooks`
routers from `app/api/v1/router.py` and reverting the migration restores the
pre-Feature-2 state without affecting catalog functionality.

---

# Known Limitations

**Orphaned user records on account deletion**
`user.deleted` Clerk webhook events are not handled. If a user deletes their
Clerk account, the Harmoniq `users` row is not removed. The record will continue
to appear on profile pages and in any future user lists, but authentication will
fail for that `clerk_id` (Clerk rejects the JWT). This is acceptable for Phase 1
because account deletion is explicitly out of scope, but the behaviour must be
understood before any feature starts listing or searching users at scale.

_Decision required before account deletion ships:_ soft-delete (set a
`deleted_at` column and exclude from queries) vs hard-delete (cascade and purge
user-generated content). This decision should be made as a spec, not ad hoc,
because it affects ratings, reviews, and any future content the user created.
Until then, any operator-initiated cleanup must be done manually via DB.

**Friends check is a stub**
`_is_friend()` always returns `False`. FRIENDS-scoped fields behave as PRIVATE
for all non-owners until the follows table ships. No backfill or migration is
needed when follows lands — only the stub implementation changes.

**Ratings count always 0**
`ratings_count` in `ProfileResponse` is hard-coded to `0` pending the ratings
table. The field is included or excluded by visibility scope correctly; it just
always reads zero.

**Activity placeholder**
`activity_placeholder: true` is a sentinel. The profile page renders "Listening
history coming soon." Real listen data comes in a later feature.

**Onboarding flag sync is non-fatal**
If the Clerk Management API call fails after user record creation, the user
will be redirected to `/onboarding` on subsequent page loads until they sign
out and back in (at which point the JWT refreshes and the flag is re-read from
Clerk — which won't have it set). Workaround: add `CLERK_SECRET_KEY` and retry
by calling the endpoint again, or set the flag manually in the Clerk dashboard.

---

# Implementation Summary

_Completed 2026-06-18 — commit `6ebe954` on branch `dev`._

## Files changed

**New — Backend**

- `backend/app/core/enums.py` — VisibilityScope StrEnum
- `backend/app/models/user.py` — User ORM model
- `backend/app/schemas/user.py` — request/response schemas with validators
- `backend/app/services/user.py` — profile CRUD + visibility enforcement
- `backend/app/services/storage.py` — Cloudflare R2 avatar upload
- `backend/app/api/v1/deps.py` — shared FastAPI dependencies
- `backend/app/api/v1/users.py` — users router (6 endpoints)
- `backend/app/api/v1/webhooks.py` — Clerk webhook handler
- `backend/alembic/versions/e5f6a7b8c9d0_add_users_table.py` — migration

**New — Frontend**

- `frontend/src/lib/users.ts` — typed API client
- `frontend/src/components/AvatarImage.tsx` — initials placeholder
- `frontend/src/components/VisibilitySelect.tsx` — visibility dropdown
- `frontend/src/app/onboarding/page.tsx`
- `frontend/src/app/u/[username]/page.tsx`
- `frontend/src/app/settings/page.tsx`

**Modified**

- `backend/app/config.py` — R2 + Clerk SK/webhook fields (optional with None default)
- `backend/app/auth.py` — added `get_optional_clerk_id`
- `backend/app/models/__init__.py` — added User import
- `backend/app/api/v1/router.py` — registered users + webhooks routers
- `backend/pyproject.toml` + `backend/poetry.lock` — added boto3
- `frontend/src/types/index.ts` — user types
- `frontend/src/middleware.ts` — onboarding gate
- `frontend/src/app/layout.tsx` — `<a>` → `<Link>` (ESLint fix)
- `frontend/src/components/SearchBar.tsx` — derive idle panel from query length
  instead of setState in effect (ESLint fix)

## Decisions made

**R2 over AWS S3** — No egress fees from R2 to Cloudflare CDN. Cost structure
is more predictable for a bootstrapped product. Founder approved 2026-06-18.

**Option B for onboarding gate** — JWT public metadata (`publicMetadata.onboarded`)
read in Next.js middleware. Avoids a DB round-trip on every page load. Requires
Clerk JWT template customisation (documented in setup.md). Founder approved
2026-06-18.

**R2/Clerk credentials are Optional in config.py** — Alembic migrations should
run with only DATABASE_URL. R2 and Clerk SK validated at call site, not at
import time. Avoids blocking all dev work if credentials aren't yet provisioned.

**`StrEnum` over `(str, Enum)`** — ruff UP042; canonical form in Python 3.12.

**Derived display name on onboarding** — Avoids `setState` synchronously in an
effect (new rule in eslint-plugin-react-hooks v5+). Clerk name pre-fills the
field as a derived value without an effect loop.

**`originalUsername` as state in settings** — Accessing a ref during render is
flagged by the same lint ruleset. Converting to state is correct since the value
gates render output.

## Future improvements

- `user.deleted` webhook — requires a deletion policy decision (soft vs hard
  delete, content cascade). Spec required before implementation.
- Real friends check in `_is_friend()` — unblock when follows table ships.
- Real ratings count — query from ratings table when that feature lands.
- Real listening activity — replace placeholder when listen-log feature lands.
- Shared TypeScript type generation from Pydantic schemas — deferred to Phase NEXT.

---

# Amendments — 2026-07-04 (Founder-approved)

## A1. New profile setting: `visibility_follows`

A fourth visibility scope joins `visibility_bio` / `visibility_activity` /
`visibility_ratings`:

- `visibility_follows` — governs who may view the user's **follower and
  following lists** (`GET /api/v1/follows/{username}/followers` and
  `/following`). Scope values are the standard `public` / `friends` /
  `private`. The owner always sees their own lists. Denied viewers receive
  403 ("This list is private."), not an empty list.
- **Follower/following counts remain always-visible** on the profile
  (Instagram model — the numbers are identity-card facts; the names are
  the shareable content).
- `GET /api/v1/follows/{username}/state` (the viewer's own relationship to
  the profile) is unaffected — it reveals only the viewer's own edges.

## A2. Default is `public` — a documented constitutional exception

Unlike the other three scopes (default `private`), `visibility_follows`
defaults to **public**, for both new accounts and all existing rows
(migration backfill). This is a deliberate exception to the
"default private" convention and to ENGINEERING_BIBLE §8.1's
most-private-default rule, approved by the Founder 2026-07-04 under
HARMONIQ.md's constitutional-exception process, on the same reasoning as
the ratings public default: the follow graph is the connective tissue of a
social product, and a dark-by-default graph would make discovery through
people impossible at launch. The setting exists so consent is explicit,
specific, and revocable — any user can tighten it at any time and the
change takes effect immediately.

Prior to this amendment the lists were world-readable with **no** setting;
this amendment strictly increases user control.

## A3. `visibility_ratings` default flips to `public`

With the ratings master switch (see phase-1-ratings-reviews.md, Amendment
A1), a `private` profile-level default would hide every new user's public
reviews from everyone. `visibility_ratings` therefore now defaults to
`public` for new accounts, and existing rows are backfilled to `public`
(behavior-preserving: before the master switch, existing public reviews
were already visible; the old setting only hid the profile count).
`visibility_bio` and `visibility_activity` keep their `private` defaults.

---

# Amendments — 2026-07-05 (Founder-approved)

## A4. Profile editing moves inline; `/settings` repurposed

Editing your own profile (avatar, display name, username, bio, all four
visibility scopes, and the Spotify connected-accounts controls) no longer
lives on a dedicated `/settings` page. It now reveals inline on the profile
page itself (`/u/{username}`), behind an "Edit profile" toggle, with
Save/Cancel — `ProfileHeader` owns the open/closed state and
`ProfileEditPanel` holds the form (`frontend/src/components/`). The
"Add a bio" prompt shown when a bio is empty opens the same panel instead
of navigating away.

`/settings` is retained as a route, but repurposed: it is now reserved for
future **global application settings** (accessibility, notifications, and
similar account-wide preferences that aren't specific to the public
profile) — none of which are implemented yet. It currently renders a
placeholder.

**Username-change navigation:** because editing now happens on the route
that itself is keyed by username, a successful save that changed the
username navigates the browser to `/u/{newUsername}` (client-side,
`router.replace`) rather than merely refreshing in place; an unchanged
username triggers a plain `router.refresh()` so any other server-rendered
data on the page (e.g. the ratings list) stays in sync with the edit.

**Spotify OAuth callback target:** the callback page
(`frontend/src/app/spotify-callback/page.tsx`) now redirects to
`/u/{username}?spotify=connected` on success (previously
`/settings?spotify=connected`), fetching the username via `GET /users/me`
immediately after the token exchange. The profile page reads the
`spotify=connected` query param server-side and passes it down as a plain
`autoOpenEdit` boolean prop — the edit panel never reads `useSearchParams`
itself, avoiding any client-side Suspense-boundary concern.

No backend changes were required for this amendment — `GET /users/me` /
`PATCH /users/me` and `GET /users/{username}` are unchanged; the edit panel
simply calls the same endpoints the old settings page called.
