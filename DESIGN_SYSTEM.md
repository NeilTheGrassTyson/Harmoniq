# DESIGN_SYSTEM.md

> Harmoniq — UI Design System v1
> Location: `DESIGN_SYSTEM.md` (repo root)

This is the literal, pixel-level translation of BRAND_BIBLE.md into implementation tokens. BRAND_BIBLE.md stays principle-level ("calm," "purposeful," "Humans Before Algorithms"); this document is where those principles become actual hex values, type choices, and component rules. When a visual decision changes, update this file — not BRAND_BIBLE.md, and not by improvising new values mid-build.

Derived from mockup iteration (chat, June 2026), checked against BRAND_BIBLE.md §7 (Home Experience Philosophy), §8 (Emotional Tone), §14 (System Boundaries), and refined using the `unslop-ui` skill to avoid generic/templated patterns. Treat every value here as a deliberate decision with a stated reason — if you need a value this file doesn't cover, flag it rather than guessing one that "looks about right."

---

## 1. Governing intent

- Calm and purposeful, not busy. If a screen needs a second look to find the important
  thing, it has too many competing elements.
- Separation comes from whitespace, not boxes. No bordered-card-grid pattern — that
  reads as a templated default (the shadcn `Card` tell) regardless of color choices.
- One accent color, used sparingly and with intentional hierarchy — not scattered
  across every surface "to look branded."
- Apple-native restraint as the base register, with exactly one distinctive original
  mark layered on top (the equalizer glyph) and one distinctive display typeface
  (Space Grotesk). A reference plus one real original cue, not a generic template and
  not maximalist branding either.

---

## 2. Color tokens

| Token                          | Value                    | Usage                                                   |
| ------------------------------ | ------------------------ | ------------------------------------------------------- |
| `--color-bg`                   | `#0b0d12`                | App frame / page background                             |
| `--color-surface-sidebar`      | `#0e1015`                | Sidebar panel                                           |
| `--color-surface-tile`         | `#151821`                | Neutral (trending) artwork tile fill                    |
| `--color-surface-tile-friend`  | `#121a2a`                | Friend-sourced artwork tile fill (blue-tinted)          |
| `--color-border-hairline`      | `rgba(255,255,255,0.07)` | All dividers, frame border                              |
| `--color-text-primary`         | `#f2f3f5`                | Titles, primary labels                                  |
| `--color-text-secondary`       | `#8b93a3`                | Artist names, nav labels, body chrome                   |
| `--color-text-tertiary`        | `#757c8c`                | Section labels, captions, placeholders                  |
| `--color-accent`               | `#2f8cff`                | The one brand accent — logomark, active nav, focus ring |
| `--color-accent-icon-trending` | `#343b4d`                | Equalizer glyph on neutral tiles                        |
| `--color-accent-icon-friend`   | `#34507c`                | Equalizer glyph on friend tiles                         |
| `--color-friend-dot`           | `#5a8fd6`                | Small "from a friend" indicator dot                     |
| `--surface-nav-active`         | `rgba(255,255,255,0.06)` | Active sidebar row                                      |
| `--surface-nav-hover`          | `rgba(255,255,255,0.04)` | Hover sidebar row                                       |
| `--surface-control`            | `rgba(255,255,255,0.05)` | Search field, profile button background                 |

**Contrast ratios (WCAG AA, verified June 2026):**

- `--color-text-primary` (`#f2f3f5`) on `--color-bg` (`#0b0d12`): ~18:1 ✓
- `--color-text-secondary` (`#8b93a3`) on `--color-bg` (`#0b0d12`): ~6.3:1 ✓
- `--color-text-tertiary` (`#757c8c`) on `--color-bg` (`#0b0d12`): ~4.65:1 ✓ (minimum 4.5:1 for normal text)
  - Previous value `#6b7385` measured 4.08:1 and failed; adjusted to `#757c8c`.

**Forbidden, without an explicit stated exception:** gradients; glow, blur, or drop
shadows (the _only_ permitted shadow is a 1.5px focus ring — see Motion); purple,
indigo, or violet as any UI color; cream/beige backgrounds; any "neon" effect achieved
through blur/glow rather than flat saturated color.

---

## 3. Typography

