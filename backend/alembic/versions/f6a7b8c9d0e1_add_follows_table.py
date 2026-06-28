"""add follows table

Revision ID: f6a7b8c9d0e1
Revises: a1b2c3d4e5f6
Create Date: 2026-06-20

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "f6a7b8c9d0e1"
down_revision: str | None = "a1b2c3d4e5f6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "follows",
        sa.Column("follower_id", sa.Uuid(), nullable=False),
        sa.Column("followed_id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "follower_id != followed_id", name="ck_follows_no_self_follow"
        ),
        sa.ForeignKeyConstraint(["follower_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["followed_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("follower_id", "followed_id"),
    )
    # Efficient follower-count and follower-list queries (who follows this user?)
    op.create_index("ix_follows_followed_id", "follows", ["followed_id"])
    # Efficient following-count and following-list queries (who does this user follow?)
    op.create_index("ix_follows_follower_id", "follows", ["follower_id"])


def downgrade() -> None:
    op.drop_index("ix_follows_follower_id", table_name="follows")
    op.drop_index("ix_follows_followed_id", table_name="follows")
    op.drop_table("follows")
