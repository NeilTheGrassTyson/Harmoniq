import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    Uuid,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database import Base


class Friendship(Base):
    """
    One row per pair, stored in canonical order (user_low_id < user_high_id)
    so a pair can never hold two rows or half a friendship
    (specs/phase-2-friend-requests.md). Independent of follows.
    """

    __tablename__ = "friendships"
    __table_args__ = (
        CheckConstraint(
            "user_low_id < user_high_id", name="ck_friendships_canonical_order"
        ),
        CheckConstraint(
            "status IN ('pending','accepted','declined')", name="ck_friendships_status"
        ),
        CheckConstraint(
            "requested_by = user_low_id OR requested_by = user_high_id",
            name="ck_friendships_requester_in_pair",
        ),
        # The primary key covers lookups by user_low_id; this covers the
        # other side of the hot friends-of-user lookup.
        Index(
            "ix_friendships_high_accepted",
            "user_high_id",
            postgresql_where=text("status = 'accepted'"),
        ),
        Index(
            "ix_friendships_low_accepted",
            "user_low_id",
            postgresql_where=text("status = 'accepted'"),
        ),
    )

    user_low_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    user_high_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    status: Mapped[str] = mapped_column(String, nullable=False)
    requested_by: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    responded_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
