# ADR 0015 — "Website Appearance": three themes, and the cost of Light

**Date:** 2026-08-30
**Status:** Accepted
**Deciders:** Founder

---

## Context

Harmoniq has shipped as a single dark theme since the design system was
written. Two things pushed on that at once.

First, the Signature surface (ADR 0014's Octave mark, extended into the
profile "listening DNA") acquired a saturated six-hue palette, a glow, film
grain and ~68 animated particles. Its whole aesthetic is dark-native, and the
Founder observed that a deeper black made the hues read better still — on true
black nothing competes with them.

Second, offering a black theme without offering a light one is an accessibility
gap for anyone who finds light-on-dark hard to read.

A naming collision also had to be resolved before either was built.
BRAND_BIBLE §6 already promises "customizable themes" as the *cosmetic* half of
Harmony v2 — chosen by a profile's owner and seen by visitors. That is a
different feature from an app-level appearance preference, and the two were
converging on the same word.

## Decision

**1. Three themes: Light, Dark, Midnight.** **Midnight is the default**
(Founder decision, 2026-09-06, superseding this ADR's original "Dark remains
the default").
Midnight is true black (`#000000`) with near-black surfaces.

**2. They live in Settings under "Website Appearance."** The name is
deliberate — it says *the site as you see it*, which is what distinguishes it
from a profile theme. Recorded in DESIGN_SYSTEM.md §2.2.

**3. "Website Appearance" and Harmony v2 profile themes stay separate** — a
separate control, a separate token layer, and a separate stored field. One is
a viewer preference; the other is a profile owner's self-expression.

**4. Light is accepted as a second treatment, not a second palette.** Its
values are recorded as a starting point and are explicitly **unverified**.

## Rationale

- **Midnight is nearly free.** It inherits Dark's text and accent values
  unchanged — only surfaces drop — so every existing contrast ratio improves
  and no new verification is needed. The Signature gains the most: with
  nothing competing, the halo can come *down* rather than up, because contrast
  is doing the work the glow was doing.
- **Separating the two "themes" now is cheap; later it is not.** If a profile
  theme and an appearance preference ever share a stored field, untangling
  them means a migration plus a visibility review — a profile theme is
  something *other people see*, so it falls under HARMONIQ §6 (Consent Before
  Visibility) in a way an appearance preference never does.
- **Naming it "Website Appearance" rather than "Theme"** keeps the word
  "theme" available for the Harmony v2 feature that BRAND_BIBLE already
  promised to users. Renaming a term users have learned violates
  BRAND_BIBLE §11.3 (Naming Stability).

## Consequences

**Light mode breaks two things rather than degrading them**, and this is the
part worth carrying forward:

- `--color-accent` (`#2f8cff`) measures roughly 3.1:1 on white. That is below
  AA for text, and it is the **focus-ring** colour — so this is an
  accessibility regression, not a cosmetic one. Light needs a darkened accent.
- The entire Signature palette is effectively invisible on white; neon yellow
  lands near 1.3:1. Light needs a separate darkened hue set, and must drop the
  glow, the grain and the particles outright — a halo on white reads as a
  smudge, and glitter needs darkness to glitter against.

So Light is an ongoing maintenance cost: two Signature treatments, forever.
**Dark + Midnight alone is a coherent product** and shipping only those two
remains a legitimate option. That choice is not foreclosed by this ADR.

Other consequences:

- **Implemented 2026-09-27** (beta-ui Phase 3, `docs/specs/beta-ui-implementation.md`).
  Midnight is the base token block in `globals.css`; Dark and Light are
  `data-theme` overrides on `<html>`, set server-side from the
  `harmoniq-appearance` cookie in the root layout. A Server Action writes the
  cookie, and its response re-renders the layout, so switching needs no reload.
  `clerkAppearance.ts` is now a per-theme function. The preference appears in no
  API payload and never reaches the backend.
- Every Light value is contrast-measured in DESIGN_SYSTEM.md §2.2. Two were
  adjusted in the pass: the accent (`#1a64d6`) and tertiary text (`#666c7a`,
  which must clear 4.5:1 on a tile fill as well as on the canvas).
- The Signature itself remains deferred (ROADMAP.md, LATER). Website
  Appearance does **not** depend on it and can ship first.

## Open questions

- ~~Does Midnight become the default?~~ **Resolved 2026-09-06: yes.** Safe to
  do without new contrast work, because Midnight inherits Dark's text and
  accent values unchanged — only the surfaces drop, so every ratio improves.
  Two consequences worth carrying: the app visibly changes for everyone on
  deploy (no stored preferences exist yet, so there is nothing to migrate), and
  **Midnight becomes the base token set with Dark as an explicit override** —
  the inverse of how the tokens are written today.
- ~~Cross-device sync?~~ **Resolved 2026-09-06: not needed.** This confirms the
  cookie-only approach and keeps the backend out of the feature entirely.
- ~~Does Light ship at all?~~ **Resolved 2026-08-30: yes**, as one of the
  three, with a real contrast pass rather than the drafted values (recorded in
  the beta-ui spec; this ADR was not updated at the time).
- ~~System preference ("Auto")?~~ **Resolved 2026-09-27: no.** The server
  cannot know the device setting on first paint, so Auto would bring back the
  flash of the wrong theme that the cookie exists to prevent.
