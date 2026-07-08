# Review Packet — ENGINEERING_BIBLE.md / BRAND_BIBLE.md change (docs pass, 2026-07-07)

**Date prepared:** 2026-07-07
**Prepared for:** Founder (ratification decision)
**Status:** Founder decision already given verbally in-session; this packet
is the formal record required by HARMONIQ.md §7 and the amendment
discipline the Bible itself prescribes.

---

## Why this packet exists

During implementation of the Melody feature, the Founder gave a direct
correction that overrides the then-current wording of both
ENGINEERING_BIBLE.md §3 and BRAND_BIBLE.md §5:

> "A melody should not have a message. It should be an interactive element
> of the page and contain a UI embed of a song/album, artist, and cover,
> with a name of who its from."

The prior wording (carried since the file's original draft, predating even
the 2026-07-04 lifecycle amendment) described Melody as carrying "an
optional short context message." That was never updated when the lifecycle
was amended on 2026-07-04, because the lifecycle amendment addressed the
Accept/Open/Reject state machine, not the message field. This packet closes
that gap.

## What changed

### ENGINEERING_BIBLE.md §3 (Melody definition paragraph)

**Before:**

> A Melody is something one user sends to another: a directed
> recommendation of a single track, carrying a sender, a recipient, an
> optional short context message, and a timestamp.

**After:**

> A Melody is something one user sends to another: a directed
> recommendation of a single track, carrying a sender, a recipient, and a
> timestamp — no message field. It renders as an interactive embed card
> (cover art, track title, artist, sender identity), not a text composer;
> the track itself is the gesture.

### BRAND_BIBLE.md §5 (Core Social Object: Melody)

**Before:**

> It contains:
> - Song (title + artist)
> - Sender identity
> - Optional short context message (lightweight)
> - Timestamp

**After:**

> It renders as an interactive embed card:
> - Cover art
> - Song (title + artist)
> - Sender identity ("From \<name\>")
> - Timestamp
>
> There is no message field. The track itself is the gesture — a Melody is
> not content, and it is not a text composer.

## Assessment

- This is a genuine scope change, not a paperwork catch-up: it removes a
  planned free-text UGC field entirely. Side effect worth recording — this
  means Melody has **zero user-generated text**, which in turn means there
  is no melody-report path needed (nothing to report). That simplification
  was already reflected in the shipped implementation (`services/melody.py`,
  `models/melody.py` — no `message` column exists) and in
  `specs/phase-1-melody.md` (written in this same docs pass).
- Cover art requirement means the embed card depends on Cover Art Archive
  availability; tracks/albums without cover art fall back to the existing
  placeholder treatment already used elsewhere in the catalog UI (no new
  design needed).
- No other section of either document references a Melody message field.
  §5.3 of BRAND_BIBLE.md ("It is closer to a message than a feed item...")
  was checked and left as-is — that line describes the UX register
  (notification-style, ephemeral, personal) of the delivery mechanism, not
  a text content field, and remains accurate.

**Recommendation:** ratify as-is. This is documentation catching up to a
decision already made and already shipped.

## Founder sign-off

- [x] ENGINEERING_BIBLE.md §3 edit: **approved and applied** (Founder,
  mid-implementation, 2026-07-07 session)
- [x] BRAND_BIBLE.md §5 edit: **approved and applied** (Founder,
  mid-implementation, 2026-07-07 session)

Process note: unlike the 4be872d incident, this edit did not ride inside a
feature commit — it is being applied as its own documentation change,
consistent with the process note recorded in
`docs/reviews/engineering-bible-855d2ac-to-4be872d.md`.
