# HARMONIQ — ENGINEERING BIBLE v1

**Revision note:** This revision folds Melody and Harmony into the domain
model as first-class entities, separates the Home and Discovery surfaces
explicitly, resolves the Spotify-embeddings question against the ToS
constraint already recorded in CLAUDE.md, and adds a short Consent &
Visibility subsection. It also adds an explicit scope boundary so this
document doesn't grow every time a new feature ships.

**Revision 2026-07-04 (Founder-ratified):** §3 Melody lifecycle updated to
the Accept / Open / Reject model with the user-only Melody inbox; the §11
Evolution Strategy edit from commit 4be872d is ratified. Review record:
`docs/reviews/engineering-bible-855d2ac-to-4be872d.md`.

**Revision 2026-07-07 (Founder-ratified):** §3 Melody definition updated —
Melody carries no message field; it renders as an interactive embed card
(cover art, track, artist, sender identity). Review record:
`docs/reviews/engineering-bible-4be872d-to-docs-pass.md`.

---

## 0. Introduction

Harmoniq is a social system built around a simple but strict idea: music is
not content, it is identity. Every design decision in the system exists to
preserve that framing.

This means Harmoniq is not a streaming platform, and it is not a
recommendation engine disguised as social media. It is a network where
people discover music through other people, and where what someone listens
to is treated as a meaningful expression of who they are.

The engineering challenge is therefore not just building feeds or APIs, but
ensuring that every layer of the system reinforces trust, identity, and
human-scale discovery rather than optimizing for passive consumption.

### 0.1 Scope of this document

This document defines the architecture needed to build Harmoniq's first
working version: identity, the trust graph, the Home and Discovery
surfaces, Melody, and Harmony. It does not attempt to pre-solve
later-phase problems — embeddings-based similarity, additional providers,
distributed architecture. Where those appear below, they are marked as
**deferred**, not designed.

When a new feature needs architecture this document doesn't cover, the
answer is a spec or an ADR, not an edit to this document. This document
should describe what kind of system Harmoniq always is; specs describe what
a particular feature does this quarter.

---

## 1. Product Philosophy as Engineering Constraint

The system is built around three irreversible constraints.

First, identity is the primary data type. A user is not defined by profile
fields or social metadata, but by a structured accumulation of musical
signals: what they listen to, what they intentionally highlight, and what
they choose to share as representative of themselves. Everything else is
secondary.

Second, discovery must be socially grounded. Any time a user encounters
music or another user, there must be a traceable chain of trust, similarity,
or intentional exposure that explains why that content exists in front of
them. Randomness is allowed only as a minor exploration mechanism, never as
the primary driver.

Third, algorithmic ranking exists only in a supporting role. It can refine
or reorder signals, but it cannot be the origin of relevance. The origin
must always be human: either through explicit action or through meaningful
behavioral similarity.

These constraints are architectural requirements, not UX preferences. A
system design that violates them is incorrect by definition.

---

## 2. System Overview

The system is intentionally structured as a modular monolith in its initial
phase. The goal is clarity of boundaries within a single backend, not
distributed complexity.

The frontend is responsible only for presentation and interaction. It does
not compute rankings, interpret trust, or access external music platforms
directly.

The backend is implemented in Python using FastAPI, chosen for clarity,
maintainability, and reduced exposure to JavaScript supply-chain risk. It is
divided into internal services that are logically separated even if
deployed together: identity management, social graph logic, music
ingestion, recommendation generation, and feed composition.

The domain layer defines the core entities of the system — stable
primitives that the entire system is built around, not database tables in
the abstract sense.

The integration layer handles communication with external music providers.
Spotify is the initial integration, abstracted behind a provider interface
so other platforms can be added without touching core logic.

---

## 3. Core Domain Model

At the center of the system is the user: not a static profile, but a
continuously evolving representation of musical behavior and intention.

**Listening signals** capture what a user listened to, when, and through
which source. On their own they are noisy; they become meaningful only when
aggregated into identity structures.

**Highlighted songs** are the most important expression of identity.
Unlike passive listening history, a highlight is an intentional act of
self-curation — what a user chooses to surface as representative of their
taste, scoped to their own profile. Highlights carry significantly higher
weight than raw listening signals in every downstream system.

