# Harmoniq — Frontend

Next.js 16 application (App Router, TypeScript). Handles all UI, routing, and client-side session management. Talks to the FastAPI backend for all data.

---

## Tech stack

- **Next.js 16** (App Router) — routing, SSR, React Server Components
- **TypeScript** (strict mode)
- **Tailwind CSS 4** — utility-first styling, tokens in the `@theme` block of `globals.css`
- **shadcn/ui primitives** on Base UI, in `src/components/ui/`, restyled onto Harmoniq's tokens — never shadcn's default theme (DESIGN_SYSTEM.md §13)
- **TanStack Query** — client-driven server state; **react-hook-form + zod** — form validation (`docs/specs/frontend-data-layer-foundation.md`)
- **Clerk** (`@clerk/nextjs`) — session UI and token management
- **Vitest** + React Testing Library — tests
- **Prettier** + `prettier-plugin-tailwindcss` — formatting

---

## Directory structure

```
frontend/
├── src/
│   ├── app/                        App Router routes; layout.tsx and globals.css at the root
│   ├── components/                 Shared UI components
│   │   └── ui/                     shadcn primitives (Button, Dialog, Form, …)
│   ├── lib/                        One typed API client per backend domain, plus
│   │                               apiBase.ts (backend origin + misconfiguration checks)
│   ├── proxy.ts                    Clerk route gate — public routes, onboarding redirect
│   └── types/
│       └── index.ts                Shared TypeScript types (mirrors backend schemas)
├── public/                         Static assets
├── .env.local.example              Required environment variables (no secrets)
├── next.config.ts                  Next.js config (image domains, etc.)
└── .prettierrc                     Prettier config
```

> **Note:** `AGENTS.md` in this directory opens with `create-next-app`'s
> Next.js 16 guidance and continues with Harmoniq's frontend rules for AI
> contributors (ADR 0013); `CLAUDE.md` just imports it. Neither is a governance
> document — those are the root-level `HARMONIQ.md`, `ENGINEERING_BIBLE.md`
> and `WORKFLOW.md`.

---

## Setup

```bash
# From the frontend/ directory:

npm install

cp .env.local.example .env.local
# Edit .env.local — fill in Clerk keys and NEXT_PUBLIC_API_URL
```

### Required environment variables

| Variable                            | Description                                           |
| ----------------------------------- | ----------------------------------------------------- |
| `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` | From Clerk dashboard → API Keys (public)              |
| `CLERK_SECRET_KEY`                  | From Clerk dashboard → API Keys (secret, server-only) |
| `NEXT_PUBLIC_API_URL`               | Backend URL — `http://localhost:8000` for local dev   |

The `NEXT_PUBLIC_CLERK_SIGN_IN_URL`, `SIGN_UP_URL`, and `AFTER_SIGN_IN/UP_URL` variables in `.env.local.example` can be copied as-is.

---

## Running locally

```bash
npm run dev
```

App runs at `http://localhost:3000`. The backend must also be running at `NEXT_PUBLIC_API_URL` for API calls to work.

---

## Development commands

```bash
# Type check (no emit)
npm run typecheck

# Lint
npm run lint

# Format (auto-fix)
npm run format

# Format check (CI — fails if unformatted)
npm run format:check

# Tests (watch mode; `npm run test:run` for a single pass)
npm run test

# Production build (smoke test before deploying)
npm run build

# Everything CI runs, in CI's order — run this before pushing
npm run verify
```

CI runs typecheck, lint, format:check, tests and build on pull requests into
`dev` and `main`. `npm run verify` is the same set locally; a hand-picked
subset has missed the format step before and turned CI red.

---

## Authentication

Clerk handles the session UI. `src/proxy.ts` (Next.js 16's replacement for `middleware.ts`) gates routes: its `isPublicRoute` matcher lists what anyone may see — home, sign-in/up, search, catalog pages and public profiles (`/u/*`) — and it sends a signed-in user with no Harmoniq account yet to `/onboarding` when they open a protected route (checking the backend, not just the `onboarded` claim, which can be stale right after sign-up).

There is no shared fetch wrapper. Each domain has a typed client in `src/lib/` that builds its URL from `API_BASE` (`src/lib/apiBase.ts`) and takes the Clerk session token as an argument, sending it as `Authorization: Bearer`. Get the token with `useAuth().getToken()` in Client Components, or `(await auth()).getToken()` from `@clerk/nextjs/server` in Server Components — `src/lib/viewer.ts` shows the server pattern.

---

## Styling conventions

- **Tailwind CSS 4** only — no CSS-in-JS. Interactive primitives come from `src/components/ui/` (shadcn on Base UI); DESIGN_SYSTEM.md §13 governs when to use them and how they are themed.
- The `@import "tailwindcss"` directive in `globals.css` replaces the v3 `@tailwind` directives — do not use `@tailwind base/components/utilities`.
- Prettier with `prettier-plugin-tailwindcss` auto-sorts class names on save / `npm run format`.
- Follow BRAND_BIBLE.md for all design decisions — tone, spacing, naming, interaction philosophy.

---

## Adding a new page

1. Create `src/app/<route>/page.tsx`
2. If the route needs a layout, add `src/app/<route>/layout.tsx`
3. Public routes (no auth required) must be added to the `isPublicRoute` matcher in `src/proxy.ts`
4. Components specific to that route live in `src/app/<route>/_components/` (prefixed `_` so Next.js doesn't treat them as routes)

---

## Deployment

Vercel auto-deploys `main` to production and `dev` to `dev.harmoniq.live` (behind a Vercel login), which is where to test signed-in before a release — see [docs/deployment.md](../docs/deployment.md#testing-on-dev-before-a-release). Other branches get automatic preview URLs, which cannot sign in because the production Clerk instance only works on `harmoniq.live` subdomains.

Root directory in Vercel: `frontend`  
Environment variables are configured in the Vercel dashboard — see [docs/deployment.md](../docs/deployment.md).
