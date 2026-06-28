# Ratings & Reviews

> Feature Spec — Phase 1 / NOW tier
> Status: Approved 2026-06-20 — Implementation complete 2026-06-20

---

# Purpose

Harmoniq's identity proposition depends on users being able to express genuine taste judgments about music. Without a ratings and reviews layer, the platform is a discovery tool with no signal — there is nothing for the social graph to transmit, nothing for trusted people to have said, and nothing for the taste-matching layer to eventually learn from.

This feature establishes the RateYourMusic-style backbone of Harmoniq: a structured, text-required rating system where a score without a review is not accepted.

The principles it strengthens are **Identity Before Engagement** (a rating with required review is an expressive act, not a tap) and **Humans Before Algorithms** (all aggregate scores emerge from individual human judgments, not a black-box signal).

---

# Scope

### In Scope

* Rating submission: an integer score (1–10) paired with a review text (15–2000 characters). Both are required; neither can be submitted without the other.
* Re-rating: submitting a new rating for an entity the user has already rated. The new rating becomes the user's current rating; the prior rating is preserved in history (not overwritten or deleted).
* Aggregate score: the average of each user's most recent rating for an entity. Computed dynamically from the `ratings` table; not stored denormalized.
* Visibility: `public` (default — intentional exception to the "default private" convention used by all other user-generated content), `friends`, or `private`. Per-rating, set at submission time and changeable afterwards.
* Track detail page: shows aggregate score and list of visible reviews.
* Album detail page: same as track.
* User profile page: shows the user's review history (most recent rating per entity).
* Report: any authenticated user can report a review. One report per (reporter, rating) pair, enforced at DB level.
* Delete: a user can hard-delete any of their own ratings. Deletion is permanent — no soft delete in Phase 1.
* Rate limiting: 10 submissions per minute per user; 20 reports per minute per user.
* Observability: submit, delete, report, and unauthorized-action attempts are logged.

### Out of Scope

* Soft delete / rating archival.
* Moderation tooling or report queue (reports are stored; admin tooling is a later feature).
* Separate "score only" ratings (score always requires review).
* Likes, reactions, or comments on reviews.
* Review pagination beyond the initial list.
* Notifications triggered by reports or new reviews.
* Friends-visibility enforcement (requires follows table — `_is_friend()` stubs to `False` until follows ships).

---

# Non-Goals

* This feature is not a recommendation engine. Ratings collected here will feed a future recommendation layer, deliberately deferred per HARMONIQ.md §2 and ROADMAP LATER tier.
* This feature is not a content moderation system. Reports are stored for future tooling.
* This feature does not surface trending or popular reviews algorithmically.

---

# User Experience

**Rating on a track/album detail page:**
1. Authenticated user navigates to a track or album detail page.
2. Below the entity metadata, a "Your review" section is visible.
3. User selects a score (1–10 button row) and writes a review (required, ≥ 15 characters).
4. User optionally changes visibility (default: public) and submits.
5. The review appears in the "Reviews" list immediately.
6. Unauthenticated users see the aggregate score and reviews but not the composer.

**Re-rating:**
Submitting again for the same entity creates a new rating row. Prior entries remain in history. The aggregate recalculates automatically.

**Review history on profile:**
The profile page shows the user's reviews (most recent per entity), linked to track/album pages. Score, review text, and date are shown.

**Delete and report:**
On their own reviews, the owner sees a delete button. On others' reviews, authenticated users see a report button. Reported reviews show "Reported" to the reporter.

**Empty state:** "No reviews yet."

---

# Functional Requirements

* System must reject a score without review text, and review text without a score.
* Score must be an integer in [1, 10] — enforced at DB level (CHECK constraint) and API level (Pydantic).
* Review text must be between 15 and 2000 characters (trimmed) — enforced at API level.
* Visibility must be one of `public`, `friends`, `private`. Default is `public`.
* Submit endpoint must accept `entity_mbid` (MusicBrainz ID); the service layer resolves the MBID to an internal UUID. If the MBID is not in the local catalog, the endpoint returns 404.
* Aggregate score must be computed from each user's most recent rating only — using a window function, not a denormalized column.
* `DELETE /ratings/{id}` must return 204 and hard-delete the row. Unauthorized attempts must be logged at WARNING level.
* `POST /ratings/{id}/report` must enforce uniqueness per (reporter, rating) pair — duplicates return 409.
* Submit endpoint: 10 requests/minute rate limit per user.
* Report endpoint: 20 requests/minute rate limit per user.
* Visibility enforcement must happen in the service layer, not in route handlers or the frontend.
* `friends` visibility stubs to `False` until the follows table ships.
* Catalog detail endpoints must accept an optional viewer auth token so visibility is computed correctly for authenticated viewers.

