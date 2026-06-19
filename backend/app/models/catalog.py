import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Artist(Base):
    __tablename__ = "artists"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    mbid: Mapped[str] = mapped_column(String, unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    sort_name: Mapped[str | None] = mapped_column(String, nullable=True)
    disambiguation: Mapped[str | None] = mapped_column(String, nullable=True)
    image_url: Mapped[str | None] = mapped_column(String, nullable=True)
    last_fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    albums: Mapped[list["Album"]] = relationship("Album", back_populates="artist")
    tracks: Mapped[list["Track"]] = relationship("Track", back_populates="artist")


class Album(Base):
    __tablename__ = "albums"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    mbid: Mapped[str] = mapped_column(String, unique=True, nullable=False, index=True)
    title: Mapped[str] = mapped_column(String, nullable=False)
    artist_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("artists.id"), nullable=True, index=True
    )
    release_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    album_type: Mapped[str | None] = mapped_column(String, nullable=True)
    cover_art_url: Mapped[str | None] = mapped_column(String, nullable=True)
    last_fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    artist: Mapped["Artist | None"] = relationship("Artist", back_populates="albums")
    tracks: Mapped[list["Track"]] = relationship("Track", back_populates="album")


class Track(Base):
    __tablename__ = "tracks"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    mbid: Mapped[str] = mapped_column(String, unique=True, nullable=False, index=True)
    title: Mapped[str] = mapped_column(String, nullable=False)
    artist_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("artists.id"), nullable=True, index=True
    )
    album_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("albums.id"), nullable=True, index=True
    )
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    track_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    disc_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    last_fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    artist: Mapped["Artist | None"] = relationship("Artist", back_populates="tracks")
    album: Mapped["Album | None"] = relationship("Album", back_populates="tracks")
