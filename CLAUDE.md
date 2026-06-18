# Project overview

A social music discovery and rating platform: the critical/rating culture of RateYourMusic, the social graph and following/feed model of Spotify's social features, and user posts/reviews as a core feature (not an afterthought). A recommendation layer built from data collected directly in-app (ratings, reviews, follows, listens) is part of the long-term vision, but per HARMONIQ.md's "Humans Before Algorithms" principle and ROADMAP.md's LATER tier, it is deliberately deferred and gated behind its own plan-mode spec — not a pillar with equal billing to the human-originated mechanics above.

## Governing principles

This project is governed by HARMONIQ.md, the project constitution. Every
feature and technical decision should be weighed against it — imported
below so it's loaded automatically every session:

@HARMONIQ.md

(Once ENGINEERING_BIBLE.md has real content, add `@ENGINEERING_BIBLE.md`
here too — it belongs in this always-loaded tier alongside the
constitution, not in the situational-reference tier below.)

## Important context: Spotify API constraints

Spotify has significantly restricted third-party developer access:

- The Recommendations endpoint was removed from the Web API (Feb 2026).
- The audio-features and audio-analysis endpoints (tempo, key, danceability)
  have been removed since late 2024.
- New developer accounts are capped at 5 authorized users in "Development
  Mode." Reaching a real audience requires applying for extended access,
  which requires a registered business and 250,000+ monthly active users.
- Spotify's developer policy prohibits training ML models on Spotify content
  or metadata.

Implication: Spotify account-linking is a nice-to-have integration (show
what a user is currently playing, optionally import a starter library), NOT
the backbone of the recommendation engine or the core data model. The taste
graph and recommendation engine must be built from data we collect directly:
ratings, reviews, follows, and listens logged inside our own app.

## Plan mode vs. auto mode

This project uses a two-tier process for deciding what needs a spec and
approval before implementation, versus what can proceed directly. The full
breakdown lives in WORKFLOW.md, imported below:

@WORKFLOW.md

One project-specific note that feeds into the Tier 1 "data collection/
storage/sharing" rule above: anything touching the recommendation engine's
data pipeline is Tier 1 by default, given the Spotify ToS constraint on
training models on Spotify content described earlier in this file.

## Situational references (not auto-loaded)

These docs matter but don't need to sit in context for every session — open
them deliberately when the task calls for it, either by asking directly or
referencing the file by name in your prompt:

- **BRAND_BIBLE.md** — consult during design/UI/copy work, and during the
  Design Audit step of the Review Workflow.
- **SPEC_TEMPLATE.md** — use when starting any Tier 1 feature.
- **ROADMAP.md** — consult during planning/prioritization conversations,
  not implementation.

## Conventions

(Fill in once the stack is chosen: formatting/linting rules, folder
structure, naming conventions, how to run tests locally.)

## First session prompt

A good way to kick this off in Claude Code: ask it to research and propose
2-3 stack options for a social app with a custom recommendation engine
(considering that you're building solo with AI tooling rather than a team),
in plan mode, before any code gets written.
