# ADR 0014 — "Website Appearance": three themes, and the cost of Light

**Date:** 2026-08-30
**Status:** Accepted
**Deciders:** Founder

---

## Context

Harmoniq has shipped as a single dark theme since the design system was
written. Two things pushed on that at once.

First, the Signature surface (ADR 0013's Octave mark, extended into the
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

**1. Three themes: Light, Dark, Midnight.** Dark remains the default.
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

- Nothing is implemented. `globals.css` still defines a single dark theme, and
  no Settings surface exists for this. Building it is Tier 1 under
  WORKFLOW.md — a net-new user-facing feature — and needs a spec.
- Every Light value in DESIGN_SYSTEM.md §2.2 needs a contrast pass before it
  is written into code. They are drafted, not verified.
- The Signature itself remains deferred (ROADMAP.md, LATER). Website
  Appearance does **not** depend on it and can ship first.

## Open questions

- **Does Midnight become the default instead of Dark?** The Founder's reaction
  to true black was favourable. Deferred — changing a default changes the
  product for existing users, which is a different decision from adding an
  option.
- **Does Light ship at all?** See the cost above. Worth deciding deliberately
  rather than by assuming three themes is the natural number.
- **System preference.** Whether "Website Appearance" offers an "Auto" option
  following `prefers-color-scheme`. Not decided; it interacts with which theme
  is the default.
