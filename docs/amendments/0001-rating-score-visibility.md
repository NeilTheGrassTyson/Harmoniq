# Amendment 0001 — Rating scores as a structurally public signal

**Status:** Ratified by the Founder, 2026-09-07
**Amends:** HARMONIQ.md §6, Consent Before Visibility
**Arises from:** `specs/phase-2-rating-visibility-split.md`

HARMONIQ.md's Amendment Process requires the previous wording, the new
wording, and the reasoning. All three are below. This is the first amendment
to the constitution; the file it amends is meant to be the most stable in the
repository, and this record exists so the change is never just a diff.

---

## Previous wording

> Visibility of identity, activity, and behavior should be explicit, specific,
> and revocable.

## New wording

> Visibility of identity, activity, and behaviour should be explicit, specific,
> and revocable. Where a signal is structurally required for the product to
> function — a numerical rating being the sole case — its publication is a
> condition of participation, disclosed before the user creates it, and the
> user retains the right to withhold the signal entirely by not rating, and to
> withdraw it by deleting the rating.

The rest of §6, including its failure condition, is unchanged.

---

## Reasoning

The rating-visibility split needs a rating's *score* to be unconditionally
public while its *review text* stays scoped. An always-public score is not
revocable in the sense §6 originally meant, so the spec was a direct conflict
with the constitution rather than a gap in it — and a permanent conflict, not
a temporary one, which is why it was handled as an amendment and not as
Constitutional Debt.

The narrowing matters as much as the permission. The clause is deliberately
written to cover exactly one signal. "Structurally required for the product to
function" is not a general-purpose exemption, and the parenthetical naming the
numerical rating as the sole case is there to stop it becoming one. A future
feature that wants always-public data needs its own amendment, not a reading
of this one.

The honest limit, recorded so nobody has to rediscover it: deleting the rating
is the revocation path. That is a weaker guarantee than §6 previously gave.

### Migration: approach C (publish all scores at rollout)

The spec set out three ways to handle ratings that already exist with
`visibility` set to `private` or `friends`, and required one to be chosen
before implementation:

- **A** — grandfather existing non-public ratings, new contract applies only to new ones
- **B** — notify affected users, publish after a grace period
- **C** — publish all scores at rollout

**The Founder chose C**, on the grounds that Harmoniq has no users yet beyond
the Founder and a small number of close friends, so the population whose data
would be retroactively disclosed is both tiny and personally known to them.
The spec recommended A and marked C "not recommended under §6 on any reading";
that recommendation was made without reference to the actual user count, and
the Founder's decision reflects a fact the spec did not have.

Two things follow, and both are conditions on this choice rather than
commentary about it:

1. **The premise must be checked before rollout, not assumed.** The `ratings`
   table defaults `visibility` to `public`, so the affected set is only rows a
   user deliberately made non-public. If that count is zero, C and A are
   behaviourally identical and no disclosure occurs at all. If it is not zero,
   the affected accounts are few enough to be told individually — which costs
   a message, and buys back the informed choice §6's failure condition is
   about.

   ```sql
   SELECT visibility, count(*) FROM ratings GROUP BY visibility;
   ```

2. **C is justified by the current user count, so it expires with it.** This
   reasoning does not survive the first user who is not a personal contact.
   If the rating-visibility split has not shipped by then, the migration
   question must be re-answered rather than inherited.

---

## What this amendment does not do

It does not approve `specs/phase-2-rating-visibility-split.md` for
implementation on its own. It removes the constitutional blocker and records
the migration decision; the spec's remaining acceptance criteria still apply,
and the check in condition 1 above is part of them.
