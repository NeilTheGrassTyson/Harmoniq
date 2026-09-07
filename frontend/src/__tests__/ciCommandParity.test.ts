/**
 * `npm run verify` must run everything frontend-ci.yml runs.
 *
 * The incident: a pre-PR check was run as a hand-picked subset of the CI
 * steps — lint, typecheck, tests — and it passed. `npm run format:check` is a
 * *separate* CI step from `npm run lint`, so Prettier was never run, and CI
 * went red on a change that had just been declared clean locally. `verify`
 * was added to close that gap by chaining the steps in the order the workflow
 * runs them.
 *
 * But `verify` is a hand-maintained copy of the workflow's step list, and
 * nothing keeps the two in sync. Add a step to frontend-ci.yml — a bundle-size
 * check, an a11y pass — and `verify` silently stops being "what CI runs" while
 * still being named that. The next person runs it, believes it, and rediscovers
 * the same incident against a different step.
 *
 * This pins the direction that actually bites: every npm script the workflow
 * invokes must be reachable from `verify`. The reverse is deliberately not
 * asserted — `verify` running something extra is a stricter local check, which
 * is fine.
 *
 * Confirmed to fail by removing `format:check` from `verify`, and again by
 * adding a step to the workflow that `verify` does not chain.
 */

import { describe, it, expect } from "vitest";
import { readFileSync } from "node:fs";
import { join } from "node:path";

const repoRoot = join(__dirname, "..", "..", "..");
const workflow = readFileSync(join(repoRoot, ".github", "workflows", "frontend-ci.yml"), "utf8");
const packageJson = JSON.parse(
  readFileSync(join(repoRoot, "frontend", "package.json"), "utf8")
) as { scripts: Record<string, string> };

/** Every `npm run <script>` the workflow executes, in order of appearance. */
function scriptsInvokedByWorkflow(): string[] {
  const found = [...workflow.matchAll(/\bnpm run ([a-z][\w:-]*)/g)].map((m) => m[1]);
  return [...new Set(found)];
}

/**
 * Scripts `npm run verify` reaches, following `npm run x && npm run y` one
 * level deep so a `verify` built out of composite scripts still resolves.
 */
function scriptsReachableFromVerify(): Set<string> {
  const seen = new Set<string>();
  const walk = (name: string) => {
    if (seen.has(name)) return;
    seen.add(name);
    const body = packageJson.scripts[name];
    if (!body) return;
    for (const m of body.matchAll(/\bnpm run ([a-z][\w:-]*)/g)) walk(m[1]);
  };
  walk("verify");
  return seen;
}

describe("frontend-ci.yml and `npm run verify`", () => {
  it("defines a verify script", () => {
    expect(packageJson.scripts.verify).toBeTruthy();
  });

  /**
   * Guards against the vacuous pass: if the workflow is restructured so the
   * regex matches nothing, every parity assertion below would trivially hold
   * and the test would report green while checking nothing at all.
   */
  it("finds the workflow's npm steps", () => {
    const invoked = scriptsInvokedByWorkflow();
    expect(invoked.length).toBeGreaterThan(0);
    // The steps that existed when this test was written. If one is
    // legitimately removed from CI, delete it here too — deliberately, not by
    // letting the extraction quietly return nothing.
    expect(invoked).toEqual(expect.arrayContaining(["typecheck", "lint", "format:check", "build"]));
  });

  it("runs every script the workflow runs", () => {
    const reachable = scriptsReachableFromVerify();
    const missing = scriptsInvokedByWorkflow().filter((s) => !reachable.has(s));
    expect(missing).toEqual([]);
  });

  it("only invokes scripts that exist in package.json", () => {
    const undeclared = scriptsInvokedByWorkflow().filter((s) => !(s in packageJson.scripts));
    expect(undeclared).toEqual([]);
  });
});
