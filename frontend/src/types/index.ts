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

// ── Friends ───────────────────────────────────────────────────────────────────

/**
 * The relationship as the viewer sees it. A sender never sees their own
 * outstanding request, so "request_sent" is only ever the reply to a send —
 * a profile shows "none" whether that request is pending or declined.
 */
export type FriendshipState = "none" | "friends" | "request_sent" | "request_received";

export type FriendRequestScope = "everyone" | "follows" | "mutuals";

export interface FriendPerson {
  id: string;
  username: string;
  display_name: string;
  avatar_url: string | null;
  /** False offers a one-tap follow-back; friendship never creates a follow. */
  you_follow: boolean;
}

export interface FriendsOverview {
  friends: FriendPerson[];
  incoming: FriendPerson[];
}

// ── Highlights ────────────────────────────────────────────────────────────────

export type HighlightType = "track" | "album" | "artist" | "playlist";

export interface HighlightReview {
  score: number;
  review_text: string;
  /** The album's review, standing in for a track the owner hasn't reviewed. */
  of_album: boolean;
}

export interface HighlightItem {
  id: string;
  entity_type: HighlightType;
  title: string;
  subtitle: string | null;
  image_url: string | null;
  /** Catalog highlights open their Harmoniq page. */
  mbid: string | null;
  /** Playlists open in Spotify. */
  external_url: string | null;
  provider: "spotify" | null;
  review: HighlightReview | null;
}

export interface HighlightsResponse {
  items: HighlightItem[];
  limit: number;
  /** Owner-only. */
  visibility?: VisibilityScope | null;
  /** Owner-only: whether playlist highlights are switched on. */
  playlists_available?: boolean | null;
}

export interface PlaylistOption {
  id: string;
  name: string;
  image_url: string | null;
  highlighted: boolean;
}

export interface PlaylistPickerResponse {
  status: "ok" | "not_connected" | "needs_permission" | "unavailable";
  playlists: PlaylistOption[];
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
  /** Same audience as follow; absent when friend requests are switched off. */
  friendship?: FriendshipState;
  bio?: string | null;
  activity_placeholder?: boolean;
  /** Owner-only — absent for every other viewer. */
  activity_scope?: VisibilityScope;
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
  /** Absent or null while highlights are switched off on the backend. */
  visibility_highlights?: VisibilityScope | null;
  melody_accept_scope: MelodyAcceptScope;
  friend_request_scope?: FriendRequestScope;
  /** Absent or null while listen history is switched off on the backend. */
  store_listening?: boolean | null;
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
  visibility_highlights?: VisibilityScope;
  melody_accept_scope?: MelodyAcceptScope;
  friend_request_scope?: FriendRequestScope;
  store_listening?: boolean;
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
  /** Stored listens only: the Harmoniq catalog track, once linked. */
  track_mbid?: string | null;
}

export interface ListeningResponse {
  connected: boolean;
  /** Linked, but the stored token is unusable — the user must reconnect. */
  needs_reconnect?: boolean;
  now_playing: ListeningTrack | null;
  recently_played: RecentlyPlayedItem[];
  /** recently_played is the user's stored history, not Spotify's live window. */
  history?: boolean;
  /** Served from storage while a refresh runs; check again shortly. */
  refreshing?: boolean;
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
  /** Absent from backends older than friend requests; fall back to has_mutual_follows. */
  has_friends?: boolean;
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
  reaction?: MelodyReaction | null;
  id: string;
  sender: UserSummary;
  track: TrackSummary;
  status: MelodyStatus;
  created_at: string;
  responded_at: string | null;
}

/** Sender's view: recipient identity, sender-visible status ('received' shown as 'sent'). */
export interface MelodySentItem {
  reaction?: MelodyReaction | null;
  id: string;
  recipient: UserSummary;
  track: TrackSummary;
  status: MelodyStatus;
  created_at: string;
  responded_at: string | null;
}

export interface MelodyInboxResponse {
  reactions_enabled?: boolean;
  items: MelodyInboxItem[];
  next_cursor: string | null;
}

export type MelodyReaction = "not_for_me" | "liked" | "loved";

export type HarmonyResponse =
  | { kind: "hidden" }
  | { kind: "shared"; summary: "listeners" | "sustained" | null }
  | {
      kind: "owner";
      visibility: VisibilityScope;
      positive_count: number;
      resolved_count: number;
      acceptance_percent: number | null;
      active_sending_months: number;
    };

export interface StreamingResponse {
  links: {
    provider: "spotify" | "apple" | "youtube" | "tidal" | "deezer" | "amazon";
    name: string;
    url: string;
    kind: "exact" | "search";
  }[];
  mapping_status: "available" | "unavailable";
}

export interface MelodySentResponse {
  items: MelodySentItem[];
  next_cursor: string | null;
}

// ── Notifications ────────────────────────────────────────────────────────────

export type NotificationType =
  | "melody_received"
  | "new_follower"
  | "friend_request_received"
  | "friend_request_accepted";

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
