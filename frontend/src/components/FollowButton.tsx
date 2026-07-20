"use client";

import { useAuth } from "@clerk/nextjs";
import { useMutation } from "@tanstack/react-query";
import { useState } from "react";
import { followUser, unfollowUser } from "@/lib/follows";

interface Props {
  username: string;
  initialIsFollowing: boolean;
  /** Fired after the follow state flips (optimistically) and rolled back on failure. */
  onChange?: (isFollowing: boolean) => void;
}

export default function FollowButton({ username, initialIsFollowing, onChange }: Props) {
  const { getToken } = useAuth();
  const [isFollowing, setIsFollowing] = useState(initialIsFollowing);

  const mutation = useMutation({
    mutationFn: async (next: boolean) => {
      const token = await getToken().catch(() => null);
      if (!token) throw new Error("Not signed in.");
      if (next) {
        await followUser(token, username);
      } else {
        await unfollowUser(token, username);
      }
      return next;
    },
    onMutate: (next) => {
      const previous = isFollowing;
      setIsFollowing(next);
      onChange?.(next);
      return { previous };
    },
    onError: (_err, _next, context) => {
      if (context) {
        setIsFollowing(context.previous);
        onChange?.(context.previous);
      }
    },
  });

  function handleClick() {
    if (mutation.isPending) return;
    mutation.mutate(!isFollowing);
  }

  return (
    <div>
      <button
        onClick={handleClick}
        disabled={mutation.isPending}
        className={
          isFollowing
            ? "rounded-control border-hairline text-secondary hover:text-primary border px-3 py-1.5 text-xs font-medium disabled:opacity-50"
            : "rounded-control bg-primary text-canvas px-3 py-1.5 text-xs font-medium hover:opacity-80 disabled:opacity-50"
        }
      >
        {isFollowing ? "Following" : "Follow"}
      </button>
      {mutation.isError && (
        <p role="alert" className="mt-1 text-xs" style={{ color: "#f87171" }}>
          Something went wrong. Try again.
        </p>
      )}
    </div>
  );
}
