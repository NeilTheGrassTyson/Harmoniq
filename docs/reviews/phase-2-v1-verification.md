# Harmony, Melody Reactions and Streaming Access — Verification

**Date:** 2026-09-08. **Engineer:** Astra.
**Runtime revision:** `7b45214e5a0fadbd6098d07c8171eb284500fd01`.
**Integration:** [PR #74 into dev](https://github.com/NeilTheGrassTyson/Harmoniq/pull/74).
Founder review, merge and acceptance remain separate from these local checks.
No production data was used or changed. `beta-ui` and other agent worktrees
were not modified. The [PR files tab](https://github.com/NeilTheGrassTyson/Harmoniq/pull/74/files)
is the complete changed-file inventory.

## Approval record

Source: the Founder's conversation with Astra on **2026-09-08**, before
implementation. This records the decisions durably under HARMONIQ.md §7:

1. Recipients should give editable not-for-me, liked, or loved/wants-more
   feedback. The approved interpretation is structured Melody reactions;
   no text conversation feature is included.
2. The Founder approved owner-only reception numbers and an optional,
   positive-only shared summary, including the proposed thresholds. Sharing
   defaults to private; friends means the existing mutual-follow relationship.
3. The Founder explicitly directed that historical and new responses be
   included together, without a legacy partition or mandatory warning.
4. The Founder approved six-service song access. Direct links or clearly
   labeled searches are the accepted baseline. Optional Spotify saving is
   contingent on consent and verified write capability; no writes ship here.

The Founder reaffirmed this scope in the resumption instructions, specifically
requiring XP/points and leaderboards to stay unimplemented. The proposed XP
formula has **no approval**. Harmony DNA and regional/global rankings remain
future ideas requiring a separate spec and governance decisions.

Approved specs: [Harmony](../../specs/phase-2-harmony-v1.md),
[Melody reactions](../../specs/phase-2-melody-reactions.md), and
[streaming access](../../specs/phase-2-streaming-access.md).

## Executed gates

| Gate                      | Commands actually run                                                                                                                              | Result                                                                                          |
| ------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------- |
| Backend static checks     | From `backend`: `poetry run ruff check .`, `poetry run ruff format --check .`, `poetry run mypy app`, `poetry run bandit -r app -c pyproject.toml` | Clean; 122 files formatted; 63 files type checked; no Bandit issues                             |
| Full backend              | `poetry run python -m pytest -q`                                                                                                                   | **778 passed, 1 xfailed**; real PostgreSQL 16 via Docker/Testcontainers; 23.53 s                |
| Frontend full gate        | From `frontend`: `npm run verify`                                                                                                                  | Types, ESLint, Prettier, **365 tests**, production Next.js build passed                         |
| Built-app browser         | From `backend`: `poetry run python ../e2e/run.py`                                                                                                  | **4 passed**, desktop and 390 px mobile; 15.5 s; real HTTP reaction limiter returned 429        |
| Migration and query audit | `poetry run python ../e2e/audit.py`                                                                                                                | Existing users/history and old-column writes preserved; actual aggregate plans use sender index |
| Harness static checks     | `poetry run ruff check ../e2e`, `poetry run ruff format --check ../e2e`                                                                            | Clean, 3 Python files                                                                           |

The backend xfail is the pre-existing follow limiter test's documented
ASGITransport limitation. It is not a new feature failure. The browser runner
separately verified the reaction limiter over real HTTP. The final assertion
clarification in streaming tests was also verified separately: **34 passed**.
GitHub CI results belong to the PR checks for the exact pushed head; local
browser and migration audits are reproducible commands, not new CI jobs.

The resumed failure in `StreamingAccess.test.tsx` was a test teardown issue:
`beforeEach(() => mock.mockReset())` returned the mock, which Vitest invoked
as cleanup after the test. A rejecting mock then threw `unavailable` after
the component had handled 404 correctly. The hook now returns nothing.
Successful older payloads missing `links` are also handled explicitly, and
both cases pass component and built-app browser coverage.

## Coverage and review

- **Reception and privacy:** no responses vs zero reception, pending rows,
  mixed outcomes, rounding, historical responses, status recovery, explicit
  reaction precedence, all 15 status/reaction combinations, sending-month UTC
  boundaries and three-month/three-recipient thresholds. Owner, anonymous,
  unrelated, mutual-follow and suspended callers follow existing policy.
  Suspended users may read, but cannot mutate. Authorization precedes the
  Melody aggregate. Non-owners receive no counts, rates or recipient details.
  A new rejection of a pending Melody causes no shared payload delta.
- **Concurrency and security:** recipient predicates and row locks protect
  edits; repeated choices preserve their timestamps; competing open/reaction
  transactions retain the opinion. No feedback notifications or score counters.
  Private endpoints use no-store; client cache identity includes the viewer
  and stale Harmony is hidden during refetch or failure. URL allowlists reject
  hostile schemes/hosts/ports/userinfo and non-song paths; public link requests
  contain only catalog identifiers/title/artist, with no private account data.
- **Browser and design:** actual built Next.js pages, FastAPI routes/JWT
  verification and disposable PostgreSQL cover send/duplicate prevention,
  receive, keyboard reaction, sender feedback, edit after open, profile
  private/public/friends/revocation, six links, exact/search labels, new-tab
  opener/referrer isolation, private rating create/delete and mutual follows.
  Failed sections, old endpoint 404s and a successful response without links
  leave the main page usable. No page errors or horizontal overflow in the
  main flow. Mobile reaction/profile screenshots were inspected; existing
  typography, restrained colors and wrapping controls are preserved.
- **Architecture:** thin routes, domain-owned aggregation and mapping, shared
  visibility helper, existing MusicBrainz adapter/limiter and design system.
  No persisted score, recommendation model, additional OAuth scope, provider
  token storage, background polling or new paid service. Streaming remains
  separate from catalog detail; mappings have a four-second timeout, bounded
  six-hour cache and coalesced requests. Client requests time out after ten
  seconds; mutations are not automatically retried after uncertain outcomes.
- **Constitution:** musical sharing stays human-initiated. Editable feedback
  improves trust; private numerical detail and explicit summary sharing
  preserve control. Provider access helps users follow a human recommendation.
  No comparison surface, engagement reward or provider-derived scoring input
  is introduced. The approved historical-data decision is recorded above.

The migration audit starts at `f8a9b0c1d2e3`, creates 1,000 users and 100,000
Melodies, then upgrades to `a9b0c1d2e3f4`. All accounts defaulted private;
historical reactions/timestamps stayed null and status response timestamps
were retained. Inserts using only old columns still work; old status updates
do not clear a newly stored opinion. This is SQL/API compatibility evidence,
not a claim that two separately deployed historical app versions were tested.

`EXPLAIN (ANALYZE, BUFFERS)` captured the actual service aggregates: both used
`ix_melodies_sender_id`, scanning 100 of the 100,000 rows. Local warm execution
was **0.177 ms owner / 0.137 ms shared**, with no temporary disk blocks. These
are query timings, not network latency or concurrent-load results. At 100 or
1,000 users the sender-scoped design is sufficient for the expected history.
At 100,000 users, unusually prolific senders, database concurrency and the
process-local provider limiter/cache deserve measurement before optimization;
there is no global-user scan or unbounded in-memory inbox aggregation here.

## External boundaries and known limits

The browser run uses per-run RSA/JWKS and Clerk boundary fixtures only in a
disposable frontend copy. The original frontend build uses the real Clerk
imports. Hosted Clerk sign-in/signup, real-account Spotify writes, mobile
native-app launch and live regional catalog availability are **not verified**
by these fixtures. Optional playlist/liked-song writes are absent; users save
inside their selected provider. Existing account/catalog/social regressions
passed the full backend/frontend suites, not a new hosted-auth acceptance run.

Read-only public HTTP checks on 2026-09-08 used “Only Shallow” by my bloody
valentine: search routes returned 200 for Spotify, Apple Music, YouTube Music,
Deezer and Amazon Music. The [Spotify song route](https://open.spotify.com/track/1KKuoYESWoUGsau6YYoEMl)
also returned 200. Apple redirected `+` spaces into literal plus signs; the
implementation now uses `%20`, whose route returned 200 without that redirect.
TIDAL redirected to `tidal.com/search` then returned **403**. The MusicBrainz
recording API for `af87f70f-14e1-452b-ba66-b3e1be7fbdf1` returned **503**.
These are reachability checks only; no authenticated playback was attempted.
TIDAL and live exact mapping were not established by this smoke run. Their
failure/search behavior is covered by deterministic tests. Exact mapping
coverage remains dependent on recording relationships; search is intentional.

Existing warnings are retained and documented: the duplicate package lock
workspace-root warning, the obsolete `vite-tsconfig-paths` notice, and the
font build's dependency on live `next/font/google` access. These were already
separate calibration candidates and are outside this approved feature slice.
Playwright also reports conflicting inherited NO_COLOR/FORCE_COLOR settings;
this affects test-log coloring only. No ESLint warning was introduced.

Local browser artifacts are in `.codex/e2e/v1-96vauch0/`: logs, report and
screenshots. They contain disposable fixture tokens and must not be published
or deployed. The runner shuts down its servers and database container.

## Release and rollback

1. Founder reviews/merges PR #74 into `dev` and performs acceptance. Production
   release remains the separate `dev` to `main` flow; this PR is not self-merged.
2. Before the new backend starts, run the existing Railway release migration
   command (`alembic upgrade head`). Confirm head `a9b0c1d2e3f4`. It adds
   `users.visibility_harmony` (private default), nullable `melodies.reaction`
   and `reacted_at`, and a reaction check constraint. There is no destructive
   migration or inferred historical-reaction backfill. Application flags do
   not make the new ORM compatible with an unmigrated database.
3. The backend flags `HARMONY_ENABLED`, `MELODY_REACTIONS_ENABLED` and
   `STREAMING_LINKS_ENABLED` default to `true`. No new credentials are required.
   Existing CORS, Clerk and MusicBrainz settings remain necessary. Deploy the
   migrated backend before the frontend when controlling rollout order; the
   new frontend also tolerates older APIs as covered above.
4. To withdraw features, set the affected flags to `false` and restart the
   backend. Harmony/streaming endpoints return 404; the inbox capability flag
   restores prior actions on its next load. Previously cached public streaming
   links can remain until their five-minute client/HTTP cache expires. Stored
   reactions remain visible to the participants and still take precedence in
   Harmony unless Harmony is also disabled.
5. If rolling application code back, **retain the additive schema and user
   feedback**. Do not run an Alembic downgrade against production. The migration's
   destructive downgrade is for disposable databases only. Verify health,
   profile, Melody send/open and catalog/rating paths after either deployment
   or rollback. Provider failures should leave search or section retry paths
   available without blocking those core flows.
