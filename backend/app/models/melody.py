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

from app.core.enums import MelodyStatus
from app.database import Base


class Melody(Base):
    """
    A directed recommendation of a single track from one user to another.

    sender_id is NOT NULL by design: a Melody must always trace back to a
    specific human sender (ENGINEERING_BIBLE §6 — the system must never
    generate or send one). track_id is a real FK — a deliberate deviation
    from Rating's polymorphic (entity_type, entity_id) pair, because a
    Melody is track-only per BRAND_BIBLE §5 and needs no polymorphism.
    Carries no free-text message (Founder decision, 2026-07-07).
    """

    __tablename__ = "melodies"
    __table_args__ = (
        CheckConstraint("sender_id != recipient_id", name="ck_melodies_no_self_send"),
        CheckConstraint(
            "status IN ('sent','received','accepted','opened','rejected')",
            name="ck_melodies_status",
        ),
        # Race-proof backstop for the duplicate-pending guard: one unresponded
        # Melody per (sender, recipient, track). Re-sending after a response
        # is allowed, so the index is partial over unresponded statuses.
        Index(
            "uq_melodies_pending_dedup",
            "sender_id",
            "recipient_id",
            "track_id",
            unique=True,
            postgresql_where=text("status IN ('sent','received')"),
        ),
        Index("ix_melodies_recipient_inbox", "recipient_id", "created_at", "id"),
        Index("ix_melodies_sender_sent", "sender_id", "created_at", "id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    sender_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id"), nullable=False, index=True
    )
    recipient_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id"), nullable=False
    )
    track_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("tracks.id"), nullable=False
    )
    status: Mapped[str] = mapped_column(
        String,
        nullable=False,
        default=MelodyStatus.SENT.value,
        server_default=MelodyStatus.SENT.value,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    received_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    responded_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
