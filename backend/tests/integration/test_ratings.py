"""
Integration tests: rating persistence, aggregate calculation, visibility enforcement,
deletion, and reporting.

Visibility enforcement is the constitutional requirement (HARMONIQ.md §6, Consent Before
Visibility): a rating with PRIVATE visibility must be absent from other users' views,
enforced at the data-access layer, not in route handlers or the frontend.

Each test function gets its own `db_session` wrapped in a transaction that rolls back on
teardown.
"""

import logging
import uuid
from datetime import UTC, datetime

import pytest
from httpx import AsyncClient
from sqlalchemy import insert, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import VisibilityScope
from app.models.catalog import Album, Track
from app.models.rating import Rating, Report
from app.models.user import User
from app.schemas.rating import RatingRead
from app.services import rating as rating_svc
from app.services import user as user_svc

# ── Helpers ───────────────────────────────────────────────────────────────────

_REVIEW = "A solid record that rewards repeated listening."


async def _make_user(
    session: AsyncSession,
    *,
    clerk_id: str,
    username: str,
) -> User:
    user = await user_svc.create_user(session, clerk_id, username, "Test User")
    await session.flush()
    return user


async def _make_album(
    session: AsyncSession,
    *,
    mbid: str,
    title: str = "Test Album",
) -> Album:
    album = Album(
        id=uuid.uuid4(),
        mbid=mbid,
        title=title,
        last_fetched_at=datetime.now(UTC),
    )
    session.add(album)
    await session.flush()
    return album


async def _make_track(
    session: AsyncSession,
    *,
    mbid: str,
    title: str = "Test Track",
) -> Track:
    track = Track(
        id=uuid.uuid4(),
        mbid=mbid,
        title=title,
        last_fetched_at=datetime.now(UTC),
    )
    session.add(track)
    await session.flush()
    return track


async def _rate(
    session: AsyncSession,
    *,
    user: User,
    entity_type: str,
    entity_id: uuid.UUID,
    score: int = 7,
    text: str = _REVIEW,
    visibility: VisibilityScope = VisibilityScope.PUBLIC,
) -> RatingRead:
    return await rating_svc.submit(
        session,
        user_id=user.id,
        entity_type=entity_type,
        entity_id=entity_id,
        score=score,
        review_text=text,
        visibility=visibility,
    )


# ── §4.1 Rating persistence ───────────────────────────────────────────────────


