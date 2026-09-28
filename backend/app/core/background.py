"""
Post-response work on its own session, at most one run per key at a time.

Views that serve stored data and refresh it after responding (listening
history, playlist highlights) share this so a burst of page views can't
multiply provider calls. The guard is in-process: with several workers each
may run one, which is acceptable for a best-effort refresh.
"""

import logging
import uuid
from collections.abc import Awaitable, Callable

from sqlalchemy.ext.asyncio import AsyncSession

from app.database import AsyncSessionLocal

logger = logging.getLogger(__name__)


async def run_exclusive(
    running: set[uuid.UUID],
    key: uuid.UUID,
    work: Callable[[AsyncSession], Awaitable[None]],
    label: str,
) -> None:
    """Run `work` on a fresh session and commit, unless a run for `key` is
    already in flight. Failures are logged, never raised: nobody is waiting."""
    if key in running:
        return
    running.add(key)
    try:
        async with AsyncSessionLocal() as session:
            await work(session)
            await session.commit()
    except Exception:
        logger.exception("Background %s failed key=%s", label, key)
    finally:
        running.discard(key)