**Display face — `Space Grotesk` (400, 500 only).** Used for the wordmark, section labels, and primary titles (song/track names). Chosen for its geometric, slightly squared terminals — sharper than the system-font fallback, and a stated choice rather than an autopilot one (avoiding Inter/Geist, which read as "no choice was made").

**Body face — system stack.** `-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif`. Used for everything secondary: artist names, nav labels, search input, captions. Keeps the "Apple-native" base register and gives the display face something quiet to contrast against.

| Role                     | Face    | Size                            | Weight |
| ------------------------ | ------- | ------------------------------- | ------ |
| Logo wordmark            | Display | 14px                            | 500    |
| Section label            | Display | 11px, uppercase, 0.6px tracking | 500    |
| Track/song title         | Display | 14px                            | 500    |
| Artist name              | Body    | 12px                            | 400    |
| Nav label                | Body    | 13px                            | 400    |
| Search input/placeholder | Body    | 13px                            | 400    |
| Caption / friend name    | Body    | 11px                            | 400    |

No weight above 500 anywhere — contrast comes from size, color, and face, not bold
weight stacking.

---

## 4. Radius scale

| Token              | Value | Usage                                   |
| ------------------ | ----- | --------------------------------------- |
| `--radius-frame`   | 14px  | Outer app frame                         |
| `--radius-control` | 8px   | Artwork tiles, search field, buttons    |
| `--radius-nav`     | 6px   | Sidebar active/hover row                |
| `--radius-full`    | 50%   | Circular elements only (profile button) |

No pill-shaped elements. No single uniform radius applied to everything — this is a small intentional scale, not one `rounded-lg` reused everywhere.

---

## 5. Spacing & grid

- Major section gap: 34px
- Section label → content gap: 14px
- Tile grid gap: 20px
- Header padding: 14px 20px
- Body padding: 26px 22px 30px
- Sidebar row padding: 7px 10px, 10px icon-to-label gap
- Header grid: `grid-template-columns: 1fr auto 1fr` — keeps the search field
  genuinely centered regardless of left/right content width, not just visually
  approximate.
- Tile grid: `repeat(auto-fit, minmax(130px, 1fr))` — reflows naturally as the
  sidebar opens/closes or the viewport changes, no fixed column count.

---

## 6. Iconography

- **UI chrome** (menu, search, profile, sidebar nav): Tabler Icons, outline style. Generic is fine here — navigation icons aren't a branding opportunity, and forcing originality onto them adds noise without adding meaning.
- **Music / brand glyph**: a custom three-bar equalizer mark (flat SVG fill, no gradient), in two tonal variants — neutral gray (`--color-accent-icon-trending`) and blue-tinted (`--color-accent-icon-friend`). This is the one recurring original visual signature. Reuse it as the logomark, the album-art placeholder before real artwork loads, and anywhere else "this is music" needs representing without a real image — loading states, empty states, and eventually the Melody object itself.

---

## 7. Layout patterns

**AppShell** — collapsible sidebar (width-animated open/close, pushes content in normal flow — never `position: fixed` or an overlay), header as a 3-column grid (menu + logo / search / profile icon).

**TrackTile** — artwork + title + artist. No border, no card background, no shadow around the tile itself. Separation between tiles comes entirely from grid gap and whitespace. This is the single highest-leverage rule in this document: the bordered mini-card grid was the main thing reading as generic/AI-templated in earlier passes, independent of any color choice.

**Friend-sourced tiles** — distinguished from neutral tiles by artwork tint (`--color-surface-tile-friend`) and a small dot + name caption beneath the artist line. Not by a colored border, and not by an avatar-initial bubble overlapping the artwork — both were tried and rejected as too decorative for what's a small piece of metadata.

**Primary action button** — `bg-accent text-canvas` background (`#2f8cff` / `#0b0d12`), `rounded-control` radius (8px), 14px / weight 500, no border, no shadow (the focus ring in §8 is the only permitted shadow). The accent color is used here because the action is the point — this is not a nav element, not a secondary affordance. Secondary actions use a surface control background (`bg-control`) with `text-primary`.

**CoverArt component** (`components/CoverArt.tsx`) — two modes:

- **Fixed-size** (default, `fill={false}`): renders a sized `<div>` wrapper with `object-cover` inside. Pass `size` in px (default 48). Fallback on missing or failed src: a `bg-tile` placeholder div, no glyph.
- **Fill mode** (`fill={true}`): renders via Next.js `<Image fill>` inside an `absolute inset-0` wrapper. **Requires** the parent to be `position: relative` with explicit pixel dimensions. Fallback: returns `null` — the parent's background and any sibling placeholder glyph show through. Use this mode for tile artwork that must fill an arbitrary parent area.

