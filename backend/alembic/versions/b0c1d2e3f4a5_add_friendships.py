"""Add explicit friendships and the friend-request consent gate.

Every existing mutual-follow pair becomes an accepted friendship, so nobody
loses friends-scoped access they had before (specs/phase-2-friend-requests.md).
Follows are left untouched: rows are created alongside them, never in place of
them, which is what lets FRIENDSHIPS_ENABLED=false fall back to mutual follow.

Revision ID: b0c1d2e3f4a5
Revises: a9b0c1d2e3f4
Create Date: 2026-09-27
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "b0c1d2e3f4a5"
down_revision: str | None = "a9b0c1d2e3f4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# Each mutual-follow pair becomes one accepted friendship. The earlier
# follower is treated as having asked first; the pair's later follow is when
# it became mutual. Module-level so the conversion itself is testable.
CONVERT_MUTUAL_FOLLOWS = """
        INSERT INTO friendships
            (user_low_id, user_high_id, status, requested_by, created_at,
             responded_at)
        SELECT a.follower_id, a.followed_id, 'accepted',
               CASE WHEN a.created_at <= b.created_at
                    THEN a.follower_id ELSE b.follower_id END,
               GREATEST(a.created_at, b.created_at),
               GREATEST(a.created_at, b.created_at)
        FROM follows a
        JOIN follows b
          ON b.follower_id = a.followed_id AND b.followed_id = a.follower_id
        WHERE a.follower_id < a.followed_id
        ON CONFLICT DO NOTHING
        """


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "friend_request_scope",
            sa.String(),
            nullable=False,
            server_default="everyone",
        ),
    )
    op.create_table(
        "friendships",
        sa.Column(
            "user_low_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "user_high_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column(
            "requested_by",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("responded_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "user_low_id < user_high_id", name="ck_friendships_canonical_order"
        ),
        sa.CheckConstraint(
            "status IN ('pending','accepted','declined')", name="ck_friendships_status"
        ),
        sa.CheckConstraint(
            "requested_by = user_low_id OR requested_by = user_high_id",
            name="ck_friendships_requester_in_pair",
        ),
    )
    op.create_index(
        "ix_friendships_high_accepted",
        "friendships",
        ["user_high_id"],
        postgresql_where=sa.text("status = 'accepted'"),
    )
    op.create_index(
        "ix_friendships_low_accepted",
        "friendships",
        ["user_low_id"],
        postgresql_where=sa.text("status = 'accepted'"),
    )
    op.create_index(
        "uq_notifications_friend_request",
        "notifications",
        ["user_id", "actor_id", "type"],
        unique=True,
        postgresql_where=sa.text(
            "type IN ('friend_request_received','friend_request_accepted')"
        ),
    )
    op.execute(CONVERT_MUTUAL_FOLLOWS)


def downgrade() -> None:
    # Operational rollback is FRIENDSHIPS_ENABLED=false, which keeps rows.
    # Explicit Alembic downgrades are for disposable environments only.
    op.drop_index("uq_notifications_friend_request", table_name="notifications")
    op.drop_index("ix_friendships_low_accepted", table_name="friendships")
    op.drop_index("ix_friendships_high_accepted", table_name="friendships")
    op.drop_table("friendships")
    op.drop_column("users", "friend_request_scope")
