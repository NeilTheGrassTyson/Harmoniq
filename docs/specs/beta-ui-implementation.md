# Beta UI Implementation

> Tier 1 spec per WORKFLOW.md §1 (net-new user-facing features; changes to how
> user data is stored). Founder-approved 2026-09-06. Branch: `beta-ui`.
> Origin: the Beta UI design canvas, whose artboards are tracked at
> `.design/logo/*.dc.html` — open those alongside this document, they are the
> visual reference for every phase.
>
> **This spec is phased with explicit stop points.** Each phase is
> independently shippable. Do not run phases together; stop at each boundary,
> complete WORKFLOW.md §2's Review Workflow, and get Founder sign-off before
> continuing. Phases 3–6 are individually Tier 1.

---

# Purpose

- **Problem:** seven commits on `beta-ui` shipped the Octave logomark, its
  raster assets, and documentation for a redesigned interface — but nothing is
  wired. `OctaveMark` and `Wordmark` have zero imports outside their own
  folder, `AppShell` still renders `EqualizerGlyph` as the logo, and
  `DESIGN_SYSTEM.md` now describes a Space Mono label face and a three-theme
  system the code does not implement. The documentation is ahead of the code,
  which inverts HARMONIQ.md §7.
- **Why it belongs in Harmoniq:** this is primarily **Design Is a Feature**
  (HARMONIQ.md §8) — an identity the product asserts in docs but does not yet
  present to users. The later phases strengthen **Musical Identity** (the
  profile as a place taste is expressed) and **Trust Between People** (the
  friends rail and Melody provenance).

---

# Scope

### In Scope

- **Phase 1** — Brand wiring, Space Mono label face, `opengraph-image`,
  `manifest`.
- **Phase 2** — Token-layer refactor of `globals.css` (no visual change).
- **Phase 3** — Website Appearance: Light / Dark / Midnight.
- **Phase 4** — Melody received/outcome timestamps.
- **Phase 5** — Friends rail on the Melodies page.
- **Phase 6** — Highlighted reviews on the profile.

### Out of Scope

- **The Listening Signature ("DNA")** — deferred by Founder decision, see
  ROADMAP.md LATER. Do not build it, and do not build "just the wave" as a
  decorative element on the profile.
- **Harmony v2 profile themes** — a different feature from Website Appearance
  (ADR 0014). Do not let the two share a control, a token layer, or a stored
  field.
- **Cross-device sync of the appearance preference** — see Phase 3.
- **Any change to the Octave mark itself.** The geometry, colour, and raster
  assets are settled (ADR 0013). Do not redraw, recolour, or re-export them.
- **Renaming `EqualizerGlyph` or removing it.** It keeps its placeholder role.

---

# Prerequisites

**1. Rebase onto `origin/dev` before writing any code.**

```bash
git fetch origin && git rebase origin/dev
```

`beta-ui` is 6 commits behind. Verified: zero file overlap, so this is clean.
The branch has never been pushed — no force-push needed.

**2. ADR numbering is already fixed — do not redo it.** `dev` carries
`0012-nav-identity-and-public-search.md`; this branch's two ADRs were renumbered
to **0013** (logomark) and **0014** (Website Appearance) ahead of the rebase, so
the merged history is contiguous with no duplicates.

**3. Read these after rebasing, before touching `AppShell` or `layout.tsx`.**
dev's `eb44a07` introduced `frontend/src/components/ViewerProvider.tsx` and
`frontend/src/lib/viewer.ts`, and rewrote parts of `layout.tsx`, `AppShell.tsx`
and `page.tsx` — all files Phases 1 and 3 edit.

---

# Phase 1 — Brand wiring + metadata (Tier 2)

## The rule that decides which glyphs change

`EqualizerGlyph` appears at 11 sites. ADR 0013 says it keeps its
placeholder/music-glyph role and loses **only** its logo role. The codebase
already draws that line cleanly:

| Role | Signal | Action |
| --- | --- | --- |
| **Logo** | `text-accent` **and** adjacent to the `harmoniq` wordmark | replace |
| **Placeholder / empty state** | `text-secondary` or unstyled, no wordmark | leave alone |

Exactly **three** sites are logos:

- `frontend/src/components/AppShell.tsx` — header
- `frontend/src/components/AuthScreen.tsx` — sign-in / sign-up
- `frontend/src/app/page.tsx` — `SignedOutLanding`

`error.tsx`, `not-found.tsx`, `ServiceUnavailable.tsx`, the `/search` empty
state, `TrackTile`, `MelodyCard` and `ListeningSection` all keep
`EqualizerGlyph`. Do not "tidy" them.

