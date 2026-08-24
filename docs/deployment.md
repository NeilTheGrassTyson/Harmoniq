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
     and it is what disables `/docs` and `/redoc`)
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

| Branch      | Purpose                                         |
| ----------- | ----------------------------------------------- |
| `main`      | Production database                             |
| `staging`   | Staging environment (create manually if needed) |
| `feature/*` | Ephemeral per-feature branches                  |

Feature branches are deleted after the PR merges.

---

## Environment separation

| Environment | Frontend           | Backend                 | Database            |
| ----------- | ------------------ | ----------------------- | ------------------- |
| Development | `localhost:3000`   | `localhost:8000`        | Neon dev branch     |
| Staging     | Vercel preview URL | Railway staging service | Neon staging branch |
| Production  | Vercel production  | Railway production      | Neon main branch    |

---

## Secrets checklist

Before deploying to production, confirm:

- [ ] `DATABASE_URL` uses the Neon **production** branch connection string
- [ ] `CLERK_JWKS_URL` matches the production Clerk application
- [ ] `CORS_ALLOWED_ORIGINS` lists every origin the app is actually served
      from — the custom domain (apex **and** `www`) as well as the
      `.vercel.app` domain, comma-separated, no trailing slashes
- [ ] `APP_ENV=production` (disables `/docs` and `/redoc` endpoints)
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
