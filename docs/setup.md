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

---

## 1. Clone and configure

```bash
git clone https://github.com/your-org/harmoniq.git
cd harmoniq
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

# Install dependencies
pip install poetry
poetry install

# Configure environment
cp .env.example .env
# Edit .env — fill in DATABASE_URL, CLERK_JWKS_URL, MUSICBRAINZ_USER_AGENT

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
cp .env.local.example .env.local
# Edit .env.local — fill in Clerk keys and NEXT_PUBLIC_API_URL

# Start the development server
npm run dev
```

The frontend is now running at `http://localhost:3000`.

---

## 4. Verify the setup

```bash
# Health check
curl http://localhost:8000/api/v1/health
# Expected: {"status":"ok","version":"0.1.0"}
```

Open `http://localhost:3000` in a browser — you should see the Harmoniq
placeholder page.

---

## 5. Running tests

```bash
# Backend tests (from backend/)
pytest

# Frontend type check (from frontend/)
npm run typecheck

# Frontend lint (from frontend/)
npm run lint

# Frontend format check (from frontend/)
npm run format:check
```

---

## 6. Database branching (Neon)

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

## 7. Common issues

**`ModuleNotFoundError: No module named 'app'`**  
Make sure your virtual environment is activated and you're running commands
from inside the `backend/` directory.

**`401 Unauthorized` on all API calls**  
The Clerk JWKS URL must match your Clerk application's instance URL exactly.
Check `CLERK_JWKS_URL` in `backend/.env`.

**Next.js build fails with missing env vars**  
Clerk requires `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` to be present at build time.
Make sure `.env.local` is populated before running `npm run build`.
