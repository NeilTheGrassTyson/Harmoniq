"""Listen history against a real database (specs/phase-2-listen-history.md).

The two tests that matter most are the merge rule (an empty or failed fetch
never blanks a profile) and the boundary (no provider row is reachable from
the recommendation accessor).
"""

from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.enums import VisibilityScope
from app.models.catalog import Track
from app.models.listen import Listen
from app.models.spotify import SpotifyConnection
from app.models.user import User
from app.services import listens as listens_svc
from app.services import spotify as spotify_svc
from app.services import user as user_svc
from tests.integration.friends_helpers import make_friends

pytestmark = pytest.mark.integration

T0 = datetime(2026, 9, 1, 12, tzinfo=UTC)


@pytest.fixture(autouse=True)
def history_on(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "listen_history_enabled", True)
    spotify_svc._listening_cache.clear()
    spotify_svc._needs_reconnect.clear()
    spotify_svc._refreshing.clear()


async def _user(session: AsyncSession, name: str, *, opted_in: bool = True) -> User:
    user = await user_svc.create_user(session, f"clerk_{name}", name, name.title())
    user.store_listening = opted_in
    await session.flush()  # the connection's FK needs the user row first
    session.add(
        SpotifyConnection(
            user_id=user.id,
            spotify_user_id=f"sp_{name}",
            refresh_token_encrypted="unused",
            scopes=spotify_svc.SCOPES,
        )
    )
    await session.flush()
    return user


def _entry(n: int, *, isrc: str | None = None) -> dict[str, Any]:
    return {
        "track": {
            "type": "track",
            "id": f"sp{n}",
            "name": f"Song {n}",
            "artists": [{"name": "Artist"}],
            "album": {"name": "Album", "images": [{"url": f"https://i.scdn.co/{n}"}]},
            "external_urls": {"spotify": f"https://open.spotify.com/track/sp{n}"},
            "external_ids": {"isrc": isrc} if isrc else {},
        },
        "played_at": (T0 + timedelta(minutes=n)).isoformat().replace("+00:00", "Z"),
    }


def _window(monkeypatch: pytest.MonkeyPatch, *numbers: int, now: Any = None) -> None:
    async def fetch(session: AsyncSession, conn: SpotifyConnection) -> dict[str, Any]:
        payload = {"now": now, "recent": [_entry(n) for n in numbers]}
        spotify_svc._listening_cache[conn.user_id] = (0.0, payload)
        return payload

    monkeypatch.setattr(spotify_svc, "_fetch_listening_payload", fetch)


async def _refresh(session: AsyncSession, user: User) -> None:
    conn = await spotify_svc.get_connection(session, user.id)
    assert conn is not None
    await spotify_svc.refresh_history(session, user, conn)
    await session.flush()


async def _titles(session: AsyncSession, user: User) -> list[str]:
    return [
        listen.track_name
        for listen, _ in await listens_svc.recent_for_display(session, user.id)
    ]


# ── Merge, never replace ──────────────────────────────────────────────────────


