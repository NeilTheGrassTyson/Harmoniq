# ADR 0002 — Frontend Framework: Next.js 15

**Date:** 2026-06-18
**Status:** Accepted
**Deciders:** Founder

---

## Context

Harmoniq requires a frontend framework for a calm, structured social UI.
Requirements: server-side rendering (artist/album pages should be indexable),
TypeScript, strong AI development tooling support, production-grade ecosystem,
and a deployment model that supports feature-branch previews.

## Decision

Use **Next.js 15 (App Router, TypeScript strict mode)** as the frontend framework.

## Rationale

- **SSR/RSC for SEO:** Artist pages, album pages, and public profiles must
  be indexable. React Server Components allow server-side data fetching with
  zero client-side bundle cost for read-only content.
- **AI development experience:** More Claude/Copilot training data exists for
  Next.js App Router than any other frontend framework. Code generation is
  reliable; bugs surface quickly.
- **Vercel-native deployment:** Next.js and Vercel are built together — zero
  configuration for preview deployments per branch, image optimization,
  and edge caching.
- **Ecosystem maturity:** Largest frontend ecosystem in existence. Every UI
  pattern Harmoniq will need has been solved and documented.
- **TypeScript strict mode:** Aligns with the backend's Pydantic type safety.
  Type errors are caught at build time.

## Styling Decision

**Tailwind CSS** — utility-first CSS that composes rather than inherits.
No prebuilt component library (shadcn, MUI, Chakra). Harmoniq's brand
(BRAND_BIBLE.md) is distinct enough that off-the-shelf components would
require heavy customization. Custom components built from scratch with
Tailwind are cleaner and do not accumulate framework-specific styling debt.

## Alternatives Considered

- **SvelteKit** — smaller ecosystem, significantly less AI training data,
  Svelte 5's runes model is a recent breaking change. Rejected on AI tooling
  gap.
- **Remix** — good form/mutation model but smaller community; ownership
  uncertainty post-Shopify acquisition. No clear advantage over Next.js.
- **Vite + React (SPA)** — no SSR, no SEO for public pages. Rejected.

## Consequences

- All frontend code is TypeScript (strict mode).
- Styling is Tailwind CSS only — no CSS-in-JS, no component library.
- Deployed on Vercel; feature branches auto-generate preview URLs.
- `next-env.d.ts` is generated automatically — do not edit it manually.
