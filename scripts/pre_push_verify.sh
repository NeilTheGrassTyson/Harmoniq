#!/usr/bin/env bash
#
# Pre-push gate: run exactly what CI runs, for the stacks this push touches.
#
# Why this exists: CLAUDE.md and docs/GITHUB_WORKFLOW.md §4 both say to run the
# full check set before pushing, and the failure mode they warn about is not
# forgetting entirely — it is running a *subset*. `npm run lint` passing feels
# like the linting is done; `format:check` is a separate CI step, and skipping
# it turned CI red on 2026-09-07. A rule that depends on remembering is the
# rule that gets skipped at 2am.
#
# Invoked from a Claude Code PreToolUse hook on `git push` (see
# .claude/settings.json), but it is an ordinary script — run it by hand, or
# wire it to .git/hooks/pre-push, and it behaves the same.
#
# With --hook it additionally prints the PreToolUse JSON Claude Code reads, so
# a failure denies the push with the real output as the reason. Without it the
# script is plain text on stderr and an exit code. JSON is assembled with sed
# and awk rather than jq or python, because neither is reliably on PATH in Git
# Bash on Windows, which is where this actually runs.
#
# Contract:
#   exit 0  checks passed, or nothing relevant changed, or a toolchain is
#           genuinely unavailable (reported, not silently swallowed)
#   exit 1  a check failed — with the failing output on stderr
#
# Deliberately NOT failing on a missing toolchain: a fresh clone or a CI
# container without node_modules should not be unable to push. A missing tool
# is reported loudly and separately from a real failure.

set -uo pipefail

hook_mode=0
[ "${1:-}" = "--hook" ] && hook_mode=1

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root" || exit 0

BASE_REF="${HARMONIQ_VERIFY_BASE:-origin/dev}"

# Everything the checks print is echoed to stderr AND captured here, so --hook
# can quote the actual failure back instead of "a check failed, go look".
log_file="$(mktemp "${TMPDIR:-/tmp}/harmoniq-prepush.XXXXXX")"
trap 'rm -f "$log_file"' EXIT

say() { printf '%s\n' "$*" >&2; }

# ── Which stacks changed? ────────────────────────────────────────────────────
# Mirrors the `changes` job in both CI workflows, including core.quotePath=false
# so a non-ASCII path is not quoted out of the ^frontend/ and ^backend/ anchors.
#
# If the base ref is unavailable (no network, fresh clone, detached state) we
# cannot know what changed — so we check everything rather than nothing. A
# pre-push gate that fails open on an unknown diff is not a gate.
changed_paths() {
  git rev-parse --verify --quiet "$BASE_REF" >/dev/null || return 1
  local base
  base="$(git merge-base HEAD "$BASE_REF" 2>/dev/null)" || return 1
  git -c core.quotePath=false diff --name-only "$base" HEAD 2>/dev/null
  # Uncommitted work is not pushed, but a dirty tree usually means the run
  # you are about to trust does not match the commits you are sending.
  git -c core.quotePath=false diff --name-only HEAD 2>/dev/null
  return 0
}

# An EMPTY diff and an UNRESOLVABLE one are different answers and must not be
# conflated. Empty means nothing changed — skip, correctly. Unresolvable means
# we do not know, so check everything. Treating empty as unresolvable would run
# the full suite on every docs-only push, which is how a gate earns its way
# into being switched off.
if paths="$(changed_paths)"; then
  resolved=1
else
  resolved=0
  paths=""
fi

if [ "$resolved" -eq 0 ]; then
  say "pre-push: cannot resolve a diff against $BASE_REF — checking both stacks."
  check_frontend=1
  check_backend=1
else
  printf '%s\n' "$paths" | grep -Eq '^(frontend/|\.github/workflows/frontend-ci\.yml$)' \
    && check_frontend=1 || check_frontend=0
  printf '%s\n' "$paths" | grep -Eq '^(backend/|\.github/workflows/backend-ci\.yml$)' \
    && check_backend=1 || check_backend=0
fi

if [ "$check_frontend" -eq 0 ] && [ "$check_backend" -eq 0 ]; then
  say "pre-push: no frontend or backend files changed — nothing to verify."
  exit 0
fi

failed=""
skipped=""

