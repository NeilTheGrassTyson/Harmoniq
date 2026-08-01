"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import AvatarImage from "@/components/AvatarImage";
import FollowButton from "@/components/FollowButton";
import ProfileEditPanel from "@/components/ProfileEditPanel";
import type { OwnProfileResponse, ProfileResponse } from "@/types";

interface ProfileHeaderProps {
  profile: ProfileResponse;
}

export default function ProfileHeader({ profile }: ProfileHeaderProps) {
  const router = useRouter();
  const [editOpen, setEditOpen] = useState(false);

  // Optimistic local copies so the read-view updates instantly on save,
  // without waiting on a server round-trip.
  const [displayName, setDisplayName] = useState(profile.display_name);
  const [avatarUrl, setAvatarUrl] = useState(profile.avatar_url);
  const [bio, setBio] = useState<string | null>("bio" in profile ? (profile.bio ?? null) : null);
  // Mirrors FollowButton's optimistic state so the count moves with the
  // button instead of waiting for a reload.
  const [followerCount, setFollowerCount] = useState(profile.follower_count);

  const handleSaved = (updated: OwnProfileResponse) => {
    setDisplayName(updated.display_name);
    setAvatarUrl(updated.avatar_url);
    setBio(updated.bio);
    setEditOpen(false);

    if (updated.username !== profile.username) {
      // The route segment itself is now stale — navigate to the new one.
      router.replace(`/u/${updated.username}`);
    } else {
      // Resync any other server-rendered data on the page (e.g. ratings).
      router.refresh();
    }
  };

  return (
    <>
      {/* ── Profile header ─────────────────────────────────────────────── */}
      <div style={{ display: "flex", alignItems: "flex-start", gap: 20, marginBottom: 24 }}>
        <AvatarImage src={avatarUrl} username={profile.username} size={72} />
        <div style={{ minWidth: 0, flex: 1 }}>
          <h1
            className="font-display text-primary"
            style={{ fontSize: 20, fontWeight: 500, lineHeight: 1.2 }}
          >
            {displayName}
          </h1>
          <p className="text-secondary" style={{ fontSize: 13, marginTop: 2 }}>
            @{profile.username}
          </p>

          {bio && (
            <p className="text-secondary" style={{ fontSize: 13, marginTop: 8, lineHeight: 1.5 }}>
              {bio}
            </p>
          )}
          {bio === null && profile.is_own_profile && (
            <button
              type="button"
              onClick={() => setEditOpen(true)}
              className="text-tertiary hover:text-secondary"
              style={{
                fontSize: 13,
                marginTop: 8,
                display: "block",
                background: "none",
                border: "none",
                padding: 0,
                textAlign: "left",
                cursor: "pointer",
              }}
            >
              Add a bio
            </button>
          )}

          {/* Follower / following counts */}
          <div style={{ display: "flex", gap: 16, marginTop: 12, fontSize: 13 }}>
            <Link
              href={`/u/${profile.username}/followers`}
              className="text-secondary hover:text-accent"
            >
              <span className="text-primary" style={{ fontWeight: 500 }}>
                {followerCount}
              </span>{" "}
              {followerCount === 1 ? "follower" : "followers"}
            </Link>
            <Link
              href={`/u/${profile.username}/following`}
              className="text-secondary hover:text-accent"
            >
              <span className="text-primary" style={{ fontWeight: 500 }}>
                {profile.following_count}
              </span>{" "}
              following
            </Link>
          </div>
        </div>
      </div>

      {/* ── Actions ────────────────────────────────────────────────────── */}
      <div className="mb-8">
        {profile.is_own_profile
          ? !editOpen && (
              <button
                type="button"
                onClick={() => setEditOpen(true)}
                className="text-secondary border-hairline rounded-control inline-block cursor-pointer border bg-none px-[14px] py-[5px] text-xs font-medium"
              >
                Edit profile
              </button>
            )
          : profile.follow !== undefined && (
              <FollowButton
                username={profile.username}
                initialIsFollowing={profile.follow.is_following}
                onChange={(isFollowing) => {
                  // Server count minus the viewer's original edge, plus their
                  // current one — idempotent under optimistic flips/rollbacks.
                  const base = profile.follower_count - (profile.follow?.is_following ? 1 : 0);
                  setFollowerCount(base + (isFollowing ? 1 : 0));
                }}
              />
            )}

        {profile.is_own_profile && editOpen && (
          <ProfileEditPanel
            initial={{ username: profile.username, displayName, avatarUrl }}
            onCancel={() => setEditOpen(false)}
            onSaved={handleSaved}
          />
        )}
      </div>
    </>
  );
}
