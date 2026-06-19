import uuid
from datetime import datetime

from sqlalchemy import DateTime, String
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.core.enums import VisibilityScope
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
    visibility_ratings: Mapped[str] = mapped_column(
        String, nullable=False, default=VisibilityScope.PRIVATE.value
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