**Melody** is a distinct entity from a highlight, and the two should not be
conflated. A highlight is something a user says about themselves. A Melody
is something one user sends to another: a directed recommendation of a
single track, carrying a sender, a recipient, and a timestamp — no message
field. It renders as an interactive embed card (cover art, track title,
artist, sender identity), not a text composer; the track itself is the
gesture. A Melody is a social gesture, not a piece of content, and it must
always trace back to a specific human sender — see section 6 for why this
matters architecturally.

A Melody has a lifecycle, modeled as an explicit state machine: `sent` →
`received`, then exactly one of `accepted` (taken without listening),
`opened` (the recipient goes to a preview and the track/album page —
acceptance plus engagement), or `rejected`. Both `accepted` and `opened`
are positive outcomes; `rejected` is recoverable and visible only to the
sender — it must never produce a notification or penalty visible to
anyone else. Every received Melody is retained and listed in the
recipient's Melody inbox (a user-only surface) with its sender and
outcome; the inbox is part of the domain model, not a presentation
convenience.

**Harmony** is a profile-level signal, not a raw entity in the same sense
as the others. It has two parts that should be kept architecturally
separate: a *computed* component (derived from Melody acceptance rate and
sustained positive reception over time, owned by the recommendation
service) and a *cosmetic* component (theme, theme song — owned by the
profile/presentation layer, not the scoring engine). Conflating these would
make the score easy to game through unrelated profile customization.

The social graph is not binary. Relationships exist as explicit
friendships, one-directional follows, and trust relationships representing
perceived taste alignment. Implicit discovery relationships form when users
encounter each other through feeds or shared content. These are first-class
data, not incidental metadata.

Tracks are normalized entities that unify music across providers,
independent of any single external system.

---

## 4. Social Graph and Trust

The social graph is the structural backbone of Harmoniq. Relationships are
weighted and semantically distinct rather than flat.

A trust relationship is directional and carries a score representing how
much one user's musical judgment is valued by another — derived from both
explicit action and implicit behavioral similarity, not just interaction
frequency.

This trust graph is the primary input into discovery. Discovery edges
extend it: when a user encounters another user through a feed, a shared
Melody, or shared content, that exposure is recorded, allowing latent
communities of taste to surface over time even without explicit follows.

---

## 5. Surfaces: Home, Discovery, and the Harmonic Feed

Harmoniq exposes two distinct surfaces. They are not two views of the same
ranking function — they have different jobs and different architectural
shapes.

**Home** is a fixed, minimal entry point, not a feed in the conventional
sense. It is composed of exactly two bounded queries: trending songs
(a global weak signal) and top songs from friends (a high-trust signal).
There is no ranking function, no algorithmic blending, and no infinite
scroll. If an implementation finds itself adding a relevance score or a
"load more" to Home, that is a sign the surfaces have been collapsed
incorrectly.

**Discovery** is the secondary, scrollable surface where users actively
explore. It is the Harmonic Feed: a structured composition of content from
trusted users (highlights, recent listening activity), followed users, and
controlled algorithmic diversity. The ranking function combines trust
strength, highlight weight, similarity, and freshness decay, with social
signals strictly dominant over algorithmic adjustment. Discovery is
optional and intent-driven — never the default landing experience.

Neither surface optimizes for engagement metrics (virality, click-through,
time-on-platform). Any such optimization would directly conflict with the
system's definition of meaningful interaction.

---

## 6. Recommendation System

Recommendations are a derived view of the social graph, not an independent
system. There are three valid outputs: users who may be worth trusting,
songs highlighted by trusted users, and songs similar to the user's
identity profile. There is no generic "trending" justification — popularity
alone never qualifies content for surfacing unless it intersects trust or
identity similarity.

**Constraint: the recommendation engine must never generate or send a
Melody on a user's behalf.** A Melody's entire design principle is that it
comes from a specific person who chose to send it. An auto-suggested or
system-sent Melody would misrepresent its own provenance and break the
trust contract the object exists to encode. Algorithmic outputs surface
through Discovery, never disguised as a Melody.

**Constraint: Harmony must never be exposed as a leaderboard, a follower
count, or a sortable global ranking.** It is computed for the profile that
earns it and displayed there — not aggregated into any feature that invites
comparison between users at a glance.

Ranking follows a strict hierarchy: trusted users first, then followed
users, then users with high similarity, and only then algorithmic
candidates.

