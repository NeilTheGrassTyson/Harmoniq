from __future__ import annotations

from pydantic import BaseModel


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


# Album and track detail carry catalog metadata only — no ratings. Reviews are
# visibility-scoped per viewer, and embedding them here made these responses
# impossible to cache (ENGINEERING_BIBLE.md §8.1). Clients read reviews from
# GET /ratings/entity/{type}/{mbid}, which enforces scope at the data layer.
class AlbumDetail(BaseModel):
    mbid: str
    title: str
    artist_name: str | None
    artist_mbid: str | None
    release_year: int | None
    album_type: str | None
    cover_art_url: str | None
    tracks: list[TrackResult]


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
