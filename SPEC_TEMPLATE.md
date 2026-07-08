# SPEC_TEMPLATE.md

> Blueprint for a single Harmoniq feature.

This is the canonical template for any feature that requires a spec (see **WORKFLOW.md, Section 1** for which features that is). Fill in every section below before handing this to Claude Code for implementation.

This document covers _what_ the feature is. It does not cover _how implementation is reviewed_ — that process is standard across every feature and lives in WORKFLOW.md, not here. Once this spec is approved, implementation proceeds straight into WORKFLOW.md's Review Workflow.

---

# Title

> Short descriptive name.

---

# Purpose

Describe:

- What problem this feature solves.
- Why it belongs in Harmoniq.
- Which core principle it strengthens — Musical Identity, Trust Between Users, or Discovery Through People (see HARMONIQ.md and BRAND_BIBLE.md §3).

_If you can't name one of the three, stop — reconsider whether this feature belongs in the product before writing the rest of the spec._

---

# Scope

### In Scope

-
-
-

### Out of Scope

-
-
-

_Out of Scope is not a formality — it's what stops Claude Code from quietly expanding the feature while implementing it._

---

# User Experience

Describe the experience from entry to completion, not the implementation.

- **Entry point** — how does a user arrive here?
- **Core flow** — the happy path, step by step.
- **Empty state** — what does this look like with no data yet?
- **Loading state** — what does the user see while waiting?
- **Error state** — what happens when something fails?
- **Success state** — how does the user know it worked?
- **Edge cases** — anything unusual worth calling out explicitly.

---

# Functional Requirements

List every expected behavior explicitly. Use the pattern that fits:

- User can...
- System should...
- Data must...
- Feature should never...

_Vague requirements get implemented vaguely. Be as literal as you'd be with a contractor, not a collaborator._

---

# Acceptance Criteria

The feature is complete only if every item below is objectively true and testable.

- [ ]
- [ ]
- [ ]

---

# Design Requirements

Reference BRAND_BIBLE.md directly where relevant.

- Does it feel minimal and intentional, not demanding? (BRAND_BIBLE §7, §8)
- Does it strengthen identity, trust, or discovery? (BRAND_BIBLE §3, §13)
- Any specific UI requirements, copy constraints, or naming that must follow BRAND_BIBLE §10–11?

---

# Technical Notes

_Optional. Include only what materially affects implementation — leave blank if nothing applies._

- Existing services or modules this touches
- APIs involved
- Database considerations
- Dependencies
- Migration requirements

---

# Rollback Plan

If this feature causes unexpected issues:

- How is it disabled?
- Can it be feature-flagged?
- Can existing data be preserved?

---

# Open Questions

_Do not silently answer product questions. Anything unresolved should live here until the founder decides._

-
-
-

---

Once approved, this spec moves into implementation under the standard process defined in **WORKFLOW.md**.
