<!-- BEGIN:nextjs-agent-rules -->

# This is NOT the Next.js you know

This version has breaking changes — APIs, conventions, and file structure may all differ from your training data. Read the relevant guide in `node_modules/next/dist/docs/` before writing any code. Heed deprecation notices.

<!-- END:nextjs-agent-rules -->

---

# Harmoniq frontend

Read the root `AGENTS.md` first — this file only adds frontend-specific
detail, it doesn't restate the project-wide rules (Tier 1/Tier 2 gate,
Spotify ToS constraint, branch flow).

## Folder structure

```
frontend/src/
├── app/            Next.js App Router pages
│   ├── album/[mbid]/
│   ├── artist/[mbid]/
│   ├── onboarding/
│   ├── settings/
│   ├── sign-in/[[...sign-in]]/
│   ├── sign-up/[[...sign-up]]/
│   ├── sso-callback/
│   ├── track/[mbid]/
│   └── u/[username]/
├── components/     Shared UI components
├── lib/            API client helpers (users, catalog, ratings, follows, home)
└── types/          Shared TypeScript types (index.ts)
```

The frontend is presentation and interaction only. It never computes
ranking logic and never talks to external music providers directly — both
are backend responsibilities (ENGINEERING_BIBLE.md §2, §7).

## Commands

- Lint: `npm run lint`
- Type check: `npm run typecheck`
- Format check: `npm run format:check` (Prettier + `prettier-plugin-tailwindcss`)
  — its own CI step, separate from lint; passing lint says nothing about it.
- Full CI-equivalent gate before pushing: `npm run verify` (typecheck,
  lint, format:check, tests, build, in that order — matches
  `.github/workflows/frontend-ci.yml`).
- Dev server: `npm run dev`

## Design

Styling is Tailwind v4 via the `@theme` block in `globals.css` — there is
no `tailwind.config.js`. Typography: Space Grotesk (display) via
`next/font/google`, system font stack for body text. UI work stays within
the established design system (Tier 2) unless the task is explicitly a
design change — consult `BRAND_BIBLE.md` for anything touching layout,
spacing, typography, motion, or copy, per the Design Audit step in
`WORKFLOW.md` §2.4.

The `unslop-ui` skill exists at `.claude/skills/unslop-ui/` for Claude
Code specifically — it is not portable to astra since `.claude/` is local,
gitignored tool state (see root `AGENTS.md`'s Multi-agent coordination
section and `docs/adr/0013-astra-second-engineer.md`).
