"""
Integration tests: moderator authz (404 existence-hiding), hide-rating
exclusion from every surface, report lifecycle, and the suspension matrix.

The surfaces list for hide is the security-critical part: entity list,
profile history, aggregate, Home trending, Home friends — plus the author's
own flagged view. A miss on any one of them is a moderation bypass.
"""

import uuid
from datetime import UTC, datetime

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user, get_optional_clerk_id
from app.core.enums import ReportStatus, VisibilityScope
from app.database import get_db
from app.main import app
from app.models.catalog import Track
from app.models.rating import Rating, Report
from app.models.user import User
from app.services import follow as follow_svc
from app.services import home as home_svc
from app.services import moderation as moderation_svc
from app.services import rating as rating_svc
from app.services import user as user_svc

# ── Helpers ───────────────────────────────────────────────────────────────────


async def _make_user(
    session: AsyncSession,
    *,
    clerk_id: str,
    username: str,
    is_moderator: bool = False,
    suspended: bool = False,
) -> User:
    user = await user_svc.create_user(session, clerk_id, username, "Test User")
    user.is_moderator = is_moderator
    if suspended:
        user.suspended_at = datetime.now(UTC)
    await session.flush()
    return user


async def _make_track(session: AsyncSession, *, mbid: str) -> Track:
    track = Track(
        id=uuid.uuid4(),
        mbid=mbid,
        title="Test Track",
        last_fetched_at=datetime.now(UTC),
    )
    session.add(track)
    await session.flush()
    return track


async def _rate(
    session: AsyncSession, *, user: User, track: Track, score: int = 7
) -> Rating:
    read = await rating_svc.submit(
        session,
        user_id=user.id,
        entity_type="track",
        entity_id=track.id,
        score=score,
        review_text="A solid record that rewards repeated listening.",
        visibility=VisibilityScope.PUBLIC,
    )
    result = await session.execute(select(Rating).where(Rating.id == read.id))
    return result.scalar_one()


def _db_override(session: AsyncSession):
    async def _override():
        yield session

    return _override


def _client_for(session: AsyncSession, clerk_id: str) -> AsyncClient:
    async def _current_user() -> str:
        return clerk_id

    async def _optional_id() -> str | None:
        return clerk_id

    app.dependency_overrides[get_db] = _db_override(session)
    app.dependency_overrides[get_current_user] = _current_user
    app.dependency_overrides[get_optional_clerk_id] = _optional_id
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


# ── Moderator authz ───────────────────────────────────────────────────────────


@pytest.mark.integration
class TestModeratorAuthz:
    _ENDPOINTS = [
        ("GET", "/api/v1/moderation/reports"),
        ("POST", f"/api/v1/moderation/reports/{uuid.uuid4()}/dismiss"),
        ("POST", f"/api/v1/moderation/ratings/{uuid.uuid4()}/hide"),
        ("POST", "/api/v1/moderation/users/someone/suspend"),
    ]

    async def test_non_moderator_gets_404_on_every_endpoint(
        self, db_session: AsyncSession
    ) -> None:
        user = await _make_user(db_session, clerk_id="mod_a_01", username="mod_a_01")

        async with _client_for(db_session, user.clerk_id) as client:
            for method, url in self._ENDPOINTS:
                resp = await client.request(method, url)
                assert resp.status_code == 404, f"{method} {url} → {resp.status_code}"
        app.dependency_overrides.clear()

    async def test_suspended_moderator_gets_404(self, db_session: AsyncSession) -> None:
        user = await _make_user(
            db_session,
            clerk_id="mod_a_02",
            username="mod_a_02",
            is_moderator=True,
            suspended=True,
        )

        async with _client_for(db_session, user.clerk_id) as client:
            resp = await client.get("/api/v1/moderation/reports")
        app.dependency_overrides.clear()
        assert resp.status_code == 404

    async def test_moderator_can_list_reports(self, db_session: AsyncSession) -> None:
        mod = await _make_user(
            db_session, clerk_id="mod_a_03", username="mod_a_03", is_moderator=True
        )

        async with _client_for(db_session, mod.clerk_id) as client:
            resp = await client.get("/api/v1/moderation/reports")
        app.dependency_overrides.clear()
        assert resp.status_code == 200
        assert resp.json() == {"items": [], "next_cursor": None}


# ── Hide: every surface ───────────────────────────────────────────────────────


