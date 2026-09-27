"""Add durable recent listening and its separate storage opt-in.

Purely additive (specs/phase-2-listen-history.md): one table, one column.
Nothing is stored until LISTEN_HISTORY_ENABLED is on and a user opts in.

Revision ID: c1d2e3f4a5b6
Revises: b0c1d2e3f4a5
Create Date: 2026-09-27
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "c1d2e3f4a5b6"
down_revision: str | None = "b0c1d2e3f4a5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "store_listening",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.create_table(
        "listens",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("source", sa.String(), nullable=False),
        sa.Column("idempotency_key", sa.String(), nullable=False),
        sa.Column(
            "track_id",
            sa.Uuid(),
            sa.ForeignKey("tracks.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("isrc", sa.String(), nullable=True),
        sa.Column("link_checked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("track_name", sa.String(), nullable=False),
        sa.Column("artist_name", sa.String(), nullable=False),
        sa.Column("album_name", sa.String(), nullable=True),
        sa.Column("album_art_url", sa.String(), nullable=True),
        sa.Column("provider_url", sa.String(), nullable=True),
        sa.Column("played_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "observed_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "source IN ('spotify','apple_music','harmoniq')", name="ck_listens_source"
        ),
        sa.UniqueConstraint(
            "user_id", "source", "idempotency_key", name="uq_listens_observation"
        ),
    )
    op.create_index("ix_listens_user_recent", "listens", ["user_id", "observed_at"])
    op.create_index(
        "ix_listens_unlinked_isrc",
        "listens",
        ["isrc"],
        postgresql_where=sa.text("track_id IS NULL"),
    )


def downgrade() -> None:
    # Operational rollback is LISTEN_HISTORY_ENABLED=false, which keeps rows.
    op.drop_index("ix_listens_unlinked_isrc", table_name="listens")
    op.drop_index("ix_listens_user_recent", table_name="listens")
    op.drop_table("listens")
    op.drop_column("users", "store_listening")
