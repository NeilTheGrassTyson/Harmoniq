"""add spotify_connections table

Revision ID: c4d5e6f7a8b9
Revises: b3c4d5e6f7a8
Create Date: 2026-07-04

One row per linked Spotify account (spec: phase-1-spotify-listening.md).
Stores only the connection itself — spotify user id, Fernet-encrypted
refresh token, granted scopes, timestamp. No listening data is persisted;
the listening surface is display-only per ENGINEERING_BIBLE §13.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "c4d5e6f7a8b9"
down_revision: str | None = "b3c4d5e6f7a8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "spotify_connections",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("spotify_user_id", sa.String(), nullable=False),
        sa.Column("refresh_token_encrypted", sa.String(), nullable=False),
        sa.Column("scopes", sa.String(), nullable=False),
        sa.Column(
            "connected_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id"),
    )
    op.create_index(
        "ix_spotify_connections_user_id",
        "spotify_connections",
        ["user_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_spotify_connections_user_id", table_name="spotify_connections")
    op.drop_table("spotify_connections")
