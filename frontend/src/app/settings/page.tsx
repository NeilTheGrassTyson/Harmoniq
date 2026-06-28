"use client";

import AppShell from "@/components/AppShell";
import { useAuth } from "@clerk/nextjs";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import AvatarImage from "@/components/AvatarImage";
import VisibilitySelect from "@/components/VisibilitySelect";
import { checkUsernameAvailable, getOwnProfile, updateProfile, uploadAvatar } from "@/lib/users";
import type { OwnProfileResponse, VisibilityScope } from "@/types";

const USERNAME_RE = /^[a-zA-Z0-9_-]{3,30}$/;

type AvailabilityState =
  | { kind: "idle" }
  | { kind: "checking" }
  | { kind: "available" }
  | { kind: "taken" }
  | { kind: "invalid" }
  | { kind: "unchanged" };

export default function SettingsPage() {
  const { getToken } = useAuth();
  const router = useRouter();

  const [loading, setLoading] = useState(true);
  const [profile, setProfile] = useState<OwnProfileResponse | null>(null);

  // Form state
  const [displayName, setDisplayName] = useState("");
  const [username, setUsername] = useState("");
  const [bio, setBio] = useState("");
  const [visibilityBio, setVisibilityBio] = useState<VisibilityScope>("private");
  const [visibilityActivity, setVisibilityActivity] = useState<VisibilityScope>("private");
  const [visibilityRatings, setVisibilityRatings] = useState<VisibilityScope>("private");

  const [availability, setAvailability] = useState<AvailabilityState>({ kind: "idle" });
  const [saveError, setSaveError] = useState<string | null>(null);
  const [saveSuccess, setSaveSuccess] = useState(false);
  const [saving, setSaving] = useState(false);

  const [avatarUploading, setAvatarUploading] = useState(false);
  const [avatarError, setAvatarError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [originalUsername, setOriginalUsername] = useState("");
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Load profile
  useEffect(() => {
    getToken()
      .then(async (token) => {
        if (!token) return;
        const data = await getOwnProfile(token);
        setProfile(data);
        setDisplayName(data.display_name);
        setUsername(data.username);
        setBio(data.bio ?? "");
        setVisibilityBio(data.visibility_bio);
        setVisibilityActivity(data.visibility_activity);
        setVisibilityRatings(data.visibility_ratings);
        setOriginalUsername(data.username);
      })
      .catch(() => setSaveError("Couldn't load your profile."))
      .finally(() => setLoading(false));
  }, [getToken]);

  const handleUsernameChange = useCallback(
    (value: string) => {
      setUsername(value);
      setSaveError(null);
      setSaveSuccess(false);

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
      setProfile((prev) => (prev ? { ...prev, avatar_url: result.avatar_url } : prev));
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
    setSaveSuccess(false);

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
      });
      setProfile(updated);
      setOriginalUsername(updated.username);
      setUsername(updated.username);
      setSaveSuccess(true);
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
      <AppShell>
        <main className="mx-auto max-w-2xl px-4 py-10">
          <div className="animate-pulse space-y-4">
            <div className="h-20 w-20 rounded-full bg-tile" /* unslop-ignore — avatar skeleton, circular per DESIGN_SYSTEM §4 */ />
            <div className="h-4 w-48 rounded bg-tile" />
            <div className="h-4 w-32 rounded bg-tile" />
          </div>
        </main>
      </AppShell>
    );
  }

  if (!profile) return null;

  const canSave =
    !saving &&
    displayName.trim().length > 0 &&
    USERNAME_RE.test(username) &&
    (username === originalUsername || availability.kind === "available");

  return (
    <AppShell>
    <main className="mx-auto max-w-2xl px-4 py-10">
      <h1 className="mb-8 text-2xl font-light tracking-tight text-primary">Settings</h1>

      <form onSubmit={handleSave} className="space-y-8">
        {/* Avatar */}
        <div>
          <p className="mb-3 text-xs font-medium tracking-widest text-tertiary uppercase">
            Avatar
          </p>
          <div className="flex items-center gap-4">
            <AvatarImage src={profile.avatar_url} username={profile.username} size={64} />
            <div>
              <button
                type="button"
                onClick={handleAvatarClick}
                disabled={avatarUploading}
                className="rounded-control border border-hairline px-3 py-1.5 text-xs font-medium text-secondary hover:text-primary disabled:opacity-50"
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
            className="mb-1.5 block text-xs font-medium tracking-widest text-tertiary uppercase"
          >
            Display name
          </label>
          <input
            id="display-name"
            type="text"
            value={displayName}
            onChange={(e) => {
              setDisplayName(e.target.value);
              setSaveSuccess(false);
            }}
            maxLength={50}
            className="w-full rounded-control border border-hairline bg-control px-3 py-2 text-sm text-primary placeholder:text-tertiary"
          />
        </div>

        {/* Username */}
        <div>
          <label
            htmlFor="username"
            className="mb-1.5 block text-xs font-medium tracking-widest text-tertiary uppercase"
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
            className="w-full rounded-control border border-hairline bg-control px-3 py-2 text-sm text-primary placeholder:text-tertiary"
          />
          <div className="mt-1 min-h-[1.25rem] text-xs">
            {availability.kind === "invalid" && (
              <span role="alert" style={{ color: "#f87171" }}>
                Letters, numbers, _ and - only · 3–30 characters.
              </span>
            )}
            {availability.kind === "taken" && (
              <span role="alert" style={{ color: "#f87171" }}>That username is taken.</span>
            )}
            {availability.kind === "available" && (
              <span className="text-accent">Available.</span>
            )}
            {availability.kind === "checking" && (
              <span className="text-tertiary">Checking…</span>
            )}
          </div>
        </div>

        {/* Bio */}
        <div>
          <label
            htmlFor="bio"
            className="mb-1.5 block text-xs font-medium tracking-widest text-tertiary uppercase"
          >
            Bio
          </label>
          <textarea
            id="bio"
            value={bio}
            onChange={(e) => {
              setBio(e.target.value);
              setSaveSuccess(false);
            }}
            maxLength={280}
            rows={3}
            placeholder="A few words about your taste…"
            className="w-full resize-none rounded-control border border-hairline bg-control px-3 py-2 text-sm text-primary placeholder:text-tertiary"
          />
          <p className="mt-1 text-right text-xs text-tertiary">{bio.length}/280</p>
        </div>

        {/* Visibility controls */}
        <div className="space-y-3">
          <p className="text-xs font-medium tracking-widest text-tertiary uppercase">
            Visibility
          </p>

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
                label: "Ratings count",
                value: visibilityRatings,
                setter: setVisibilityRatings,
              },
            ] as const
          ).map(({ field, label, value, setter }) => (
            <div key={field} className="flex items-center justify-between gap-4">
              <label
                htmlFor={`vis-${field}`}
                className="text-sm text-secondary"
              >
                {label}
              </label>
              <VisibilitySelect
                id={`vis-${field}`}
                value={value}
                onChange={(v) => {
                  setter(v);
                  setSaveSuccess(false);
                }}
              />
            </div>
          ))}

          <p className="text-xs text-tertiary">Friends means people you both follow.</p>
        </div>

        {/* Save */}
        {saveError && <p role="alert" className="text-sm text-red-500">{saveError}</p>}
        {saveSuccess && <p role="status" className="text-sm" style={{ color: "#4ade80" }}>Saved.</p>}

        <div className="flex items-center gap-4">
          <button
            type="submit"
            disabled={!canSave}
            className="rounded-control bg-primary px-5 py-2 text-sm font-medium text-canvas transition-opacity hover:opacity-80 disabled:cursor-not-allowed disabled:opacity-40"
          >
            {saving ? "Saving…" : "Save changes"}
          </button>
          <button
            type="button"
            onClick={() => router.push(`/u/${profile.username}`)}
            className="text-sm text-tertiary hover:text-secondary"
          >
            Back to profile
          </button>
        </div>
      </form>
    </main>
    </AppShell>
  );
}
