# WORKFLOW.md

> How decisions get made and features get built in Harmoniq.

This document describes **process** — how work moves from idea to shipped feature. It does not define principles (that's HARMONIQ.md) or product identity (that's BRAND_BIBLE.md). Per HARMONIQ.md's Hierarchy of Truth, process documents sit outside that hierarchy: they define *how* decisions are made, not *what* is true. That means this document can be revised more freely than the Constitution, as the workflow itself improves.

---

# 1. Two Tiers of Work

Not every change needs a spec. This section is the single source of truth for which tier a piece of work falls into — CLAUDE.md references this list rather than duplicating it.

### Tier 1 — Requires a Spec (Plan Mode)

Write a spec using SPEC_TEMPLATE.md, get it approved by the Founder, *then* implement. This applies to:

* Any net-new, user-facing feature.
* Choosing or changing the tech stack, an authentication/identity provider, or a deployment/hosting platform.
* Adding any new paid third-party service, API, or SaaS dependency.
* Any schema change that isn't purely additive (renames, drops, type changes on existing tables).
* Anything involving real payments, billing, or money.
* Anything irreversible (deleting data, dropping tables, force-pushing, rewriting git history).
* Any change to how user data is collected, stored, or shared — including anything touching the recommendation engine's data pipeline.

When in doubt, treat it as Tier 1. A spec is cheap; an unreviewed irreversible decision is not.

### Tier 2 — Auto Mode (No Spec Required)

Proceed directly, no spec needed:

* Implementing a plan that's already been approved.
* Writing and fixing tests.
* Refactors that don't change behavior.
* Bug fixes.
* UI/styling work within the established design system.
* Routine CRUD endpoints that follow an already-established pattern.

Tier 2 work still ends up going through the **Review Workflow** below before it's considered done — it just skips the spec-and-approval step that precedes it.

---

# 2. The Review Workflow

This is the standard sequence every feature — Tier 1 or Tier 2 — passes through during and after implementation. It is identical every time, which is why it lives here instead of being repeated inside every spec.

## 2.1 Implementation

* Clean, modular code.
* Readable naming.
* Tests where appropriate.
* No unnecessary complexity.

## 2.2 Static Analysis

Must pass before moving on:

* Formatting
* Linting
* Type checking
* Tests
* Build verification

No warnings are ignored without explicit, documented justification.

## 2.3 Optimization Audit

**Performance** — avoid unnecessary renders, duplicated state, excess network requests, unoptimized queries; lazy-load where appropriate.

**Responsiveness** — fast perceived performance, appropriate loading states, smooth interactions, no blocking operations.

**Resource Usage** — no memory leaks; listeners, timers, and subscriptions are cleaned up; no unnecessary polling.

**Scalability** — briefly consider expected behavior at 100, 1,000, and 100,000 users. Document any concerns rather than solving for scale prematurely (HARMONIQ.md §4, Simplicity Before Complexity).

## 2.4 Design Audit

Check against BRAND_BIBLE.md: layout, spacing, typography, motion, accessibility, copywriting, visual consistency.

Ask plainly: *does this feel like Harmoniq?*

## 2.5 Security Audit

Review: authentication, authorization, input validation, data exposure, API security, secrets, rate limiting, privacy, consent, logging.

Document any identified risk — per HARMONIQ.md §5 and §6, Security and Consent are never traded against speed or simplicity, so a risk found here doesn't get silently waved through.

## 2.6 Documentation

Update whatever is affected: feature docs, architecture docs, API docs, component docs, database docs, ENGINEERING_BIBLE.md, BRAND_BIBLE.md (if applicable), ADRs (if applicable).

No feature ships with outdated documentation (HARMONIQ.md §7).

## 2.7 Architecture Review

* Does this duplicate existing logic?
* Does this increase coupling?
* Can responsibilities be simplified?
* Does it respect module boundaries?
* Is it maintainable?
* Does it introduce unnecessary technical debt?

**Constitution check** — run the feature against HARMONIQ.md's Decision Framework directly:

* Does it strengthen musical identity?
* Does it increase trust between people?
* Does it improve discovery through people?
* Does it simplify the product?
* Does it respect a user's control over their own visibility?
* Does it improve or preserve security?
* Will this still feel correct years from now?

If the answer is "no" to multiple questions, that's a signal to revisit the feature — not just note it and move on.

---

# 3. Final Deliverables

Before a feature is considered closed, provide:

* **Summary** — concise overview of what was implemented.
* **Files Changed** — full list.
* **Decisions Made** — any implementation decision that may affect future development.
* **Future Improvements** — intentionally deferred enhancements.
* **Known Limitations** — accepted tradeoffs.

---

# 4. Definition of Done

A feature — Tier 1 or Tier 2 — is complete only when:

* [ ] Spec fully implemented (Tier 1 only).
* [ ] Acceptance criteria satisfied (Tier 1 only).
* [ ] Static analysis passes.
* [ ] Optimization audit completed.
* [ ] Design audit completed.
* [ ] Security audit completed.
* [ ] Documentation updated.
* [ ] Architecture review completed.
* [ ] No unresolved critical issues remain.

Completion means functional, maintainable, performant, secure, consistent with Harmoniq's philosophy, and ready to evolve — not just "it works."
