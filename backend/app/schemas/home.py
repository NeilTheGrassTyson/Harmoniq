from __future__ import annotations

import uuid

from pydantic import BaseModel


class TrackSummary(BaseModel):
    id: uuid.UUID
    mbid: str
    title: str
    artist_name: str | None
    cover_art_url: str | None


class UserSummary(BaseModel):
    id: uuid.UUID
    username: str
    display_name: str
    avatar_url: str | None


class TrendingEntry(BaseModel):
    track: TrackSummary
    aggregate_score: float


class FriendEntry(BaseModel):
    track: TrackSummary
    score: int
    rated_by: UserSummary


class HomeResponse(BaseModel):
    trending: list[TrendingEntry]
    trending_error: bool = False
    friends: list[FriendEntry]
    friends_error: bool = False
    has_mutual_follows: bool