# ── Frontend ─────────────────────────────────────────────────────────────────
# `npm run verify` and not a hand-picked subset, on purpose: it chains
# typecheck, lint, format:check, tests and build in the order frontend-ci.yml
# runs them, and ciCommandParity.test.ts fails if the two ever drift apart.
if [ "$check_frontend" -eq 1 ]; then
  if ! command -v npm >/dev/null 2>&1; then
    skipped="${skipped}frontend (npm not found) "
  elif [ ! -d frontend/node_modules ]; then
    skipped="${skipped}frontend (node_modules missing — run 'npm ci' in frontend/) "
  else
    say "pre-push: running 'npm run verify' in frontend/ ..."
    if ( cd frontend && npm run verify ) 2>&1 | tee -a "$log_file" >&2; then
      say "pre-push: frontend OK"
    else
      failed="${failed}frontend "
    fi
  fi
fi

# ── Backend ──────────────────────────────────────────────────────────────────
# Poetry is not on PATH on Windows (CLAUDE.md), where `py -m poetry` is the
# documented invocation — try both before declaring it unavailable.
if [ "$check_backend" -eq 1 ]; then
  poetry_cmd=""
  if command -v poetry >/dev/null 2>&1; then
    poetry_cmd="poetry"
  elif command -v py >/dev/null 2>&1 && py -m poetry --version >/dev/null 2>&1; then
    poetry_cmd="py -m poetry"
  fi

  if [ -z "$poetry_cmd" ]; then
    skipped="${skipped}backend (poetry not found on PATH or via 'py -m poetry') "
  else
    say "pre-push: running backend checks ..."
    # Placeholders only. Settings() reads these at import time; nothing here
    # connects to a database. Same values backend-ci.yml uses.
    if (
      cd backend \
        && DATABASE_URL="${DATABASE_URL:-postgresql+asyncpg://ci:ci@localhost/ci_placeholder}" \
           CLERK_JWKS_URL="${CLERK_JWKS_URL:-https://example.clerk.accounts.dev/.well-known/jwks.json}" \
           MUSICBRAINZ_USER_AGENT="${MUSICBRAINZ_USER_AGENT:-Harmoniq/0.1.0 (ci@harmoniq.test)}" \
           APP_ENV=test \
        $poetry_cmd run ruff check . \
        && $poetry_cmd run ruff format --check . \
        && $poetry_cmd run mypy app \
        && $poetry_cmd run bandit -r app -c pyproject.toml -q \
        && $poetry_cmd run pytest -q
    ) 2>&1 | tee -a "$log_file" >&2; then
      say "pre-push: backend OK"
    else
      failed="${failed}backend "
    fi
  fi
fi

# ── Verdict ──────────────────────────────────────────────────────────────────
# Trim the accumulator's trailing space so messages read cleanly.
skipped="${skipped% }"
failed="${failed% }"

if [ -n "$skipped" ]; then
  say ""
  say "pre-push: NOT VERIFIED — $skipped"
  say "pre-push: those checks did not run, so CI is the first thing that will see this."
fi

# Escape a string for embedding in a JSON string literal. Strips ANSI colour
# (npm and vitest emit it even when piped) and any remaining control bytes,
# which would otherwise produce JSON the hook runner rejects — leaving the push
# silently un-gated, the one failure this script must not have.
json_escape() {
  sed -e 's/\x1b\[[0-9;]*[A-Za-z]//g' \
      -e 's/\\/\\\\/g' \
      -e 's/"/\\"/g' \
      -e 's/\r//g' \
      -e 's/\t/    /g' \
      -e 's/[[:cntrl:]]//g' \
    | awk 'BEGIN { ORS = "" } { if (NR > 1) printf "\\n"; print }'
}

if [ -n "$failed" ]; then
  say ""
  say "pre-push: FAILED — $failed"
  if [ "$hook_mode" -eq 1 ]; then
    # Only the tail: the reason is shown inline, and the full run is already
    # on stderr above for anyone who wants it.
    reason="$(printf 'Pre-push checks failed (%s) — not pushing.\n\n%s\n' \
      "$failed" "$(tail -n 40 "$log_file" 2>/dev/null)" | json_escape)"
    printf '{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"deny","permissionDecisionReason":"%s"}}\n' "$reason"
    exit 0
  fi
  exit 1
fi

if [ "$hook_mode" -eq 1 ] && [ -n "$skipped" ]; then
  printf '{"systemMessage":"pre-push: not verified — %s"}\n' "$(printf '%s' "$skipped" | json_escape)"
fi

exit 0