---

## 8. Motion

- Tile hover: `transform: translateY(-2px)`, ~150ms ease. That's it.
- Sidebar open/close: width transition, ~200ms ease.
- The _only_ permitted shadow anywhere: a 1.5px solid focus ring (`box-shadow: 0 0 0 1.5px rgba(47,140,255,.6)`).
- Focus ring is applied **globally** via `:focus-visible` in `globals.css` so every
  interactive element (buttons, links, inputs, selects) gets a consistent ring on
  keyboard navigation. Mouse clicks suppress it (`:focus-visible` vs `:focus`).
  Do not override this with `outline: none` unless the element has an equivalent
  visible focus state.
- No parallax, no scroll-triggered fade-ins, no scroll jacking, no decorative motion.
  Respect `prefers-reduced-motion` — already implemented for tile-hover and sidebar
  transitions in `globals.css`.

---

## 9. Anti-pattern guardrails (unslop-ui)

Check against these before calling any screen done — see `unslop-ui`'s
`references/tells.md` for the full data behind each:

- No repeated `border + border-radius + padding` div pattern around list items (the shadcn `Card` tell) — this document's tile pattern exists specifically to avoid it.
- No purple/indigo/violet anywhere, including in disabled or secondary states.
- No cream/beige background paired with a serif display font and a sage/green accent (the "tasteful default" tell) — not a risk given the dark theme, but worth naming so it's never reached for in a light-mode variant later without a real decision.
- No unprompted glow or blur on the dark surfaces. Dark mode is fine; glow without a stated reason is the tell, not darkness itself.
- No emoji used as icons.
- No centered-hero-plus-three-feature-cards skeleton on any marketing-adjacent surface
  (settings empty states, onboarding, etc.).
- Inter and Geist are not used without a stated reason. Space Grotesk is this
  project's stated display choice, for the reasons in §3.

---

## 10. Sidebar Navigation

Four fixed links rendered inside `AppShell`'s collapsible sidebar. Implemented in `frontend/src/components/AppShell.tsx`.

| Link     | Route           | Icon      | Visibility     |
| -------- | --------------- | --------- | -------------- |
| Home     | `/`             | House     | Always visible |
| Search   | `/search`       | Magnifier | Always visible |
| Profile  | `/u/[username]` | Person    | Signed-in only |
| Settings | `/settings`     | Gear      | Always visible |

**Active state:** `background: rgba(255,255,255,0.06)` (`--color-nav-active`) set via inline style when the link is active. Active links also carry `aria-current="page"` for accessibility. Inactive links show `rgba(255,255,255,0.04)` (`--color-nav-hover`) on hover, suppressed when the link is already active.

**Active matching rules:**

- Home: exact match `pathname === "/"`
- Search: `pathname.startsWith("/search")`
- Profile: `pathname.startsWith("/u/[own username]")` — sub-pages (`/followers`, `/following`) also trigger active
- Settings: `pathname.startsWith("/settings")`

**Signed-out behavior:** Profile link is conditionally rendered only when `useUser()` returns `isSignedIn === true` with a non-null `user.username`. Home, Search, and Settings are unconditional.

---

## 11. Search

### SearchBar dropdown

The search dropdown lives in `components/SearchBar.tsx` and is attached to the
header input. It fetches catalog and user results in parallel; either fetch may fail
without suppressing the other.

**Section order** (top to bottom, each section omitted if empty):

| Section | Contents            | Item layout                                                                                              |
| ------- | ------------------- | -------------------------------------------------------------------------------------------------------- |
| People  | User search results | AvatarImage (28px, circular) · display_name (primary, 500wt) · @username (11px, `--color-text-tertiary`) |
| Artists | Catalog artists     | ArtworkThumb (32px, circular) · name · disambiguation (11px, tertiary)                                   |
| Albums  | Catalog albums      | ArtworkThumb (32px, 6px radius) · title · artist · year (tertiary)                                       |
| Tracks  | Catalog tracks      | Music-note icon box (32px) · title · artist · album · duration (right, tabular)                          |

