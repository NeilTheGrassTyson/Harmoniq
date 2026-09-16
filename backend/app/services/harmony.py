"""Profile-only reception, including historical responses; no provider inputs.

Authorization precedes aggregation. Other viewers' query and schema contain
only positive signals, never counts from which rejection can be reconstructed.
"""

from datetime import UTC, datetime
from typing import Literal

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import VisibilityScope
from app.core.visibility import scope_allows
from app.models.melody import Melody
from app.models.user import User
from app.schemas.harmony import (
    HarmonyHidden,
    HarmonyOwn,
    HarmonyResponse,
    HarmonyShared,
)
from app.services import follow as follow_svc
from app.services import user as user_svc


def window_start(now: datetime) -> datetime:
    """Inclusive start of the current UTC sending month and five before it."""
    now = now.astimezone(UTC)
    year, month = divmod(now.year * 12 + now.month - 1 - 5, 12)
    return datetime(year, month + 1, 1, tzinfo=UTC)


async def get_harmony(
    session: AsyncSession,
    username: str,
    viewer_clerk_id: str | None,
    *,
    now: datetime | None = None,
) -> HarmonyResponse | None:
    owner = await user_svc.get_by_username(session, username)
    if owner is None:
        return None
    viewer = (
        await user_svc.get_by_clerk_id(session, viewer_clerk_id)
        if viewer_clerk_id
        else None
    )
    is_owner = viewer is not None and viewer.id == owner.id
    scope = VisibilityScope(owner.visibility_harmony)
    is_friend = False
    if not is_owner and viewer is not None and scope == VisibilityScope.FRIENDS:
        is_friend = await follow_svc.is_mutual_follow(session, viewer.id, owner.id)
    if not scope_allows(scope, is_owner=is_owner, is_friend=is_friend):
        return HarmonyHidden()

    # Explicit opinion always wins over a navigation/status event. No backfill.
    positive = case(
        (Melody.reaction.is_not(None), Melody.reaction.in_(["liked", "loved"])),
        else_=Melody.status.in_(["accepted", "opened"]),
    )
    now = now or datetime.now(UTC)
    in_window = (Melody.created_at >= window_start(now)) & (Melody.created_at <= now)
    month = func.date_trunc("month", func.timezone("UTC", Melody.created_at))
    months = func.count(func.distinct(month)).filter(positive & in_window)
    if not is_owner:
        row = (
            await session.execute(
                select(
                    func.count().label("positives"),
                    months.label("months"),
                    func.count(func.distinct(Melody.recipient_id))
                    .filter(in_window)
                    .label("recipients"),
                ).where(Melody.sender_id == owner.id, positive)
            )
        ).one()
        summary: Literal["listeners", "sustained"] | None = None
        if row.months >= 3 and row.recipients >= 3:
            summary = "sustained"
        elif row.positives:
            summary = "listeners"
        return HarmonyShared(summary=summary)

    resolved = Melody.reaction.is_not(None) | Melody.status.in_(
        ["accepted", "opened", "rejected"]
    )
    row = (
        await session.execute(
            select(
                func.count().filter(positive).label("positives"),
                func.count().filter(resolved).label("resolved"),
                months.label("months"),
            ).where(Melody.sender_id == owner.id)
        )
    ).one()
    # Integer half-up rounding, without floating point or Python's ties-to-even.
    rate = (
        (200 * row.positives + row.resolved) // (2 * row.resolved)
        if row.resolved
        else None
    )
    return HarmonyOwn(
        visibility=scope,
        positive_count=row.positives,
        resolved_count=row.resolved,
        acceptance_percent=rate,
        active_sending_months=row.months,
    )


async def set_visibility(
    session: AsyncSession, user: User, visibility: VisibilityScope
) -> None:
    user.visibility_harmony = visibility.value
    user.updated_at = datetime.now(UTC)
    await session.flush()
