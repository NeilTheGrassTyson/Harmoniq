import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, String, text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.core.enums import MelodyAcceptScope, VisibilityScope
from app.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(PGUUID, primary_key=True, default=uuid.uuid4)
    clerk_id: Mapped[str] = mapped_column(
        String, unique=True, nullable=False, index=True
    )
    username: Mapped[str] = mapped_column(
        String, unique=True, nullable=False, index=True
    )
    display_name: Mapped[str] = mapped_column(String(50), nullable=False)
    avatar_url: Mapped[str | None] = mapped_column(String, nullable=True)
    bio: Mapped[str | None] = mapped_column(String(280), nullable=True)
    visibility_bio: Mapped[str] = mapped_column(
        String, nullable=False, default=VisibilityScope.PRIVATE.value
    )
    visibility_activity: Mapped[str] = mapped_column(
        String, nullable=False, default=VisibilityScope.PRIVATE.value
    )
    # Public defaults below are documented constitutional exceptions — see
    # specs/phase-1-user-accounts-profiles.md and phase-1-ratings-reviews.md,
    # Amendments 2026-07-04. visibility_ratings is a master switch over every
    # rating surface; a private default would hide all new users' public
    # reviews and nullify the approved ratings public-default exception.
    visibility_ratings: Mapped[str] = mapped_column(
        String, nullable=False, default=VisibilityScope.PUBLIC.value
    )
    visibility_follows: Mapped[str] = mapped_column(
        String, nullable=False, default=VisibilityScope.PUBLIC.value
    )
    # Who may send this user a Melody. Consent guard for the anyone-can-send
    # model (Founder decision 2026-07-07). Not a VisibilityScope: it gates an
    # inbound gesture, not visibility of owned data.
    melody_accept_scope: Mapped[str] = mapped_column(
        String, nullable=False, default=MelodyAcceptScope.EVERYONE.value
    )
    # Moderation fields. is_moderator is granted only via manual SQL — no API
    # path ever writes it (Founder decision 2026-07-07). suspended_at doubles
    # as flag and audit timestamp; NULL = active. Unsuspend is manual SQL.
    is_moderator: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
    suspended_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
