"""add moderation fields: is_moderator, suspended_at, rating hide, report status

is_moderator is granted only via manual SQL — no API writes it. suspended_at
NULL = active. ratings.hidden_at/hidden_by implement the moderation soft-hide.
reports gains a status lifecycle (open/dismissed/actioned) with resolution
audit fields; existing rows are covered by the 'open' server default.

Revision ID: e7f8a9b0c1d2
Revises: d6e7f8a9b0c1
Create Date: 2026-07-07
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "e7f8a9b0c1d2"
down_revision: str | None = "d6e7f8a9b0c1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "is_moderator",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.add_column(
        "users", sa.Column("suspended_at", sa.DateTime(timezone=True), nullable=True)
    )

    op.add_column(
        "ratings", sa.Column("hidden_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column("ratings", sa.Column("hidden_by", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        "fk_ratings_hidden_by_users", "ratings", "users", ["hidden_by"], ["id"]
    )

    op.add_column(
        "reports",
        sa.Column(
            "status", sa.String(), nullable=False, server_default=sa.text("'open'")
        ),
    )
    op.add_column(
        "reports", sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column("reports", sa.Column("resolved_by", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        "fk_reports_resolved_by_users", "reports", "users", ["resolved_by"], ["id"]
    )
    op.create_index("ix_reports_status_created", "reports", ["status", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_reports_status_created", table_name="reports")
    op.drop_constraint("fk_reports_resolved_by_users", "reports", type_="foreignkey")
    op.drop_column("reports", "resolved_by")
    op.drop_column("reports", "resolved_at")
    op.drop_column("reports", "status")
    op.drop_constraint("fk_ratings_hidden_by_users", "ratings", type_="foreignkey")
    op.drop_column("ratings", "hidden_by")
    op.drop_column("ratings", "hidden_at")
    op.drop_column("users", "suspended_at")
    op.drop_column("users", "is_moderator")
