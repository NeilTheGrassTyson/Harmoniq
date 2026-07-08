"""add ratings and reports tables

Revision ID: a1b2c3d4e5f6
Revises: e5f6a7b8c9d0
Create Date: 2026-06-20

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "a1b2c3d4e5f6"
down_revision: str | None = "e5f6a7b8c9d0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ratings",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("entity_type", sa.String(), nullable=False),
        sa.Column("entity_id", sa.Uuid(), nullable=False),
        sa.Column("score", sa.Integer(), nullable=False),
        sa.Column("review_text", sa.String(length=2000), nullable=False),
        sa.Column(
            "visibility",
            sa.String(),
            nullable=False,
            server_default="public",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("score >= 1 AND score <= 10", name="ck_ratings_score"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ratings_user_id", "ratings", ["user_id"])
    # Supports efficient "most recent rating per user per entity" queries
    op.create_index(
        "ix_ratings_user_entity_created",
        "ratings",
        ["user_id", "entity_type", "entity_id", "created_at"],
    )
    op.create_index(
        "ix_ratings_entity",
        "ratings",
        ["entity_type", "entity_id"],
    )

    op.create_table(
        "reports",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("reporter_id", sa.Uuid(), nullable=False),
        sa.Column("rating_id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["reporter_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["rating_id"], ["ratings.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "reporter_id", "rating_id", name="uq_reports_reporter_rating"
        ),
    )
    op.create_index("ix_reports_reporter_id", "reports", ["reporter_id"])
    op.create_index("ix_reports_rating_id", "reports", ["rating_id"])


def downgrade() -> None:
    op.drop_index("ix_reports_rating_id", table_name="reports")
    op.drop_index("ix_reports_reporter_id", table_name="reports")
    op.drop_table("reports")

    op.drop_index("ix_ratings_entity", table_name="ratings")
    op.drop_index("ix_ratings_user_entity_created", table_name="ratings")
    op.drop_index("ix_ratings_user_id", table_name="ratings")
    op.drop_table("ratings")
