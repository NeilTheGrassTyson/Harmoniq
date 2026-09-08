# ADR 0013 — Astra Joins as a Second, Equal Engineering Contributor

**Date:** 2026-09-07
**Status:** Accepted
**Deciders:** Founder

---

## Context

The Founder gained access to OpenAI Codex (operating in this project under
the name **astra**) via a student promotion and wants to bring it onto
Harmoniq alongside Claude Code. Codex-family agents read `AGENTS.md` at
startup the way Claude Code reads `CLAUDE.md` — the two files are the
equivalent onboarding mechanism for different tools, not overlapping
config. `frontend/AGENTS.md` already existed but held only Next.js's
auto-generated boilerplate; there was no root or `backend/` `AGENTS.md`,
so astra starting cold at the repo root would see none of HARMONIQ.md,
ENGINEERING_BIBLE.md, WORKFLOW.md, the Tier 1 gate, the Spotify ToS
constraint, or the Windows/Poetry toolchain gotchas that have already cost
sessions (per `docs/setup.md` §10 and the `git log` trail of doc fixes for
exactly this).

`AGENTS.md` has no `@import` mechanism (unlike `CLAUDE.md`), so the
governing docs can't simply be pulled in — each `AGENTS.md` has to name
them and restate the load-bearing constraints inline.

## Decision

1. **Astra is an equal Engineering contributor, not an Advisory role.**
   Per HARMONIQ.md's Governance section, the Engineering role covers
   implementation, software architecture, code quality, technical
   optimization, and refactoring. Astra and Claude Code both fill that
   role with equal standing — same authority, same constraints, no
   elevated or reduced trust on either side. Disagreements between them
   are resolved the same way disagreements between any two contributors
   are resolved under Governance: reasoning and tradeoffs laid out, Founder
   decides.

2. **`AGENTS.md` files were authored at root, `backend/`, and appended to
   `frontend/`** (the existing Next.js block is left intact), each
   restating: the governing-doc reading order, the Tier 1/Tier 2 gate
   from WORKFLOW.md §1, the Spotify ToS constraint on the recommendation
   pipeline, the one-directional branch flow (feature → `dev` → `main`),
   the pre-push "run everything CI runs" commands, and the Windows/Poetry
   venv gotchas. Each file also states it must be kept in sync with its
   `CLAUDE.md` counterpart by hand, since no import mechanism does it
   automatically.

3. **`.codex/` is gitignored**, mirroring the existing `.claude/` entry —
   whatever local, non-portable state a Codex-family CLI keeps (session
   state, local tool config) gets the same privacy treatment Claude
   Code's `.claude/` already gets. `AGENTS.md` itself stays tracked, the
   same way `CLAUDE.md` is tracked: these are project governance docs, not
   local state.

4. **Collision avoidance, not a merge policy change.** Both agents may work
   in git worktrees (already this project's pattern) with distinct
   branch/lane ownership assigned per task, to keep two agents from editing
   the same shared branch concurrently. Each agent's commits carry its own
   `Co-Authored-By:` trailer (`Astra <noreply@openai.com>` /
   `Claude <noreply@anthropic.com>`) so provenance stays auditable per
   ENGINEERING_BIBLE.md §8's audit-logging expectation for mutations.

## Consequences

- Two independent engineering perspectives are now available for spec and
  PR review — useful adversarially (a second opinion catching what one
  agent missed), at the cost of needing explicit lane assignment to avoid
  both agents mutating the same branch at once.
- `AGENTS.md` and `CLAUDE.md` are now two files that must be manually kept
  consistent. This is accepted drift-risk, flagged in both files, rather
  than solved with a generated/symlinked file — this project has already
  been burned once by a symlink-based doc-sharing assumption that broke on
  a different OS (commit `b2765b2`), so a lighter, explicitly-flagged
  duplication was chosen over a second symlink dependency.
- Neither `AGENTS.md` nor `CLAUDE.md` is a substitute for reading
  HARMONIQ.md, ENGINEERING_BIBLE.md, and WORKFLOW.md directly — both files
  are pointers plus a restated safety net, not the source of truth.
