"""Make two users friends the way the product does: a request, then an accept."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import FriendshipState
from app.models.user import User
from app.services import friendship as friendship_svc


async def make_friends(session: AsyncSession, a: User, b: User) -> None:
    sent, error = await friendship_svc.send_request(session, a, b)
    assert sent is FriendshipState.REQUEST_SENT, error
    accepted, error = await friendship_svc.accept_request(session, b, a)
    assert accepted is FriendshipState.FRIENDS, error
    await session.flush()
