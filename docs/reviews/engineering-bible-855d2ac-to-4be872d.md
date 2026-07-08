# Review Packet — ENGINEERING_BIBLE.md change in commit 4be872d

**Date prepared:** 2026-07-04
**Prepared for:** Founder (ratification decision)
**Status:** Awaiting Founder review — ENGINEERING_BIBLE.md and
BRAND_BIBLE.md are unchanged until this packet is ruled on.

---

## Why this packet exists

Commit `4be872d` ("feat: navigation, search overhaul, user search, rating
pre-fill", 2026-06-28) modified ENGINEERING_BIBLE.md — a Hierarchy-of-Truth
document — inside a feature commit, with no recorded ratification. Per
HARMONIQ.md §7 (Documentation Is Part of the Product) and the amendment
discipline the Bible itself prescribes, the Founder asked to review the
change before ratifying it.

## What actually changed (the short version)

The raw diff is 659 lines, which overstates the change dramatically. A
whitespace-insensitive diff shows the file was converted from LF to CRLF
line endings (every line "changed" byte-wise, no text changed), plus
**exactly one substantive edit**, in §11 Evolution Strategy.

**Before (855d2ac):**

> Phase 1 (this document): a modular monolith backend, Spotify as the only
> integration, focused on the trust graph, identity model, Melody, Harmony,
> and the Home/Discovery split.

**After (4be872d):**

> Phase 1 (this document): a modular monolith backend, MusicBrainz as the
> canonical music source (on-demand ingestion), focused on the trust graph,
> identity model, ratings, follows, Melody, Harmony, and the Home/Discovery
> split. Spotify is a deferred supplementary integration (account linking,
> "currently playing") — not the data backbone. See CLAUDE.md for Spotify
> API constraints that govern this decision.

Every other section (0–10, 12, 13, and the revision note at the top) is
textually identical between the two commits.

## Assessment

- The §11 edit records what was already true and already decided elsewhere:
  CLAUDE.md documents the Spotify API constraints, ADR 0006 chose
  MusicBrainz as the canonical music database, and ROADMAP.md lists Spotify
  as a supplementary integration. The edit brings §11 into line with those
  documents; it does not introduce a new decision.
- It also adds "ratings, follows" to the Phase 1 feature list, matching
  what was actually built.
- The process was wrong (a governing-doc edit riding inside a feature
  commit), but the content is consistent with the documented record.

**Recommendation:** ratify the §11 edit as-is. The CRLF conversion is
cosmetic churn; normalizing line endings repo-wide (e.g. via
`.gitattributes`) can be handled separately if desired.

## Substantive diff (whitespace-insensitive)

```diff
 ## 11. Evolution Strategy

-Phase 1 (this document): a modular monolith backend, Spotify as the only
-integration, focused on the trust graph, identity model, Melody, Harmony,
-and the Home/Discovery split.
+Phase 1 (this document): a modular monolith backend, MusicBrainz as the
+canonical music source (on-demand ingestion), focused on the trust graph,
+identity model, ratings, follows, Melody, Harmony, and the Home/Discovery
+split. Spotify is a deferred supplementary integration (account linking,
+"currently playing") — not the data backbone. See CLAUDE.md for Spotify
+API constraints that govern this decision.

 Phase 2 (deferred, not designed here): additional music providers, more
 sophisticated similarity modeling.
```

(Full raw diff reproducible with
`git diff 855d2ac 4be872d -- ENGINEERING_BIBLE.md`; whitespace-insensitive
form with `git diff --ignore-all-space 855d2ac 4be872d -- ENGINEERING_BIBLE.md`.)

---

## Proposed further edits (NOT applied — for approval with this packet)

The Founder redefined the Melody interaction model on 2026-07-04. The
current wording in both governing docs no longer matches it. Proposed
replacement text below; on approval these edits are applied to the two
documents in a dedicated docs commit.

### The ratified model (source of truth for the edits)

A recipient of a Melody can:

- **Accept** — take the recommendation without listening now. A positive
  outcome in its own right.
- **Open** — immediately go to a preview and the song/album page. Opening
  is also a positive outcome; it is acceptance plus engagement. (The
  previous separate `previewed (demo)` intermediate state is absorbed into
  Open.)
- **Reject** — dismiss. Recoverable, and visible to the sender only; never
  a notification or penalty visible to anyone else.

Every Melody a user has ever received is stored in a **Melody inbox** — a
user-only page listing each Melody with its sender and what the recipient
did with it (accepted / opened / rejected).

### Proposed edit A — ENGINEERING_BIBLE.md §3, Melody lifecycle paragraph

Replace:

> A Melody has a lifecycle, modeled as an explicit state machine: `sent` →
> `received`, then either `rejected`, or `opened` — opening a Melody is
> itself the acceptance; there is no separate accept step. The demo path
> branches before that: `sent` → `received` → `previewed (demo)` →
> `opened` or `rejected`.
> Rejection is recoverable and visible only to the sender — it must never
> produce a notification or penalty visible to anyone else.

With:

> A Melody has a lifecycle, modeled as an explicit state machine: `sent` →
> `received`, then exactly one of `accepted` (taken without listening),
> `opened` (the recipient goes to a preview and the track/album page —
> acceptance plus engagement), or `rejected`. Both `accepted` and `opened`
> are positive outcomes; `rejected` is recoverable and visible only to the
> sender — it must never produce a notification or penalty visible to
> anyone else. Every received Melody is retained and listed in the
> recipient's Melody inbox (a user-only surface) with its sender and
> outcome; the inbox is part of the domain model, not a presentation
> convenience.

### Proposed edit B — BRAND_BIBLE.md §5.1 (Melody States)

Replace the state list with:

> - **Sent**
> - **Received**
> - **Accepted** (taken without listening)
> - **Opened** (previewed and visited — also a positive outcome)
> - **Rejected** (recoverable)
>
> Each state is intentional and visible in private user (sender/recipient)
> history. Every Melody a user receives is kept in their Melody inbox — a
> user-only page listing each Melody, who sent it, and what the recipient
> did with it.

### Proposed edit C — BRAND_BIBLE.md §5.2 (Recipient Actions)

Replace with:

> When receiving a Melody, the user can:
>
> - **Accept** → take the recommendation without listening right now
> - **Open** → go straight to a preview and the song/album page
> - **Reject** → dismiss without social penalty (recoverable from the
>   inbox)
>
> Accepting and opening are both positive responses. Rejection must remain
> socially neutral to avoid discouraging sharing, and is visible to the
> sender only.

### Ripple effects to note (no edit proposed yet)

- ROADMAP.md's "Demo + Open (Melody enhancement)" NEXT-tier item is
  absorbed by the new Open behavior; the Melody spec should resolve whether
  that roadmap entry is removed or repurposed.
- The Melody inbox is a new user-facing surface and will be scoped in the
  Melody Tier 1 spec, not here.

---

## Founder sign-off

- [x] §11 Evolution Strategy edit (4be872d): **ratified** (Founder, 2026-07-04)
- [x] Proposed edit A (ENGINEERING_BIBLE §3): **approved and applied** (2026-07-04)
- [x] Proposed edits B & C (BRAND_BIBLE §5.1–5.2): **approved and applied** (2026-07-04)

Process note going forward (already agreed): changes to Hierarchy-of-Truth
documents get their own commit (or ADR) and never ride inside a feature
commit.
