from datetime import datetime

from pydantic import BaseModel


class ConnectUrlResponse(BaseModel):
    url: str


class SpotifyCallbackRequest(BaseModel):
    code: str
    state: str


class SpotifyConnectionStatus(BaseModel):
    connected: bool
    spotify_user_id: str | None = None
    connected_at: datetime | None = None


class ListeningTrack(BaseModel):
    track_name: str
    artist_name: str
    album_name: str | None = None
    album_art_url: str | None = None
    spotify_url: str | None = None


class RecentlyPlayedItem(ListeningTrack):
    played_at: datetime
    # Stored listens only: the Harmoniq catalog track, once linked by ISRC.
    track_mbid: str | None = None


class ListeningResponse(BaseModel):
    """Display-only view of a user's listening. recently_played comes from
    stored rows when history is on for this user, live from Spotify otherwise."""

    connected: bool
    # True when a connection exists (or existed) but cannot be used — the
    # stored token will not decrypt, or Spotify rejected it. Distinct from
    # `connected: false`, which means no account was ever linked. Collapsing
    # the two told users to "connect Spotify" on a profile whose settings page
    # said they already had.
    needs_reconnect: bool = False
    now_playing: ListeningTrack | None = None
    recently_played: list[RecentlyPlayedItem] = []
    # True when recently_played is this user's stored history rather than
    # Spotify's live window — the UI then says it's what Harmoniq has seen.
    history: bool = False
    # True when this answer came from storage while a refresh from Spotify
    # runs in the background; the client checks again shortly.
    refreshing: bool = False
