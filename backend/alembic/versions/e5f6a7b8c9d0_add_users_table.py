"""add users table

Revision ID: e5f6a7b8c9d0
Revises: c3f8a1b2d4e5
Create Date: 2026-06-18

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e5f6a7b8c9d0"
down_revision: str | None = "c3f8a1b2d4e5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("clerk_id", sa.String(), nullable=False),
        sa.Column("username", sa.String(), nullable=False),
        sa.Column("display_name", sa.String(length=50), nullable=False),
        sa.Column("avatar_url", sa.String(), nullable=True),
        sa.Column("bio", sa.String(length=280), nullable=True),
        sa.Column(
            "visibility_bio",
            sa.String(),
            nullable=False,
            server_default="private",
        ),
        sa.Column(
            "visibility_activity",
            sa.String(),
            nullable=False,
            server_default="private",
        ),
        sa.Column(
            "visibility_ratings",
            sa.String(),
            nullable=False,
            server_default="private",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("clerk_id"),
        sa.UniqueConstraint("username"),
    )
    op.create_index("ix_users_clerk_id", "users", ["clerk_id"])
    op.create_index("ix_users_username", "users", ["username"])


def downgrade() -> None:
    op.drop_index("ix_users_username", table_name="users")
    op.drop_index("ix_users_clerk_id", table_name="users")
    op.drop_table("users")
