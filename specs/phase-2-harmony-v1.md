# Harmony v1 — Personal Reception Signal

> **Status: DRAFT — awaiting Founder approval.** Prepared 2026-09-08.
> The Founder requested Phase 2 implementation, “harmony messaging,” and
> third-party song access. This proposal makes the missing Harmony product
> decisions reviewable; it does not claim those decisions are ratified.
> Tier 1 under WORKFLOW.md §1. No feature code has been written.

## Purpose

Help a person understand how their recommendations resonate with the people
they chose to send music to. This strengthens Trust Between Users and
Discovery Through People (BRAND_BIBLE.md §3). Harmony belongs on a profile,
never in rankings, Home, notifications, or comparison surfaces
(ENGINEERING_BIBLE.md §3 and §6).

## Scope

### In scope — proposed

- A Harmony section on the owner's profile, calculated from their sent
  Melodies, with acceptance and sustained-reception information.
- Explicit private / friends / public visibility for a separate, positive-only
  summary. Default private for existing and new accounts.
- Continued message-less Melody sharing, including the existing send,
  receive, accept, open, reject, and recovery paths.
- Streaming access described in `phase-2-streaming-access.md`.

### Out of scope

- Text conversations or text attached to a Melody, pending clarification of
  “harmony messaging.” ADR 0009 currently excludes message text.
- Leaderboards, score sorting, badges, notifications about score changes,
  ranking input, automated Melodies, and cosmetic Harmony v2 features.
- The other draft Phase 2 features, and integration of `beta-ui`.
- Provider listening data as input to Harmony.

## User experience — proposed

The owner sees Harmony below their profile identity, in a quiet section using
the current design system. An explanation describes precisely which Melody
outcomes count. With no resolved Melodies, show “No responses yet,” rather
than 0% or a low score. The owner can choose who sees the positive-only
summary; the rate and numerical details always remain owner-only.

Loading and failure affect only this section. A failed request never appears
as a score of zero. Hiding the summary takes effect on the next request,
including after a previously authorized response was cached by a client.

The existing Melody inbox continues to use music cards and recipient actions.
“Open” records an intentional opening; it does not prove completed playback
inside another service. Streaming, saving, or following an external link never
sends a Melody automatically or changes its outcome implicitly.

## Functional requirements — proposed decisions for ratification

1. **Owner acceptance rate:** `100 * positive / resolved`, rounded to the
   nearest whole percent, where positive is accepted + opened and resolved is
   accepted + opened + rejected. Sent/received are excluded. No resolved
   Melodies yields no rate. Count a Melody once; an accepted-to-opened upgrade
   does not add another positive. Recovery from rejection changes the current
   result, rather than creating another event.
2. **Owner sustained reception:** show the number of calendar months, among
   the current UTC month and previous five months, in which the owner sent a
   Melody that currently has a positive outcome. Use `created_at` explicitly:
   the existing `responded_at` is overwritten on an acceptance-to-open upgrade
   and cannot establish first-positive timing. Copy must describe the sending
   month, not invent a historical listening or acceptance timestamp.
3. **Other viewers:** never return the rate, denominator, rejection count,
   recipient identities, track identities, or individual response timestamps.
   Subject to visibility, a positive-only summary says “Your music has found
   listeners” after a positive outcome, and “Finding resonance over time” when
   positive outcomes span at least three sending months in the six-month
   window and at least three distinct recipients in that window. These exact
   thresholds and copy are proposed product choices, not existing rules.
4. **Rejection protection:** changing a pending Melody to rejected must have
   no effect on any non-owner response. Sharing an acceptance percentage can
   expose rejection through subtraction, particularly with a small sample;
   therefore this draft keeps all negative-sensitive details owner-only.
5. **Visibility:** perform authorization before aggregation, using existing
   scope semantics. “Friends” uses the current mutual-follow definition;
   this work must not implement the unapproved friend-request spec. Do not
   expose the chosen visibility setting to other viewers.
6. **Disclosure:** explain to a Melody recipient that positive responses can
   contribute to the sender's aggregate Harmony summary, while “Not for me”
   remains private. Whether pre-existing positive responses may contribute to
   a newly shared summary requires explicit Founder ratification below.
7. No third-party content, engagement analytics, profile customization,
   follower counts, or unrelated activity changes the calculation.

## Acceptance criteria

- [ ] Founder resolves the naming/scope question and ratifies the calculation,
      public-summary policy, thresholds, and historical-data decision.
- [ ] Empty, pending-only, mixed outcomes, recovery, and accepted-to-opened
      upgrades produce the documented owner results.
- [ ] Month boundaries, repeated recipients, and UTC boundaries are covered.
- [ ] Changing pending to rejected never changes a non-owner payload.
- [ ] Owner / anonymous / unrelated / mutual-follow / suspended-user cases
      respect visibility, including immediate revocation.
- [ ] No aggregate response contains recipient identities or Melody details.
- [ ] Profile and existing Melody flows work through the real frontend,
      backend, and disposable PostgreSQL database.
- [ ] Existing account, catalog, rating, follow, and notification regressions
      pass, along with the required static checks and build.

## Design requirements

Follow BRAND_BIBLE.md §6, §8, and §10. Harmony is understated and explanatory.
No red/green judgment, celebratory animation, progress goals, or percentile
comparisons. Preserve current typography and spacing; `beta-ui` stays separate.

## Technical notes

- Isolate aggregation in a domain service, with thin API handlers and a
  profile component. The frontend never computes a score.
- Add only a private-default visibility column if the shared summary is
  ratified. No backfill of inferred listening events or response timestamps.
- Use indexed sender-scoped database aggregation; do not load an unbounded
  inbox into application memory. Do not persist a second score that can drift.
- No shared HTTP caching of responses containing Harmony or visibility data.
- Confirm indexes and query plans against representative synthetic histories.

## Rollback plan

Gate the feature independently. Turning it off restores existing profile
behavior without changing Melody rows. Preserve any additive setting column
on rollback; do not drop production data to roll application code back.
Test old-client/new-backend and new-client/old-backend behavior before release.

## Open questions requiring Founder decision

1. Does “harmony messaging” mean the Harmony signal plus existing Melody
   song cards, or new text conversations? This proposal recommends the former.
2. Approve the proposed owner rate and positive-only shareable summary, or
   specify another model? Exact acceptance/rejection-sensitive details cannot
   be shared without revisiting the existing rejection-privacy contract.
3. May already-recorded positive responses contribute to an explicitly shared
   summary, or should only responses after the new disclosure be eligible?
   No historical-data use is authorized by this draft.

## Verification record

Baseline on `dev` commit `f584650`, before implementation:
`cd backend && poetry run python -m pytest -q` completed with **705 passed,
1 expected failure**, using Testcontainers and real PostgreSQL. The expected
failure is the existing follow rate-limit test's ASGITransport limitation.
These results validate the starting point, not this unimplemented feature.

The implementation test plan is in
`docs/reviews/phase-2-v1-test-plan.md`.
