"""add notifications table

Minimal in-app notification center: melody_received and new_follower only.
Partial unique indexes make creation idempotent (re-follow never re-notifies;
a melody notifies exactly once). No event type exists for rejection.

Revision ID: d6e7f8a9b0c1
Revises: c5d6e7f8a9b0
Create Date: 2026-07-07
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "d6e7f8a9b0c1"
down_revision: str | None = "c5d6e7f8a9b0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "notifications",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("type", sa.String(), nullable=False),
        sa.Column("actor_id", sa.Uuid(), nullable=False),
        sa.Column("melody_id", sa.Uuid(), nullable=True),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["actor_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["melody_id"], ["melodies.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_notifications_user_list", "notifications", ["user_id", "created_at", "id"]
    )
    op.create_index(
        "ix_notifications_unread",
        "notifications",
        ["user_id"],
        postgresql_where=sa.text("read_at IS NULL"),
    )
    op.create_index(
        "uq_notifications_follower",
        "notifications",
        ["user_id", "actor_id"],
        unique=True,
        postgresql_where=sa.text("type = 'new_follower'"),
    )
    op.create_index(
        "uq_notifications_melody",
        "notifications",
        ["melody_id"],
        unique=True,
        postgresql_where=sa.text("melody_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_notifications_melody", table_name="notifications")
    op.drop_index("uq_notifications_follower", table_name="notifications")
    op.drop_index("ix_notifications_unread", table_name="notifications")
    op.drop_index("ix_notifications_user_list", table_name="notifications")
    op.drop_table("notifications")