@pytest.mark.integration
class TestRatingPersistence:
    async def test_submit_creates_row(self, db_session: AsyncSession) -> None:
        user = await _make_user(db_session, clerk_id="clerk_rp_01", username="rp_u1")
        track = await _make_track(db_session, mbid="mbid-rp-01")

        rating = await _rate(
            db_session, user=user, entity_type="track", entity_id=track.id
        )

        result = await db_session.execute(select(Rating).where(Rating.id == rating.id))
        assert result.scalar_one_or_none() is not None

    async def test_submit_stores_all_fields(self, db_session: AsyncSession) -> None:
        user = await _make_user(db_session, clerk_id="clerk_rp_02", username="rp_u2")
        album = await _make_album(db_session, mbid="mbid-rp-02")

        await _rate(
            db_session,
            user=user,
            entity_type="album",
            entity_id=album.id,
            score=8,
            visibility=VisibilityScope.PRIVATE,
        )

        result = await db_session.execute(
            select(Rating).where(
                Rating.user_id == user.id, Rating.entity_id == album.id
            )
        )
        row = result.scalar_one()
        assert row.score == 8
        assert row.review_text == _REVIEW
        assert row.visibility == "private"
        assert row.entity_type == "album"

    async def test_default_visibility_is_public(self, db_session: AsyncSession) -> None:
        """Ratings default to public — intentional exception to default-private convention."""
        user = await _make_user(db_session, clerk_id="clerk_rp_03", username="rp_u3")
        track = await _make_track(db_session, mbid="mbid-rp-03")

        await _rate(db_session, user=user, entity_type="track", entity_id=track.id)

        result = await db_session.execute(
            select(Rating).where(Rating.user_id == user.id)
        )
        assert result.scalar_one().visibility == "public"

    async def test_rerating_preserves_history(self, db_session: AsyncSession) -> None:
        user = await _make_user(db_session, clerk_id="clerk_rp_04", username="rp_u4")
        track = await _make_track(db_session, mbid="mbid-rp-04")

        await _rate(
            db_session, user=user, entity_type="track", entity_id=track.id, score=5
        )
        await _rate(
            db_session, user=user, entity_type="track", entity_id=track.id, score=9
        )

        result = await db_session.execute(
            select(Rating).where(
                Rating.user_id == user.id, Rating.entity_id == track.id
            )
        )
        rows = result.scalars().all()
        assert len(rows) == 2
        assert {r.score for r in rows} == {5, 9}

    async def test_rating_has_uuid_id_and_timestamp(
        self, db_session: AsyncSession
    ) -> None:
        user = await _make_user(db_session, clerk_id="clerk_rp_05", username="rp_u5")
        track = await _make_track(db_session, mbid="mbid-rp-05")

        rating = await _rate(
            db_session, user=user, entity_type="track", entity_id=track.id
        )

        result = await db_session.execute(select(Rating).where(Rating.id == rating.id))
        row = result.scalar_one()
        assert isinstance(row.id, uuid.UUID)
        assert row.created_at is not None

    async def test_score_check_constraint_enforced(
        self, db_session: AsyncSession
    ) -> None:
        user = await _make_user(db_session, clerk_id="clerk_rp_06", username="rp_u6")
        track = await _make_track(db_session, mbid="mbid-rp-06")

        with pytest.raises(IntegrityError):
            await db_session.execute(
                insert(Rating).values(
                    id=uuid.uuid4(),
                    user_id=user.id,
                    entity_type="track",
                    entity_id=track.id,
                    score=0,
                    review_text=_REVIEW,
                    visibility="public",
                    created_at=datetime.now(UTC),
                )
            )
            await db_session.flush()


# ── §4.2 Aggregate calculation ────────────────────────────────────────────────


@pytest.mark.integration
class TestAggregateCalculation:
    async def test_no_ratings_returns_none(self, db_session: AsyncSession) -> None:
        track = await _make_track(db_session, mbid="mbid-agg-01")

        assert await rating_svc.get_aggregate(db_session, "track", track.id) is None

    async def test_single_rating_returns_that_score(
        self, db_session: AsyncSession
    ) -> None:
        user = await _make_user(db_session, clerk_id="clerk_agg_01", username="agg_u1")
        track = await _make_track(db_session, mbid="mbid-agg-02")

        await _rate(
            db_session, user=user, entity_type="track", entity_id=track.id, score=7
        )

        assert await rating_svc.get_aggregate(
            db_session, "track", track.id
        ) == pytest.approx(7.0)

    async def test_multiple_users_averaged(self, db_session: AsyncSession) -> None:
        u1 = await _make_user(db_session, clerk_id="clerk_agg_02a", username="agg_u2a")
        u2 = await _make_user(db_session, clerk_id="clerk_agg_02b", username="agg_u2b")
        track = await _make_track(db_session, mbid="mbid-agg-03")

        await _rate(
            db_session, user=u1, entity_type="track", entity_id=track.id, score=6
        )
        await _rate(
            db_session, user=u2, entity_type="track", entity_id=track.id, score=8
        )

        assert await rating_svc.get_aggregate(
            db_session, "track", track.id
        ) == pytest.approx(7.0)

    async def test_rerate_uses_most_recent_only(self, db_session: AsyncSession) -> None:
        """Window function must select each user's latest rating, ignoring earlier ones."""
        user = await _make_user(db_session, clerk_id="clerk_agg_03", username="agg_u3")
        track = await _make_track(db_session, mbid="mbid-agg-04")

        await _rate(
            db_session, user=user, entity_type="track", entity_id=track.id, score=3
        )
        await _rate(
            db_session, user=user, entity_type="track", entity_id=track.id, score=9
        )

        assert await rating_svc.get_aggregate(
            db_session, "track", track.id
        ) == pytest.approx(9.0)

    async def test_different_entities_isolated(self, db_session: AsyncSession) -> None:
        user = await _make_user(db_session, clerk_id="clerk_agg_04", username="agg_u4")
        t1 = await _make_track(db_session, mbid="mbid-agg-05a")
        t2 = await _make_track(db_session, mbid="mbid-agg-05b")

        await _rate(
            db_session, user=user, entity_type="track", entity_id=t1.id, score=2
        )
        await _rate(
            db_session, user=user, entity_type="track", entity_id=t2.id, score=10
        )

        assert await rating_svc.get_aggregate(
            db_session, "track", t1.id
        ) == pytest.approx(2.0)
        assert await rating_svc.get_aggregate(
            db_session, "track", t2.id
        ) == pytest.approx(10.0)


