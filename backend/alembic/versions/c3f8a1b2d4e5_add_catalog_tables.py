"""add catalog tables

Revision ID: c3f8a1b2d4e5
Revises:
Create Date: 2026-06-18 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c3f8a1b2d4e5"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "artists",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("mbid", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("sort_name", sa.String(), nullable=True),
        sa.Column("disambiguation", sa.String(), nullable=True),
        sa.Column("image_url", sa.String(), nullable=True),
        sa.Column("last_fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_artists_mbid", "artists", ["mbid"], unique=True)

    op.create_table(
        "albums",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("mbid", sa.String(), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("artist_id", sa.Uuid(), nullable=True),
        sa.Column("release_year", sa.Integer(), nullable=True),
        sa.Column("album_type", sa.String(), nullable=True),
        sa.Column("cover_art_url", sa.String(), nullable=True),
        sa.Column("last_fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["artist_id"], ["artists.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_albums_mbid", "albums", ["mbid"], unique=True)
    op.create_index("ix_albums_artist_id", "albums", ["artist_id"])

    op.create_table(
        "tracks",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("mbid", sa.String(), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("artist_id", sa.Uuid(), nullable=True),
        sa.Column("album_id", sa.Uuid(), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("track_number", sa.Integer(), nullable=True),
        sa.Column("disc_number", sa.Integer(), nullable=True),
        sa.Column("last_fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["artist_id"], ["artists.id"]),
        sa.ForeignKeyConstraint(["album_id"], ["albums.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_tracks_mbid", "tracks", ["mbid"], unique=True)
    op.create_index("ix_tracks_artist_id", "tracks", ["artist_id"])
    op.create_index("ix_tracks_album_id", "tracks", ["album_id"])


def downgrade() -> None:
    op.drop_table("tracks")
    op.drop_table("albums")
    op.drop_table("artists")
