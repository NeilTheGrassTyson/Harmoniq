"""add pg_trgm extension and trigram indexes for local-first search

Revision ID: f8a9b0c1d2e3
Revises: e7f8a9b0c1d2
Create Date: 2026-08-01

"""

from collections.abc import Sequence

from alembic import op

revision: str = "f8a9b0c1d2e3"
down_revision: str | None = "e7f8a9b0c1d2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Purely additive (specs/local-first-search.md): fuzzy-match support for
    # the local-first search path. pg_trgm is a trusted extension on Neon.
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.execute(
        "CREATE INDEX ix_artists_name_trgm ON artists USING gin (name gin_trgm_ops)"
    )
    # Aliases (VARCHAR[]) are matched in the query via array_to_string but
    # deliberately NOT indexed: array_to_string is STABLE, not IMMUTABLE, so
    # an expression index would need a custom wrapper function. Artists is
    # the smallest catalog table; revisit if artist-search latency grows.
    op.execute(
        "CREATE INDEX ix_albums_title_trgm ON albums USING gin (title gin_trgm_ops)"
    )
    op.execute(
        "CREATE INDEX ix_tracks_title_trgm ON tracks USING gin (title gin_trgm_ops)"
    )


def downgrade() -> None:
    op.drop_index("ix_tracks_title_trgm", table_name="tracks")
    op.drop_index("ix_albums_title_trgm", table_name="albums")
    op.drop_index("ix_artists_name_trgm", table_name="artists")
    # The extension is left in place (other objects may come to depend on it).
