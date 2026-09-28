import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database import Base


class SpotifyConnection(Base):
    """
    A user's linked Spotify account. refresh_token_encrypted holds Fernet
    ciphertext (app/core/crypto.py), never a plaintext token.

    Listening data is display-only. By default it is never written to the
    database; with LISTEN_HISTORY_ENABLED on and the user's own opt-in, up to
    20 recent plays are kept in `listens` (phase-2-listen-history.md), deleted
    when this connection is removed, and never read by recommendation code.
    """

    __tablename__ = "spotify_connections"

    id: Mapped[uuid.UUID] = mapped_column(PGUUID, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID,
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )
    spotify_user_id: Mapped[str] = mapped_column(String, nullable=False)
    refresh_token_encrypted: Mapped[str] = mapped_column(String, nullable=False)
    scopes: Mapped[str] = mapped_column(String, nullable=False)
    connected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
