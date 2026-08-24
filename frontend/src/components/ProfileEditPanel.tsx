"use client";

import { useAuth } from "@clerk/nextjs";
import { useCallback, useEffect, useRef, useState } from "react";
import { z } from "zod";
import AvatarImage from "@/components/AvatarImage";
import VisibilitySelect from "@/components/VisibilitySelect";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { isNetworkError } from "@/lib/apiBase";
import { getOwnProfile, updateProfile, uploadAvatar } from "@/lib/users";
import { USERNAME_RE, useUsernameAvailability } from "@/lib/useUsernameAvailability";
import type { OwnProfileResponse, VisibilityScope } from "@/types";

// One schema for the editable text fields — the save gate and the input
// constraints read from the same rules instead of scattered checks.
const profileSchema = z.object({
  displayName: z.string().trim().min(1).max(50),
  username: z.string().regex(USERNAME_RE),
  bio: z.string().max(280),
});

interface ProfileEditPanelProps {
  initial: {
    username: string;
    displayName: string;
    avatarUrl: string | null;
  };
  onCancel: () => void;
  onSaved: (updated: OwnProfileResponse) => void;
}

export default function ProfileEditPanel({ initial, onCancel, onSaved }: ProfileEditPanelProps) {
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

  const [saveError, setSaveError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  const [avatarUploading, setAvatarUploading] = useState(false);
  const [avatarError, setAvatarError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [originalUsername, setOriginalUsername] = useState(initial.username);
  const { availability, check: checkUsername } = useUsernameAvailability(originalUsername);

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

  const handleUsernameChange = useCallback(
    (value: string) => {
      setUsername(value);
      setSaveError(null);
      checkUsername(value);
    },
    [checkUsername]
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

    if (!profileSchema.safeParse({ displayName, username, bio }).success) return;

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
      // A request that never reached the backend throws a raw "Load failed"
      // (Safari) or "Failed to fetch" (Chrome); neither belongs on screen.
      setSaveError(
        isNetworkError(err)
          ? "Couldn't reach Harmoniq. Your changes weren't saved — check your connection and try again."
          : (err instanceof Error && err.message) ||
              "Something went wrong. Your changes weren't saved."
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
    profileSchema.safeParse({ displayName, username, bio }).success &&
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
        <Input
          id="display-name"
          type="text"
          value={displayName}
          onChange={(e) => setDisplayName(e.target.value)}
          maxLength={50}
          className="h-auto px-3 py-2 text-sm"
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
        <Input
          id="username"
          type="text"
          value={username}
          onChange={(e) => handleUsernameChange(e.target.value)}
          autoCapitalize="none"
          spellCheck={false}
          maxLength={30}
          className="h-auto px-3 py-2 text-sm"
        />
        <div className="mt-1 min-h-[1.25rem] text-xs">
          {availability.kind === "invalid" && (
            <span role="alert" className="text-destructive">
              Letters, numbers, _ and - only · 3–30 characters.
            </span>
          )}
          {availability.kind === "taken" && (
            <span role="alert" className="text-destructive">
              That username is taken.
            </span>
          )}
          {availability.kind === "available" && <span className="text-accent">Available.</span>}
          {availability.kind === "checking" && <span className="text-tertiary">Checking…</span>}
          {availability.kind === "error" && (
            <span className="text-tertiary">Couldn&apos;t check that username. Try again.</span>
          )}
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
        <Textarea
          id="bio"
          value={bio}
          onChange={(e) => setBio(e.target.value)}
          maxLength={280}
          rows={3}
          placeholder="A few words about your taste…"
          className="min-h-0 resize-none px-3 py-2 text-sm"
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

      {/* Save / Cancel */}
      {saveError && (
        <p role="alert" className="text-sm text-red-500">
          {saveError}
        </p>
      )}

      <div className="flex items-center gap-4">
        <Button
          type="submit"
          disabled={!canSave}
          className="h-auto px-5 py-2 disabled:cursor-not-allowed disabled:opacity-40"
        >
          {saving ? "Saving…" : "Save changes"}
        </Button>
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
