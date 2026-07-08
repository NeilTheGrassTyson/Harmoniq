"""add artists.aliases

Revision ID: d5e6f7a8b9c0
Revises: c4d5e6f7a8b9
Create Date: 2026-07-05

Purely additive: nullable TEXT[] of MusicBrainz alias names (translations,
transliterations, common abbreviations), populated on ingest so artist
search can match alternate names. Not surfaced through the API yet.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "d5e6f7a8b9c0"
down_revision: str | None = "c4d5e6f7a8b9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "artists",
        sa.Column("aliases", sa.ARRAY(sa.String()), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("artists", "aliases")
