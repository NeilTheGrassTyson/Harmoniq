"""add index supporting home trending time-window query

Revision ID: a2b3c4d5e6f7
Revises: f6a7b8c9d0e1
Create Date: 2026-06-20

"""

from collections.abc import Sequence

from alembic import op

revision: str = "a2b3c4d5e6f7"
down_revision: str | None = "f6a7b8c9d0e1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Supports: WHERE entity_type = 'track' AND created_at >= <cutoff>
    # used by the Home Trending query to scan only recent track ratings.
    op.create_index(
        "ix_ratings_entity_type_created_at",
        "ratings",
        ["entity_type", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_ratings_entity_type_created_at", table_name="ratings")