---

## 7. API and System Boundaries

The system exposes a minimal set of APIs reflecting its core primitives:
authentication, identity management, music ingestion, social graph
mutation, highlights, Melody send/respond, Home retrieval, and Discovery
retrieval. Home and Discovery are separate endpoints, not parameterized
views of one feed call — this keeps the architectural split in section 5
from being quietly undone at the API layer.

Each API manipulates a single conceptual domain. The frontend is strictly
prohibited from computing ranking logic or talking to external music
providers directly; the backend is prohibited from encoding presentation
assumptions.

---

## 8. Security, Consent, and Supply Chain Integrity

Given the risks in JavaScript ecosystems, particularly npm supply-chain
vulnerabilities, the backend intentionally avoids Node.js. Python FastAPI
minimizes dependency surface area and improves auditability. Dependencies
must be explicitly pinned; dynamic execution of external code is forbidden;
integration with external providers happens only through controlled adapter
interfaces. Production stays isolated from development and staging. All
mutations to social or trust data are logged for auditability.

### 8.1 Consent & visibility

Every shareable entity — a highlight, listening activity, Melody history,
Harmony detail — carries an explicit visibility scope set by its owner
(private / friends / public), defaulting to the most private option.
Visibility changes are revocable and take effect immediately; the system
does not continue serving content past a revoked grant from cache or a
stale fan-out.

Enforcement happens at the data-access layer, not the presentation layer.
A query for another user's listening activity must itself respect
visibility scope — it is not acceptable for an API to return private data
and rely on the frontend to hide it.

---

## 9. Real-Time Systems

Real-time functionality is intentionally limited to ephemeral states —
"currently listening" indicators and live highlight updates — to enhance
social presence, not drive engagement loops. Feed updates and ranking
changes are explicitly non-real-time, by design, to preserve calm system
behavior.

---

## 10. Non-Goals

Harmoniq is not a viral content platform. It does not optimize for
engagement maximization or infinite scroll retention. It does not rely on
advertising or monetization that distorts ranking. It does not attempt to
replace Spotify or Apple Music. It does not auto-generate or auto-send
Melodies on a user's behalf. It is not an AI-first recommendation engine —
machine learning may assist similarity, but it does not define relevance.

---

## 11. Evolution Strategy

Phase 1 (this document): a modular monolith backend, MusicBrainz as the
canonical music source (on-demand ingestion), focused on the trust graph,
identity model, ratings, follows, Melody, Harmony, and the Home/Discovery
split. Spotify is a deferred supplementary integration (account linking,
"currently playing") — not the data backbone. See CLAUDE.md for Spotify
API constraints that govern this decision.

Phase 2 (deferred, not designed here): additional music providers, more
sophisticated similarity modeling.

Phase 3 (deferred, not designed here): architectural evolution into graph
databases or distributed services, only after clear evidence the monolith
is insufficient.

At every stage, structural changes must preserve the primacy of trust and
identity.

---

## 12. Implementation Guidance for Claude

Prioritize clarity over optimization. Services should be modular but not
prematurely distributed. Dependencies should be explicit and minimal. All
logic touching trust, identity, or recommendation must remain inspectable
and traceable.

Any proposed architectural change must include a clear explanation of
tradeoffs, particularly how it affects system coherence and alignment with
Harmoniq's principles. If a design improves performance but weakens trust
or identity clarity, reject it unless explicitly approved by the Founder.

If an implementation decision arises that this document doesn't cover,
record it as an ADR in `docs/adr/` rather than expanding this document —
the Bible should change when the architecture changes, not when a feature
ships.

---

## 13. Open Questions

The mathematical formulation of trust scoring is not yet defined and should
be treated as an evolving system, refined as real usage data accumulates.

Similarity modeling beyond direct trust-graph traversal is deferred to
Phase 2. When it is built, it must be trained only on data collected
directly within Harmoniq — ratings, reviews, listens, follows — never on
Spotify content or metadata, per the developer policy already recorded in
CLAUDE.md. Spotify-derived data may be displayed; it may not be used as
training input.

The role of blog-style or exploratory discovery surfaces has not been
integrated into the Discovery hierarchy.

The relationship between profile identity surfaces and feed-based discovery
needs further definition in a later iteration.