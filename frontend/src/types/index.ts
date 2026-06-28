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
  aggregate_score: number | null;
  reviews: RatingRead[];
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
  aggregate_score: number | null;
  reviews: RatingRead[];
}

// ── User search ───────────────────────────────────────────────────────────────

export interface UserSearchResult {
  username: string;
  display_name: string;
  avatar_url: string | null;
}

// ── Users & profiles ──────────────────────────────────────────────────────────

export type VisibilityScope = "private" | "friends" | "public";

// ── Follow / Following ────────────────────────────────────────────────────────

export interface FollowState {
  is_following: boolean;
  follows_you: boolean;
  is_friend: boolean;
}

export interface FollowSummary {
  user_id: string;
  username: string;
  display_name: string;
  avatar_url: string | null;
}

export interface FollowListResponse {
  items: FollowSummary[];
  next_cursor: string | null;
}

/** Public or viewer-scoped profile. Gated fields are absent (not null) when excluded by visibility. */
export interface ProfileResponse {
  username: string;
  display_name: string;
  avatar_url: string | null;
  is_own_profile: boolean;
  follower_count: number;
  following_count: number;
  follow?: FollowState;
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

// ── Ratings & Reviews ─────────────────────────────────────────────────────────

export interface ReviewerInfo {
  username: string;
  display_name: string;
  avatar_url: string | null;
}

export interface RatingRead {
  id: string;
  reviewer: ReviewerInfo;
  score: number;
  review_text: string;
  visibility: VisibilityScope;
  created_at: string;
}

export interface EntityRatingListResponse {
  aggregate_score: number | null;
  reviews: RatingRead[];
}

export interface UserRatingRead {
  id: string;
  entity_type: string;
  entity_mbid: string | null;
  entity_title: string | null;
  score: number;
  review_text: string;
  visibility: VisibilityScope;
  created_at: string;
}

export interface UserRatingListResponse {
  reviews: UserRatingRead[];
}

// ── Home ─────────────────────────────────────────────────────────────────────

export interface TrackSummary {
  id: string;
  mbid: string;
  title: string;
  artist_name: string | null;
  cover_art_url: string | null;
}

export interface UserSummary {
  id: string;
  username: string;
  display_name: string;
  avatar_url: string | null;
}

export interface TrendingEntry {
  track: TrackSummary;
  aggregate_score: number;
}

export interface FriendEntry {
  track: TrackSummary;
  score: number;
  rated_by: UserSummary;
}

export interface HomeResponse {
  trending: TrendingEntry[];
  trending_error: boolean;
  friends: FriendEntry[];
  friends_error: boolean;
  has_mutual_follows: boolean;
}

export interface RatingSubmitRequest {
  entity_type: string;
  entity_mbid: string;
  score: number;
  review_text: string;
  visibility?: VisibilityScope;
}
