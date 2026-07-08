import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, Uuid, text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database import Base


class Notification(Base):
    """
    An in-app notification addressed to user_id, caused by actor_id.

    Both current event types are inherently visible to their recipient (a
    Melody sent to them; someone following them), so no visibility scope is
    stored — the consent check is that nothing else ever becomes a
    notification without one.
    """

    __tablename__ = "notifications"
    __table_args__ = (
        Index("ix_notifications_user_list", "user_id", "created_at", "id"),
        # Cheap unread count.
        Index(
            "ix_notifications_unread",
            "user_id",
            postgresql_where=text("read_at IS NULL"),
        ),
        # Idempotency backstops (inserts use ON CONFLICT DO NOTHING):
        # a re-follow never re-notifies; a melody notifies exactly once.
        Index(
            "uq_notifications_follower",
            "user_id",
            "actor_id",
            unique=True,
            postgresql_where=text("type = 'new_follower'"),
        ),
        Index(
            "uq_notifications_melody",
            "melody_id",
            unique=True,
            postgresql_where=text("melody_id IS NOT NULL"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id"), nullable=False
    )
    type: Mapped[str] = mapped_column(String, nullable=False)
    actor_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id"), nullable=False
    )
    melody_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("melodies.id"), nullable=True
    )
    read_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
