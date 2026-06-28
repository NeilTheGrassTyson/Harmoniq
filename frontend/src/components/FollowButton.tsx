"use client";

import { useAuth } from "@clerk/nextjs";
import { useState } from "react";
import { followUser, unfollowUser } from "@/lib/follows";

interface Props {
  username: string;
  initialIsFollowing: boolean;
}

export default function FollowButton({ username, initialIsFollowing }: Props) {
  const { getToken } = useAuth();
  const [isFollowing, setIsFollowing] = useState(initialIsFollowing);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleClick() {
    if (pending) return;
    setPending(true);
    setError(null);

    const token = await getToken().catch(() => null);
    if (!token) {
      setPending(false);
      return;
    }

    const previous = isFollowing;
    // Optimistic update
    setIsFollowing(!previous);

    try {
      if (previous) {
        await unfollowUser(token, username);
      } else {
        await followUser(token, username);
      }
    } catch {
      // Roll back on failure
      setIsFollowing(previous);
      setError("Something went wrong. Try again.");
    } finally {
      setPending(false);
    }
  }

  return (
    <div>
      <button
        onClick={handleClick}
        disabled={pending}
        className={
          isFollowing
            ? "rounded-control border-hairline text-secondary hover:text-primary border px-3 py-1.5 text-xs font-medium disabled:opacity-50"
            : "rounded-control bg-primary text-canvas px-3 py-1.5 text-xs font-medium hover:opacity-80 disabled:opacity-50"
        }
      >
        {isFollowing ? "Following" : "Follow"}
      </button>
      {error && (
        <p role="alert" className="mt-1 text-xs" style={{ color: "#f87171" }}>
          {error}
        </p>
      )}
    </div>
  );
}
