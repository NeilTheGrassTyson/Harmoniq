import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, Uuid, text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database import Base


class Highlight(Base):
    """
    Something a user deliberately chose to represent their taste
    (specs/phase-2-highlights.md). Up to 15 per user across all types.

    Track, album and artist highlights reference the catalog (entity_id, the
    same unconstrained polymorphic reference ratings use). A playlist
    highlight references a provider playlist, plus only the display fields
    needed to render its card; those follow the provider live, refreshed in
    the background, and are never recommendation input.
    """

    __tablename__ = "highlights"
    __table_args__ = (
        CheckConstraint(
            "entity_type IN ('track','album','artist','playlist')",
            name="ck_highlights_type",
        ),
        CheckConstraint(
            "(entity_type = 'playlist' AND provider IS NOT NULL"
            " AND provider_ref IS NOT NULL AND entity_id IS NULL)"
            " OR (entity_type <> 'playlist' AND entity_id IS NOT NULL"
            " AND provider IS NULL AND provider_ref IS NULL)",
            name="ck_highlights_reference",
        ),
        Index(
            "uq_highlights_entity",
            "user_id",
            "entity_type",
            "entity_id",
            unique=True,
            postgresql_where=text("entity_id IS NOT NULL"),
        ),
        Index(
            "uq_highlights_playlist",
            "user_id",
            "provider",
            "provider_ref",
            unique=True,
            postgresql_where=text("provider_ref IS NOT NULL"),
        ),
        Index("ix_highlights_user", "user_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    entity_type: Mapped[str] = mapped_column(String, nullable=False)
    entity_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    provider: Mapped[str | None] = mapped_column(String, nullable=True)
    provider_ref: Mapped[str | None] = mapped_column(String, nullable=True)
    display_name: Mapped[str | None] = mapped_column(String, nullable=True)
    display_image_url: Mapped[str | None] = mapped_column(String, nullable=True)
    display_refreshed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
