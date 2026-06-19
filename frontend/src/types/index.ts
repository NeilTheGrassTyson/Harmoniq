// Shared TypeScript types — extended as features are built.
// Types should mirror the Pydantic schemas defined in the backend.

export interface HealthResponse {
  status: string;
  version: string;
}

// ── Catalog ───────────────────────────────────────────────────────────────────

export interface ArtistResult {
  mbid: string;
  name: string;
  disambiguation: string | null;
  image_url: string | null;
}

export interface AlbumResult {
  mbid: string;
  title: string;
  artist_name: string | null;
  release_year: number | null;
  cover_art_url: string | null;
}

export interface TrackResult {
  mbid: string;
  title: string;
  artist_name: string | null;
  album_title: string | null;
  album_mbid: string | null;
  duration_ms: number | null;
}

export interface SearchResponse {
  artists: ArtistResult[];
  albums: AlbumResult[];
  tracks: TrackResult[];
}

export interface ArtistDetail {
  mbid: string;
  name: string;
  sort_name: string | null;
  disambiguation: string | null;
  image_url: string | null;
  albums: AlbumResult[];
}

export interface AlbumDetail {
  mbid: string;
  title: string;
  artist_name: string | null;
  artist_mbid: string | null;
  release_year: number | null;
  album_type: string | null;
  cover_art_url: string | null;
  tracks: TrackResult[];
}

export interface TrackDetail {
  mbid: string;
  title: string;
  artist_name: string | null;
  artist_mbid: string | null;
  album_title: string | null;
  album_mbid: string | null;
  cover_art_url: string | null;
  duration_ms: number | null;
  track_number: number | null;
  disc_number: number | null;
}

// ── Users & profiles ──────────────────────────────────────────────────────────

export type VisibilityScope = "private" | "friends" | "public";

/** Public or viewer-scoped profile. Gated fields are absent (not null) when excluded by visibility. */
export interface ProfileResponse {
  username: string;
  display_name: string;
  avatar_url: string | null;
  is_own_profile: boolean;
  bio?: string | null;
  activity_placeholder?: boolean;
  ratings_count?: number;
}

/** Full profile for the authenticated owner, including visibility settings. */
export interface OwnProfileResponse {
  username: string;
  display_name: string;
  avatar_url: string | null;
  bio: string | null;
  visibility_bio: VisibilityScope;
  visibility_activity: VisibilityScope;
  visibility_ratings: VisibilityScope;
}

export interface UsernameCheckResponse {
  available: boolean;
}

export interface AvatarUploadResponse {
  avatar_url: string;
}

export interface ProfileUpdateRequest {
  display_name?: string;
  username?: string;
  bio?: string | null;
  visibility_bio?: VisibilityScope;
  visibility_activity?: VisibilityScope;
  visibility_ratings?: VisibilityScope;
}
