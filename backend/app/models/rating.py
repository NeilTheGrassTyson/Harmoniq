import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    Uuid,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.core.enums import ReportStatus
from app.database import Base


class Rating(Base):
    __tablename__ = "ratings"
    __table_args__ = (
        CheckConstraint("score >= 1 AND score <= 10", name="ck_ratings_score"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id"), nullable=False, index=True
    )
    entity_type: Mapped[str] = mapped_column(String, nullable=False)
    # Polymorphic FK: references tracks.id or albums.id depending on entity_type.
    # No DB-level FK constraint — enforced in the service layer.
    entity_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    score: Mapped[int] = mapped_column(Integer, nullable=False)
    review_text: Mapped[str] = mapped_column(String(2000), nullable=False)
    visibility: Mapped[str] = mapped_column(
        String, nullable=False, default="public", server_default="public"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    # Moderation soft-hide: set (timestamp + acting moderator) removes the
    # rating from every public surface; the author still sees their own.
    hidden_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    hidden_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id"), nullable=True
    )


class Report(Base):
    __tablename__ = "reports"
    __table_args__ = (
        UniqueConstraint("reporter_id", "rating_id", name="uq_reports_reporter_rating"),
        Index("ix_reports_status_created", "status", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    reporter_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id"), nullable=False, index=True
    )
    rating_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("ratings.id"), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(
        String,
        nullable=False,
        default=ReportStatus.OPEN.value,
        server_default=text("'open'"),
    )
    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    resolved_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