---

# Acceptance Criteria

* [ ] An authenticated user can submit a 1–10 score with a review ≥ 15 characters for a track or album.
* [ ] Submitting without a score or without review text is rejected with a 422.
* [ ] Submitting again for the same entity creates a new rating row; prior row is preserved.
* [ ] Aggregate score on track/album detail page reflects the average of each user's most recent rating.
* [ ] Ratings with `private` visibility are not visible to other users.
* [ ] Ratings with `public` visibility appear on track/album detail pages for unauthenticated viewers.
* [ ] Submit endpoint enforces a 10/min rate limit.
* [ ] Report endpoint enforces a 20/min rate limit.
* [ ] A user can delete their own rating (returns 204; row is removed).
* [ ] A user cannot delete another user's rating (returns 403).
* [ ] Reporting the same rating twice returns 409.
* [ ] User profile page shows the user's review history.
* [ ] All static analysis passes: ruff, mypy (backend); tsc, eslint, prettier (frontend).

---

# Design Requirements

**Composer:**
The score selector is a row of 10 numbered buttons (1–10). Selected score is highlighted. Review textarea shows character count. Visibility selector reuses the existing `VisibilitySelect` component. Submit button is disabled until a score is selected and review meets the minimum length.

**Review list:**
Each review shows reviewer username, score, review text, and date. Owner sees a delete button; others see a report button that changes to "Reported" after use.

**Aggregate display:**
`X.X / 10` in a clean typographic treatment above the review list. Only shown when at least one public review exists.

**No engagement patterns:**
No likes, no upvotes, no "helpful review" ranking. Reviews are ordered by most recent.

---

# Technical Notes

**Polymorphic entity reference:**
The `ratings` table uses `entity_type` (`"track"` or `"album"`) + `entity_id` (internal UUID). There is no DB-level FK constraint on `entity_id` since it references two different tables; referential integrity is enforced in the service layer via `resolve_entity()`.

**Database schema:**
```
ratings
  id            UUID PK
  user_id       UUID FK → users.id NOT NULL      INDEX
  entity_type   VARCHAR NOT NULL                  -- 'track' | 'album'
  entity_id     UUID NOT NULL                     -- internal PK of the entity (no FK constraint)
  score         INTEGER NOT NULL                  CHECK (score >= 1 AND score <= 10)
  review_text   VARCHAR(2000) NOT NULL
  visibility    VARCHAR NOT NULL DEFAULT 'public'
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now()

  INDEX ix_ratings_user_id (user_id)
  INDEX ix_ratings_entity (entity_type, entity_id, created_at)
  INDEX ix_ratings_user_entity_created (user_id, entity_type, entity_id, created_at)

reports
  id            UUID PK
  reporter_id   UUID FK → users.id NOT NULL   INDEX
  rating_id     UUID FK → ratings.id NOT NULL INDEX
  UNIQUE (reporter_id, rating_id)
```

**Aggregate query pattern:**
```sql
SELECT AVG(score) FROM (
  SELECT score,
    ROW_NUMBER() OVER (PARTITION BY user_id ORDER BY created_at DESC) AS rn
  FROM ratings
  WHERE entity_type = :entity_type AND entity_id = :entity_id
    AND visibility = 'public'
) sub WHERE rn = 1
```

**Rate limiting:** `slowapi` decorators on submit and report endpoints. `Request` is the first route parameter per slowapi convention.

**No new paid dependencies.**

---

# Observability

* Rating submit, delete, and report events logged at INFO level (user_id, entity_type, entity_mbid).
* Unauthorized delete attempts logged at WARNING level.
* Duplicate report attempts logged at INFO level.
* Service-level errors logged at ERROR level with context.
* Review text must not appear in log output at INFO or above.

---

# Rollback Plan

Both new tables (`ratings`, `reports`) are additive. The Alembic migration is reversible via `alembic downgrade`. Removing the `ratings` router from `router.py` disables all rating endpoints with no impact on existing features.

---

# Special Notes

**Public default visibility:**
Deliberate exception to the "default private" convention used by all other user-generated content in Harmoniq. Ratings are the primary social signal of the product — defaulting to private would make the platform dark from launch. Approved as a constitutional exception per HARMONIQ.md's governance model.

---

*Approved 2026-06-20. Implementation proceeds under the standard Review Workflow in WORKFLOW.md.*

---

# Implementation Summary

*Completed 2026-06-20 — branch `dev`.*

## Files changed

