"""add users.visibility_follows; visibility_ratings defaults to public

Revision ID: b3c4d5e6f7a8
Revises: a2b3c4d5e6f7
Create Date: 2026-07-04

Two consent-model changes, both Founder-approved 2026-07-04 (see
specs/phase-1-user-accounts-profiles.md Amendments and
specs/phase-1-ratings-reviews.md Amendments):

1. visibility_follows — owner-controlled scope for follower/following
   lists. Default (and backfill via server_default) is 'public', a
   documented constitutional exception to the "default private"
   convention. Existing users keep the previously world-readable list
   behavior; the setting lets any user tighten it, effective immediately.

2. visibility_ratings becomes a master switch over every rating surface.
   Its default therefore flips to 'public', extending the ratings
   public-by-default exception to the profile level — a 'private' default
   would hide every new user's public reviews from everyone, nullifying
   the approved exception. Existing 'private' rows are backfilled to
   'public' because that PRESERVES current behavior: before this
   amendment the profile setting only hid the ratings count, so existing
   public reviews were visible; leaving the switch at 'private' would
   silently hide them.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "b3c4d5e6f7a8"
down_revision: str | None = "a2b3c4d5e6f7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "visibility_follows",
            sa.String(),
            nullable=False,
            server_default=sa.text("'public'"),
        ),
    )
    op.alter_column(
        "users",
        "visibility_ratings",
        server_default=sa.text("'public'"),
    )
    op.execute("UPDATE users SET visibility_ratings = 'public'")


def downgrade() -> None:
    op.alter_column("users", "visibility_ratings", server_default=None)
    op.drop_column("users", "visibility_follows")
