"""Add highlights and their public-by-default visibility.

Additive (specs/phase-2-highlights.md): one table, one users column. The
public default is a recorded constitutional exception, bounded by every
highlight being added explicitly; nothing is created by this migration.

Revision ID: d2e3f4a5b6c7
Revises: c1d2e3f4a5b6
Create Date: 2026-09-27
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "d2e3f4a5b6c7"
down_revision: str | None = "c1d2e3f4a5b6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "visibility_highlights",
            sa.String(),
            nullable=False,
            server_default="public",
        ),
    )
    op.create_table(
        "highlights",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("entity_type", sa.String(), nullable=False),
        sa.Column("entity_id", sa.Uuid(), nullable=True),
        sa.Column("provider", sa.String(), nullable=True),
        sa.Column("provider_ref", sa.String(), nullable=True),
        sa.Column("display_name", sa.String(), nullable=True),
        sa.Column("display_image_url", sa.String(), nullable=True),
        sa.Column("display_refreshed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "entity_type IN ('track','album','artist','playlist')",
            name="ck_highlights_type",
        ),
        sa.CheckConstraint(
            "(entity_type = 'playlist' AND provider IS NOT NULL"
            " AND provider_ref IS NOT NULL AND entity_id IS NULL)"
            " OR (entity_type <> 'playlist' AND entity_id IS NOT NULL"
            " AND provider IS NULL AND provider_ref IS NULL)",
            name="ck_highlights_reference",
        ),
    )
    op.create_index(
        "uq_highlights_entity",
        "highlights",
        ["user_id", "entity_type", "entity_id"],
        unique=True,
        postgresql_where=sa.text("entity_id IS NOT NULL"),
    )
    op.create_index(
        "uq_highlights_playlist",
        "highlights",
        ["user_id", "provider", "provider_ref"],
        unique=True,
        postgresql_where=sa.text("provider_ref IS NOT NULL"),
    )
    op.create_index("ix_highlights_user", "highlights", ["user_id", "created_at"])


def downgrade() -> None:
    # Operational rollback is HIGHLIGHTS_ENABLED=false, which keeps rows.
    op.drop_index("ix_highlights_user", table_name="highlights")
    op.drop_index("uq_highlights_playlist", table_name="highlights")
    op.drop_index("uq_highlights_entity", table_name="highlights")
    op.drop_table("highlights")
    op.drop_column("users", "visibility_highlights")
