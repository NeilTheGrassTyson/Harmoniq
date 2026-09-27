# ADR 0016 — Online presence lives in process memory, which pins the backend to one process

**Date:** 2026-09-27
**Status:** Accepted
**Deciders:** Founder (feature and consent model), Engineering (storage)

---

## Context

beta-ui Phase 5 adds a friends rail with an **Online** group
(`docs/specs/beta-ui-phase-5-presence.md`). "Online" had never existed:
nothing recorded whether anyone had Harmoniq open. The Founder approved
building it as ephemeral, opt-in state — Private by default, never shown as
"Offline", never stored, never logged.

Presence needs somewhere to live between a heartbeat and a friend's read of it.
The options were the database, a shared cache (Redis or similar), or the
backend process's own memory.

## Decision

**Presence is a map of user id → monotonic time of last heartbeat, in the
backend process's memory** (`backend/app/services/presence.py`). Only users
whose Online status admits anyone are recorded. An entry counts for 120
seconds, then is dropped. A restart forgets everyone.

## Rationale

- **Not the database.** A heartbeat a minute per open tab is write traffic
  with no durable value, and a persisted "last active" column is precisely the
  "last seen" record the spec rules out. Data that must not outlive the moment
  shouldn't be written somewhere built to outlive it.
- **Not a shared cache — yet.** Redis would be a new paid service, a Tier 1
  decision of its own (WORKFLOW.md §1), bought for a scale Harmoniq doesn't
  have.
- **Memory is already the pattern.** The Spotify listening cache
  (`services/spotify.py`) is in-process for the same reasons, and the backend
  runs one process: `Procfile` and `railway.json` start a single `uvicorn`
  with no `--workers`.

## Consequences

- **The backend must stay one process on one replica.** With two, a heartbeat
  lands in one and a friend's read hits the other: people flicker online and
  offline at random. The listening cache already depends on this; presence
  makes it user-visible. `docs/deployment.md` has hit multiple replicas before
  (the "stale replica" troubleshooting entries).
- **Scaling out is a prerequisite change, not a config change.** Before adding
  workers or replicas, move presence (and the listening cache) to a shared
  store. That is the reevaluation condition for this ADR.
- **Deploys and restarts show everyone offline for up to a minute**, until
  their next heartbeat. Accepted: presence is a courtesy, not a guarantee.
- Presence never needs deleting on account deletion, a data export, or a
  migration: there is nothing on disk.
