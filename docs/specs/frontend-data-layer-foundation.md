# Frontend Data Layer & Component Foundation

> Tier 1 spec per WORKFLOW.md §1 (tech-stack change: new frontend
> dependencies). Founder-approved 2026-07-19/20; this document records the
> approved scope. Origin: external frontend review + full audit (see plan
> record and PR #36 for the Tier 2 bug fixes that preceded this work).

---

# Purpose

- **Problem:** the frontend has no caching layer (every navigation re-fetches
  near-static MusicBrainz catalog data), no schema-based form validation
  (each form hand-rolls its own rules inconsistently), and no shared UI
  primitives (every button/input/select is styled inline per page).
- **Why it belongs in Harmoniq:** this is an enabling/quality change under
  HARMONIQ.md §3 (Quality Before Speed) — it does not add a user-facing
  feature and is not force-fit under Identity/Trust/Discovery. It makes the
  surfaces that *do* serve those pillars (profiles, ratings, Melodies,
  follows) faster, more consistent, and less buggy-feeling.

# Scope

### In Scope

- Next.js native fetch caching for RSC-fetched catalog data (frontend).
- `Cache-Control` headers on read-only catalog endpoints (backend).
- TanStack Query for client-driven state: follows, rating submission,
  Melody actions, listening polling.
- shadcn/ui primitives (Button, Input, Textarea, Select, Dialog, Form,
  Label) via the shadcn CLI, restyled onto existing design tokens.
- react-hook-form + zod replacing ad hoc validation in onboarding,
  RatingComposer, ProfileEditPanel, and settings.
- DESIGN_SYSTEM.md amendment documenting shadcn as the primitive layer.

### Out of Scope

- shadcn `Card` or any bordered-card layout (DESIGN_SYSTEM.md §1/§7/§9).
- Redis or any external cache store.
- Caching on any visibility-scoped or per-user endpoint
  (ENGINEERING_BIBLE.md §8.1 — cached responses must not outlive a revoked
  visibility grant).
- Visual redesign of any surface — this is infrastructure, not a redesign.
- Clerk production-keys swap (separate config task; Founder handles
  credentials).

# Functional Requirements

- Catalog pages (album/artist/track by MBID) must serve repeat navigations
  from cache rather than re-hitting MusicBrainz.
- System should revalidate cached catalog data on a conservative TTL
  (near-static data; 24h default, tag-based invalidation available).
- User-facing mutations (follow, rate, Melody accept/open/reject) must
  reflect immediately in the UI and invalidate affected queries.
- All forms must validate against a zod schema shared between the input
  constraints and the submit gate; error messages must be field-level.
- Feature should never render shadcn's default theme — every primitive maps
  to `@theme` tokens in `globals.css`.
- Data must never be cached on endpoints returning visibility-scoped
  content.

# Acceptance Criteria

- [ ] Repeat navigation to a catalog page issues no duplicate MusicBrainz
      round-trip (verified via network inspection).
- [ ] `curl -I` shows `Cache-Control` on catalog reads and absent on all
      user/visibility-scoped endpoints.
- [ ] Follow/rate/Melody actions update the UI without a full reload and
      refetch affected lists.
- [ ] Onboarding, RatingComposer, ProfileEditPanel, and settings validate
      via zod schemas with field-level errors.
- [ ] No bordered-card-grid pattern introduced anywhere (Design Audit
      against DESIGN_SYSTEM.md §9).
- [ ] Lint, typecheck, and full test suites pass; backend pytest passes.

# Design Requirements

- DESIGN_SYSTEM.md §14 (added by this spec) governs shadcn usage: behavior
  and accessibility only, visuals from existing tokens.
- Focus states use the existing global `:focus-visible` ring — shadcn's
  per-component ring utilities are stripped.
- Copy and layout of migrated forms are unchanged — like-for-like swaps.

# Technical Notes

- Dependencies added: `@tanstack/react-query`, `react-hook-form`, `zod`,
  `@hookform/resolvers`, shadcn CLI-generated components (Radix
  primitives).
- One `QueryClient` per request via a root client provider component
  (SSR-safe per TanStack App Router guidance); Server Components keep
  direct `await`s and pass `initialData`.
- Existing `frontend/src/lib/*.ts` functions are wrapped as
  query/mutation functions, not replaced.
- Backend: `Cache-Control` headers set in `backend/app/api/v1/catalog.py`
  responses only.

# Rollback Plan

- Each phase is an independent commit; any phase can be reverted alone.
- Caching: removing the `next` fetch options / header lines restores
  previous behavior with no data migration.
- TanStack Query and shadcn adoption are additive per-component; a
  reverted component returns to its previous inline implementation.

# Open Questions

- None — the four open questions from the plan were resolved by the
  Founder 2026-07-19 (backend caching in scope; Clerk keys fixed
  separately; shadcn CLI approved; DESIGN_SYSTEM.md amended, visual rules
  kept).