## What to build

- Replace the three logo sites with `Wordmark` (word + octave underline), or
  `OctaveMark` where only the mark fits. **Preserve `AppShell`'s responsive
  rule**: the mark alone below `sm`, the full lockup from `sm` up — at 390px
  the wordmark competes with the search field for the same row.
- Colour the mark with `--color-brand` (`text-brand`), not `--color-accent`.
  This is the token's first real use.
- Add **Space Mono** (400, 700) via `next/font/google` in `layout.tsx`
  alongside Space Grotesk; expose it as a theme font variable; apply it to
  section labels at **10.5px / 700 / 1.1px tracking** (DESIGN_SYSTEM.md §3).
  Sites: `page.tsx`'s `SectionLabel`, and the two settings headings in
  `ConnectedAccounts.tsx` and `MelodySettings.tsx` — which currently disagree
  with each other. Standardise on the uppercase micro-label.
- Add `frontend/src/app/opengraph-image.tsx`. **Highest-value item in this
  phase**: every shared Harmoniq link currently previews with no image, on a
  product whose whole mechanic is sharing links.
- Add `frontend/src/app/manifest.ts` returning `MetadataRoute.Manifest`, with
  icons pointing at the committed brand PNGs.

## Functional requirements

- The header logo must remain a link to `/` with an accessible name.
- The mark must not animate on load. `.octave-draw` is reserved for Melody
  arrival only (DESIGN_SYSTEM.md §8).
- `opengraph-image` must render the wordmark in real Space Grotesk, not a
  fallback face.

## Acceptance criteria

- [ ] `OctaveMark` / `Wordmark` are imported by exactly the three logo sites.
- [ ] `git grep EqualizerGlyph` still returns all eight non-logo call sites.
- [ ] Header shows mark-only below `sm`, full lockup from `sm` up.
- [ ] Section labels render in Space Mono at 10.5/700/1.1px.
- [ ] Build route table lists `○ /opengraph-image` and
      `○ /manifest.webmanifest` alongside `○ /icon.svg` and `○ /apple-icon`.
- [ ] `npm run lint && npm run typecheck && npm run test:run && npm run build`
      all pass. Baseline is 0 errors / 3 pre-existing warnings — do not
      introduce a fourth.

## Test impact — smaller than it looks

- `frontend/src/__tests__/AppShell.test.tsx:47` mocks
  `@/components/EqualizerGlyph`. Repoint it at the brand components. It asserts
  nothing about the glyph, so no assertion changes.
- `SearchPage.test.tsx` is the **only** test asserting on the glyph
  (`getByTestId("equalizer-glyph")`), and it targets the search empty state,
  which keeps `EqualizerGlyph`. **It does not break.**
- `MelodyInbox.test.tsx` and `SendMelodyPanel.test.tsx` mock the glyph
  inertly. Vitest does not error on a mock for a module no longer in the tree,
  so these rot quietly — remove them if they become dead.
- `ListeningSection.test.tsx` asserts `row.querySelector("svg")`. `Wordmark`
  renders a `<span>` wrapper, not a bare `<svg>` — do not put it in a
  listening row.
- `OctaveMark` and `Wordmark` have **no tests**. Add basic render tests.

**STOP. Review and sign-off before Phase 2.**

---

# Phase 2 — Token-layer refactor (Tier 2, zero visual change)

Prerequisite for Phase 3. This phase must produce **no visible difference**.

`globals.css` defines the palette in **three** places — `@theme` (line ~9),
`@theme inline` (~38), and `:root` (~224) — plus a **fourth** copy in
`frontend/src/lib/clerkAppearance.ts`, which Clerk needs because its components
render their own DOM and cannot inherit CSS variables.

## What to build

- Convert the three hardcoded escapes to `var()`:
  1. `body { background-color: #0b0d12; color: #f2f3f5; }`
  2. `:focus-visible { box-shadow: 0 0 0 1.5px rgba(47,140,255,.6); }`
  3. `.listening-now-row` — `rgba(47,140,255,.06)` fill, `#2f8cff` border
- Restructure so **one** swappable `:root` token set feeds `@theme`.
- **Correct DESIGN_SYSTEM.md §2 and §2.2 to the code's token names.** The
  tables say `--color-bg` / `--color-surface-sidebar` / `--color-text-primary`;
  the code uses `--color-canvas` / `--color-sidebar` / `--color-primary`. The
  **doc is wrong, not the code** — taking it literally would rename every
  utility class in the app for no benefit.

## Acceptance criteria

- [ ] No hardcoded palette hex remains in `globals.css` outside the token
      definitions themselves.
