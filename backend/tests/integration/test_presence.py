"""
Integration tests: the friends rail (beta-ui Phase 5,
docs/specs/beta-ui-phase-5-presence.md).

Every rule here is consent (HARMONIQ.md §6): only mutual follows, Online only
with Online status shared, Private carrying no status at all, revocation
without waiting out the window, and no time value anywhere in the payload.
"""

from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import VisibilityScope
from app.models.user import User
from app.schemas.spotify import ListeningResponse, ListeningTrack
from app.services import follow as follow_svc
from app.services import presence as presence_svc
from app.services import spotify as spotify_svc
from app.services import user as user_svc


@pytest.fixture(autouse=True)
def _fresh_store(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(presence_svc, "_last_seen", {})


@pytest.fixture(autouse=True)
def _no_spotify(monkeypatch: pytest.MonkeyPatch) -> dict[str, ListeningResponse]:
    """Listening is get_listening's job (tested with Spotify); stub it here."""
    playing: dict[str, ListeningResponse] = {}

    async def fake_get_listening(
        session: AsyncSession, profile_user: User, viewer: User | None
    ) -> ListeningResponse | None:
        return playing.get(profile_user.username)

    monkeypatch.setattr(spotify_svc, "get_listening", fake_get_listening)
    return playing


async def _user(
    session: AsyncSession, tag: str, display: str, presence: str = "private"
) -> User:
    user = await user_svc.create_user(session, f"pres_{tag}", f"pres_{tag}", display)
    user.visibility_presence = presence
    await session.flush()
    return user


async def _mutual(session: AsyncSession, a: User, b: User) -> None:
    await follow_svc.follow(session, a.id, b.id)
    await follow_svc.follow(session, b.id, a.id)


def _states(resp: Any) -> dict[str, Any]:
    return {f.username: f.state for f in resp.friends}


@pytest.mark.integration
class TestFriendsRail:
    async def test_only_mutual_follows_appear(self, db_session: AsyncSession) -> None:
        me = await _user(db_session, "01me", "Me")
        mutual = await _user(db_session, "01mu", "Mutual", "friends")
        i_follow = await _user(db_session, "01if", "I Follow", "friends")
        follows_me = await _user(db_session, "01fm", "Follows Me", "friends")
        await _mutual(db_session, me, mutual)
        await follow_svc.follow(db_session, me.id, i_follow.id)
        await follow_svc.follow(db_session, follows_me.id, me.id)

        rail = await presence_svc.friends_presence(db_session, me)

        # A one-way follow is never friendship, in either direction.
        assert [f.username for f in rail.friends] == ["pres_01mu"]

    async def test_online_needs_a_beat_and_a_shared_status(
        self, db_session: AsyncSession
    ) -> None:
        me = await _user(db_session, "02me", "Me")
        online = await _user(db_session, "02on", "Online", "friends")
        away = await _user(db_session, "02of", "Away", "friends")
        for f in (online, away):
            await _mutual(db_session, me, f)

        assert presence_svc.heartbeat(online) is True
        rail = await presence_svc.friends_presence(db_session, me)

        assert _states(rail) == {"pres_02on": "online", "pres_02of": "offline"}

    async def test_private_is_its_own_state_not_offline(
        self, db_session: AsyncSession
    ) -> None:
        me = await _user(db_session, "03me", "Me")
        hidden = await _user(db_session, "03pr", "Hidden", "private")
        await _mutual(db_session, me, hidden)

        # They have Harmoniq open — and it leaves no trace.
        assert presence_svc.heartbeat(hidden) is False
        assert hidden.id not in presence_svc._last_seen

        rail = await presence_svc.friends_presence(db_session, me)
        assert _states(rail) == {"pres_03pr": None}

    async def test_public_admits_exactly_who_friends_admits(
        self, db_session: AsyncSession
    ) -> None:
        me = await _user(db_session, "04me", "Me")
        pub = await _user(db_session, "04pu", "Public", "public")
        stranger = await _user(db_session, "04st", "Stranger", "public")
        await _mutual(db_session, me, pub)
        presence_svc.heartbeat(pub)
        presence_svc.heartbeat(stranger)

        rail = await presence_svc.friends_presence(db_session, me)

        assert _states(rail) == {"pres_04pu": "online"}

    async def test_going_private_revokes_without_waiting_for_the_window(
        self, db_session: AsyncSession
    ) -> None:
        me = await _user(db_session, "05me", "Me")
        friend = await _user(db_session, "05fr", "Friend", "friends")
        await _mutual(db_session, me, friend)
        presence_svc.heartbeat(friend)
        assert _states(await presence_svc.friends_presence(db_session, me)) == {
            "pres_05fr": "online"
        }

        await user_svc.update_profile(
            db_session,
            friend,
            display_name=None,
            username=None,
            bio=None,
            visibility_bio=None,
            visibility_activity=None,
            visibility_ratings=None,
            visibility_presence=VisibilityScope.PRIVATE,
        )

        assert friend.id not in presence_svc._last_seen
        assert _states(await presence_svc.friends_presence(db_session, me)) == {
            "pres_05fr": None
        }

    async def test_unfollowing_removes_on_the_next_read(
        self, db_session: AsyncSession
    ) -> None:
        me = await _user(db_session, "06me", "Me")
        friend = await _user(db_session, "06fr", "Friend", "friends")
        await _mutual(db_session, me, friend)
        presence_svc.heartbeat(friend)

        await follow_svc.unfollow(db_session, friend.id, me.id)

        assert (await presence_svc.friends_presence(db_session, me)).friends == []

    async def test_groups_then_alphabetical_with_no_times_anywhere(
        self, db_session: AsyncSession, _no_spotify: dict[str, ListeningResponse]
    ) -> None:
        me = await _user(db_session, "07me", "Me")
        people = {
            "07zl": ("zed", "friends"),
            "07al": ("Ana", "private"),  # listening overrides a private status
            "07on": ("bo", "friends"),
            "07of": ("Cy", "friends"),
            "07pz": ("zoe", "private"),
            "07pa": ("Abe", "private"),
        }
        users = {}
        for tag, (name, scope) in people.items():
            users[tag] = await _user(db_session, tag, name, scope)
            await _mutual(db_session, me, users[tag])
        for tag in ("07zl", "07al"):
            _no_spotify[f"pres_{tag}"] = ListeningResponse(
                connected=True,
                now_playing=ListeningTrack(track_name="Xtal", artist_name="Aphex Twin"),
            )
        presence_svc.heartbeat(users["07on"])

        rail = await presence_svc.friends_presence(db_session, me)

        assert [(f.display_name, f.state) for f in rail.friends] == [
            ("Ana", "listening"),
            ("zed", "listening"),
            ("bo", "online"),
            ("Cy", "offline"),
            ("Abe", None),
            ("zoe", None),
        ]
        assert rail.friends[0].track is not None
        assert rail.friends[0].track.title == "Xtal"
        payload = str(rail.model_dump(mode="json"))
        for forbidden in ("seen", "_at", "time", "idle", "since"):
            assert forbidden not in payload

    async def test_setting_is_own_profile_only(self, db_session: AsyncSession) -> None:
        owner = await _user(db_session, "08ow", "Owner", "friends")
        viewer = await _user(db_session, "08vi", "Viewer")

        own = user_svc.build_own_profile(owner)
        assert own.visibility_presence == VisibilityScope.FRIENDS

        public = await user_svc.get_profile(db_session, owner.username, viewer.clerk_id)
        assert public is not None
        assert "presence" not in str(public.model_dump(mode="json"))

    async def test_new_accounts_start_private(self, db_session: AsyncSession) -> None:
        user = await user_svc.create_user(db_session, "pres_09", "pres_09", "New")
        assert user.visibility_presence == VisibilityScope.PRIVATE.value


@pytest.mark.integration
class TestPresenceRoutes:
    """Through the real routes, rate limiter included. The service tests above
    call presence_svc directly, which is how a route that 500'd on every
    request once passed the whole suite."""

    async def test_heartbeat_route(
        self, db_session: AsyncSession, authed_client: tuple[Any, str]
    ) -> None:
        client, clerk_id = authed_client
        user = await user_svc.create_user(db_session, clerk_id, "pres_rt_01", "Route")
        user.visibility_presence = "friends"
        await db_session.flush()

        resp = await client.post("/api/v1/presence/heartbeat")

        assert resp.status_code == 200
        assert resp.json() == {"recorded": True}
        assert "x-ratelimit-limit" in {k.lower() for k in resp.headers}
        assert presence_svc.is_online(user.id)

    async def test_friends_route(
        self, db_session: AsyncSession, authed_client: tuple[Any, str]
    ) -> None:
        client, clerk_id = authed_client
        me = await user_svc.create_user(db_session, clerk_id, "pres_rt_02", "Me")
        friend = await _user(db_session, "rt02f", "Friend", "friends")
        await _mutual(db_session, me, friend)
        presence_svc.heartbeat(friend)

        resp = await client.get("/api/v1/presence/friends")

        assert resp.status_code == 200
        assert resp.json() == {
            "friends": [
                {
                    "username": "pres_rt02f",
                    "display_name": "Friend",
                    "avatar_url": None,
                    "state": "online",
                    "track": None,
                }
            ]
        }
