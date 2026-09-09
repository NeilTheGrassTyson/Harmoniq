"""Add private Harmony visibility and optional recipient reactions.

Revision ID: a9b0c1d2e3f4
Revises: f8a9b0c1d2e3
Create Date: 2026-09-08
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "a9b0c1d2e3f4"
down_revision: str | None = "f8a9b0c1d2e3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "visibility_harmony", sa.String(), nullable=False, server_default="private"
        ),
    )
    op.add_column("melodies", sa.Column("reaction", sa.String(), nullable=True))
    op.add_column(
        "melodies", sa.Column("reacted_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.create_check_constraint(
        "ck_melodies_reaction",
        "melodies",
        "reaction IS NULL OR reaction IN ('not_for_me','liked','loved')",
    )


def downgrade() -> None:
    # Operational rollback uses feature switches and keeps user feedback.
    # Explicit Alembic downgrades are for disposable environments only.
    op.drop_constraint("ck_melodies_reaction", "melodies", type_="check")
    op.drop_column("melodies", "reacted_at")
    op.drop_column("melodies", "reaction")
    op.drop_column("users", "visibility_harmony")