@pytest.mark.integration
class TestHideRating:
    async def test_hidden_excluded_from_every_surface_but_visible_to_author(
        self, db_session: AsyncSession
    ) -> None:
        mod = await _make_user(
            db_session, clerk_id="mod_h_01m", username="mod_h_01m", is_moderator=True
        )
        author = await _make_user(
            db_session, clerk_id="mod_h_01a", username="mod_h_01a"
        )
        other = await _make_user(db_session, clerk_id="mod_h_01o", username="mod_h_01o")
        friend = await _make_user(
            db_session, clerk_id="mod_h_01f", username="mod_h_01f"
        )
        # author ↔ friend are mutuals so the Home friends section applies.
        await follow_svc.follow(db_session, author.id, friend.id)
        await follow_svc.follow(db_session, friend.id, author.id)
        track = await _make_track(db_session, mbid="mbid-mod-h-01")
        rating = await _rate(db_session, user=author, track=track, score=9)
        other_rating = await _rate(db_session, user=other, track=track, score=3)
        assert other_rating is not None

        success, error = await moderation_svc.hide_rating(
            db_session, moderator_id=mod.id, rating_id=rating.id
        )
        assert success, error

        # 1. Entity list: gone for others, present + flagged for the author.
        for_other = await rating_svc.list_for_entity(
            db_session, "track", track.id, viewer_id=other.id
        )
        assert rating.id not in [r.id for r in for_other.reviews]
        for_author = await rating_svc.list_for_entity(
            db_session, "track", track.id, viewer_id=author.id
        )
        own = [r for r in for_author.reviews if r.id == rating.id]
        assert len(own) == 1 and own[0].hidden is True

        # 2. Aggregate: only the non-hidden rating counts.
        aggregate = await rating_svc.get_aggregate(db_session, "track", track.id)
        assert aggregate == 3.0

        # 3. Profile history: gone for others, flagged for the author.
        profile_for_other = await rating_svc.list_for_user(
            db_session, author, viewer_id=other.id
        )
        assert rating.id not in [r.id for r in profile_for_other.reviews]
        profile_own = await rating_svc.list_for_user(
            db_session, author, viewer_id=author.id
        )
        assert any(r.id == rating.id and r.hidden for r in profile_own.reviews)

        # 4. Counts: excluded for others, included for the author.
        assert await rating_svc.count_for_user(db_session, author, other.id) == 0
        assert await rating_svc.count_for_user(db_session, author, author.id) == 1

        # 5. Home trending: only the visible rating's score shows.
        trending = await home_svc.get_trending(db_session, limit=10)
        entry = [t for t in trending if t.track.id == track.id]
        assert entry and entry[0].aggregate_score == 3.0

        # 6. Home friends section (friend's view): hidden rating absent.
        friends_top = await home_svc.get_friends_top_tracks(
            db_session, viewer_id=friend.id, limit=10
        )
        assert all(
            not (e.rated_by.id == author.id and e.track.id == track.id)
            for e in friends_top
        )

    async def test_hide_marks_open_reports_actioned(
        self, db_session: AsyncSession
    ) -> None:
        mod = await _make_user(
            db_session, clerk_id="mod_h_02m", username="mod_h_02m", is_moderator=True
        )
        author = await _make_user(
            db_session, clerk_id="mod_h_02a", username="mod_h_02a"
        )
        r1 = await _make_user(db_session, clerk_id="mod_h_02r1", username="mod_h_02r1")
        r2 = await _make_user(db_session, clerk_id="mod_h_02r2", username="mod_h_02r2")
        track = await _make_track(db_session, mbid="mbid-mod-h-02")
        rating = await _rate(db_session, user=author, track=track)

        for reporter in (r1, r2):
            ok, _ = await rating_svc.report_rating(db_session, reporter.id, rating.id)
            assert ok

        success, _ = await moderation_svc.hide_rating(
            db_session, moderator_id=mod.id, rating_id=rating.id
        )
        assert success

        reports = (
            (
                await db_session.execute(
                    select(Report).where(Report.rating_id == rating.id)
                )
            )
            .scalars()
            .all()
        )
        assert len(reports) == 2
        assert all(r.status == ReportStatus.ACTIONED.value for r in reports)
        assert all(
            r.resolved_by == mod.id and r.resolved_at is not None for r in reports
        )

    async def test_double_hide_conflicts(self, db_session: AsyncSession) -> None:
        mod = await _make_user(
            db_session, clerk_id="mod_h_03m", username="mod_h_03m", is_moderator=True
        )
        author = await _make_user(
            db_session, clerk_id="mod_h_03a", username="mod_h_03a"
        )
        track = await _make_track(db_session, mbid="mbid-mod-h-03")
        rating = await _rate(db_session, user=author, track=track)

        success, _ = await moderation_svc.hide_rating(db_session, mod.id, rating.id)
        assert success
        success, error = await moderation_svc.hide_rating(db_session, mod.id, rating.id)
        assert not success and "already" in error


# ── Report lifecycle ──────────────────────────────────────────────────────────