- [ ] `git grep -E "#0b0d12|#151821|#f2f3f5|#2f8cff|#0e1015" frontend/src`
      returns only `globals.css` and `clerkAppearance.ts`.
- [ ] DESIGN_SYSTEM.md token names match `globals.css` exactly.
- [ ] Screenshots before and after are identical at desktop and mobile widths.

**STOP. Review and sign-off before Phase 3.**

---

# Phase 3 — Website Appearance (Tier 1)

Light / Dark / Midnight, in Settings under the heading **"Website
Appearance"**. That name is load-bearing: it is the *viewer's* preference,
distinct from Harmony v2 profile themes (ADR 0014).

## The deciding constraint: no flash

**Persist to a cookie, read in the RSC root layout.** A server-persisted
preference is only known after `getToken()` → `GET /users/me` resolves in a
client effect, so every page load would paint Dark and then repaint. The
codebase already guards against this exact bug class — the sidebar default
lives in CSS specifically because a JS measurement *"flashes a 220px sidebar
across more than half a phone screen before hydration corrects it."* A theme
flash is that bug at full-viewport scale.

A cookie also works on signed-out surfaces (`/sign-in`, `/sign-up`,
`global-error.tsx`), where there is no user record at all.

**No backend work in v1.** Cookie-only avoids the 7-file
enum/model/migration/schema/route/service change entirely.

## What to build

- `[data-theme="light" | "midnight"]` on `<html>`, set server-side from the
  cookie. Dark is the default and needs no attribute.
- Token override blocks per theme, layered on Phase 2's single token set.
- A Settings section following `MelodySettings.tsx`'s pattern: optimistic
  update, no save button, error in a `role="alert"`. There is no network call
  here, so the failure mode is narrower.
- **`clerkAppearance.ts` must be derived per theme**, or Clerk's modals stay
  dark on Light.
- **Light needs a real contrast pass.** The values in DESIGN_SYSTEM.md §2.2 are
  drafted and explicitly unverified. Two things break rather than degrade:
  `--color-accent` measures ~3.1:1 on white — below AA, and it is the
  **focus-ring** colour, so this is an accessibility regression, not a cosmetic
  one; and every Signature hue is invisible on white. Light gets a darkened
  accent and a darkened hue set, and drops glow, grain and particles entirely.

## Acceptance criteria

- [ ] Switching theme repaints without a full reload.
- [ ] Hard reload in each theme shows **no flash** of the previous theme.
- [ ] Signed-out pages honour the cookie.
- [ ] Clerk modals match the active theme.
- [ ] Every Light token passes WCAG AA, focus ring included, with the measured
      ratios recorded in DESIGN_SYSTEM.md §2.2 replacing "unverified".
- [ ] The preference appears in **no** profile API payload (ROADMAP.md: it is
      per-viewer and must never become a visible field).

**STOP. Review and sign-off before Phase 4.**

---

# Phase 4 — Melody timestamps (Tier 1)

Every Melody shows a local **Received** stamp, plus an outcome stamp
(**Accepted** / **Opened** / **Passed**) once acted on. See
`.design/logo/MelodiesBeta.dc.html` and `MelodyBeta.dc.html`.

- Display is trivial; **persisting a state-transition time is a schema
  change.** The Melody state machine (ENGINEERING_BIBLE §3) currently records
  the current state, not when it was reached. Migration precedent:
  `backend/alembic/versions/b3c4d5e6f7a8_add_visibility_follows.py`.
- **"Local" means client-rendered.** A server-rendered UTC value hydrating
  against a client-rendered local one is a mismatch — render the stamp
  client-side, or send an ISO string and format after mount.
- Timestamps use the label face (Space Mono), matching the mockup.
- A rejected Melody's outcome stamp is visible **to the recipient and the
  sender only**, never to anyone else (ENGINEERING_BIBLE §3).

**STOP. Review and sign-off before Phase 5.**

---

# Phase 5 — Friends rail (Tier 1 — consent-sensitive)

A right-hand rail on the Melodies page: **Listening now → Online → Offline**,
alphabetical within each group, with a single hover action to send a Melody.
See `.design/logo/MelodiesBeta.dc.html`.

**This phase exposes who is listening to what. Treat it as a privacy feature
that happens to have a UI.**

- Presence is an ephemeral real-time state, which ENGINEERING_BIBLE §9
  explicitly permits — but §8.1 requires enforcement at the **data-access
  layer**, not the presentation layer. The query itself must respect
  visibility scope; it is not acceptable to return presence and hide it in the
  client.
- Default to the most private option. Revocation takes effect immediately, with
  no serving from cache or a stale fan-out.