async def test_listens_outlive_the_providers_window(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    user = await _user(db_session, "lh_merge")
    _window(monkeypatch, 1, 2)
    await _refresh(db_session, user)
    _window(monkeypatch, 3)
    await _refresh(db_session, user)
    assert await _titles(db_session, user) == ["Song 3", "Song 2", "Song 1"]


@pytest.mark.parametrize("failure", ["empty", "error", "revoked"])
async def test_an_empty_or_failed_fetch_leaves_stored_rows_intact(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch, failure: str
) -> None:
    user = await _user(db_session, f"lh_keep_{failure}")
    _window(monkeypatch, 1, 2)
    await _refresh(db_session, user)

    async def failing(session: AsyncSession, conn: SpotifyConnection) -> dict[str, Any]:
        if failure == "empty":
            # Like the real fetch: a successful (if empty) answer fills the cache.
            empty: dict[str, Any] = {"now": None, "recent": []}
            spotify_svc._listening_cache[conn.user_id] = (
                spotify_svc.time.monotonic(),
                empty,
            )
            return empty
        if failure == "error":
            raise httpx.ConnectError("Spotify unreachable")
        raise spotify_svc.SpotifyNotConnectedError("unusable")

    monkeypatch.setattr(spotify_svc, "_fetch_listening_payload", failing)
    spotify_svc._listening_cache.clear()
    await _refresh(db_session, user)
    assert await _titles(db_session, user) == ["Song 2", "Song 1"]
    after = await spotify_svc.get_listening(db_session, user, viewer=user)
    # A failed refresh is not reported as still running, so clients settle.
    assert after and after.refreshing is False
    if failure == "revoked":
        response = await spotify_svc.get_listening(db_session, user, viewer=user)
        assert (
            response and response.needs_reconnect and len(response.recently_played) == 2
        )


async def test_repeated_views_neither_duplicate_nor_exceed_twenty(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    user = await _user(db_session, "lh_cap")
    _window(monkeypatch, *range(1, 16))
    await _refresh(db_session, user)
    await _refresh(db_session, user)
    _window(monkeypatch, *range(10, 31))
    await _refresh(db_session, user)
    count = await db_session.execute(
        select(func.count()).select_from(Listen).where(Listen.user_id == user.id)
    )
    assert count.scalar_one() == listens_svc.STORED_LIMIT
    titles = await _titles(db_session, user)
    assert titles[0] == "Song 30" and titles[-1] == "Song 11"


# ── Serving ───────────────────────────────────────────────────────────────────


async def test_a_view_never_waits_on_the_provider(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    user = await _user(db_session, "lh_fast")
    _window(monkeypatch, 1)
    await _refresh(db_session, user)
    spotify_svc._listening_cache.clear()

    async def unreachable(*_args: Any) -> dict[str, Any]:
        raise AssertionError("the view must not call Spotify")

    monkeypatch.setattr(spotify_svc, "_fetch_listening_payload", unreachable)
    user.visibility_activity = VisibilityScope.PUBLIC.value
    for viewer in (None, user):  # anonymous views may trigger refreshes too
        response = await spotify_svc.get_listening(db_session, user, viewer=viewer)
        assert response and response.history and response.refreshing
        assert [item.track_name for item in response.recently_played] == ["Song 1"]
        assert response.now_playing is None


async def test_now_playing_comes_from_a_warm_cache(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    user = await _user(db_session, "lh_now")
    now = {"is_playing": True, "item": _entry(9)["track"]}
    _window(monkeypatch, 1, now=now)
    await _refresh(db_session, user)
    spotify_svc._listening_cache[user.id] = (
        spotify_svc.time.monotonic(),
        spotify_svc._listening_cache[user.id][1],
    )
    response = await spotify_svc.get_listening(db_session, user, viewer=user)
    assert (
        response
        and response.now_playing
        and response.now_playing.track_name == "Song 9"
    )
    assert response.refreshing is False


async def test_private_listening_is_withheld_in_the_query(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    owner = await _user(db_session, "lh_priv")
    stranger = await _user(db_session, "lh_str", opted_in=False)
    friend = await _user(db_session, "lh_fr", opted_in=False)
    _window(monkeypatch, 1)
    await _refresh(db_session, owner)
    assert owner.visibility_activity == VisibilityScope.PRIVATE.value
    assert await spotify_svc.get_listening(db_session, owner, viewer=stranger) is None
    assert await spotify_svc.get_listening(db_session, owner, viewer=None) is None
    owner.visibility_activity = VisibilityScope.FRIENDS.value
    await make_friends(db_session, owner, friend)
    assert await spotify_svc.get_listening(db_session, owner, viewer=stranger) is None
    seen = await spotify_svc.get_listening(db_session, owner, viewer=friend)
    assert seen and [i.track_name for i in seen.recently_played] == ["Song 1"]


async def test_a_provider_without_play_times_is_representable(
    db_session: AsyncSession,
) -> None:
    user = await _user(db_session, "lh_apple")
    await listens_svc.record(
        db_session,
        user.id,
        [
            listens_svc.ObservedListen(
                source="apple_music",
                idempotency_key="am1",
                track_name="Apple Song",
                artist_name="Artist",
            )
        ],
    )
    response = await spotify_svc.get_listening(db_session, user, viewer=user)
    assert response and response.recently_played[0].track_name == "Apple Song"
    ((listen, _),) = await listens_svc.recent_for_display(db_session, user.id)
    assert listen.played_at is None
    assert response.recently_played[0].played_at == listen.observed_at


# ── Consent and deletion ──────────────────────────────────────────────────────


async def test_withdrawing_the_opt_in_deletes_every_row(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    user = await _user(db_session, "lh_withdraw")
    _window(monkeypatch, 1, 2)
    await _refresh(db_session, user)
    own = await user_svc.update_profile(
        db_session, user, None, None, user.bio, None, None, None, store_listening=False
    )
    assert own.store_listening is False
    assert await _titles(db_session, user) == []
    # Opted out, the section goes back to the live window and stores nothing.
    await _refresh(db_session, user)
    assert await _titles(db_session, user) == []


async def test_disconnecting_spotify_deletes_its_rows_only(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    user = await _user(db_session, "lh_disc")
    _window(monkeypatch, 1)
    await _refresh(db_session, user)
    await listens_svc.record(
        db_session,
        user.id,
        [
            listens_svc.ObservedListen(
                source="harmoniq",
                idempotency_key="h1",
                track_name="Own",
                artist_name="A",
            )
        ],
    )
    await spotify_svc.disconnect(db_session, user)
    assert await _titles(db_session, user) == ["Own"]


async def test_nothing_is_stored_without_the_opt_in_or_the_feature(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    out = await _user(db_session, "lh_out", opted_in=False)
    _window(monkeypatch, 1)
    await _refresh(db_session, out)
    live = await spotify_svc.get_listening(db_session, out, viewer=out)
    assert live and not live.history and live.recently_played[0].track_name == "Song 1"
    assert await _titles(db_session, out) == []

    monkeypatch.setattr(settings, "listen_history_enabled", False)
    opted = await _user(db_session, "lh_off")
    await _refresh(db_session, opted)
    assert await _titles(db_session, opted) == []
    # And no one can opt in while the feature is off.
    own = await user_svc.update_profile(
        db_session, out, None, None, None, None, None, None, store_listening=True
    )
    assert own.store_listening is None and out.store_listening is False


async def test_an_opt_in_can_be_withdrawn_while_the_feature_is_off(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    user = await _user(db_session, "lh_withdraw_off")
    _window(monkeypatch, 1, 2)
    await _refresh(db_session, user)
    monkeypatch.setattr(settings, "listen_history_enabled", False)
    # The switch they turned on stays on the settings page so it can be undone.
    assert user_svc.build_own_profile(user).store_listening is True
    own = await user_svc.update_profile(
        db_session, user, None, None, None, None, None, None, store_listening=False
    )
    await db_session.flush()
    assert own.store_listening is None
    assert await _titles(db_session, user) == []


# ── The boundary ──────────────────────────────────────────────────────────────


async def test_no_provider_row_is_reachable_from_the_recommendation_accessor(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    user = await _user(db_session, "lh_boundary")
    _window(monkeypatch, 1, 2)
    await _refresh(db_session, user)
    await listens_svc.record(
        db_session,
        user.id,
        [
            listens_svc.ObservedListen(
                source=source,
                idempotency_key=source,
                track_name=source,
                artist_name="A",
            )
            for source in ("apple_music", "harmoniq")
        ],
    )
    reachable = await listens_svc.first_party_listens(db_session, user.id)
    assert [listen.source for listen in reachable] == ["harmoniq"]


# ── Linking to the catalog ────────────────────────────────────────────────────


async def test_listens_link_to_the_catalog_by_isrc_when_they_can(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    user = await _user(db_session, "lh_link")
    track = Track(mbid="mb-rec-1", title="Song 1", last_fetched_at=T0)
    db_session.add(track)
    await db_session.flush()
    await listens_svc.record(
        db_session,
        user.id,
        [
            listens_svc.ObservedListen(
                source="spotify",
                idempotency_key=key,
                track_name=key,
                artist_name="A",
                isrc=isrc,
                played_at=T0 + timedelta(minutes=i),
            )
            for i, (key, isrc) in enumerate(
                [("found", "USAAA0000001"), ("missing", "USAAA0000002"), ("busy", "X3")]
            )
        ],
    )
    lookups: list[str] = []

    async def lookup(isrc: str) -> dict[str, Any] | None:
        lookups.append(isrc)
        if isrc == "X3":
            raise httpx.ConnectError("MusicBrainz busy")
        return {"recordings": [{"id": "mb-rec-1"}]} if isrc.endswith("1") else None

    monkeypatch.setattr(listens_svc.mb, "lookup_isrc", lookup)
    assert await listens_svc.link_some(db_session, limit=10) == 2
    rows = {
        listen.track_name: (listen, mbid)
        for listen, mbid in await listens_svc.recent_for_display(db_session, user.id)
    }
    assert rows["found"][1] == "mb-rec-1"
    assert rows["missing"][1] is None and rows["missing"][0].link_checked_at is not None
    assert rows["busy"][0].link_checked_at is None  # an outage is retried later
    lookups.clear()
    await listens_svc.link_some(db_session, limit=10)
    assert lookups == ["X3"]


async def test_a_broken_ingestion_settles_its_isrc_without_blocking_the_rest(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    user = await _user(db_session, "lh_broken")
    await listens_svc.record(
        db_session,
        user.id,
        [
            listens_svc.ObservedListen(
                source="spotify",
                idempotency_key=isrc,
                track_name=isrc,
                artist_name="A",
                isrc=isrc,
                played_at=T0 + timedelta(minutes=i),
            )
            for i, isrc in enumerate(["BROKEN1", "FINE2"])
        ],
    )

    async def lookup(isrc: str) -> dict[str, Any] | None:
        return {"recordings": [{"id": f"mb-{isrc}"}]}

    async def get_track(mbid: str, session: AsyncSession) -> Any:
        if mbid == "mb-BROKEN1":
            raise ValueError("malformed recording")
        session.add(Track(mbid=mbid, title="Fine", last_fetched_at=T0))
        await session.flush()
        return object()

    monkeypatch.setattr(listens_svc.mb, "lookup_isrc", lookup)
    monkeypatch.setattr(listens_svc.catalog_svc, "get_track", get_track)
    assert await listens_svc.link_some(db_session, limit=10) == 2
    rows = {
        listen.track_name: (listen, mbid)
        for listen, mbid in await listens_svc.recent_for_display(db_session, user.id)
    }
    # Not an outage, so not retried forever — and the next ISRC still linked.
    assert rows["BROKEN1"][1] is None
    assert rows["BROKEN1"][0].link_checked_at is not None
    assert rows["FINE2"][1] == "mb-FINE2"


async def test_a_linking_failure_never_rolls_back_the_recording(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    user = await _user(db_session, "lh_linkfail")
    _window(monkeypatch, 1, 2)

    async def link_some(session: AsyncSession, limit: int = 3) -> int:
        raise RuntimeError("linking exploded")

    monkeypatch.setattr(listens_svc, "link_some", link_some)
    await _refresh(db_session, user)
    assert await _titles(db_session, user) == ["Song 2", "Song 1"]


async def test_an_unexpected_fetch_failure_still_floors_the_cache(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    user = await _user(db_session, "lh_unexpected")

    async def broken(session: AsyncSession, conn: SpotifyConnection) -> Any:
        raise KeyError("items")

    monkeypatch.setattr(spotify_svc, "_fetch_listening_payload", broken)
    await _refresh(db_session, user)
    assert user.id in spotify_svc._listening_cache


async def test_one_background_refresh_per_user_at_a_time(
    db_session: AsyncSession,
) -> None:
    user = await _user(db_session, "lh_single")
    spotify_svc._refreshing.add(user.id)
    await spotify_svc.refresh_in_background(user.id)  # returns without work
    assert user.id in spotify_svc._refreshing
