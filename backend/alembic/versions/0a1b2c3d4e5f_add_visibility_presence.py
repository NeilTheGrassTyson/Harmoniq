"""add users.visibility_presence (beta-ui Phase 5: Online status)

Additive. Every existing account starts Private — no one is shown as online
until they choose to be (docs/specs/beta-ui-phase-5-presence.md). Presence
itself is never persisted; this column is only the consent.

Revision ID: 0a1b2c3d4e5f
Revises: f8a9b0c1d2e3
Create Date: 2026-09-27
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0a1b2c3d4e5f"
down_revision: str | None = "f8a9b0c1d2e3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "visibility_presence",
            sa.String(),
            nullable=False,
            server_default=sa.text("'private'"),
        ),
    )


def downgrade() -> None:
    op.drop_column("users", "visibility_presence")