# ── §4.3 Visibility enforcement ───────────────────────────────────────────────


@pytest.mark.integration
class TestVisibilityEnforcement:
    """
    Consent Before Visibility (HARMONIQ.md §6): service layer must withhold
    private ratings from other viewers — not return them as null.
    """

    async def test_public_rating_visible_to_anonymous(
        self, db_session: AsyncSession
    ) -> None:
        user = await _make_user(db_session, clerk_id="clerk_ve_01", username="ve_u1")
        track = await _make_track(db_session, mbid="mbid-ve-01")

        await _rate(
            db_session,
            user=user,
            entity_type="track",
            entity_id=track.id,
            visibility=VisibilityScope.PUBLIC,
        )

        result = await rating_svc.list_for_entity(
            db_session, "track", track.id, viewer_id=None
        )
        assert len(result.reviews) == 1

    async def test_private_rating_hidden_from_stranger(
        self, db_session: AsyncSession
    ) -> None:
        owner = await _make_user(db_session, clerk_id="clerk_ve_02a", username="ve_u2a")
        stranger = await _make_user(
            db_session, clerk_id="clerk_ve_02b", username="ve_u2b"
        )
        track = await _make_track(db_session, mbid="mbid-ve-02")

        await _rate(
            db_session,
            user=owner,
            entity_type="track",
            entity_id=track.id,
            visibility=VisibilityScope.PRIVATE,
        )

        result = await rating_svc.list_for_entity(
            db_session, "track", track.id, viewer_id=stranger.id
        )
        assert len(result.reviews) == 0

    async def test_private_rating_visible_to_owner(
        self, db_session: AsyncSession
    ) -> None:
        owner = await _make_user(db_session, clerk_id="clerk_ve_03", username="ve_u3")
        track = await _make_track(db_session, mbid="mbid-ve-03")

        await _rate(
            db_session,
            user=owner,
            entity_type="track",
            entity_id=track.id,
            visibility=VisibilityScope.PRIVATE,
        )

        result = await rating_svc.list_for_entity(
            db_session, "track", track.id, viewer_id=owner.id
        )
        assert len(result.reviews) == 1

    async def test_friends_scope_behaves_as_private_for_non_friend(
        self, db_session: AsyncSession
    ) -> None:
        """
        _is_friend() stubs to False until the follows table ships.
        FRIENDS-scoped ratings must behave as PRIVATE today; this test pins that behavior
        so the change is visible when follows land.
        """
        owner = await _make_user(db_session, clerk_id="clerk_ve_04a", username="ve_u4a")
        viewer = await _make_user(
            db_session, clerk_id="clerk_ve_04b", username="ve_u4b"
        )
        track = await _make_track(db_session, mbid="mbid-ve-04")

        await _rate(
            db_session,
            user=owner,
            entity_type="track",
            entity_id=track.id,
            visibility=VisibilityScope.FRIENDS,
        )

        result = await rating_svc.list_for_entity(
            db_session, "track", track.id, viewer_id=viewer.id
        )
        assert len(result.reviews) == 0

    async def test_list_for_user_excludes_private_from_stranger(
        self, db_session: AsyncSession
    ) -> None:
        owner = await _make_user(db_session, clerk_id="clerk_ve_05a", username="ve_u5a")
        stranger = await _make_user(
            db_session, clerk_id="clerk_ve_05b", username="ve_u5b"
        )
        track = await _make_track(db_session, mbid="mbid-ve-05")

        await _rate(
            db_session,
            user=owner,
            entity_type="track",
            entity_id=track.id,
            visibility=VisibilityScope.PRIVATE,
        )

        result = await rating_svc.list_for_user(
            db_session, owner.id, viewer_id=stranger.id
        )
        assert len(result.reviews) == 0

    async def test_count_for_user_counts_public_only_for_stranger(
        self, db_session: AsyncSession
    ) -> None:
        owner = await _make_user(db_session, clerk_id="clerk_ve_06a", username="ve_u6a")
        stranger = await _make_user(
            db_session, clerk_id="clerk_ve_06b", username="ve_u6b"
        )
        t1 = await _make_track(db_session, mbid="mbid-ve-06a")
        t2 = await _make_track(db_session, mbid="mbid-ve-06b")

        await _rate(
            db_session,
            user=owner,
            entity_type="track",
            entity_id=t1.id,
            visibility=VisibilityScope.PUBLIC,
        )
        await _rate(
            db_session,
            user=owner,
            entity_type="track",
            entity_id=t2.id,
            visibility=VisibilityScope.PRIVATE,
        )

        count = await rating_svc.count_for_user(
            db_session, owner.id, viewer_id=stranger.id
        )
        assert count == 1


