"""
Moderation service: report queue, dismiss, hide rating, suspend user.

Access control lives in the CurrentModerator dependency (api/v1/deps.py);
every function here assumes the caller is already a verified moderator.
Hide is soft: the rating stays in the database, excluded from every public
surface via _can_view / SQL filters in services/rating.py and home.py, and
still visible (flagged) to its author. Unsuspend has no endpoint — manual
SQL only (Founder decision 2026-07-07).
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.core.enums import ReportStatus
from app.models.rating import Rating, Report
from app.models.user import User
from app.schemas.home import UserSummary
from app.schemas.moderation import (
    ReportCursor,
    ReportedRating,
    ReportQueueItem,
    ReportQueueResponse,
)

logger = logging.getLogger(__name__)

DEFAULT_PAGE_SIZE = 20

_ERR_REPORT_NOT_FOUND = "Report not found."
_ERR_REPORT_RESOLVED = "This report has already been resolved."
_ERR_RATING_NOT_FOUND = "Review not found."
_ERR_ALREADY_HIDDEN = "This review is already hidden."
_ERR_USER_NOT_FOUND = "User not found."
_ERR_ALREADY_SUSPENDED = "This account is already suspended."
_ERR_SUSPEND_MODERATOR = "Moderators can't be suspended from here."


def _now() -> datetime:
    return datetime.now(tz=UTC)


# ── Report queue ──────────────────────────────────────────────────────────────


async def list_reports(
    session: AsyncSession,
    status_filter: str | None = ReportStatus.OPEN.value,
    cursor: str | None = None,
    limit: int = DEFAULT_PAGE_SIZE,
) -> ReportQueueResponse:
    reporter = aliased(User)
    author = aliased(User)

    open_counts = (
        select(Report.rating_id, func.count().label("open_count"))
        .where(Report.status == ReportStatus.OPEN.value)
        .group_by(Report.rating_id)
        .subquery()
    )

    base = (
        select(
            Report.id,
            Report.status,
            Report.created_at,
            reporter.id.label("reporter_id"),
            reporter.username.label("reporter_username"),
            reporter.display_name.label("reporter_display_name"),
            reporter.avatar_url.label("reporter_avatar_url"),
            Rating.id.label("rating_id"),
            Rating.entity_type,
            Rating.score,
            Rating.review_text,
            Rating.hidden_at,
            author.id.label("author_id"),
            author.username.label("author_username"),
            author.display_name.label("author_display_name"),
            author.avatar_url.label("author_avatar_url"),
            author.suspended_at.label("author_suspended_at"),
            func.coalesce(open_counts.c.open_count, 0).label("open_report_count"),
        )
        .join(reporter, reporter.id == Report.reporter_id)
        .join(Rating, Rating.id == Report.rating_id)
        .join(author, author.id == Rating.user_id)
        .outerjoin(open_counts, open_counts.c.rating_id == Report.rating_id)
    )

    if status_filter is not None:
        base = base.where(Report.status == status_filter)

    if cursor is not None:
        c = ReportCursor.decode(cursor)
        base = base.where(
            or_(
                Report.created_at < c.created_at,
                and_(Report.created_at == c.created_at, Report.id > c.report_id),
            )
        )

    base = base.order_by(Report.created_at.desc(), Report.id.asc()).limit(limit + 1)
    rows = (await session.execute(base)).all()

    has_more = len(rows) > limit
    page = rows[:limit]

    items = [
        ReportQueueItem(
            id=row.id,
            status=ReportStatus(row.status),
            created_at=row.created_at,
            reporter=UserSummary(
                id=row.reporter_id,
                username=row.reporter_username,
                display_name=row.reporter_display_name,
                avatar_url=row.reporter_avatar_url,
            ),
            rating=ReportedRating(
                id=row.rating_id,
                entity_type=row.entity_type,
                score=row.score,
                review_text=row.review_text,
                hidden=row.hidden_at is not None,
                author=UserSummary(
                    id=row.author_id,
                    username=row.author_username,
                    display_name=row.author_display_name,
                    avatar_url=row.author_avatar_url,
                ),
                author_suspended=row.author_suspended_at is not None,
            ),
            open_report_count=row.open_report_count,
        )
        for row in page
    ]

    next_cursor: str | None = None
    if has_more and page:
        last = page[-1]
        next_cursor = ReportCursor(
            created_at=last.created_at, report_id=last.id
        ).encode()

    return ReportQueueResponse(items=items, next_cursor=next_cursor)


# ── Actions ───────────────────────────────────────────────────────────────────


async def dismiss_report(
    session: AsyncSession,
    moderator_id: uuid.UUID,
    report_id: uuid.UUID,
) -> tuple[bool, str]:
    result = await session.execute(select(Report).where(Report.id == report_id))
    report = result.scalar_one_or_none()
    if report is None:
        return False, _ERR_REPORT_NOT_FOUND
    if report.status != ReportStatus.OPEN.value:
        return False, _ERR_REPORT_RESOLVED

    report.status = ReportStatus.DISMISSED.value
    report.resolved_at = _now()
    report.resolved_by = moderator_id
    await session.flush()

    logger.info(
        "Moderation: report dismissed report_id=%s moderator_id=%s",
        report_id,
        moderator_id,
    )
    return True, ""


async def hide_rating(
    session: AsyncSession,
    moderator_id: uuid.UUID,
    rating_id: uuid.UUID,
) -> tuple[bool, str]:
    """Soft-hide + mark every open report on this rating as actioned."""
    result = await session.execute(select(Rating).where(Rating.id == rating_id))
    rating = result.scalar_one_or_none()
    if rating is None:
        return False, _ERR_RATING_NOT_FOUND
    if rating.hidden_at is not None:
        return False, _ERR_ALREADY_HIDDEN

    now = _now()
    rating.hidden_at = now
    rating.hidden_by = moderator_id

    reports_result = await session.execute(
        select(Report).where(
            Report.rating_id == rating_id,
            Report.status == ReportStatus.OPEN.value,
        )
    )
    for report in reports_result.scalars().all():
        report.status = ReportStatus.ACTIONED.value
        report.resolved_at = now
        report.resolved_by = moderator_id

    await session.flush()

    logger.info(
        "Moderation: rating hidden rating_id=%s author_id=%s moderator_id=%s",
        rating_id,
        rating.user_id,
        moderator_id,
    )
    return True, ""


async def suspend_user(
    session: AsyncSession,
    moderator_id: uuid.UUID,
    username: str,
) -> tuple[bool, str]:
    result = await session.execute(
        select(User).where(User.username == username.lower())
    )
    user = result.scalar_one_or_none()
    if user is None:
        return False, _ERR_USER_NOT_FOUND
    if user.is_moderator:
        return False, _ERR_SUSPEND_MODERATOR
    if user.suspended_at is not None:
        return False, _ERR_ALREADY_SUSPENDED

    user.suspended_at = _now()
    await session.flush()

    logger.info(
        "Moderation: user suspended user_id=%s username=%s moderator_id=%s",
        user.id,
        username,
        moderator_id,
    )
    return True, ""
