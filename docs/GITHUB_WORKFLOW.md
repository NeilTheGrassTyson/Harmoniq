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

| Branch          | Lifetime  | Purpose                                                        |
| --------------- | --------- | -------------------------------------------------------------- |
| `main`          | Permanent | Production. Deploys to Vercel + Railway. Always releasable.     |
| `dev`           | Permanent | Integration. Where feature work accumulates before a release.   |
| `feat/*`        | Temporary | One net-new feature. Deleted on merge.                          |
| `fix/*`         | Temporary | One bug fix. Deleted on merge.                                  |
| `docs/`, `chore/`, `refactor/`, `style/` | Temporary | Same rule — scoped to one change, deleted on merge. |

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

| Workflow      | Triggers on                     | Jobs                                     |
| ------------- | ------------------------------- | ---------------------------------------- |
| `backend-ci`  | changes under `backend/**`      | Lint & type check (ruff, mypy) · Tests (pytest) |
| `frontend-ci` | changes under `frontend/**`     | Lint, typecheck & format (ESLint, tsc, Prettier) · Build |

Both run on pushes to `main` and `dev`, and on pull requests targeting
`main` or `dev`. **`dev` must stay in those trigger lists.** They originally
filtered on `main` alone, which meant every `feature → dev` PR merged with no
lint, no type check, and no tests — the entire integration path was
unguarded, and the gap was invisible because the PR simply showed no checks
rather than failing ones.

### Run the gate locally before opening a PR

CI is a backstop, not the first line of defence. WORKFLOW.md §2.2 requires
formatting, linting, type checking, and tests to pass before a change is
considered done — run all four locally:

```bash
cd frontend && npm run lint && npm run typecheck && npm run format:check && npm run test:run
```

```bash
cd backend && poetry run ruff check app tests && poetry run ruff format --check app tests && poetry run python -m pytest
```

`format:check` is the one most easily forgotten, because ESLint passing feels
like "the linting is done" — it isn't. Prettier is a separate gate, and
generated files (anything a CLI scaffolds into the repo) almost never arrive
Prettier-clean. The backend test suite needs Docker running, since the
integration tests use Testcontainers against real PostgreSQL.

**A red PR does not get merged.** If CI is failing, fix it or explicitly
document why the failure is acceptable — merging red puts the failure on the
receiving branch, where the next person inherits it.

---

## 5. Repository settings

| Setting                          | Value | Why                                                       |
| -------------------------------- | ----- | --------------------------------------------------------- |
| Default branch                   | `main` | Production is what a visitor should land on.              |
| Automatically delete head branch | On    | Keeps merged `feat/*` branches from accumulating.         |

**Automatic head-branch deletion has one sharp edge.** It deletes the *head*
branch of any merged PR — and in a `dev → main` PR, the head branch is `dev`.
So the setting that usefully cleans up feature branches will also delete the
permanent integration branch, silently, the moment a release merges.

Because auto-delete is deliberately kept on (it does the right thing for the
disposable branches, which are the overwhelming majority), `dev` needs
explicit protection from it. Two ways, in order of preference:

1. **A branch protection rule on `dev`.** GitHub never auto-deletes a
   protected branch, so feature branches keep collapsing normally while `dev`
   survives. This is the durable fix and it costs nothing else.
2. **Recreate `dev` immediately after every `dev → main` merge**, as a
   standing manual step:

   ```bash
   git checkout main && git pull && git push origin main:refs/heads/dev
   ```

Option 1 is preferred precisely because option 2 depends on someone
remembering, every time, forever.

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
made it look like it still existed. `dev` was recreated from `main` on
2026-07-25.

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

# Before opening the PR — run the full gate (see §4)

# Ship it
git push -u origin feat/my-thing
gh pr create --base dev

# Release
gh pr create --base main --head dev
# then confirm dev still exists; recreate it if not (see §5)
```
