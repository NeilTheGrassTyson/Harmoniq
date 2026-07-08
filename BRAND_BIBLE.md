# BRAND_BIBLE.md

## Harmoniq Brand System v1.0

---

## 1. Purpose

This document defines how Harmoniq should feel, speak, and behave across every user interaction.

It is a **system of constraints**, not marketing copy.

It ensures that as the product scales, it remains:

- emotionally coherent
- structurally consistent
- culturally distinct
- aligned with its core philosophy

If something feels “off,” this document is the reference point for correction.

---

## 2. Brand Definition

Harmoniq is a **social music discovery network built around trust and musical identity**.

It is not a streaming platform.  
It is not a content feed.  
It is not an algorithmic recommendation engine.

It is a system where:

> Music is transmitted between people as a signal of taste and identity.

The primary unit of value is not content itself, but **the act of sharing music between trusted individuals**.

---

## 3. Core Principles

Every feature, interaction, and design decision must reinforce at least one of:

### 3.1 Musical Identity

How a person’s taste defines and expresses who they are.

### 3.2 Trust

How music sharing becomes a social signal between people.

### 3.3 Discovery Through People

How users find music through other humans, not abstract feeds.

If a feature does not strengthen at least one of these, it should be questioned.

---

## 4. Product Mental Model

Harmoniq is composed of three primary layers:

### 4.1 Home (Minimal Entry Layer)

The Home screen is intentionally sparse.

It behaves more like a **calm entry point than a feed**.

It contains only:

- Trending songs (global weak signal)
- Top songs from friends (high-trust signal)

No infinite scroll.  
No algorithmic overload.  
No persistent content density.

The goal is orientation, not consumption.

---

### 4.2 Discovery Layer (Intentional Exploration)

A secondary browsing surface where users actively explore music.

Sources of discovery:

- Listening history-based recommendations
- Playlist-based recommendations
- What trusted connections are currently listening to

This layer is:

- optional
- scrollable
- intent-driven

It is not the default experience.

---

### 4.3 Social Recommendation System

The core social mechanic of Harmoniq.

Music is shared as structured social objects rather than passive content.

These objects are called:

> **Melodies**

---

## 5. Core Social Object: Melody

A **Melody** is a recommendation of a song from one user to another.

It renders as an interactive embed card:

- Cover art
- Song (title + artist)
- Sender identity ("From \<name\>")
- Timestamp

There is no message field. The track itself is the gesture — a Melody is
not content, and it is not a text composer.
It is a **social gesture encoded as music**.

---

### 5.1 Melody States

A Melody can exist in the following states:

- **Sent**
- **Received**
- **Accepted** (taken without listening)
- **Opened** (previewed and visited — also a positive outcome)
- **Rejected** (recoverable)

Each state is intentional and visible in private user (sender/recipient)
history. Every Melody a user receives is kept in their Melody inbox — a
user-only page listing each Melody, who sent it, and what the recipient
did with it.

---

### 5.2 Recipient Actions

When receiving a Melody, the user can:

- **Accept** → take the recommendation without listening right now
- **Open** → go straight to a preview and the song/album page
- **Reject** → dismiss without social penalty (recoverable from the inbox)

Accepting and opening are both positive responses. Rejection must remain
socially neutral to avoid discouraging sharing, and is visible to the
sender only.

---

### 5.3 Design Principle

A Melody is:

- atomic (one song, one intent)
- personal (sent from a specific user)
- intentional (requires action, not passive scrolling)

It is closer to a message than a feed item. It comes as a notification-style pop-up with quick actions stated above.

---

## 6. Core Social Metric: Harmony

Each user has a profile-level signal called:

> **Harmony**

Harmony reflects a users general taste. It is customizable, personal, but championed by their commendation statistics.

Harmony has two distinct parts, which must never be conflated (see ENGINEERING_BIBLE §3):

**Computed** — what actually determines the signal (Harmony v1):

- acceptance rate of sent Melodies
- meaningful engagement with shared songs
- sustained positive reception over time

**Cosmetic** — presentation only, never affects the computed signal (Harmony v2):

- Featured recent listening activity (if public account)
- Customizable themes
- Theme song!

---

### 6.1 Important Constraint

Harmony is **not a vanity metric**.

It must never feel like:

- follower count
- popularity score
- engagement farming system

It should feel like:

> “How often your taste resonates with others.”

It is a display of _alignment_, not attention.

---

### 6.2 Visibility

Harmony should be:

- present but not dominant
- visible on profiles
- never constantly broadcast in feeds or prompts

---