@pytest.mark.integration
class TestReportLifecycle:
    async def test_dismiss_and_double_dismiss(self, db_session: AsyncSession) -> None:
        mod = await _make_user(
            db_session, clerk_id="mod_r_01m", username="mod_r_01m", is_moderator=True
        )
        author = await _make_user(
            db_session, clerk_id="mod_r_01a", username="mod_r_01a"
        )
        reporter = await _make_user(
            db_session, clerk_id="mod_r_01r", username="mod_r_01r"
        )
        track = await _make_track(db_session, mbid="mbid-mod-r-01")
        rating = await _rate(db_session, user=author, track=track)
        ok, _ = await rating_svc.report_rating(db_session, reporter.id, rating.id)
        assert ok

        queue = await moderation_svc.list_reports(db_session)
        assert len(queue.items) == 1
        report_id = queue.items[0].id
        assert queue.items[0].open_report_count == 1
        assert queue.items[0].rating.author.username == author.username

        success, _ = await moderation_svc.dismiss_report(db_session, mod.id, report_id)
        assert success

        # Dismissed reports leave the open queue…
        assert (await moderation_svc.list_reports(db_session)).items == []
        # …and can't be resolved twice.
        success, error = await moderation_svc.dismiss_report(
            db_session, mod.id, report_id
        )
        assert not success and "already" in error

    async def test_reporting_hidden_rating_still_allowed(
        self, db_session: AsyncSession
    ) -> None:
        mod = await _make_user(
            db_session, clerk_id="mod_r_02m", username="mod_r_02m", is_moderator=True
        )
        author = await _make_user(
            db_session, clerk_id="mod_r_02a", username="mod_r_02a"
        )
        reporter = await _make_user(
            db_session, clerk_id="mod_r_02r", username="mod_r_02r"
        )
        track = await _make_track(db_session, mbid="mbid-mod-r-02")
        rating = await _rate(db_session, user=author, track=track)

        success, _ = await moderation_svc.hide_rating(db_session, mod.id, rating.id)
        assert success
        ok, _ = await rating_svc.report_rating(db_session, reporter.id, rating.id)
        assert ok

        queue = await moderation_svc.list_reports(db_session)
        assert len(queue.items) == 1
        assert queue.items[0].rating.hidden is True


# ── Suspension ────────────────────────────────────────────────────────────────


@pytest.mark.integration
class TestSuspension:
    async def test_suspend_guards(self, db_session: AsyncSession) -> None:
        mod = await _make_user(
            db_session, clerk_id="mod_s_01m", username="mod_s_01m", is_moderator=True
        )
        other_mod = await _make_user(
            db_session, clerk_id="mod_s_01n", username="mod_s_01n", is_moderator=True
        )
        user = await _make_user(db_session, clerk_id="mod_s_01u", username="mod_s_01u")

        success, error = await moderation_svc.suspend_user(
            db_session, mod.id, "mod_s_01_missing"
        )
        assert not success and "not found" in error.lower()

        success, error = await moderation_svc.suspend_user(
            db_session, mod.id, other_mod.username
        )
        assert not success and "can't be suspended" in error

        success, _ = await moderation_svc.suspend_user(
            db_session, mod.id, user.username
        )
        assert success
        success, error = await moderation_svc.suspend_user(
            db_session, mod.id, user.username
        )
        assert not success and "already" in error

    async def test_suspension_matrix_writes_403_reads_200(
        self, db_session: AsyncSession
    ) -> None:
        suspended = await _make_user(
            db_session, clerk_id="mod_s_02u", username="mod_s_02u", suspended=True
        )
        target = await _make_user(
            db_session, clerk_id="mod_s_02t", username="mod_s_02t"
        )
        track = await _make_track(db_session, mbid="mbid-mod-s-02")

        writes = [
            (
                "POST",
                "/api/v1/ratings/",
                {
                    "entity_type": "track",
                    "entity_mbid": track.mbid,
                    "score": 7,
                    "review_text": "A solid record that rewards listening.",
                },
            ),
            (
                "PATCH",
                f"/api/v1/ratings/{uuid.uuid4()}/visibility",
                {"visibility": "public"},
            ),
            ("DELETE", f"/api/v1/ratings/{uuid.uuid4()}", None),
            ("POST", f"/api/v1/ratings/{uuid.uuid4()}/report", None),
            ("POST", f"/api/v1/follows/{target.username}", None),
            ("DELETE", f"/api/v1/follows/{target.username}", None),
            ("PATCH", "/api/v1/users/me", {"display_name": "New Name"}),
            (
                "POST",
                "/api/v1/melodies",
                {"recipient_username": target.username, "track_mbid": track.mbid},
            ),
            ("POST", f"/api/v1/melodies/{uuid.uuid4()}/respond", {"action": "accept"}),
        ]
        reads = [
            "/api/v1/users/me",
            f"/api/v1/users/{target.username}",
            "/api/v1/melodies/inbox",
            "/api/v1/melodies/sent",
            "/api/v1/notifications",
            "/api/v1/notifications/unread-count",
            "/api/v1/home",
        ]

        async with _client_for(db_session, suspended.clerk_id) as client:
            for method, url, body in writes:
                resp = await client.request(method, url, json=body)
                assert resp.status_code == 403, (
                    f"{method} {url} → {resp.status_code} (expected 403)"
                )
                assert "suspended" in resp.json()["detail"].lower()

            for url in reads:
                resp = await client.get(url)
                assert resp.status_code == 200, (
                    f"GET {url} → {resp.status_code} (expected 200)"
                )
        app.dependency_overrides.clear()
