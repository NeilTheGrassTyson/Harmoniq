# Deployment Guide

Harmoniq uses a split deployment:

- **Frontend** → Vercel (automatic from `main`)
- **Backend** → Railway (automatic from `main`, with migration release command)
- **Database** → Neon (managed PostgreSQL, always on)

---

## Frontend — Vercel

### Initial setup (once)

1. Push the repository to GitHub.
2. Go to [vercel.com](https://vercel.com) → New Project → Import from GitHub.
3. Set **Root Directory** to `frontend`.
4. Vercel auto-detects Next.js. Click Deploy.
5. In Project Settings → Environment Variables, add:
   - `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY`
   - `CLERK_SECRET_KEY`
   - `NEXT_PUBLIC_CLERK_SIGN_IN_URL` = `/sign-in`
   - `NEXT_PUBLIC_CLERK_SIGN_UP_URL` = `/sign-up`
   - `NEXT_PUBLIC_API_URL` = your Railway backend URL

   Do **not** set `NEXT_PUBLIC_CLERK_AFTER_SIGN_IN_URL` or
   `..._AFTER_SIGN_UP_URL`. `@clerk/nextjs` 7 ignores both — they were replaced
   by `..._FALLBACK_REDIRECT_URL` / `..._FORCE_REDIRECT_URL`, and the default
   (`/`) is what we want anyway. Delete them from the Vercel project if present.

   `NEXT_PUBLIC_*` values are **inlined at build time**. Changing one and
   redeploying the existing build output does nothing — trigger a new build.

### Ongoing deployment

Push to `main` → Vercel deploys automatically.  
Push to any other branch → Vercel creates a preview URL.

### Custom domain

Settings → Domains → Add your domain. Vercel handles HTTPS automatically.

**Then add the new origin to `CORS_ALLOWED_ORIGINS` on Railway and redeploy
the backend.** A custom domain is a new origin as far as the browser is
concerned, and the backend will reject every request from it until it is
listed. Nothing about the site looks broken from the server — pages render,
because server-side rendering bypasses CORS entirely — while every
interactive feature in the browser fails silently. Add the apex and `www`
separately (`https://example.com` and `https://www.example.com` are distinct
origins) unless one redirects to the other before any page loads.

---

## Backend — Railway

### Initial setup (once)

1. Go to [railway.app](https://railway.app) → New Project → Deploy from GitHub.
2. Select the Harmoniq repository.
3. Railway detects the `Procfile` in `backend/`. Set **Root Directory** to
   `backend`.
4. In the service's Variables tab, add:
   - `DATABASE_URL` (from Neon — use the pooled connection string)
   - `CLERK_JWKS_URL`
   - `CORS_ALLOWED_ORIGINS` = every origin the frontend is served from, no
     trailing slashes — currently
     `https://harmoniq.live,https://www.harmoniq.live`
   - `MUSICBRAINZ_USER_AGENT`
   - `APP_ENV` = `production` (must be exactly this — the value is validated,
     and it is what disables `/docs` and `/redoc`). An invalid value refuses to
     boot, but a **missing** one does not: it defaults to `development`, which
     serves `/docs` and `/redoc` publicly and echoes every SQL statement into
     the logs. Startup logs the resolved value (`APP_ENV: production`) and warns
     if it says `development` while the CORS allow-list has no localhost origin
     — grep Deploy Logs for `APP_ENV:` to confirm what the service actually
     resolved.
   - `CLERK_SECRET_KEY` — without it the `onboarded` flag never syncs back to
     Clerk and users are re-gated to `/onboarding`
   - `CLERK_WEBHOOK_SECRET` — without it every inbound Clerk webhook fails
   - `TOKEN_ENCRYPTION_KEY` — Fernet key; see the troubleshooting note below
   - `R2_ACCOUNT_ID`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`,
     `R2_BUCKET_NAME`, `R2_PUBLIC_URL` — without these avatar upload fails
   - `SPOTIFY_CLIENT_ID`, `SPOTIFY_CLIENT_SECRET`, `SPOTIFY_REDIRECT_URI` —
     without these account linking is unavailable

   Everything from `CLERK_SECRET_KEY` down fails *silently* at runtime rather
   than loudly at startup: the service boots fine and the feature is simply
   dead. There is no `DEBUG` variable — verbose logging is derived from
   `APP_ENV`.
5. Railway reads `railway.json` and runs `alembic upgrade head` as a release
   command before traffic shifts to each new revision.

### Ongoing deployment

Push to `main` → Railway deploys automatically.  
The release command runs migrations before the new revision goes live —
migrations always precede application code during a deploy.

### Clerk webhook (production)

`docs/setup.md` §5 covers the local ngrok version of this. The production
endpoint is the **Railway** origin, not `harmoniq.live` — the handler lives in
the backend, and pointing Clerk at the frontend domain is the easy mistake.

In **Clerk Dashboard → Webhooks → Add Endpoint**, with the **production**
instance selected (the one on `clerk.harmoniq.live`, not a
`*.clerk.accounts.dev` dev instance):

- **URL:** `https://harmoniq-production-ac1f.up.railway.app/api/v1/webhooks/clerk`
- **Events:** `user.updated` — and only that one. `app/api/v1/webhooks.py`
  handles exactly one event type; anything else is logged and answered
  `{"received": true}` without doing a thing. In particular `user.created`
  does **not** create a Harmoniq account: that happens through
  `POST /api/v1/users/` when the person finishes onboarding.
- Copy the endpoint's **Signing Secret** (`whsec_…`) into Railway as
  `CLERK_WEBHOOK_SECRET`.

The signing secret is **per endpoint**, not per instance, so an endpoint
recreated or moved between instances issues a new one and the old value stops
verifying.

Confirm the endpoint is live and checking signatures — an unsigned POST must
be rejected:

```bash
curl -s -X POST -H 'Content-Type: application/json' -d '{"type":"ping"}' "https://harmoniq-production-ac1f.up.railway.app/api/v1/webhooks/clerk"
```

`{"detail":"Invalid webhook payload."}` with a 400 is the correct answer; a
200 would mean signature verification is not running. Then send a test event
from the Clerk dashboard and look for `Clerk webhook received event_type=` in
Railway's Deploy Logs.

Failures here are already legible — `_verify_svix_signature` raises a
descriptive `ValueError` that is logged as
`Clerk webhook verification failed: <reason>`, naming a missing secret, a
bad base64 secret, a timestamp outside the 5-minute replay window, or no
matching signature. Check Deploy Logs before changing anything.

What breaks without it: nothing a user does directly. `user.updated` syncs a
display-name or avatar change made **in Clerk's own UI** back to the Harmoniq
record. Profile edits made inside Harmoniq go through the API and are
unaffected.

### Rolling back

In Railway dashboard → Deployments → select a previous deployment → Redeploy.  
If the rollback involves a schema downgrade, run `alembic downgrade <revision>`
manually from the Railway shell before redeploying.

---

## Database — Neon

### Connection strings

Neon provides two connection string types:

- **Direct** — for migration runs and admin operations
- **Pooled** (PgBouncer) — for the live application (`DATABASE_URL` in Railway)

Use the pooled string in `DATABASE_URL` for the running application.  
Use the direct string when running `alembic upgrade head` (pooler doesn't
support the `SET` commands Alembic uses for advisory locks).

### Branches

| Branch       | Role                                                 |
| ------------ | ---------------------------------------------------- |
| `production` | **The live database.** Railway points here. Default. |
| `staging`    | Root branch; a stale copy. Safe for local dev.       |
| `feature/*`  | Ephemeral per-feature branches                       |

Feature branches are deleted after the PR merges.

There is no `main` branch. This table said there was until 2026-08-30, and
said production lived on it — wrong on both the name and the role, which is
what made the incident below take an hour instead of five minutes.

**`production` is a child of `staging`, not the root.** That inversion is a
historical accident, not a design: the project's root branch is the one that
went stale while the child took the live traffic. It has one sharp
consequence — **"Reset from parent" is available on `production`, and running
it would replace every live user, rating, follow and Melody with the stale
root.** That is the ordinary way to refresh a staging branch, so the button is
one plausible mis-click from destroying production. Neon's **branch
protection** (paid plans) blocks reset and deletion; it is the guardrail, and
the naming is only a label on top of it.

**Railway binds to an endpoint ID, not a branch name.** Renaming a branch does
not move its compute, so `DATABASE_URL` keeps working across renames — and
conversely, a branch called `production` is not necessarily the one being
served. Compare the `ep-…` host in `DATABASE_URL` against the endpoint each
branch lists; that is the only authoritative mapping.

---

## Environment separation

| Environment | Frontend           | Backend                 | Database                 |
| ----------- | ------------------ | ----------------------- | ------------------------ |
| Development | `localhost:3000`   | `localhost:8000`        | Neon `staging` branch    |
| Staging     | Vercel preview URL | Railway staging service | Neon `staging` branch    |
| Production  | Vercel production  | Railway production      | Neon `production` branch |

Local `backend/.env` points at `staging`, which is correct — development must
not write to the live database. It also means a migration run locally has not
touched production. Railway's release command migrates production on deploy;
if you need to confirm, compare `alembic_version` on both branches rather than
assuming they agree.

---

## Secrets checklist

Before deploying to production, confirm:

- [ ] `DATABASE_URL` uses the Neon **production** branch connection string
- [ ] `CLERK_JWKS_URL` matches the production Clerk application
- [ ] `CORS_ALLOWED_ORIGINS` lists every origin the app is actually served
      from — the custom domain (apex **and** `www`) as well as the
      `.vercel.app` domain, comma-separated, no trailing slashes
- [ ] `APP_ENV=production` (disables `/docs` and `/redoc` endpoints) — confirm
      from Deploy Logs, not from the Variables tab: the line reads
      `APP_ENV: production (debug=False)`
- [ ] The four silently-optional groups are set if you want those features:
      `CLERK_SECRET_KEY`, `CLERK_WEBHOOK_SECRET`, `R2_*`, `SPOTIFY_*` +
      `TOKEN_ENCRYPTION_KEY`
- [ ] No `.env` files committed to git

---

## Troubleshooting (from the first live deploy, 2026-07-08)

Every issue below was an environment/config problem, not an application
bug — the app code was correct throughout. Recorded here since the
symptoms (500s, "Failed to fetch," 503s) look identical to real bugs from
the browser and are easy to misdiagnose without Railway's Deploy Logs.

- **Railway's `releaseCommand` in `railway.json` silently not running
  migrations under the Railpack builder.** Deploy Logs showed no alembic
  output between `Starting Container` and `Uvicorn running`. Workaround:
  run `alembic upgrade head` by hand from the Railway service shell after
  each deploy that includes a migration, until this is root-caused.
- **`DATABASE_URL` hostname typo/mismatch** → `socket.gaierror: [Errno -5]
  No address associated with hostname` on `alembic upgrade head`. Copy the
  host from Neon's connection string dialog exactly; don't hand-edit it.
- **Bare `postgresql://` scheme** → `ModuleNotFoundError: No module named
  'psycopg2'` at boot. This project only installs `asyncpg`. The scheme
  must be `postgresql+asyncpg://`, not `postgresql://`.
- **libpq-style query params (`sslmode=require&channel_binding=require`)
  on an asyncpg URL** → `TypeError: connect() got an unexpected keyword
  argument 'sslmode'`. asyncpg uses a different param name and doesn't
  support `channel_binding` at all. Use `?ssl=require` only.
- **Stale/crashed Railway deployments left running alongside the current
  one** produced inconsistent responses (same request, different results
  across retries) because traffic was hitting more than one replica.
  Check Railway's Deployments tab and remove any crashed ones; confirm
  you're down to exactly one active replica.
- **Trailing slash in `CORS_ALLOWED_ORIGINS`** silently breaks the origin
  match (`https://harmoniq.live/` ≠ `https://harmoniq.live`
  as far as `CORSMiddleware` is concerned) — the frontend UI feature-gates
  on it, so this shows up as buttons staying disabled/greyed out rather
  than a visible network error. Normalised away in `config.py` since
  2026-08-18, but the shape of the failure is the one to remember.
- **An origin missing from `CORS_ALLOWED_ORIGINS` entirely** (2026-08-22).
  Pages render, but every call the browser makes fails: search returns
  nothing, and onboarding shows "Couldn't check that username" followed by
  a bare "Load failed" on Continue. Server-rendered pages and the `proxy.ts`
  gate keep working because server-side requests are not subject to CORS,
  which makes it read as an application bug. Cause: the `harmoniq.live`
  custom domain was added to Vercel but never added to the Railway variable.
  Confirm from any terminal — the header is the whole answer:

  ```bash
  curl -i -H "Origin: https://harmoniq.live" \
    "https://harmoniq-production-ac1f.up.railway.app/api/v1/health"
  ```

  No `access-control-allow-origin` in the response → the origin is not
  allowed. The backend now logs a warning naming any rejected origin (see
  `app/core/cors.py`), so check Railway's Deploy Logs first; it prints the
  exact string to paste into the variable.
- **`NEXT_PUBLIC_API_URL` pointing at the Vercel dashboard** (2026-08-29).
  The value was `https://vercel.com/<team>/<project>/<deployment-id>` — the
  deployment-inspector URL, one copy away from the deploy screen — instead of
  the Railway origin. Every `/api/v1/*` path under it answers `404 text/html`,
  which the catalog and profile pages faithfully render as "Nothing here." and
  "Harmoniq is unreachable": production looked like a routing bug and stayed
  broken for days. Confirm from any terminal:

  ```bash
  curl -s -o /dev/null -w '%{http_code}
' "$NEXT_PUBLIC_API_URL/api/v1/health"
  ```

  Anything but `200` means the variable is wrong. The value must be a bare
  origin — no path, no trailing slash — and it is **inlined at build time**, so
  correcting it requires a fresh build, not a redeploy of the existing one.
  `lib/apiBase.ts` now refuses values of this shape and says so in the browser
  console on every deployed load (ADR 0011, ADR 0012).
- **Writing to the wrong Neon branch, believing it was production**
  (2026-08-30). After the two Clerk fixes below, `/api/v1/users/me` returned
  `404 User not found` for a signed-in user whose profile was publicly
  visible: the `users` row's `clerk_id` had been left behind by the move from
  the Clerk development instance to production. The `UPDATE` correcting it was
  run in the Neon SQL editor, which opens on the project's **default** branch
  — not the branch Railway serves. The write landed on a stale copy, the fix
  appeared to do nothing, and it was re-run and re-verified several times
  against the same wrong database.

  Branch **names cannot be trusted** for this, and neither can the default.
  What works is a marker: pick a fact only the live database can have — a
  follow, rating or account created through the app minutes ago — and query
  for it.

  ```sql
  SELECT COUNT(*) AS follower_rows FROM follows f JOIN users u ON u.id = f.followed_id WHERE u.username = '<a real user>';
  ```

  Compare that against what the live API reports for the same profile
  (`GET /api/v1/users/<username>` → `follower_count`, which the endpoint
  computes as a plain `COUNT(*)`, so the two are directly comparable).
  Disagreement means the editor is not on the served branch. The Neon
  console's **Compute** column corroborates it independently — the branch
  taking live traffic burns visibly more CU-hrs than an idle copy.

  Two API responses narrowed this down before any database access. On
  `/api/v1/users/me`, a `401` means the token was rejected while a `404` means
  it verified and no row matched — different problems. And
  `GET /api/v1/users/<own-username>` **with** a bearer token returns
  `is_own_profile: false` when the row exists but its `clerk_id` does not match
  the caller: a lookup by username and a lookup by `clerk_id` disagreeing
  *inside a single request* proves the row is present and the column is wrong,
  with no psql prompt needed.
- **`CLERK_JWKS_URL` pointing at the wrong Clerk *instance*** (2026-08-30).
  Distinct from the placeholder case below, and quieter: the fetch succeeds
  and the JWKS parses, it just holds a different instance's key. Public pages
  browse normally and **every authenticated request returns
  `401 {"detail":"JWT key not found"}`** — Settings won't load, Spotify won't
  connect, Melodies won't list. Clerk's `kid` *is* the instance id, so
  comparing the two is the whole diagnosis. From the browser console on the
  live site:

  ```bash
  curl -s https://clerk.harmoniq.live/.well-known/jwks.json | grep -o '"kid":"[^"]*"'
  ```

  Compare that against the `kid` in the header of a live session token, and
  against whatever `CLERK_JWKS_URL` is set to on Railway. The value must be
  `https://clerk.harmoniq.live/.well-known/jwks.json` — the production
  instance's own domain. A `*.clerk.accounts.dev` host there is a development
  instance and will never verify a production token. **Check
  `CLERK_SECRET_KEY` at the same time**: the two are set together and go wrong
  together, and a test-mode key silently skips writing
  `publicMetadata.onboarded` on every new account. The backend now logs both
  the resolved JWKS URL and the secret key's mode on boot, warns when either
  looks like a dev instance under `APP_ENV=production`, and names the
  offending `kid` alongside the ones it does know (`app/auth.py`,
  `app/main.py`). It also re-fetches the JWKS once on an unknown `kid`, so a
  genuine Clerk key rotation heals itself instead of waiting for a restart.
- **`CLERK_JWKS_URL` left as the literal placeholder value** (i.e. never
  swapped in your real Clerk instance subdomain) causes account creation
  to fail as an opaque `TypeError: Failed to fetch` in the browser, with
  no useful network-tab detail. Root cause only visible in Railway Deploy
  Logs as a `ConnectError`/`ConnectTimeout` trying to resolve the
  placeholder hostname. This happens because an unhandled exception during
  JWT verification propagates through `SecurityHeadersMiddleware`
  (`app/core/security.py`) and the resulting 500 response loses its CORS
  headers — the browser reports that as a failed fetch, not a 500, so the
  real error never reaches the console. Always double-check this value
  against your actual Clerk dashboard subdomain, not just that it's "set."
- **Malformed `TOKEN_ENCRYPTION_KEY`** (set, but not a valid Fernet key —
  32 url-safe base64 bytes) 500'd `GET /spotify/listening/{username}` for
  any user with a linked Spotify connection. Found by the 2026-07-09 live
  visibility audit. The code now degrades this to `connected: false`
  (`app/core/crypto.py` raises `TokenCryptoError` for malformed keys, not
  raw `ValueError`), but the env var still needs a real key: generate with
  `python -c "from cryptography.fernet import Fernet;
  print(Fernet.generate_key().decode())"`, set it on Railway, then
  reconnect Spotify on any affected account (tokens encrypted under the
  old value are orphaned by a key change).

---

## Seeding the catalog (before first invites)

Run `backend/scripts/seed_catalog.py` once against the production
database so new users don't land on an empty Search — see
`docs/setup.md` § "Seeding the catalog" for usage and flags.