# ── §4.4 Delete rating ────────────────────────────────────────────────────────


@pytest.mark.integration
class TestDeleteRating:
    async def test_delete_own_rating_returns_true(
        self, db_session: AsyncSession
    ) -> None:
        user = await _make_user(db_session, clerk_id="clerk_del_01", username="del_u1")
        track = await _make_track(db_session, mbid="mbid-del-01")
        rating = await _rate(
            db_session, user=user, entity_type="track", entity_id=track.id
        )

        assert await rating_svc.delete_rating(db_session, rating.id, user.id) is True

    async def test_delete_own_rating_removes_row(
        self, db_session: AsyncSession
    ) -> None:
        user = await _make_user(db_session, clerk_id="clerk_del_02", username="del_u2")
        track = await _make_track(db_session, mbid="mbid-del-02")
        rating = await _rate(
            db_session, user=user, entity_type="track", entity_id=track.id
        )

        await rating_svc.delete_rating(db_session, rating.id, user.id)

        result = await db_session.execute(select(Rating).where(Rating.id == rating.id))
        assert result.scalar_one_or_none() is None

    async def test_delete_nonexistent_returns_false(
        self, db_session: AsyncSession
    ) -> None:
        user = await _make_user(db_session, clerk_id="clerk_del_03", username="del_u3")

        assert (
            await rating_svc.delete_rating(db_session, uuid.uuid4(), user.id) is False
        )

    async def test_delete_other_users_rating_returns_false(
        self, db_session: AsyncSession
    ) -> None:
        owner = await _make_user(
            db_session, clerk_id="clerk_del_04a", username="del_u4a"
        )
        other = await _make_user(
            db_session, clerk_id="clerk_del_04b", username="del_u4b"
        )
        track = await _make_track(db_session, mbid="mbid-del-04")
        rating = await _rate(
            db_session, user=owner, entity_type="track", entity_id=track.id
        )

        assert await rating_svc.delete_rating(db_session, rating.id, other.id) is False

    async def test_unauthorized_delete_logs_warning(
        self, db_session: AsyncSession, caplog: pytest.LogCaptureFixture
    ) -> None:
        owner = await _make_user(
            db_session, clerk_id="clerk_del_05a", username="del_u5a"
        )
        other = await _make_user(
            db_session, clerk_id="clerk_del_05b", username="del_u5b"
        )
        track = await _make_track(db_session, mbid="mbid-del-05")
        rating = await _rate(
            db_session, user=owner, entity_type="track", entity_id=track.id
        )

        with caplog.at_level(logging.WARNING, logger="app.services.rating"):
            await rating_svc.delete_rating(db_session, rating.id, other.id)

        assert any("Unauthorized delete attempt" in r.message for r in caplog.records)

    async def test_row_intact_after_unauthorized_delete(
        self, db_session: AsyncSession
    ) -> None:
        owner = await _make_user(
            db_session, clerk_id="clerk_del_06a", username="del_u6a"
        )
        other = await _make_user(
            db_session, clerk_id="clerk_del_06b", username="del_u6b"
        )
        track = await _make_track(db_session, mbid="mbid-del-06")
        rating = await _rate(
            db_session, user=owner, entity_type="track", entity_id=track.id
        )

        await rating_svc.delete_rating(db_session, rating.id, other.id)

        result = await db_session.execute(select(Rating).where(Rating.id == rating.id))
        assert result.scalar_one_or_none() is not None


