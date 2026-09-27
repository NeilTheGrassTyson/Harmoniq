import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
    Uuid,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base

LISTEN_SOURCES = ("spotify", "apple_music", "harmoniq")


class Listen(Base):
    """
    One observed play, kept so a profile's Listening section survives the
    provider's rolling window (specs/phase-2-listen-history.md). Capped at 20
    per user on write.

    Provider rows (source != 'harmoniq') are display-only: Spotify forbids
    using its data to train or inform recommendations. Recommendation code
    must read listens only through listens.first_party_listens().

    The display fields are a snapshot so a listen shows immediately; track_id
    is the link to Harmoniq's catalog, filled in later from the ISRC when
    MusicBrainz can resolve it (Founder decision 2026-09-27).
    """

    __tablename__ = "listens"
    __table_args__ = (
        CheckConstraint(
            "source IN ('spotify','apple_music','harmoniq')", name="ck_listens_source"
        ),
        UniqueConstraint(
            "user_id", "source", "idempotency_key", name="uq_listens_observation"
        ),
        Index("ix_listens_user_recent", "user_id", "observed_at"),
        Index(
            "ix_listens_unlinked_isrc",
            "isrc",
            postgresql_where=text("track_id IS NULL"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    source: Mapped[str] = mapped_column(String, nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String, nullable=False)
    track_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("tracks.id", ondelete="SET NULL"), nullable=True
    )
    isrc: Mapped[str | None] = mapped_column(String, nullable=True)
    link_checked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    track_name: Mapped[str] = mapped_column(String, nullable=False)
    artist_name: Mapped[str] = mapped_column(String, nullable=False)
    album_name: Mapped[str | None] = mapped_column(String, nullable=True)
    album_art_url: Mapped[str | None] = mapped_column(String, nullable=True)
    provider_url: Mapped[str | None] = mapped_column(String, nullable=True)
    # Nullable: Apple Music reports no play time. Display falls back to
    # observed_at without special-casing the provider.
    played_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    observed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
