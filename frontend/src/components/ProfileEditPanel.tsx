"use client";

import { useAuth } from "@clerk/nextjs";
import { useCallback, useEffect, useRef, useState } from "react";
import AvatarImage from "@/components/AvatarImage";
import VisibilitySelect from "@/components/VisibilitySelect";
import { checkUsernameAvailable, getOwnProfile, updateProfile, uploadAvatar } from "@/lib/users";
import { disconnectSpotify, getSpotifyConnection, getSpotifyConnectUrl } from "@/lib/spotify";
import type { OwnProfileResponse, SpotifyConnectionStatus, VisibilityScope } from "@/types";

const USERNAME_RE = /^[a-zA-Z0-9_-]{3,30}$/;

type AvailabilityState =
  | { kind: "idle" }
  | { kind: "checking" }
  | { kind: "available" }
  | { kind: "taken" }
  | { kind: "invalid" }
  | { kind: "unchanged" };

interface ProfileEditPanelProps {
  initial: {
    username: string;
    displayName: string;
    avatarUrl: string | null;
  };
  /** True immediately after the Spotify OAuth callback redirects back here. */
  spotifyJustConnected?: boolean;
  onCancel: () => void;
  onSaved: (updated: OwnProfileResponse) => void;
}

export default function ProfileEditPanel({
  initial,
  spotifyJustConnected = false,
  onCancel,
  onSaved,
}: ProfileEditPanelProps) {
  const { getToken } = useAuth();

  const [loading, setLoading] = useState(true);
  const [avatarUrl, setAvatarUrl] = useState(initial.avatarUrl);

  // Form state
  const [displayName, setDisplayName] = useState(initial.displayName);
  const [username, setUsername] = useState(initial.username);
  const [bio, setBio] = useState("");
  const [visibilityBio, setVisibilityBio] = useState<VisibilityScope>("private");
  const [visibilityActivity, setVisibilityActivity] = useState<VisibilityScope>("private");
  const [visibilityRatings, setVisibilityRatings] = useState<VisibilityScope>("private");
  const [visibilityFollows, setVisibilityFollows] = useState<VisibilityScope>("public");

  const [availability, setAvailability] = useState<AvailabilityState>({ kind: "idle" });
  const [saveError, setSaveError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  const [avatarUploading, setAvatarUploading] = useState(false);
  const [avatarError, setAvatarError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [originalUsername, setOriginalUsername] = useState(initial.username);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const [spotify, setSpotify] = useState<SpotifyConnectionStatus | null>(null);
  const [spotifyBusy, setSpotifyBusy] = useState(false);
  const [spotifyError, setSpotifyError] = useState<string | null>(null);

  // Load full profile (visibility settings + bio aren't in the page's ProfileResponse)
  useEffect(() => {
    getToken()
      .then(async (token) => {
        if (!token) return;
        const data = await getOwnProfile(token);
        setAvatarUrl(data.avatar_url);
        setDisplayName(data.display_name);
        setUsername(data.username);
        setBio(data.bio ?? "");
        setVisibilityBio(data.visibility_bio);
        setVisibilityActivity(data.visibility_activity);
        setVisibilityRatings(data.visibility_ratings);
        setVisibilityFollows(data.visibility_follows);
        setOriginalUsername(data.username);
      })
      .catch(() => setSaveError("Couldn't load your profile."))
      .finally(() => setLoading(false));
  }, [getToken]);

  // Spotify connection status — loaded separately so a Spotify hiccup never
  // blocks the profile form.
  useEffect(() => {
    getToken()
      .then(async (token) => {
        if (!token) return;
        const status = await getSpotifyConnection(token);
        setSpotify(status);
      })
      .catch(() => setSpotify(null));
  }, [getToken]);

  const handleSpotifyConnect = async () => {
    setSpotifyBusy(true);
    setSpotifyError(null);
    try {
      const token = await getToken();
      if (!token) throw new Error("Not authenticated");
      const { url } = await getSpotifyConnectUrl(token);
      window.location.assign(url);
    } catch (err: unknown) {
      setSpotifyError(
        err instanceof Error ? err.message : "Spotify integration isn't available right now."
      );
      setSpotifyBusy(false);
    }
  };

  const handleSpotifyDisconnect = async () => {
    setSpotifyBusy(true);
    setSpotifyError(null);
    try {
      const token = await getToken();
      if (!token) throw new Error("Not authenticated");
      await disconnectSpotify(token);
      setSpotify({ connected: false, spotify_user_id: null, connected_at: null });
    } catch {
      setSpotifyError("Couldn't disconnect. Try again.");
    } finally {
      setSpotifyBusy(false);
    }
  };

  const handleUsernameChange = useCallback(
    (value: string) => {
      setUsername(value);
      setSaveError(null);

      if (debounceRef.current) clearTimeout(debounceRef.current);

      if (value === originalUsername) {
        setAvailability({ kind: "unchanged" });
        return;
      }
      if (!value) {
        setAvailability({ kind: "idle" });
        return;
      }
      if (!USERNAME_RE.test(value)) {
        setAvailability({ kind: "invalid" });
        return;
      }

      setAvailability({ kind: "checking" });
      debounceRef.current = setTimeout(async () => {
        try {
          const result = await checkUsernameAvailable(value);
          setAvailability(result.available ? { kind: "available" } : { kind: "taken" });
        } catch {
          setAvailability({ kind: "idle" });
        }
      }, 300);
    },
    [originalUsername]
  );

  const handleAvatarClick = () => fileInputRef.current?.click();

  const handleAvatarChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setAvatarError(null);

    const allowed = ["image/jpeg", "image/png", "image/webp"];
    if (!allowed.includes(file.type)) {
      setAvatarError("Please upload a JPEG, PNG, or WebP image.");
      return;
    }
    if (file.size > 5 * 1024 * 1024) {
      setAvatarError("File must be under 5 MB.");
      return;
    }

    setAvatarUploading(true);
    try {
      const token = await getToken();
      if (!token) throw new Error("Not authenticated");
      const result = await uploadAvatar(token, file);
      setAvatarUrl(result.avatar_url);
    } catch {
      setAvatarError("Couldn't upload your photo. Try again.");
    } finally {
      setAvatarUploading(false);
      // Reset file input so re-selecting the same file triggers onChange again
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  };

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaveError(null);

    if (!USERNAME_RE.test(username)) return;
    if (!displayName.trim()) return;

    const isUsernameChanged = username !== originalUsername;
    if (isUsernameChanged && availability.kind !== "available") return;

    setSaving(true);
    try {
      const token = await getToken();
      if (!token) throw new Error("Not authenticated");
      const updated = await updateProfile(token, {
        display_name: displayName.trim(),
        username: isUsernameChanged ? username : undefined,
        bio: bio.trim() || null,
        visibility_bio: visibilityBio,
        visibility_activity: visibilityActivity,
        visibility_ratings: visibilityRatings,
        visibility_follows: visibilityFollows,
      });
      onSaved(updated);
    } catch (err: unknown) {
      setSaveError(
        err instanceof Error ? err.message : "Something went wrong. Your changes weren't saved."
      );
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="border-hairline mt-4 animate-pulse space-y-4 border-t pt-6">
        <div className="bg-tile h-16 w-16 rounded-full" />
        <div className="bg-tile h-4 w-48 rounded" />
        <div className="bg-tile h-4 w-32 rounded" />
      </div>
    );
  }

  const canSave =
    !saving &&
    displayName.trim().length > 0 &&
    USERNAME_RE.test(username) &&
    (username === originalUsername || availability.kind === "available");

  return (
    <form onSubmit={handleSave} className="border-hairline mt-4 space-y-8 border-t pt-6">
      {/* Avatar */}
      <div>
        <p className="text-tertiary mb-3 text-xs font-medium tracking-widest uppercase">Avatar</p>
        <div className="flex items-center gap-4">
          <AvatarImage src={avatarUrl} username={username} size={64} />
          <div>
            <button
              type="button"
              onClick={handleAvatarClick}
              disabled={avatarUploading}
              className="rounded-control border-hairline text-secondary hover:text-primary border px-3 py-1.5 text-xs font-medium disabled:opacity-50"
            >
              {avatarUploading ? "Uploading…" : "Change photo"}
            </button>
            {avatarError && <p className="mt-1 text-xs text-red-500">{avatarError}</p>}
          </div>
          <input
            ref={fileInputRef}
            type="file"
            accept="image/jpeg,image/png,image/webp"
            className="hidden"
            onChange={handleAvatarChange}
          />
        </div>
      </div>

      {/* Display name */}
      <div>
        <label
          htmlFor="display-name"
          className="text-tertiary mb-1.5 block text-xs font-medium tracking-widest uppercase"
        >
          Display name
        </label>
        <input
          id="display-name"
          type="text"
          value={displayName}
          onChange={(e) => setDisplayName(e.target.value)}
          maxLength={50}
          className="rounded-control border-hairline bg-control text-primary placeholder:text-tertiary w-full border px-3 py-2 text-sm"
        />
      </div>

      {/* Username */}
      <div>
        <label
          htmlFor="username"
          className="text-tertiary mb-1.5 block text-xs font-medium tracking-widest uppercase"
        >
          Username
        </label>
        <input
          id="username"
          type="text"
          value={username}
          onChange={(e) => handleUsernameChange(e.target.value)}
          autoCapitalize="none"
          spellCheck={false}
          maxLength={30}
          className="rounded-control border-hairline bg-control text-primary placeholder:text-tertiary w-full border px-3 py-2 text-sm"
        />
        <div className="mt-1 min-h-[1.25rem] text-xs">
          {availability.kind === "invalid" && (
            <span role="alert" style={{ color: "#f87171" }}>
              Letters, numbers, _ and - only · 3–30 characters.
            </span>
          )}
          {availability.kind === "taken" && (
            <span role="alert" style={{ color: "#f87171" }}>
              That username is taken.
            </span>
          )}
          {availability.kind === "available" && <span className="text-accent">Available.</span>}
          {availability.kind === "checking" && <span className="text-tertiary">Checking…</span>}
        </div>
      </div>

      {/* Bio */}
      <div>
        <label
          htmlFor="bio"
          className="text-tertiary mb-1.5 block text-xs font-medium tracking-widest uppercase"
        >
          Bio
        </label>
        <textarea
          id="bio"
          value={bio}
          onChange={(e) => setBio(e.target.value)}
          maxLength={280}
          rows={3}
          placeholder="A few words about your taste…"
          className="rounded-control border-hairline bg-control text-primary placeholder:text-tertiary w-full resize-none border px-3 py-2 text-sm"
        />
        <p className="text-tertiary mt-1 text-right text-xs">{bio.length}/280</p>
      </div>

      {/* Visibility controls */}
      <div className="space-y-3">
        <p className="text-tertiary text-xs font-medium tracking-widest uppercase">Visibility</p>

        {(
          [
            { field: "bio", label: "Bio", value: visibilityBio, setter: setVisibilityBio },
            {
              field: "activity",
              label: "Listening activity",
              value: visibilityActivity,
              setter: setVisibilityActivity,
            },
            {
              field: "ratings",
              label: "Ratings & reviews",
              value: visibilityRatings,
              setter: setVisibilityRatings,
            },
            {
              field: "follows",
              label: "Follower / following lists",
              value: visibilityFollows,
              setter: setVisibilityFollows,
            },
          ] as const
        ).map(({ field, label, value, setter }) => (
          <div key={field} className="flex items-center justify-between gap-4">
            <label htmlFor={`vis-${field}`} className="text-secondary text-sm">
              {label}
            </label>
            <VisibilitySelect id={`vis-${field}`} value={value} onChange={setter} />
          </div>
        ))}

        <p className="text-tertiary text-xs">Friends means people you both follow.</p>
      </div>

      {/* Connected accounts */}
      <div>
        <p className="text-tertiary mb-3 text-xs font-medium tracking-widest uppercase">
          Connected accounts
        </p>
        {spotify?.connected ? (
          <div className="flex items-center justify-between gap-4">
            <p className="text-secondary text-sm">
              Spotify — connected as <span className="text-primary">{spotify.spotify_user_id}</span>
              {spotify.connected_at && (
                <span className="text-tertiary">
                  {" "}
                  · since{" "}
                  {new Date(spotify.connected_at).toLocaleDateString(undefined, {
                    month: "short",
                    day: "numeric",
                    year: "numeric",
                  })}
                </span>
              )}
            </p>
            <button
              type="button"
              onClick={handleSpotifyDisconnect}
              disabled={spotifyBusy}
              className="rounded-control border-hairline text-secondary hover:text-primary border px-3 py-1.5 text-xs font-medium disabled:opacity-50"
            >
              {spotifyBusy ? "Working…" : "Disconnect"}
            </button>
          </div>
        ) : (
          <div className="flex items-center justify-between gap-4">
            <p className="text-secondary text-sm">Spotify</p>
            <button
              type="button"
              onClick={handleSpotifyConnect}
              disabled={spotifyBusy}
              className="rounded-control border-hairline text-secondary hover:text-primary border px-3 py-1.5 text-xs font-medium disabled:opacity-50"
            >
              {spotifyBusy ? "Working…" : "Connect Spotify"}
            </button>
          </div>
        )}
        <p className="text-tertiary mt-2 text-xs">
          Listening activity is shown on your profile according to your Listening activity
          visibility setting.
        </p>
        {spotifyJustConnected && spotify?.connected && (
          <p role="status" className="mt-1 text-xs" style={{ color: "#4ade80" }}>
            Spotify connected.
          </p>
        )}
        {spotifyError && (
          <p role="alert" className="mt-1 text-xs" style={{ color: "#f87171" }}>
            {spotifyError}
          </p>
        )}
      </div>

      {/* Save / Cancel */}
      {saveError && (
        <p role="alert" className="text-sm text-red-500">
          {saveError}
        </p>
      )}

      <div className="flex items-center gap-4">
        <button
          type="submit"
          disabled={!canSave}
          className="rounded-control bg-primary text-canvas px-5 py-2 text-sm font-medium transition-opacity hover:opacity-80 disabled:cursor-not-allowed disabled:opacity-40"
        >
          {saving ? "Saving…" : "Save changes"}
        </button>
        <button
          type="button"
          onClick={onCancel}
          className="text-tertiary hover:text-secondary text-sm"
        >
          Cancel
        </button>
      </div>
    </form>
  );
}
