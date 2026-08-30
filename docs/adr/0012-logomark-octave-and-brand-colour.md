# ADR 0012 — Logomark: the Octave wave, and a logo-only neon accent

**Date:** 2026-08-30
**Status:** Accepted
**Deciders:** Founder

---

## Context

Harmoniq had no logomark. `EqualizerGlyph.tsx` — the three-bar equalizer
introduced in DESIGN_SYSTEM.md §6 — was doing three jobs at once: album-art
placeholder before real artwork loads, generic "this is music" glyph in empty
and loading states, and, by default rather than by decision, the logo in the
app header and on the signed-out landing.

That overloading is a problem for a product whose identity is the point. A
placeholder that appears hundreds of times per session cannot also be the mark
that means "Harmoniq" — the mark stops carrying identity and becomes chrome.

Three directions were drawn and reviewed:

- **Note Q** — the terminal `q` of the wordmark drawn as a quarter note.
- **Level H** — an H whose legs are unequal equalizer bars, continuing the
  existing glyph's shape language.
- **Octave** — two waves in a 2:1 frequency ratio, crossing the centreline
  together at shared nodes.

The Founder selected Octave, then four forks of it (the wave alone, an H built
around the wave, the wave sampled into vertical level bars, and those bars
arranged as an H). The unmodified wave — fork C1 — was selected.

A neon cyan-blue was requested alongside it, against a stated reference of
Tron's blue and the dark, restrained interfaces of Spotify and Steam.

## Decision

**1. The Harmoniq logomark is the Octave wave.** Two curves over a shared
centreline: a fundamental of one period across the frame, and an overtone at
twice the frequency, meeting it at every node. Flat stroke, round caps, no
gradient and no glow.

**2. The brand colour is `#19d8ff`, and it is logo-only for now.** It is
recorded as `--color-brand` in DESIGN_SYSTEM.md §2 and is deliberately *not*
the same value as `--color-accent` (`#2f8cff`), which remains the UI token for
focus rings, active navigation, and primary buttons.

**3. `EqualizerGlyph` keeps its in-product role and loses its logo role.** It
remains the album-art placeholder and the music glyph in empty/loading states.
It is no longer the logomark.

**4. The wordmark is a React component, not an `.svg` asset.** The word is
live text in Space Grotesk (already loaded by `next/font` in `layout.tsx`); the
wave is geometry beneath it.

## Rationale

- **The mark states the product's thesis.** Harmony is the profile-level
  signal the whole social mechanic resolves to (BRAND_BIBLE §6). An octave is
  the one interval every listener hears as agreement. The mark is therefore a
  picture of two things resonating, not a generic audio squiggle.
- **It is ownable in a crowded space.** Bar-and-equalizer marks are the most
  saturated shape language in music software; the rejected Level H sat squarely
  in it. The second wave and the shared nodes are what make this specific.
- **Splitting brand colour from UI accent avoids an unforced regression.**
  `#2f8cff` was contrast-verified against `#0b0d12` (DESIGN_SYSTEM.md §2) and
  is load-bearing for the focus ring that every keyboard user depends on.
  Re-pointing it to a neon cyan is a separate change with its own WCAG work;
  bundling it into a logo decision would have smuggled an accessibility change
  through a branding review.
- **A component wordmark avoids a font trap.** An `.svg` wordmark with live
  `<text>` renders in a fallback face on any machine without Space Grotesk;
  outlining the letterforms requires vector tooling this repo does not have.
  In-app, the font is already loaded, so a component is both correct and
  simpler.

## Consequences

- `frontend/src/app/icon.svg` and `frontend/src/app/apple-icon.tsx` now serve
  the mark as the browser tab icon and iOS home-screen icon. The apple icon is
  generated at build time by `next/og` because nothing in this toolchain can
  rasterise an SVG and Apple touch icons must be PNG.
- `frontend/src/app/favicon.ico` still exists and still wins the
  `/favicon.ico` slot. It must be deleted for the new mark to appear
  consistently — see `docs/BRAND_ASSETS.md`.
- `OctaveMark.tsx` and `Wordmark.tsx` exist but are **not wired into
  `AppShell`**. The header, the signed-out landing, and every other surface
  still render `EqualizerGlyph` as the logo. Rewiring waits on the beta-UI
  mockup review.
- A new stated motion exception, `.octave-draw`, is recorded in
  DESIGN_SYSTEM.md §8. It is scoped to Melody arrival only.

## Open questions

- **Does `--color-accent` move to the neon?** Deferred. It requires re-running
  the WCAG AA checks in DESIGN_SYSTEM.md §2 for the focus ring, primary button
  foreground, and `.listening-now-row` border, and deciding whether the
  friend-tile tints (`--color-surface-tile-friend`, `--color-friend-dot`,
  `--color-accent-icon-friend`) shift with it. Until then the product is
  deliberately two-blue: neon in the mark, `#2f8cff` in the interface.
- **Does the mark replace `EqualizerGlyph` in the Melody card?** The Melody is
  the one object whose provenance is a person, which is what the octave
  encodes. Raised by the mockups; not decided here.
