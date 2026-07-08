# Local Development Setup

This guide gets a new contributor from zero to running both the backend and
frontend locally. No Docker required.

---

## Prerequisites

| Tool | Version | Install |
|---|---|---|
| Python | 3.12+ | [python.org](https://python.org) |
| Poetry | 2.x | `pip install poetry` |
| Node.js | 20+ | [nodejs.org](https://nodejs.org) |
| npm | 10+ | included with Node.js |
| Git | any | [git-scm.com](https://git-scm.com) |

You also need accounts on:
- **Neon** (neon.tech) — create a project, copy the connection string
- **Clerk** (clerk.com) — create an application, copy the API keys

The following are optional for local development (features degrade gracefully
without them):
- **Cloudflare** — R2 bucket for avatar uploads (avatar upload returns 503
  without it; all other features work)
- **Clerk webhook** — for syncing Clerk profile changes to Harmoniq (only
  needed if you want `user.updated` events to propagate)

---

## Quick start (Windows)

Once prerequisites are installed and environment variables are configured (see
section 4), these two scripts manage the full dev environment from the project
root:

```powershell
# Start backend + frontend (each opens in its own terminal window)
.\scripts\start-dev.ps1

# Stop everything and close those windows
.\scripts\stop-dev.ps1
```

`start-dev.ps1` locates the venv uvicorn, starts the backend and frontend in
separate PowerShell windows, and prints the local URLs. `stop-dev.ps1` kills
both process trees (including child uvicorn/node processes) and closes those
windows.

The numbered steps below cover first-time setup and the manual equivalent of
what the scripts automate.

---

## 1. Clone and configure

```bash
git clone https://github.com/NeilTheGrassTyson/Harmoniq.git
cd Harmoniq
```

---

## 2. Backend setup

```bash
cd backend

# Create and activate virtual environment
python -m venv .venv
# macOS/Linux:
source .venv/bin/activate
# Windows:
.venv\Scripts\activate

# Install dependencies (includes boto3 for R2 uploads)
pip install poetry
poetry install

# Configure environment — see "Environment variables" section below
cp .env.example .env   # if .env.example exists; otherwise edit .env directly

# Run database migrations
alembic upgrade head

# Start the development server
uvicorn app.main:app --reload --port 8000
```

The API is now running at `http://localhost:8000`.  
Interactive docs: `http://localhost:8000/docs`

---

## 3. Frontend setup

Open a new terminal:

```bash
cd frontend

# Install dependencies
npm install

# Configure environment
cp .env.local.example .env.local   # if .env.local.example exists
# Edit .env.local — fill in Clerk keys and NEXT_PUBLIC_API_URL

# Start the development server
npm run dev
```

The frontend is now running at `http://localhost:3000`.

---

## 4. Environment variables

### Backend (`backend/.env`)

Minimum required to run the server and migrations:

```env
DATABASE_URL=postgresql+asyncpg://user:pass@host/db?ssl=require
CLERK_JWKS_URL=https://<your-clerk-instance>.clerk.accounts.dev/.well-known/jwks.json
MUSICBRAINZ_USER_AGENT=Harmoniq/0.1.0 (your@email.com)
```

Additional variables for user accounts and avatars:

```env
# Clerk Management API — Dashboard → API Keys → Secret keys
# Required for the onboarding gate to sync to Clerk JWT after first sign-up.
# Without this, users are redirected to /onboarding on every page load until
# they sign out and back in (JWT refreshes on next sign-in).
CLERK_SECRET_KEY=sk_live_...

# Clerk webhook secret — see "Clerk webhook setup" section below
CLERK_WEBHOOK_SECRET=whsec_...

# Cloudflare R2 — see "R2 setup" section below
R2_ACCOUNT_ID=
R2_ACCESS_KEY_ID=
R2_SECRET_ACCESS_KEY=
R2_BUCKET_NAME=harmoniq-avatars
R2_PUBLIC_URL=https://pub-xxxx.r2.dev
```

Additional variables for Spotify account linking (see "Spotify setup" below):

```env
# Spotify Developer Dashboard → your app → Settings
SPOTIFY_CLIENT_ID=
SPOTIFY_CLIENT_SECRET=
# Must EXACTLY match the redirect URI registered in the dashboard.
# New Spotify apps require a loopback IP literal (127.0.0.1, not localhost).
SPOTIFY_REDIRECT_URI=http://127.0.0.1:3000/spotify-callback

# Fernet key encrypting stored Spotify refresh tokens (also signs OAuth state).
# Generate once:  python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
# Rotating or losing it orphans stored tokens — users just reconnect.
TOKEN_ENCRYPTION_KEY=
```

### Frontend (`frontend/.env.local`)

```env
NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=pk_test_...
CLERK_SECRET_KEY=sk_test_...
NEXT_PUBLIC_API_URL=http://localhost:8000
```

---

## 5. Clerk configuration

### JWT template (required for onboarding gate)

The onboarding gate reads `publicMetadata.onboarded` from the Clerk JWT. For
this to work, you must add a custom claim to the session token:

1. Go to **Clerk Dashboard → Configure → Sessions → Customize session token**
2. Add the following JSON under "Claims" — the shorthand must be written
   **without spaces inside the braces**, exactly as shown:
   ```json
   {
     "metadata": "{{user.public_metadata}}"
   }
   ```
   ⚠️ `"{{ user.public_metadata }}"` (with spaces) is NOT interpolated —
   Clerk passes it through as a literal string, the middleware can't read
   `metadata.onboarded`, and every protected page bounces through
   /onboarding. Verify after saving: the minted session token's `metadata`
   claim must be a JSON object, not a `{{ … }}` string.
3. Save. New tokens issued after this point will include the `metadata` claim.

Without this step, authenticated users cannot be gated to `/onboarding`
after sign-up (the middleware skips the gate when the claim is missing or
malformed rather than bouncing everyone).

### Webhook endpoint (optional for local dev)

The `user.updated` webhook syncs Clerk profile changes (display name, avatar)
to the Harmoniq DB. For local development you can use
[ngrok](https://ngrok.com) to expose your local server:

```bash
ngrok http 8000
```

Then in **Clerk Dashboard → Webhooks → Add Endpoint**:
- URL: `https://<your-ngrok-id>.ngrok.io/api/v1/webhooks/clerk`
- Events: `user.updated`
- Copy the **Signing Secret** and add it to `backend/.env` as `CLERK_WEBHOOK_SECRET`.

---

## 6. Cloudflare R2 setup (avatar uploads)

If you want avatar uploads to work locally:

1. Log into **Cloudflare Dashboard → R2 → Create bucket**
   - Suggested name: `harmoniq-avatars-dev`
2. Enable public access on the bucket:
   - In the bucket settings, under **Public access**, enable "Allow public access"
   - Note the public URL (format: `https://pub-xxxx.r2.dev`)
3. Create an R2 API token:
   - **Cloudflare Dashboard → R2 → Manage R2 API Tokens → Create API Token**
   - Permissions: Object Read & Write on your bucket
   - Copy the **Access Key ID** and **Secret Access Key**
4. Find your **Account ID** in the top-right of the Cloudflare dashboard
5. Add to `backend/.env`:
   ```env
   R2_ACCOUNT_ID=<account-id>
   R2_ACCESS_KEY_ID=<access-key-id>
   R2_SECRET_ACCESS_KEY=<secret-access-key>
   R2_BUCKET_NAME=harmoniq-avatars-dev
   R2_PUBLIC_URL=https://pub-xxxx.r2.dev
   ```

Without R2 configured, the `POST /api/v1/users/me/avatar` endpoint returns
503. All other endpoints work normally.

---

## 6b. Spotify setup (account linking + listening display)

1. Go to the [Spotify Developer Dashboard](https://developer.spotify.com/dashboard)
   and create an app (Development Mode is fine — capped at 5 users).
2. In the app's settings, add the redirect URI **exactly**:
   `http://127.0.0.1:3000/spotify-callback`
   (Spotify's 2025 policy rejects `localhost` for new apps — loopback IP
   literal required. You still browse the app on `http://localhost:3000`
   as normal: Clerk dev sessions only exist on the localhost origin, so
   the callback page automatically forwards Spotify's 127.0.0.1 redirect
   back to localhost before completing the connection.)
3. Under **User Management**, add the Spotify account email of every user
   who will connect (dev-mode allowlist). A 403 "user not registered"
   during OAuth means the account isn't on this list.
   ⚠️ **Inviting testers:** this cap is hard — 5 external users max in
   Development Mode, each pre-registered by email here before they can
   link. If Spotify linking isn't part of what you're testing with a given
   cohort, skip this step entirely; every other feature works without it.
4. Copy the Client ID and Client Secret into `backend/.env`
   (`SPOTIFY_CLIENT_ID`, `SPOTIFY_CLIENT_SECRET`, `SPOTIFY_REDIRECT_URI`).
5. Generate the token-encryption key:

   ```bash
   python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
   ```

   and set it as `TOKEN_ENCRYPTION_KEY`.

Without Spotify configured, `GET /api/v1/spotify/connect-url` returns 503
and the settings page shows the connect button's error state. All other
endpoints work normally. Only the encrypted refresh token is stored;
listening data is fetched live and never persisted
(specs/phase-1-spotify-listening.md).

---

## 7. Verify the setup

```bash
# Health check
curl http://localhost:8000/api/v1/health
# Expected: {"status":"ok","version":"0.1.0"}
```

Open `http://localhost:3000` in a browser. Sign up via Clerk, complete
onboarding (choose a username), and you should land on your profile page at
`/u/<your-username>`.

---

## 8. Running tests

### Backend

The test suite has two tiers, separated by the `integration` marker.

**Unit tier — no external dependencies, runs in milliseconds:**

```bash
cd backend
poetry run pytest -m "not integration" -q
```

**Integration tier — requires Docker (Testcontainers spins up Postgres 16):**

```bash
cd backend
poetry run pytest -m "integration" -q
```

**Full suite with coverage:**

```bash
cd backend
poetry run pytest --cov=app --cov-report=term-missing -q
```

If Docker is not available (e.g. CI without a Docker daemon, or a machine where
Docker is not installed), use `-m "not integration"` to run only the unit tier.
The CI workflow (`backend-ci.yml`) runs the full suite on `ubuntu-latest`, which
has Docker pre-installed.

### Static analysis

```bash
cd backend
poetry run ruff check .          # lint
poetry run ruff format --check . # format
poetry run mypy app              # types (tests/ excluded)
```

### Frontend

```bash
cd frontend

# Type check
npm run typecheck

# Lint
npm run lint
```

---

## 8b. Granting moderator access

`is_moderator` is granted only via a direct database write — no API path
sets it (Founder decision, 2026-07-07; see `specs/phase-1-moderation.md`).
The moderation surface itself is existence-hidden (404, not 403) for
non-moderators, so there is nothing to configure beyond this column.

```sql
UPDATE users SET is_moderator = true WHERE username = 'your-username';
```

Run this against the target database (local Postgres, a Neon branch, or
the deployed instance) after the account has completed onboarding. To
revoke: set it back to `false`. There is no in-app UI for this by design —
see `specs/phase-1-moderation.md` Known Limitations before scaling past a
single Founder-moderator.

---

## 9. Database branching (Neon)

Neon supports database branches that mirror git branches. For feature work:

1. Create a database branch in the Neon console (or via Neon CLI):
   ```bash
   neon branches create --name feature/your-feature
   ```
2. Copy the branch's connection string into your local `.env`.
3. Run `alembic upgrade head` against the branch.
4. When the feature is merged, delete the branch.

This keeps your local migrations isolated without affecting `main`.

---

## 10. Common issues

**`ModuleNotFoundError: No module named 'app'`**  
Make sure your virtual environment is activated and you're running commands
from inside the `backend/` directory.

**`401 Unauthorized` on all API calls**  
The Clerk JWKS URL must match your Clerk application's instance URL exactly.
Check `CLERK_JWKS_URL` in `backend/.env`.

**Next.js build fails with missing env vars**  
Clerk requires `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` to be present at build time.
Make sure `.env.local` is populated before running `npm run build`.

**Redirected to `/onboarding` on every page load after completing onboarding**  
The Clerk JWT template is not configured. See step 5 (Clerk configuration →
JWT template). After configuring it, sign out and sign back in so a new token
is issued.

**Avatar upload returns 503**  
R2 credentials are not configured. See step 6. Avatar upload is optional for
local development.

**`ValidationError` on backend startup with missing R2/Clerk variables**  
These variables now have `None` defaults — this should not happen. If it does,
check that your `.env` file doesn't have syntax errors (no spaces around `=`).
