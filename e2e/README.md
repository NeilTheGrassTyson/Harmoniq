# Isolated Phase 2 browser tests

From `frontend`, install locked dependencies and the Chromium test browser:

```sh
npm ci
npx playwright install chromium
```

With Docker running and backend dependencies installed, run from `backend`:

```sh
poetry run python ../e2e/run.py
```

The runner creates a disposable PostgreSQL container, applies all Alembic
migrations, and runs the actual FastAPI routes, services, JWT verifier and
database. Each run creates its own RSA signing key and a local JWKS/catalog
fixture server. No production data, account, token, or environment file is
used. Dependencies and the font build require network access.

It copies the Next.js source into an ignored `.codex/e2e/` run directory and
builds that copy. Only the Clerk boundary imports are replaced with the
fixtures in this directory. The deployed source has no test authentication
switch. The fixture cookie never authenticates the backend by itself: the
backend verifies the signed bearer token against that run's JWKS.

Playwright exercises desktop and mobile viewports against the built pages and
real API/database. MusicBrainz responses and the Spotify destination page are
controlled fixtures. This verifies Harmoniq's behavior across those boundaries;
it does not verify Clerk's hosted sign-in or a streaming service's native app.

Servers and the container stop on completion. Build/server logs, screenshots,
failure traces, a report and disposable fixture tokens remain in the printed
run directory. Those tokens expire after two hours and only match the deleted
test database/key. The run directory is gitignored. Do not deploy or publish
the copied fixture build or its traces. A normal `npm run verify` independently
validates the original frontend, including its real Clerk imports.

For migration compatibility and query plans, also run from `backend`:

```sh
poetry run python ../e2e/audit.py
```

This separate disposable container starts at the preceding migration, seeds
100 synthetic accounts and 10,000 synthetic pre-migration Melodies, and applies
the new migration. The selected sender still has roughly 100 rows, preserving
the query-plan selectivity of the larger fixture with less setup work.
It checks private defaults, retained history, and old-column insert/update
compatibility. It then captures the actual Harmony service queries and prints
`EXPLAIN (ANALYZE, BUFFERS)` results. These local timings are not production
latency or a concurrent load test.
