# ADR 0009 — Melody Carries No Message; Renders as an Embed Card

**Date:** 2026-07-07
**Status:** Accepted
**Deciders:** Founder

---

## Context

The original Melody design (ENGINEERING_BIBLE.md §3, BRAND_BIBLE.md §5, as
drafted before implementation) described a Melody as carrying "an optional
short context message" alongside the track, sender, recipient, and
timestamp — a small free-text field the sender could attach.

Mid-implementation, the Founder gave a direct correction:

> "A melody should not have a message. It should be an interactive element
> of the page and contain a UI embed of a song/album, artist, and cover,
> with a name of who its from."

A decision was required before the send-flow UI and backend schema could be
finalized: keep the optional message field, or remove it entirely in favor
of a pure embed-card presentation.

## Decision

**A Melody carries no message field, ever.** It is represented as an
interactive embed card: cover art, track title, artist, and sender identity
("From \<name\>"). There is no text input anywhere in the send flow. The
`melodies` table has no `message`/`note`/`comment` column
(`backend/app/models/melody.py`).

## Rationale

- **Identity over commentary.** HARMONIQ.md §1 (Identity Before Engagement)
  frames Harmoniq around musical identity expressed through the track
  itself, not commentary about it — ratings and reviews already own the
  "words about music" surface. A message field on Melody would duplicate
  that role and blur the boundary between "I'm recommending this track" and
  "I have something to say about it."
- **Removes a UGC/moderation surface for free.** A free-text field sent
  directly between two users, outside any public feed, is a common abuse
  vector (harassment, spam links) that would need its own reporting and
  moderation path. Removing it means Melody has zero user-generated text —
  nothing to report, nothing for the Moderation system (ADR-adjacent to
  `specs/phase-1-moderation.md`) to review on this surface.
- **Simplicity.** HARMONIQ.md §4 (Simplicity Before Complexity): the embed
  card is a single, reusable component (`MelodyCard.tsx`) with no
  composer state, no character limits, no draft-persistence concerns.
- **The track already carries intent.** Sending a specific track to a
  specific person, by construction, is the message — HARMONIQ.md's design
  framing for Melody is "a social gesture encoded as music"
  (BRAND_BIBLE.md §5), which this decision makes literal.

## Consequences

- `ENGINEERING_BIBLE.md` §3 and `BRAND_BIBLE.md` §5 amended in this same
  docs pass to remove the message-field language; see
  `docs/reviews/engineering-bible-4be872d-to-docs-pass.md` for the full
  before/after text and Founder sign-off.
- `specs/phase-1-melody.md` documents the embed-card model as the shipped
  behavior, not an aspiration.
- No melody-report endpoint exists or is planned — there is nothing on a
  Melody a recipient could need to report beyond the track itself, which is
  already reportable via the normal rating/entity report path if the track
  metadata itself is the problem (a MusicBrainz data issue, not a Melody
  issue).

## Reevaluation condition

Revisit only if a future Founder-approved feature needs sender-attributable
free text attached to a specific action (a different, purpose-built
mechanism should be spec'd for that — not a retrofit onto Melody).
