"""
Home API: Trending and Top songs from friends.

A single authenticated endpoint returns both sections in one response.
Each section is wrapped in _safe_section so a DB failure in one does not
take down the other — the caller receives an error flag and an empty list
for the failing section while the other section renders normally.
"""

import logging
import uuid

from fastapi import APIRouter

from app.api.v1.deps import CurrentUser, DbSession
from app.config import settings
from app.schemas.home import FriendEntry, HomeResponse, TrendingEntry
from app.services import follow as follow_svc
from app.services import home as home_svc

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/home", tags=["home"])


@router.get("", response_model=HomeResponse)
async def get_home(session: DbSession, current_user: CurrentUser) -> HomeResponse:
    """Returns Trending and Top songs from friends for the authenticated user."""
    # Fetch mutual follows once; pass it into both sections to avoid a second
    # round-trip when get_friends_top_tracks would otherwise call it again.
    mutual_follow_ids: set[uuid.UUID] = set()
    try:
        mutual_follow_ids = await follow_svc.get_mutual_follow_ids(
            session, current_user.id
        )
    except Exception:
        logger.exception(
            "Home: failed to get mutual follows for user_id=%s", current_user.id
        )

    trending_result: list[TrendingEntry] | None = await home_svc._safe_section(
        "trending",
        home_svc.get_trending(session, settings.home_trending_count),
    )
    friends_result: list[FriendEntry] | None = await home_svc._safe_section(
        "friends",
        home_svc.get_friends_top_tracks(
            session,
            current_user.id,
            settings.home_friends_count,
            mutual_follow_ids=mutual_follow_ids,
        ),
    )

    return HomeResponse(
        trending=trending_result or [],
        trending_error=trending_result is None,
        friends=friends_result or [],
        friends_error=friends_result is None,
        has_mutual_follows=bool(mutual_follow_ids),
    )
