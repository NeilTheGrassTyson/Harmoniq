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