**New — Backend**
- `backend/app/models/rating.py` — Rating and Report ORM models with CheckConstraint on score
- `backend/app/schemas/rating.py` — request/response schemas; VisibilityScope StrEnum; REVIEW_MIN_LENGTH, REVIEW_MAX_LENGTH, ENTITY_TYPES constants
- `backend/app/services/rating.py` — submit, list_for_entity, list_for_user, count_for_user, get_aggregate, update_visibility, delete_rating, report_rating; resolve_entity MBID→UUID helper
- `backend/app/api/v1/ratings.py` — 6 endpoints with rate limiting
- `backend/alembic/versions/a1b2c3d4e5f6_add_ratings_table.py` — migration for both tables and all indexes

**Modified — Backend**
- `backend/app/models/__init__.py` — Rating, Report imports
- `backend/app/api/v1/router.py` — registered ratings router
- `backend/app/schemas/catalog.py` — added aggregate_score and reviews to AlbumDetail and TrackDetail
- `backend/app/services/catalog.py` — get_album and get_track now accept optional viewer_clerk_id and return rating data
- `backend/app/api/v1/catalog.py` — get_album and get_track accept OptionalClerkId
- `backend/app/services/user.py` — ratings_count populated from rating_svc.count_for_user() (replaced hardcoded 0); viewer variable scoping bug fixed

**New — Frontend**
- `frontend/src/components/RatingComposer.tsx` — score selector, review textarea, visibility picker, submit
- `frontend/src/components/ReviewList.tsx` — review items with delete/report/visibility controls
- `frontend/src/components/RatingSection.tsx` — aggregate display + composer + review list; manages optimistic state
- `frontend/src/lib/ratings.ts` — typed API client for all ratings endpoints

**Modified — Frontend**
- `frontend/src/types/index.ts` — added ReviewerInfo, RatingRead, EntityRatingListResponse, UserRatingRead, UserRatingListResponse; extended AlbumDetail and TrackDetail with aggregate_score and reviews; RatingSubmitRequest uses entity_mbid (not entity_id)
- `frontend/src/lib/catalog.ts` — catalogGet, getAlbum, and getTrack accept optional auth token
- `frontend/src/app/track/[mbid]/page.tsx` — passes auth token to getTrack; renders RatingSection
- `frontend/src/app/album/[mbid]/page.tsx` — same pattern as track page
- `frontend/src/app/u/[username]/page.tsx` — fetches and renders user review history

## Decisions made

**entity_mbid in submit payload (not entity_id):**
The frontend only knows MBIDs, not internal UUIDs. The submit endpoint accepts `entity_mbid`; the service resolves it to an internal UUID via `resolve_entity()`. Keeps the public API surface consistent with catalog endpoints (all use MBIDs).

**Polymorphic entity reference without DB FK:**
`ratings.entity_id` references either `tracks.id` or `albums.id` depending on `entity_type`. A DB-level FK would require two separate FK constraints or a junction table. Service-layer enforcement via `resolve_entity()` achieves the same safety with less schema complexity. If the MBID doesn't resolve, the endpoint returns 404 before any row is written.

**Aggregate via window function (no denormalized column):**
`ROW_NUMBER() OVER (PARTITION BY user_id ORDER BY created_at DESC)` selects each user's most-recent rating in a subquery; AVG is applied to that set. Avoids maintaining a denormalized `is_current` boolean across inserts and deletes.

**Report duplicate detection via IntegrityError (not pre-check):**
The UNIQUE constraint on `(reporter_id, rating_id)` catches duplicates at the DB level. The service catches `IntegrityError`, rolls back, and returns `(False, "duplicate")`. This is race-condition safe and avoids a pre-flight SELECT.

**Public default for rating visibility:**
Ratings default to `public`, not `private`. Documented as an explicit exception to the "default private" convention used elsewhere. See Special Notes above.

**VisibilityScope StrEnum reused from core/enums.py:**
No duplication — the same enum used for profile visibility covers rating visibility.

## Future improvements

- Real friends check in `_is_friend()` — unblock when follows table ships.
- Report queue and admin moderation tooling — spec required before implementation.
- Paginated review list — currently returns all visible reviews in a single response.
- Re-rating UX: composer could pre-fill the user's most recent score/text on revisit.
- `ENGINEERING_BIBLE.md` update — document the polymorphic entity reference pattern and window-function aggregate approach if a future feature (e.g. listen logs) needs to follow it.

## Known limitations

- `friends` visibility always resolves to `False` until the follows table ships. Any rating set to `friends` visibility behaves like `private` until that feature lands.
- Review list is not paginated. All visible reviews for an entity are returned in a single response.
- Report storage only — no admin interface or moderation queue exists yet.