- Deliberately omitted from the mockup, and must stay omitted: status text,
  idle timers, "last seen", and any sort by a measure of a person. Rows are
  people; the track is a subtitle, never a headline.

**STOP. Review and sign-off before Phase 6.**

---

# Phase 6 — Highlighted reviews on the profile

A self-curated showcase — the same gesture as highlighting a song. One featured
review with an excerpt, then two compact ones. See
`.design/logo/ProfileBeta.dc.html`.

- Framing must follow BRAND_BIBLE.md §6.3: **no "Top reviews", no "Most
  helpful", no helpfulness count, no review-count leaderboard.** Approved
  language treats a review as a personal account ("Mara's take"), not content
  competing for visibility.
- Tier depends on an open question below: Tier 2 if reviews are already public
  by default, Tier 1 if this changes what is visible about a user.

---

# Design Requirements

- Every phase is checked against BRAND_BIBLE.md §7 (calm, non-demanding) and
  §8 (recognition over stimulation) during WORKFLOW.md §2.4.
- **Motion is constrained.** DESIGN_SYSTEM.md §8 bans decorative motion. The
  sanctioned exceptions are `.eq-bar`, `.skeleton-pulse`, `.octave-draw`
  (Melody arrival only), and the Signature surface's ambient set — which is
  out of scope here. Do not add motion outside these.
- **`--color-brand` is logo-only.** Never a button, nav state, or border.
- The Signature exception in DESIGN_SYSTEM.md §2.1 (six hues, glow, grain,
  particles) is scoped to a surface this spec does not build. Do not borrow it.

---

# Technical Notes

- **Read the bundled Next docs before writing Next code.** `frontend/AGENTS.md`
  is not boilerplate: this version has breaking changes from training data.
  `node_modules/next/dist/docs/` has the guides — `metadata/manifest.md`,
  `metadata/opengraph-image.md`, `functions/image-response.md`,
  `functions/generate-image-metadata.md` are the relevant ones.
- **`ImageResponse`'s `id` prop is a `Promise` and must be awaited.**
  `Number(id)` without `await` yields `NaN` and the build fails inside satori
  with `inputValue.trim is not a function`, which points nowhere near the
  cause. This cost real time already.
- **Custom fonts in `ImageResponse`** need the font bytes via the `fonts`
  option. `frontend/public/brand/fonts/SpaceGrotesk-Medium.ttf` is committed for
  exactly this. It is a **build input, not a served webfont** — the app loads
  the face through `next/font`. Do not `@font-face` it. `OFL.txt` beside it must
  stay (licence requirement). satori does not accept woff2, which is why the
  `next/font` cache is unusable here.
- **Settings persistence pattern:** `MelodySettings.tsx` → `updateProfile()` in
  `frontend/src/lib/users.ts` → `PATCH /api/v1/users/me`. Plain `fetch`, no
  React Query — settings surfaces deliberately do not use it, and there is no
  own-profile query cache to invalidate.
- **Machine note:** `node` is not resolvable through the Bash tool on this
  Windows machine — run all `npm`/`npx` work through PowerShell. The backend
  venv lives in the main checkout, not the worktree.

---

# Rollback Plan

- Phases 1–2 are presentation-only: `git revert` the phase commit.
- Phase 3 is cookie-only, so rollback is a revert plus a stale cookie that the
  next render ignores. No migration to unwind.
- Phase 4 adds a column; the migration has a `downgrade()`. Display can be
  reverted independently of the schema.
- Phase 5 must be revertible **without leaving presence data exposed** — if
  the rail is pulled, the query that serves presence goes with it.

---

# Open Questions

_Do not answer these while implementing. Bring them to the Founder._

1. **Does Midnight become the default instead of Dark?** ADR 0014 leaves this
   open. Adding an option and changing a default are different decisions; the
   second changes the product for people who never asked.
2. **Is there an "Auto" option** following `prefers-color-scheme`? Recommend
   deferring — it reintroduces the flash problem the cookie approach solves.
3. **Cross-device sync of the appearance preference** — accepted as deferred,
   or wanted in v1? Wanting it means the backend change Phase 3 avoids.
4. **Friends rail visibility** — which scope governs presence? A new field, or
   does it reuse `visibility_activity`?
5. **Are reviews public by default?** Determines whether Phase 6 is Tier 1 or
   Tier 2.
6. **`beta-ui` does not match `GITHUB_WORKFLOW.md`'s `type/short-kebab`
   branch convention.** Leave it, or rename before the PR to `dev`?

---

Once approved, each phase proceeds under the standard process in **WORKFLOW.md**.
