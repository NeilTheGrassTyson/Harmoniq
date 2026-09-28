import uuid
from typing import Literal

from pydantic import BaseModel, Field

from app.core.enums import HighlightType, VisibilityScope


class HighlightReview(BaseModel):
    """The owner's own review, shown only when the viewer may see it."""

    score: int
    review_text: str
    # The album's review standing in for a track the owner hasn't reviewed.
    of_album: bool = False


class HighlightItem(BaseModel):
    id: uuid.UUID
    entity_type: HighlightType
    title: str
    subtitle: str | None = None
    image_url: str | None = None
    # Catalog highlights open their Harmoniq page; playlists open Spotify.
    mbid: str | None = None
    external_url: str | None = None
    provider: Literal["spotify"] | None = None
    review: HighlightReview | None = None


class HighlightsResponse(BaseModel):
    items: list[HighlightItem]
    limit: int
    # Owner-only: who else can see them. Never sent to another viewer.
    visibility: VisibilityScope | None = None
    # Playlists (for the owner): whether they can be added right now.
    playlists_available: bool | None = None


class AddHighlightRequest(BaseModel):
    entity_type: HighlightType
    mbid: str | None = Field(default=None, max_length=64)
    playlist_id: str | None = Field(default=None, max_length=64)


class PlaylistOption(BaseModel):
    id: str
    name: str
    image_url: str | None = None
    highlighted: bool = False


class PlaylistPickerResponse(BaseModel):
    status: Literal["ok", "not_connected", "needs_permission", "unavailable"]
    playlists: list[PlaylistOption] = []