# ── §4.5 Report rating ────────────────────────────────────────────────────────


@pytest.mark.integration
class TestReportRating:
    async def test_report_creates_db_row(self, db_session: AsyncSession) -> None:
        owner = await _make_user(
            db_session, clerk_id="clerk_rep_01a", username="rep_u1a"
        )
        reporter = await _make_user(
            db_session, clerk_id="clerk_rep_01b", username="rep_u1b"
        )
        track = await _make_track(db_session, mbid="mbid-rep-01")
        rating = await _rate(
            db_session, user=owner, entity_type="track", entity_id=track.id
        )

        success, _ = await rating_svc.report_rating(db_session, reporter.id, rating.id)

        assert success is True
        result = await db_session.execute(
            select(Report).where(
                Report.reporter_id == reporter.id, Report.rating_id == rating.id
            )
        )
        assert result.scalar_one_or_none() is not None

    async def test_self_report_rejected(self, db_session: AsyncSession) -> None:
        user = await _make_user(db_session, clerk_id="clerk_rep_02", username="rep_u2")
        track = await _make_track(db_session, mbid="mbid-rep-02")
        rating = await _rate(
            db_session, user=user, entity_type="track", entity_id=track.id
        )

        success, error = await rating_svc.report_rating(db_session, user.id, rating.id)

        assert success is False
        assert "own review" in error.lower()

    async def test_duplicate_report_rejected(self, db_session: AsyncSession) -> None:
        """UNIQUE constraint on (reporter_id, rating_id) caught as IntegrityError."""
        owner = await _make_user(
            db_session, clerk_id="clerk_rep_03a", username="rep_u3a"
        )
        reporter = await _make_user(
            db_session, clerk_id="clerk_rep_03b", username="rep_u3b"
        )
        track = await _make_track(db_session, mbid="mbid-rep-03")
        rating = await _rate(
            db_session, user=owner, entity_type="track", entity_id=track.id
        )

        # Pre-seed the first report directly to avoid rollback state in the session.
        db_session.add(
            Report(
                id=uuid.uuid4(),
                reporter_id=reporter.id,
                rating_id=rating.id,
                created_at=datetime.now(UTC),
            )
        )
        await db_session.flush()

        success, error = await rating_svc.report_rating(
            db_session, reporter.id, rating.id
        )

        assert success is False
        assert "already reported" in error.lower()

    async def test_report_nonexistent_rating_rejected(
        self, db_session: AsyncSession
    ) -> None:
        reporter = await _make_user(
            db_session, clerk_id="clerk_rep_04", username="rep_u4"
        )

        success, error = await rating_svc.report_rating(
            db_session, reporter.id, uuid.uuid4()
        )

        assert success is False
        assert "not found" in error.lower()


# ── §4.6 Ratings API (HTTP) ───────────────────────────────────────────────────


