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
   - `NEXT_PUBLIC_CLERK_AFTER_SIGN_IN_URL` = `/`
   - `NEXT_PUBLIC_CLERK_AFTER_SIGN_UP_URL` = `/`
   - `NEXT_PUBLIC_API_URL` = your Railway backend URL

### Ongoing deployment

Push to `main` → Vercel deploys automatically.  
Push to any other branch → Vercel creates a preview URL.

### Custom domain

Settings → Domains → Add your domain. Vercel handles HTTPS automatically.

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
   - `CORS_ALLOWED_ORIGINS` = your Vercel production URL (no trailing slash)
   - `MUSICBRAINZ_USER_AGENT`
   - `APP_ENV` = `production`
   - `DEBUG` = `false`
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
- [ ] `CORS_ALLOWED_ORIGINS` lists only the Vercel production domain
- [ ] `APP_ENV=production` (disables `/docs` and `/redoc` endpoints)
- [ ] `DEBUG=false`
- [ ] No `.env` files committed to git
