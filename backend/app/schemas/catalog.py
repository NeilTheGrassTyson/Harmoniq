from __future__ import annotations

from pydantic import BaseModel

from app.schemas.rating import RatingRead


class ArtistResult(BaseModel):
    mbid: str
    name: str
    disambiguation: str | None
    image_url: str | None


class AlbumResult(BaseModel):
    mbid: str
    title: str
    artist_name: str | None
    release_year: int | None
    # 'album' | 'ep' | 'single' where known; None on search results built
    # straight from MB payloads that predate ingestion.
    album_type: str | None = None
    cover_art_url: str | None


class TrackResult(BaseModel):
    mbid: str
    title: str
    artist_name: str | None
    album_title: str | None
    album_mbid: str | None
    duration_ms: int | None


class SearchResponse(BaseModel):
    artists: list[ArtistResult]
    albums: list[AlbumResult]
    tracks: list[TrackResult]


class ArtistDetail(BaseModel):
    mbid: str
    name: str
    sort_name: str | None
    disambiguation: str | None
    image_url: str | None
    albums: list[AlbumResult]


class AlbumDetail(BaseModel):
    mbid: str
    title: str
    artist_name: str | None
    artist_mbid: str | None
    release_year: int | None
    album_type: str | None
    cover_art_url: str | None
    tracks: list[TrackResult]
    aggregate_score: float | None = None
    reviews: list[RatingRead] = []


class TrackDetail(BaseModel):
    mbid: str
    title: str
    artist_name: str | None
    artist_mbid: str | None
    album_title: str | None
    album_mbid: str | None
    cover_art_url: str | None
    duration_ms: int | None
    track_number: int | None
    disc_number: int | None
    aggregate_score: float | None = None
    reviews: list[RatingRead] = []
