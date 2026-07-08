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
  album_type?: "album" | "ep" | "single" | "compilation" | "other" | null;
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

export type MelodyAcceptScope = "everyone" | "follows" | "mutuals";

/** Full profile for the authenticated owner, including visibility settings. */
export interface OwnProfileResponse {
  username: string;
  display_name: string;
  avatar_url: string | null;
  bio: string | null;
  visibility_bio: VisibilityScope;
  visibility_activity: VisibilityScope;
  visibility_ratings: VisibilityScope;
  visibility_follows: VisibilityScope;
  melody_accept_scope: MelodyAcceptScope;
  is_moderator: boolean;
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
  visibility_follows?: VisibilityScope;
  melody_accept_scope?: MelodyAcceptScope;
}

// ── Spotify (account linking + listening display) ─────────────────────────────

export interface SpotifyConnectionStatus {
  connected: boolean;
  spotify_user_id: string | null;
  connected_at: string | null;
}

export interface ListeningTrack {
  track_name: string;
  artist_name: string;
  album_name: string | null;
  album_art_url: string | null;
  spotify_url: string | null;
}

export interface RecentlyPlayedItem extends ListeningTrack {
  played_at: string;
}

export interface ListeningResponse {
  connected: boolean;
  now_playing: ListeningTrack | null;
  recently_played: RecentlyPlayedItem[];
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
  /** True only in the author's own view of a moderation-hidden review. */
  hidden?: boolean;
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
  hidden?: boolean;
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

// ── Melody ───────────────────────────────────────────────────────────────────

export type MelodyStatus = "sent" | "received" | "accepted" | "opened" | "rejected";

export type MelodyRespondAction = "accept" | "open" | "reject";

/** Recipient's view: true status, sender identity. */
export interface MelodyInboxItem {
  id: string;
  sender: UserSummary;
  track: TrackSummary;
  status: MelodyStatus;
  created_at: string;
  responded_at: string | null;
}

/** Sender's view: recipient identity, sender-visible status ('received' shown as 'sent'). */
export interface MelodySentItem {
  id: string;
  recipient: UserSummary;
  track: TrackSummary;
  status: MelodyStatus;
  created_at: string;
  responded_at: string | null;
}

export interface MelodyInboxResponse {
  items: MelodyInboxItem[];
  next_cursor: string | null;
}

export interface MelodySentResponse {
  items: MelodySentItem[];
  next_cursor: string | null;
}

// ── Notifications ────────────────────────────────────────────────────────────

export type NotificationType = "melody_received" | "new_follower";

export interface NotificationMelodyRef {
  id: string;
  track: TrackSummary;
}

export interface NotificationItem {
  id: string;
  type: NotificationType;
  actor: UserSummary;
  melody: NotificationMelodyRef | null;
  read: boolean;
  created_at: string;
}

export interface NotificationListResponse {
  items: NotificationItem[];
  next_cursor: string | null;
}

export interface UnreadCountResponse {
  count: number;
}

// ── Moderation ───────────────────────────────────────────────────────────────

export type ReportStatus = "open" | "dismissed" | "actioned";

export interface ReportedRating {
  id: string;
  entity_type: string;
  score: number;
  review_text: string;
  hidden: boolean;
  author: UserSummary;
  author_suspended: boolean;
}

export interface ReportQueueItem {
  id: string;
  status: ReportStatus;
  created_at: string;
  reporter: UserSummary;
  rating: ReportedRating;
  open_report_count: number;
}

export interface ReportQueueResponse {
  items: ReportQueueItem[];
  next_cursor: string | null;
}
