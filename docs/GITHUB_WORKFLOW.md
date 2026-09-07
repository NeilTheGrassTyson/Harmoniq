# GITHUB_WORKFLOW.md

> How Harmoniq's code physically moves through GitHub: branches, pull
> requests, CI, and repository settings.

This is the operational companion to **WORKFLOW.md**. WORKFLOW.md defines
_what_ has to happen before code is considered done (tiers, the Review
Workflow, the Definition of Done). This document defines _where the commits
go_ and _what GitHub is configured to do about them_.

Like WORKFLOW.md, this is a process document: per HARMONIQ.md's Hierarchy of
Truth it sits outside that hierarchy and may be revised as the workflow
improves. It does not override WORKFLOW.md — if the two disagree about
process, WORKFLOW.md wins and this file gets corrected.

Written 2026-07-25, after a branch-management incident described in
[§7 Incident record](#7-incident-record).

---

## 1. Branches

| Branch                                   | Lifetime  | Purpose                                                       |
| ---------------------------------------- | --------- | ------------------------------------------------------------- |
| `main`                                   | Permanent | Production. Deploys to Vercel + Railway. Always releasable.   |
| `dev`                                    | Permanent | Integration. Where feature work accumulates before a release. |
| `feat/*`                                 | Temporary | One net-new feature. Deleted on merge.                        |
| `fix/*`                                  | Temporary | One bug fix. Deleted on merge.                                |
| `docs/`, `chore/`, `refactor/`, `style/` | Temporary | Same rule — scoped to one change, deleted on merge.           |

**`main` and `dev` are permanent.** Neither is ever deleted, and neither is
ever a temporary branch that happens to stick around. Everything else is
disposable and should be deleted as soon as its PR merges.

Branch names use `type/short-kebab-description`, where `type` matches the
commit type it will mostly carry (`feat/melody-inbox`,
`fix/onboarding-race`). The type prefix is what makes the branch list
readable at a glance.

---

## 2. Integration direction

Work flows in **one direction only**:

```
feat/* ──▶ dev ──▶ main
```

1. Branch off `dev`.
2. Open a PR into `dev`. Merge it. The feature branch is deleted.
3. When `dev` is ready to release, open a single PR from `dev` into `main`.

**Never merge `main → dev` and `dev → main` for the same changes.** Replaying
commits through both paths produces duplicate SHAs with identical content,
and GitHub then reports the branches as simultaneously "N ahead / N behind"
while their files are byte-identical. This obscures real divergence. If `dev`
needs something that landed on `main` (a hotfix, say), bring it over once and
let it flow back through the normal `dev → main` PR.

This rule is the canonical one from WORKFLOW.md §1; it is restated here
because it is the reason the rest of this document exists.

### Hotfixes

A genuine production emergency may branch from `main` and PR straight into
`main`. Immediately afterward, bring `main` into `dev` **once** so the two
don't diverge, and note it in the PR. This is the single sanctioned exception
to §2, and it should be rare — reach for it only when waiting for the normal
`dev → main` path would keep production broken.

---

## 3. Pull requests

Every change reaches `dev` and `main` through a PR. No direct pushes to
either branch.

A PR body should state:

- **What changed** and why, in prose a reviewer can follow without the diff.
- **Verification** — the commands actually run and their results, not
  "tests pass". If something was checked manually in a browser, say so.
- **Anything deliberately deferred**, so it isn't mistaken for an oversight.

Keep one PR to one coherent change. If a mechanical fix (a formatting pass,
a rename) has to ride along, call it out explicitly in the body so the
reviewer knows which parts of the diff need real attention.

**Never bundle unrelated uncommitted work.** Check `git status` before
`git add -A`; if the working tree holds someone else's in-progress changes,
stage only your own paths.

### Commit messages

Conventional-commit style: `type: imperative summary`, where `type` is one of
`feat`, `fix`, `docs`, `refactor`, `style`, `test`, `chore`. The body explains
_why_, not _what_ — the diff already says what.

---

## 4. CI

Two workflows, both in `.github/workflows/`:

| Workflow      | Triggers on                 | Jobs                                                                                            |
| ------------- | --------------------------- | ----------------------------------------------------------------------------------------------- |
| `backend-ci`  | every PR; filters per job   | Detect backend changes · Lint & type check (ruff, mypy, bandit) · Tests (pytest) · **Backend CI gate** |
| `frontend-ci` | every PR; filters per job   | Detect frontend changes · Lint, typecheck & format (ESLint, tsc, Prettier) · Tests (vitest) · Build · **Frontend CI gate** |

Neither workflow has a **workflow-level `paths:` filter** — see §5 for why
that absence is what makes their gates requireable. Instead each starts with
a `changes` job that diffs the PR against its merge base, and the real jobs
carry `if: needs.changes.outputs.<stack> == 'true'`. On a PR that touches no
file for that stack they skip; on a push to `main` or `dev` they always run,
because a green history on the integration branches is worth more than the
saved minutes.

The two workflows are deliberately symmetrical. If you change the shape of
one — the filter, the gate's failure condition, the skip semantics — change
the other to match, or the next person will reasonably assume they behave
the same way when they no longer do.

Both run on pushes to `main` and `dev`, and on pull requests targeting
`main` or `dev`. **`dev` must stay in those trigger lists.** They originally
filtered on `main` alone, which meant every `feature → dev` PR merged with no
lint, no type check, and no tests — the entire integration path was
unguarded, and the gap was invisible because the PR simply showed no checks
rather than failing ones.

`frontend-ci` ran no tests at all until 2026-08-26 — a green frontend check
meant "it compiles and lints", not "the tests pass", and the whole suite was
verified on developer machines only. Both stacks now run their tests in CI.

### Run the gate locally before opening a PR

CI is a backstop, not the first line of defence. WORKFLOW.md §2.2 requires
formatting, linting, type checking, and tests to pass before a change is
considered done — run all four locally:

```bash
cd frontend && npm run verify
```

```bash
cd backend && poetry run ruff check . \
  && poetry run ruff format --check . \
  && poetry run mypy app \
  && poetry run bandit -r app -c pyproject.toml \
  && poetry run python -m pytest -q
```

Both commands are written to match what CI actually runs, and the two places
they most easily drift are worth stating outright:

- **`npm run verify`, not a hand-picked subset.** It runs typecheck, lint,
  `format:check`, tests, and `build`, in the order `frontend-ci.yml` runs
  them. `format:check` is the step most easily forgotten, because ESLint
  passing feels like "the linting is done" — it isn't. Prettier is a
  separate gate, and generated files (anything a CLI scaffolds into the
  repo) almost never arrive Prettier-clean. `build` is the other one: a
  type error `tsc --noEmit` tolerates can still fail `next build`.
- **Backend `ruff` runs over `.`, not `app tests`.** CI lints the whole
  `backend/` directory, which includes `alembic/` and `scripts/` — 15 files
  the narrower invocation silently skips. A local run that passes on
  `app tests` says nothing about those.

The backend test suite needs Docker running, since the integration tests use
Testcontainers against real PostgreSQL. Without it, `pytest tests/unit` still
runs the full unit tier.

### Or let it run itself

`scripts/pre_push_verify.sh` runs the two blocks above automatically, for only
the stacks the push actually touches — it reuses the same merge-base diff and
the same `core.quotePath=false` anchoring as the CI `changes` jobs, so what it
decides to run matches what CI will run. It exits non-zero on a real failure
and reports, rather than fails, when a toolchain is missing: a fresh clone
without `node_modules` should not be unable to push. The same applies to
Docker — when the daemon is not running it runs `pytest tests/unit` and says
the integration tier was not verified, rather than blocking the push on an
absent dependency.

Two ways to make it automatic — they are independent, and doing both is
reasonable since they cover different pushes:

```bash
# Any push you make yourself, from any tool
ln -sf ../../scripts/pre_push_verify.sh .git/hooks/pre-push
```

For pushes Claude Code makes, add a `PreToolUse` hook in `.claude/settings.json`
(untracked, so it is per-machine):

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "if": "Bash(git push *)",
            "command": "bash \"${CLAUDE_PROJECT_DIR:-.}/scripts/pre_push_verify.sh\" --hook",
            "timeout": 600,
            "statusMessage": "Running CI checks before push..."
          }
        ]
      }
    ]
  }
}
```

The `if` clause means the hook is only spawned for `git push`, not for every
shell command. `--hook` makes the script emit the deny decision as JSON with
the failing output as the reason, so a blocked push says which check failed
and where — not just that something did.

**A red PR does not get merged.** If CI is failing, fix it or explicitly
document why the failure is acceptable — merging red puts the failure on the
receiving branch, where the next person inherits it.

---

## 5. Repository settings

| Setting                          | Value  | Why                                                       |
| -------------------------------- | ------ | --------------------------------------------------------- |
| Default branch                   | `main` | Production is what a visitor should land on.              |
| Automatically delete head branch | On     | Keeps merged `feat/*` branches from accumulating.         |
| Branch protection on `dev`       | On     | Blocks deletion (including auto-delete) and force-pushes; requires `Backend CI gate`. `Frontend CI gate` exists but is not yet marked required — see below. |

**Automatic head-branch deletion has one sharp edge.** It deletes the _head_
branch of any merged PR — and in a `dev → main` PR, the head branch is `dev`.
So the setting that usefully cleans up feature branches will also delete the
permanent integration branch, silently, the moment a release merges.

Because auto-delete is deliberately kept on (it does the right thing for the
disposable branches, which are the overwhelming majority), `dev` is
protected from it by a branch protection rule — **applied 2026-07-25**.
GitHub refuses to delete a protected branch, so feature branches keep
collapsing normally while `dev` survives its own release PR. Verified by
attempting the delete: GitHub returns `422 Cannot delete this branch`.

The rule blocks deletions and force-pushes, and — since 2026-09-07 —
requires one status check: **`Backend CI gate`**. **`Frontend CI gate` is not
yet in that list**; the job exists and reports, but a Founder still has to
mark it required (see the end of this section). Review requirements stay off,
since a solo founder cannot approve their own PR.

That required check was previously impossible. Both workflows used
workflow-level `paths:` filters, so a frontend-only PR never triggered the
backend jobs at all, and a required backend check would sit permanently
"expected" and block the merge forever. Until this was fixed, a Bandit
finding showed up as a red check that nothing actually stopped — CI
reported the problem and the merge proceeded anyway.

Two details make each gate work, and both are load-bearing:

- **Neither workflow has a workflow-level `paths:` filter** (§4). Each
  therefore starts on every PR and always produces its check. Filtering
  moved into the `changes` job, so the expensive jobs still skip when no
  file for that stack changed — the gate reports green off skipped
  dependencies, which is exactly the "expected forever" trap it avoids.
- **The checks are named `Backend CI gate` and `Frontend CI gate`, not
  `Tests`.** `Tests` is a job name in *both* workflows; requiring a check by
  that name would be ambiguous between them. Each gate's name is unique on
  purpose — do not rename one without updating the branch protection rule,
  or protection will silently wait on a check that no longer exists.

A gate fails if any job it depends on failed or was cancelled, and passes if
they were skipped:

```yaml
if: contains(needs.*.result, 'failure') || contains(needs.*.result, 'cancelled')
```

`frontend-ci` was left advisory when the backend gate landed, and was given
the same treatment on 2026-09-07 — same `changes` job, same skip semantics,
same failure condition. Until then a frontend-only PR could merge with a red
ESLint, Prettier, vitest, or build result, because nothing required the
check.

**Adding the workflow does not by itself enforce it, and it is not enforced
today.** A gate job only becomes blocking once `Frontend CI gate` is added to
the required-checks list in the `dev` branch protection rule, by hand, in
repository settings — a Founder action, not something a PR can do. GitHub
will not offer the name until the check has reported at least once, so it can
only be added after the first PR carrying this workflow has run. Until that
happens a red frontend check is still advisory, exactly as before.

Settings → Branches → the `dev` rule → Require status checks to pass → add
`Frontend CI gate`. Update the table above when it is done.

If protection is ever removed, the fallback is to recreate `dev` by hand
after every `dev → main` merge — worse, because it depends on someone
remembering every time:

```bash
git checkout main && git pull && git push origin main:refs/heads/dev
```

---

## 6. Branch hygiene

- Delete a branch as soon as its PR merges. Auto-delete handles this for
  merged PRs; branches abandoned without merging need manual cleanup.
- Prune stale remote-tracking refs locally: `git fetch --prune`. Without
  this, `git branch -r` keeps showing branches that no longer exist on
  GitHub, which is how a deleted `dev` can look present locally.
- Leaving a tool behind means leaving its branches behind too. When
  Dependabot was removed (2026-07-09), nine `dependabot/*` branches stayed
  on the remote until they were cleaned up on 2026-07-25.

---

## 7. Incident record

Kept because HARMONIQ.md §7 holds that a significant decision — or a
significant mistake — should not exist only in conversation.

**2026-07-20 — `dev` was deleted by a release merge.** PR #40 merged
`dev → main`. Auto-delete removed the head branch, which was `dev` itself.
Nothing was lost (every commit was already in `main`), but the integration
branch simply vanished, and local clones kept a stale `origin/dev` ref that
made it look like it still existed. `dev` was recreated from `main` and
protected on 2026-07-25 (§5), so this cannot recur.

**2026-07-20 — a PR merged with CI red.** The same `dev → main` PR merged
with the frontend `Lint, typecheck & format` job failing: twelve files, most
of them scaffolded by the shadcn CLI, were not Prettier-formatted. The
failure reached `main` and had to be fixed afterward. Two causes, both now
addressed above: the pre-PR gate was run without `format:check` (§4), and the
`feature → dev` PR that introduced the files ran no CI at all (§4), so the
problem was not visible until the release PR.

---

## 8. Quick reference

```bash
# Start work
git checkout dev && git pull
git checkout -b feat/my-thing

# Before opening the PR — run exactly what CI runs (see §4)
(cd frontend && npm run verify)
(cd backend && poetry run ruff check . && poetry run ruff format --check . \
  && poetry run mypy app && poetry run bandit -r app -c pyproject.toml \
  && poetry run python -m pytest -q)

# Ship it
git push -u origin feat/my-thing
gh pr create --base dev

# Release
gh pr create --base main --head dev
# dev is protected, so the merge no longer deletes it (see §5)
```
