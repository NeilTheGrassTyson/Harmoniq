# Rating Visibility — Splitting the Score from the Commentary

> **Status: DRAFT — awaiting Founder approval, and requiring a constitutional
> amendment before it can be implemented.** Tier 1 per WORKFLOW.md §1 ("any
> change to how user data is collected, stored, or shared"). Nothing here is
> implemented.
>
> Raised by the Founder on 2026-09-06 while specifying Highlights, with the
> observation that "this may need a constitutional amendment entirely." It
> does. This is its own spec because it changes the visibility contract for
> every rating surface in the product, not just Highlights.

---

# Purpose

Today a rating is a single unit: a score from 1–10 and a written review, hidden
or shown together by one visibility setting.

The proposal separates them:

- **The numerical score is always public.** It has no visibility setting.
- **The written commentary is friends-only** — reachable behind a "read more"
  affordance, shown only to mutual follows.
- A viewer who cannot see the commentary is offered a **Follow** control where
  the text would be.

**Principle strengthened: Discovery Through People.** A score that is always
readable makes taste legible at a glance, which is what lets one person
evaluate another's recommendations at all. The commentary — the personal,
discursive part — stays within the circle a user has actually accepted.

---

# ⚠️ This requires a constitutional amendment

**HARMONIQ.md §6, Consent Before Visibility**, currently reads in part:

> Visibility of identity, activity, and behavior should be explicit, specific,
> and revocable.

and fails when:

> a user's activity or identity becomes visible without that user's informed
> choice.

An always-public score is **not revocable**. A user who wants their rating of
an album unseen would have no way to achieve it short of deleting the rating.
That is a direct conflict with §6 as written, not a gap in it.

Per HARMONIQ.md's Amendment Process, only the Founder may ratify an amendment,
and it must record the previous wording, the new wording, and the reasoning.
**That amendment must be ratified before this spec is implemented** — this is
not a case for Constitutional Debt, because the conflict is permanent rather
than a temporary exception with a condition for removal.

A possible shape for the amendment, offered for the Founder to accept, revise
or reject:

> Visibility of identity, activity, and behaviour should be explicit, specific,
> and revocable. Where a signal is structurally required for the product to
> function — a numerical rating being the sole case — its publication is a
> condition of participation, disclosed before the user creates it, and the
> user retains the right to withhold the signal entirely by not rating, and to
> withdraw it by deleting the rating.

The honest reading of that: deleting the rating remains the revocation path.
Whether that satisfies §6's spirit is the Founder's judgement, not this
document's.

---

# 🛑 The blocking problem: retroactive disclosure

**This is the part that must not be missed.**

Ratings already carry a per-row `visibility` column
(`backend/app/models/rating.py`), independent of the user-level
`visibility_ratings` master switch. Users therefore already have ratings marked
`private` or `friends` — set deliberately, under the current contract, on the
understanding that the whole rating was hidden.

Making scores unconditionally public would **publish the scores of every
existing private rating**, retroactively, without the author choosing it. That
is precisely §6's stated failure condition, applied to real users' existing
data. It is a disclosure event, not a schema change.

Three ways to handle it, for the Founder to choose. **This spec cannot be
implemented until one is chosen.**

| | Approach | Consequence |
| --- | --- | --- |
| **A (recommended)** | New contract applies to new ratings only; existing non-public ratings are grandfathered and stay fully hidden | No disclosure. Cost: two rating regimes coexist indefinitely, and the model must carry the distinction. |
| **B** | Notify affected users in advance, publish scores after a grace period in which they may delete ratings | Honours consent through informed choice. Cost: a notification flow and a waiting period before the feature lands. |
| **C** | Publish all scores at rollout | Simplest. Publishes data users chose to hide, with no notice. Not recommended under §6 on any reading. |

Whatever is chosen, it belongs in the amendment's reasoning, not only here.

---

# Scope

### In Scope

- Splitting rating visibility into an always-public score and a friends-gated
  commentary.
- Redefining what the user-level `visibility_ratings` switch governs.
- The viewer-facing affordance where commentary is withheld.
- The migration decision above.

### Out of Scope

- Moderation. `hidden_at` already removes a rating from every public surface
  and continues to outrank all of this — a moderated rating discloses nothing,
  score included.
- Highlights themselves (`specs/phase-2-highlights.md`), which consume this
  model but do not define it.
- Any change to scoring, the 1–10 range, or how ratings are written.

---

# User Experience

On any rating surface — a profile, a Highlight, an album page — a viewer sees:

| Viewer | Score | Commentary |
| --- | --- | --- |
| The author | ✅ | ✅ |
| A mutual follow ("friend") | ✅ | ✅ |
| Any other signed-in user | ✅ | ✗ — a **Follow** control in its place |
| A signed-out visitor | ✅ | ✗ — a prompt to sign in |

**The control is a friend request, and it now has a mechanism.** The Founder
described a "follow request button." At the time this codebase had no such
flow — `follow()` and `unfollow()` are one-directional and immediate, and
"friend" was derived from mutual following, so a viewer could not initiate
anything that resolved.

That gap is closed by `specs/phase-2-friend-requests.md` (Founder decision,
2026-09-06: model it on Steam), which makes friendship explicit and
requestable. **This spec depends on it.** Friends-only commentary is a wall
rather than a door until a viewer can ask.

With that in place the control is an honest **Add friend** — a request the
owner accepts or declines. A decline is silent, per the Melody precedent in
ENGINEERING_BIBLE §3, so no one is put in the position of having visibly
refused someone.

Note also, correcting the earlier framing here: explicit friendship is not a
departure from the Bible. §3 already lists "explicit friendships,
one-directional follows, and trust relationships" as distinct types; only the
first was missing from the code.

---

# Functional Requirements

1. A rating's `score` is returned on every surface to every viewer, subject
   only to moderation (`hidden_at`) and the migration decision above.
2. `review_text` is returned only to the author and to mutual follows.
3. Withholding is enforced in the query, at the data-access layer
   (ENGINEERING_BIBLE §8.1) — never by omitting it in the UI. A withheld review
   must not be present in the API response at all.
4. The API must not leak the commentary's *existence* beyond what is intended.
   Decide explicitly whether a viewer may know a hidden review exists (needed
   to render "read more" only when there is something to read) — see Open
   Questions.
5. `visibility_ratings` is redefined to govern **commentary only**. Its
   description in `backend/app/models/user.py` — currently "a master switch
   over every rating surface" — must be rewritten, along with
   `specs/phase-1-ratings-reviews.md`.
6. The per-rating `visibility` column keeps meaning for commentary and must not
   be silently repurposed.
7. `review_text` is currently `nullable=False`: every rating has text. If a
   score-only rating should be possible under the new model, that is a schema
   change and belongs in this spec — see Open Questions.

---

# Acceptance Criteria

- A signed-out visitor sees a score and no commentary, and no commentary text
  appears anywhere in the API response.
- A signed-in non-friend sees a score and an Add-friend control.
- A mutual follow sees both.
- A moderated rating (`hidden_at` set) discloses nothing to anyone but its
  author — score included. Verified by test.
- Whichever migration option is chosen, a test pins it: under **A**, a
  pre-existing private rating's score is still not returned to a stranger.
- Redefining `visibility_ratings` does not change what Home's friends section
  surfaces, which is already friends-scoped
  (`app/services/home.py::_compute_friends_top_tracks`).

---

# Technical Notes

Surfaces that read ratings and will need auditing against the new rule:
`app/services/rating.py`, `app/services/home.py` (friends' top tracks filters
private ratings today), `app/services/user.py` (`ratings_count`),
`app/api/v1/ratings.py`, moderation, notifications, and the catalog detail
pages, which were deliberately split from reviews so that catalog payloads stay
publicly cacheable (`specs/frontend-data-layer-foundation.md`).

**Caching is a live risk.** Catalog responses are publicly cacheable precisely
because they carry no viewer-scoped data. If scores become universally public
they may be cacheable, but any response carrying commentary must never be —
mixing the two into one cacheable payload would serve one user's friends-only
review to a stranger from cache. Keep the split that already exists.

`ratings_count` should be revisited: under the new model, is the count a count
of scores (public) or of readable reviews (viewer-dependent)?

---

# Rollback Plan

Behind a settings flag, default off. Off restores today's unified behaviour
exactly, since the underlying columns are unchanged — this spec changes what is
*returned*, not what is stored. That is what makes rollback clean, and it is
worth preserving that property during implementation.

Under migration option **A**, the grandfather marker must survive rollback so
that re-enabling does not disclose the ratings it was protecting.

---

# Open Questions

_Founder decides._

1. **The migration decision (A, B or C above).** Blocking.
2. **The constitutional amendment wording.** Blocking.
3. **Sequencing.** Friend requests must ship first, or the friends-only tier
   has no way in. That ordering is a decision, not an assumption.
4. **May a viewer know that a review they cannot read exists?** Rendering a
   "read more" affordance only when there is something to read discloses that
   the author wrote something. Always showing the control discloses nothing but
   is misleading when there is nothing behind it.
5. **Should score-only ratings become possible?** `review_text` is
   `nullable=False` today, so rating something currently requires writing about
   it. If the score is the public signal, requiring prose to produce one is a
   meaningful barrier.
6. **Does this change the per-rating `visibility` control at all,** or does a
   user keep setting individual reviews to private/friends/public while the
   score ignores it?