### 6.3 Ratings & Reviews

- Ratings and reviews are a foundational, day-one feature (see ROADMAP.md, NOW tier) and must follow the same constraints as every other surface in this document.
- A rating or review is an expression of musical identity — more deliberate and textured than a Melody, but not a popularity contest. It must never be displayed or framed in a way that invites cross-user comparison: no review-count leaderboards, no "top critics," no helpfulness scores that function as a status ladder.
- Approved language treats a review as a personal account of a listening experience ("Your take on this album") rather than content competing for visibility ("Top reviews," "Most helpful," "Trending takes").
- An aggregate rating (e.g. an album's average score) is permitted, since it reflects collective taste rather than individual performance. No per-user review metric may be surfaced in a way that resembles the leaderboard framing Harmony explicitly forbids (see §6.1, and ENGINEERING_BIBLE §6).

---

## 7. Home Experience Philosophy

The Home experience must feel:

- minimal
- calm
- non-demanding

It should never compete for attention.

It should feel like:

> “There is something here if you want it, but nothing is asking for you.”

---

## 8. Emotional Tone System

Harmoniq’s emotional identity is defined by:

### Desired Emotional States

- calm curiosity
- quiet discovery
- understated connection
- subtle recognition
- personal relevance without intrusion

### Avoided Emotional States

- urgency
- hype
- pressure
- performance anxiety
- excessive excitement
- manipulative engagement loops

The emotional target is:

> Recognition over stimulation

---

## 9. Brand Personality

Harmoniq behaves like:

- a thoughtful friend who shares music carefully
- a quiet curator of meaningful connections
- a system that reveals patterns rather than shouting suggestions
- a mediator between people and taste

It does NOT behave like:

- a social feed platform
- a dopamine-driven recommendation engine
- a gamified engagement system

---

## 10. Language System

### 10.1 Voice Characteristics

- minimal but intentional
- precise rather than expressive
- emotionally aware but not emotional
- avoids unnecessary explanation

---

### 10.2 Microcopy Principles

Microcopy should:

- guide without pushing
- suggest without persuading
- inform without overwhelming

---

### 10.3 Approved Language Patterns

Preferred:

- “Based on your listening history”
- “Shared through trusted connections”
- “People with similar taste also listened to this”

Avoid:

- “You’ll love this!”
- “Don’t miss out!”
- “Trending now!!!”
- “Hot picks just for you!”

---

## 11. Naming System

### 11.1 Canonical Terms

| Concept               | Name    |
| --------------------- | ------- |
| Recommendation object | Melody  |
| User resonance signal | Harmony |

These are system-level terms, not marketing terms.

---

### 11.2 Naming Philosophy

Names should be:

- human
- subtle
- emotionally grounded
- conceptually meaningful without being literal

Avoid:

- generic SaaS terms (feed, dashboard, insights)
- overly AI-centric language (smart, assistant, engine)
- loud or hype-driven naming

---

### 11.3 Naming Stability Principle

Once a term is introduced into user interaction flows, it should be:

- stable over time
- not frequently rebranded
- treated as part of user vocabulary

---

## 12. Social Dynamics Philosophy

Harmoniq is not about broadcasting identity.

It is about:

> transmitting taste between people who trust each other’s judgment.

Key idea:

- sharing music is a **social signal**
- receiving music is a **trust event**
- repeated exchange builds **musical alignment**

---

## 13. Interaction Philosophy

Every interaction must reinforce at least one:

- musical identity
- trust between users
- discovery through people

If it does not, it is likely noise.

---

## 14. System Boundaries

Harmoniq must avoid:

- engagement-maximizing design patterns
- infinite scroll as primary experience
- algorithmic over-personalization that feels invasive
- competitive social pressure
- performative metrics

Harmoniq should feel:

- calm even when active
- social without being noisy
- structured without being rigid

---

## 15. Product Identity Summary

Harmoniq is:

> a quiet social network built around music as a language of trust

It is not:

- a streaming service
- a recommendation engine
- a social media feed

It is:

- a system for exchanging musical identity between people

---

## 16. Open Philosophy Layer (Evolving)

These are intentionally unresolved to preserve design flexibility:

- How visible should Harmony be in daily UX?
- Should Melody feel closer to messaging or feed objects?
- How much history of social sharing should users see?
- Should discovery ever become primary over social exchange?

These will be resolved through product iteration, not branding alone.

---

## 17. Closing Principle

Harmoniq should always feel:

> intentional, quiet, and human — even when it is algorithmic underneath.

The product succeeds when users forget the system and remember the people behind the music.
