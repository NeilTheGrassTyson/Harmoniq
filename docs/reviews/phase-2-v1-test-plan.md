# Phase 2 v1 — Verification and Release Plan

**Date:** 2026-09-08. **State:** preparation, not an implementation report.
**Lane:** `feat/astra-harmoniq-v1`, based on `dev` at `f584650` after PR #73.

The feature proposals are `specs/phase-2-harmony-v1.md` and
`specs/phase-2-streaming-access.md`. Their open product decisions must be
ratified before dependent code is written (WORKFLOW.md §1).

## Baseline evidence

- Read the root/stack AGENTS files, constitution, Engineering Bible, workflow,
  GitHub workflow, Melody spec/ADR, roadmap, and affected source paths.
- Docker is available in this session (server 29.5.3), despite the earlier
  environment limitation. Install locked dependencies in the isolated
  worktree; leave Claude's worktrees and `beta-ui` alone.
- `cd backend && poetry run python -m pytest -q`: **705 passed, 1 xfailed**
  in 29.65 seconds, with Testcontainers PostgreSQL and Alembic migrations.
  Used local CI placeholders for required settings, not production secrets.
- The expected failure is the existing follow rate-limit test, whose marker
  documents the ASGITransport limitation. Real HTTP rate-limit behavior must
  be tested when adding network-level coverage; an xfail is not proof of it.
- Frontend verification for the unchanged baseline was completed in PR #73:
  337 tests, types, lint, formatting, production build, CI, and Vercel preview.
  Rerun the complete gate after feature implementation.

## Coverage matrix

| Area                  | Test layer                       | Required cases                                                                                                                            |
| --------------------- | -------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------- |
| Harmony arithmetic    | Unit                             | Empty, pending only, mixed results, rounding, recovered rejection, upgrade counted once                                                   |
| Sustained reception   | Unit + DB                        | UTC month boundaries, stable sending-month semantics, repeated recipients, threshold edges                                                |
| Harmony privacy       | API + PostgreSQL                 | Owner/anonymous/unrelated/mutual/suspended viewers; private/friends/public; hide after prior read; no rejection-sensitive non-owner delta |
| Melody regression     | API + browser                    | Send, notification, receive, accept, open, reject, recovery, no read-receipt leak, consent scopes, duplicate send                         |
| Provider mapping      | Unit + HTTP contract             | Exact recording relations, absent/ambiguous mappings, no album-as-song match, malformed IDs, provider errors, timeout, bounded cache      |
| URL safety            | Unit + browser                   | Scheme/host/port/userinfo/path rejection, encoded titles, new-tab isolation, no private data in requests                                  |
| Spotify consent       | HTTP + DB                        | Existing read-only connection, explicit scope upgrade, canceled consent, insufficient scope, expired/revoked tokens, disconnect           |
| Spotify writes        | HTTP + DB + designated live test | Active caller, owned playlist, pagination, wrong-owner request, Liked Songs, duplicate click, 401/403/429/5xx, uncertain append timeout   |
| New UI                | Component + browser              | Empty/loading/error/success, desktop/mobile, keyboard/focus, exact/search distinction, failed section leaves main flow usable             |
| Cross-version rollout | Integration + built app          | Old frontend/new API and new frontend/old API; additive migration; switches off; rollback retains data                                    |
| Existing product      | Full suites + browser smoke      | Signup/onboarding/auth, catalog/search, ratings/visibility, follows, notifications, profile/settings                                      |

## End-to-end environment

Use a disposable PostgreSQL database with synthetic accounts, catalog rows,
and Melody histories. Run the real FastAPI server and built Next.js app on
local ports. Keep authentication fixtures confined to test infrastructure;
do not add a production auth-bypass switch. Obtain designated test-account
sessions for the real authentication smoke path.

Mock provider HTTP boundaries for deterministic fault coverage. Also perform
read-only live link checks for representative recordings. Report these as
different kinds of evidence: mocked saves do not demonstrate a live provider
grant, and opening a desktop HTTPS link does not demonstrate every mobile
app's handoff behavior. A Vercel preview connected to production Railway is
not an isolated backend test environment.

## Commands and release gate

- Backend: `poetry run ruff check .`, `poetry run ruff format --check .`,
  `poetry run mypy app`, `poetry run bandit -r app -c pyproject.toml`, then
  `poetry run python -m pytest -q` with real PostgreSQL.
- Frontend: `npm run verify` in full.
- Browser: document the runner, actual scenarios, artifacts, and exact app
  commit; include network failures and horizontal-overflow/focus checks.
- Review performance, design, security/consent, documentation, architecture,
  and migration compatibility per WORKFLOW.md §2. Verify the PR's CI gates.
- Provide an implementation PR into `dev` with the Astra co-author trailer,
  exact test results, limitations, configuration/migration instructions, and
  rollback procedure. Founder merges and performs their own acceptance test.
- Do not deploy to `main`, mutate production data for testing, or claim that
  tests guarantee the live site cannot break. Confidence must be tied to
  the environments and paths actually exercised.