@pytest.mark.integration
class TestRatingsAPI:
    async def test_submit_returns_201_with_review_data(
        self, authed_client: tuple[AsyncClient, str], db_session: AsyncSession
    ) -> None:
        ac, clerk_id = authed_client
        await _make_user(db_session, clerk_id=clerk_id, username="api_sub1")
        await _make_track(db_session, mbid="mbid-api-s01")

        resp = await ac.post(
            "/api/v1/ratings/",
            json={
                "entity_type": "track",
                "entity_mbid": "mbid-api-s01",
                "score": 8,
                "review_text": _REVIEW,
            },
        )

        assert resp.status_code == 201
        body = resp.json()
        assert body["score"] == 8
        assert body["review_text"] == _REVIEW
        assert body["reviewer"]["username"] == "api_sub1"

    async def test_submit_unknown_entity_returns_404(
        self, authed_client: tuple[AsyncClient, str], db_session: AsyncSession
    ) -> None:
        ac, clerk_id = authed_client
        await _make_user(db_session, clerk_id=clerk_id, username="api_sub2")

        resp = await ac.post(
            "/api/v1/ratings/",
            json={
                "entity_type": "track",
                "entity_mbid": "mbid-does-not-exist",
                "score": 5,
                "review_text": _REVIEW,
            },
        )

        assert resp.status_code == 404

    async def test_submit_bad_score_returns_422(
        self, authed_client: tuple[AsyncClient, str], db_session: AsyncSession
    ) -> None:
        ac, clerk_id = authed_client
        await _make_user(db_session, clerk_id=clerk_id, username="api_sub3")

        resp = await ac.post(
            "/api/v1/ratings/",
            json={
                "entity_type": "track",
                "entity_mbid": "any",
                "score": 0,
                "review_text": _REVIEW,
            },
        )

        assert resp.status_code == 422

    async def test_submit_review_too_short_returns_422(
        self, authed_client: tuple[AsyncClient, str], db_session: AsyncSession
    ) -> None:
        ac, clerk_id = authed_client
        await _make_user(db_session, clerk_id=clerk_id, username="api_sub4")

        resp = await ac.post(
            "/api/v1/ratings/",
            json={
                "entity_type": "track",
                "entity_mbid": "any",
                "score": 5,
                "review_text": "too short",
            },
        )

        assert resp.status_code == 422

    async def test_submit_bad_entity_type_returns_422(
        self, authed_client: tuple[AsyncClient, str], db_session: AsyncSession
    ) -> None:
        ac, clerk_id = authed_client
        await _make_user(db_session, clerk_id=clerk_id, username="api_sub5")

        resp = await ac.post(
            "/api/v1/ratings/",
            json={
                "entity_type": "artist",
                "entity_mbid": "any",
                "score": 5,
                "review_text": _REVIEW,
            },
        )

        assert resp.status_code == 422

    async def test_list_entity_returns_reviews_and_aggregate(
        self, authed_client: tuple[AsyncClient, str], db_session: AsyncSession
    ) -> None:
        ac, clerk_id = authed_client
        user = await _make_user(db_session, clerk_id=clerk_id, username="api_list1")
        track = await _make_track(db_session, mbid="mbid-api-l01")
        await _rate(
            db_session, user=user, entity_type="track", entity_id=track.id, score=6
        )

        resp = await ac.get("/api/v1/ratings/entity/track/mbid-api-l01")

        assert resp.status_code == 200
        body = resp.json()
        assert body["aggregate_score"] == pytest.approx(6.0)
        assert len(body["reviews"]) == 1

    async def test_list_entity_unknown_mbid_returns_empty(
        self, anon_client: AsyncClient
    ) -> None:
        resp = await anon_client.get(
            "/api/v1/ratings/entity/track/mbid-totally-unknown"
        )

        assert resp.status_code == 200
        body = resp.json()
        assert body["aggregate_score"] is None
        assert body["reviews"] == []

    async def test_list_entity_bad_type_returns_400(
        self, anon_client: AsyncClient
    ) -> None:
        resp = await anon_client.get("/api/v1/ratings/entity/artist/any-mbid")

        assert resp.status_code == 400

    async def test_list_user_returns_history(
        self, authed_client: tuple[AsyncClient, str], db_session: AsyncSession
    ) -> None:
        ac, clerk_id = authed_client
        user = await _make_user(db_session, clerk_id=clerk_id, username="api_hist1")
        track = await _make_track(db_session, mbid="mbid-api-h01")
        await _rate(
            db_session, user=user, entity_type="track", entity_id=track.id, score=7
        )

        resp = await ac.get("/api/v1/ratings/user/api_hist1")

        assert resp.status_code == 200
        body = resp.json()
        assert len(body["reviews"]) == 1
        assert body["reviews"][0]["score"] == 7

    async def test_list_user_unknown_returns_404(
        self, anon_client: AsyncClient
    ) -> None:
        resp = await anon_client.get("/api/v1/ratings/user/nobody_here_xyz")

        assert resp.status_code == 404

    async def test_delete_own_rating_returns_204(
        self, authed_client: tuple[AsyncClient, str], db_session: AsyncSession
    ) -> None:
        ac, clerk_id = authed_client
        user = await _make_user(db_session, clerk_id=clerk_id, username="api_del1")
        track = await _make_track(db_session, mbid="mbid-api-d01")
        rating = await _rate(
            db_session, user=user, entity_type="track", entity_id=track.id
        )

        resp = await ac.delete(f"/api/v1/ratings/{rating.id}")

        assert resp.status_code == 204

    async def test_delete_other_users_rating_returns_404(
        self, authed_client: tuple[AsyncClient, str], db_session: AsyncSession
    ) -> None:
        ac, clerk_id = authed_client
        await _make_user(db_session, clerk_id=clerk_id, username="api_del2_viewer")
        owner = await _make_user(
            db_session, clerk_id="clerk_api_del2_owner", username="api_del2_owner"
        )
        track = await _make_track(db_session, mbid="mbid-api-d02")
        rating = await _rate(
            db_session, user=owner, entity_type="track", entity_id=track.id
        )

        resp = await ac.delete(f"/api/v1/ratings/{rating.id}")

        assert resp.status_code == 404

    async def test_report_rating_returns_204(
        self, authed_client: tuple[AsyncClient, str], db_session: AsyncSession
    ) -> None:
        ac, clerk_id = authed_client
        await _make_user(db_session, clerk_id=clerk_id, username="api_rep1_reporter")
        owner = await _make_user(
            db_session, clerk_id="clerk_api_rep1_owner", username="api_rep1_owner"
        )
        track = await _make_track(db_session, mbid="mbid-api-r01")
        rating = await _rate(
            db_session, user=owner, entity_type="track", entity_id=track.id
        )

        resp = await ac.post(f"/api/v1/ratings/{rating.id}/report")

        assert resp.status_code == 204

    async def test_duplicate_report_returns_409(
        self, authed_client: tuple[AsyncClient, str], db_session: AsyncSession
    ) -> None:
        ac, clerk_id = authed_client
        reporter = await _make_user(
            db_session, clerk_id=clerk_id, username="api_rep2_reporter"
        )
        owner = await _make_user(
            db_session, clerk_id="clerk_api_rep2_owner", username="api_rep2_owner"
        )
        track = await _make_track(db_session, mbid="mbid-api-r02")
        rating = await _rate(
            db_session, user=owner, entity_type="track", entity_id=track.id
        )

        # Pre-seed a report so the HTTP call sees a duplicate constraint violation.
        db_session.add(
            Report(
                id=uuid.uuid4(),
                reporter_id=reporter.id,
                rating_id=rating.id,
                created_at=datetime.now(UTC),
            )
        )
        await db_session.flush()

        resp = await ac.post(f"/api/v1/ratings/{rating.id}/report")

        assert resp.status_code == 409

    async def test_self_report_returns_403(
        self, authed_client: tuple[AsyncClient, str], db_session: AsyncSession
    ) -> None:
        ac, clerk_id = authed_client
        user = await _make_user(db_session, clerk_id=clerk_id, username="api_rep3_self")
        track = await _make_track(db_session, mbid="mbid-api-r03")
        rating = await _rate(
            db_session, user=user, entity_type="track", entity_id=track.id
        )

        resp = await ac.post(f"/api/v1/ratings/{rating.id}/report")

        assert resp.status_code == 403

    async def test_update_visibility_returns_200(
        self, authed_client: tuple[AsyncClient, str], db_session: AsyncSession
    ) -> None:
        ac, clerk_id = authed_client
        user = await _make_user(db_session, clerk_id=clerk_id, username="api_vis1")
        track = await _make_track(db_session, mbid="mbid-api-v01")
        rating = await _rate(
            db_session,
            user=user,
            entity_type="track",
            entity_id=track.id,
            visibility=VisibilityScope.PUBLIC,
        )

        resp = await ac.patch(
            f"/api/v1/ratings/{rating.id}/visibility",
            json={"visibility": "private"},
        )

        assert resp.status_code == 200
        assert resp.json()["visibility"] == "private"