Section dividers: `1px solid rgba(255,255,255,0.07)` between sections when more than
one is visible. No divider above the first section.

Section labels: 11px, uppercase, 0.6px tracking, `--color-text-tertiary`, Space Grotesk.

### URL sync

When the user is on `/search`, each debounced SearchBar query also calls
`router.push("/search?q=…")` so the page body re-fetches and stays in sync.
On all other routes, the SearchBar dropdown operates in-place without touching the URL.

### /search page empty state

Shown when `?q` is absent or shorter than 2 characters:

- `EqualizerGlyph` at 36px, fill `#8b93a3` (`--color-text-secondary`), horizontally
  and vertically centered (80px top padding, flex column).
- Label: `"Search for music or people"` — 14px, Space Grotesk, `--color-text-secondary`.

### /search page results

Same People / Artists / Albums / Tracks section order as the dropdown, capped at 10
items per section. Item layout uses 40px artwork (circular for artists and people,
8px radius for albums). Results are rendered in `app/search/page.tsx`.

---

## 12. Ratings & Reviews

### RatingComposer props

`components/RatingComposer.tsx` accepts an optional `initialRating` prop:

```ts
initialRating?: { score: number; review_text: string; visibility: string }
```

When `initialRating` is provided:

- The score button for that score is pre-selected (`aria-pressed="true"`).
- The text field is pre-filled with the existing review text.
- The visibility selector is set to the existing visibility.
- The submit button label reads **"Update review"** instead of **"Submit review"**.

When `initialRating` is absent:

- The form is blank.
- The submit button label reads **"Submit review"**.

After a successful submit, `RatingSection` updates its `ownReview` state and passes it back as `initialRating`. The `useEffect` in `RatingComposer` syncs the form to the saved state, so the composer always reflects what the user last submitted without requiring a page refresh.

### RatingSection optimistic update logic

`components/RatingSection.tsx` finds the signed-in user's existing review on mount:

```ts
initialReviews.find((r) => r.reviewer.username === ownUsername);
```

On submit (`handleSubmitted`), the reviews list is updated by:

1. Filtering out any row that matches **either** `r.id === rating.id` or
   `r.reviewer.username === rating.reviewer.username`.
2. Prepending the returned rating.

This means an update **replaces** the existing row (list length unchanged) and a
new review **inserts** a new row (list grows by one). The double-filter guards
against the backend upsert returning an unexpected ID change, and makes the intent
explicit in the code.

### Profile page — follower/following links

The follower and following counts on `/u/[username]` are rendered as `<Link>`
elements pointing to `/u/[username]/followers` and `/u/[username]/following`
respectively. They carry `hover:text-accent` (`--color-accent`, `#2f8cff`) to make
their clickable nature visually apparent on hover. No underline is shown by default.

---

## 13. Component primitives (shadcn/ui)

**Founder-ratified 2026-07-20** (spec:
`docs/specs/frontend-data-layer-foundation.md`). shadcn/ui is the official
primitive layer for interactive controls — Button, Input, Textarea, Select,
Dialog, Form, Label — adopted for its interaction behavior and
accessibility (Radix), **not** its visual language. The rules:

- Every shadcn component is restyled onto the tokens in this document at
  install time: colors from §2, radii from §4, type from §3. shadcn's
  default theme variables are remapped to the existing `@theme` block in
  `globals.css`, never added alongside it.
- The `Card` component is not installed. The bordered-card-grid ban in
  §1/§7/§9 stands unchanged — adopting shadcn does not relax any visual
  rule in this document.
- Focus states come from the existing global `:focus-visible` ring (§8);
  per-component ring utilities are stripped from generated components.
- New interactive controls use these primitives instead of hand-styled
  elements; existing components migrate opportunistically, not in a
  big-bang rewrite.
- Form validation pairs these primitives with react-hook-form + zod;
  validation rules live in zod schemas, not scattered input attributes.

---

## 14. Provenance

This file is the implementation source of truth for the `@theme` block in `frontend/src/app/globals.css` (Tailwind v4 — no `tailwind.config.js`) and for every new or retrofitted component. Token names in this doc map directly to the `--color-*`, `--radius-*`, and `--font-*` custom properties declared there. If a screen needs a value not listed here, that's a signal to add it deliberately — to this document first, then to `globals.css` — not to improvise locally and let the system drift.
