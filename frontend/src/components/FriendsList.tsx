"use client";

import Link from "next/link";
import { useAuth } from "@clerk/nextjs";
import { useMutation } from "@tanstack/react-query";
import { useState } from "react";
import AvatarImage from "@/components/AvatarImage";
import FollowButton from "@/components/FollowButton";
import { acceptFriendRequest, declineFriendRequest, removeFriend } from "@/lib/friends";
import { friendlyError } from "@/lib/apiBase";
import type { FriendPerson, FriendsOverview } from "@/types";

type Action = "accept" | "decline" | "remove";

const quiet =
  "rounded-control border-hairline text-secondary hover:text-primary border px-3 py-1.5 text-xs font-medium disabled:opacity-50";

function byName(a: FriendPerson, b: FriendPerson) {
  return a.display_name.localeCompare(b.display_name) || a.username.localeCompare(b.username);
}

function Person({ person, children }: { person: FriendPerson; children: React.ReactNode }) {
  return (
    <li className="border-hairline flex flex-wrap items-center gap-3 border-b py-3 last:border-b-0">
      <Link href={`/u/${person.username}`} className="flex min-w-0 flex-1 items-center gap-3">
        <AvatarImage src={person.avatar_url} username={person.username} size={36} />
        <span className="min-w-0">
          <span className="text-primary block truncate text-sm font-medium">
            {person.display_name}
          </span>
          <span className="text-tertiary block truncate text-xs">@{person.username}</span>
        </span>
      </Link>
      <div className="flex flex-wrap items-center gap-2">{children}</div>
    </li>
  );
}

/**
 * Owner-only lists. Friendship never creates a follow, so wherever the owner
 * doesn't follow someone a Follow control sits beside them — the one-tap
 * follow-back (Founder decision 2026-09-27). There is deliberately no list of
 * requests the owner has sent.
 */
export default function FriendsList({ initial }: { initial: FriendsOverview }) {
  const { getToken } = useAuth();
  const [friends, setFriends] = useState(initial.friends);
  const [incoming, setIncoming] = useState(initial.incoming);
  const [removing, setRemoving] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const mutation = useMutation({
    mutationFn: async ({ person, action }: { person: FriendPerson; action: Action }) => {
      const token = await getToken().catch(() => null);
      if (!token) throw new Error("Not signed in.");
      const call = {
        accept: acceptFriendRequest,
        decline: declineFriendRequest,
        remove: removeFriend,
      }[action];
      await call(token, person.username);
    },
    onMutate: () => setError(null),
    onSuccess: (_result, { person, action }) => {
      if (action === "accept") {
        setIncoming((list) => list.filter((p) => p.id !== person.id));
        setFriends((list) => [...list, person].sort(byName));
      } else if (action === "decline") {
        setIncoming((list) => list.filter((p) => p.id !== person.id));
      } else {
        setFriends((list) => list.filter((p) => p.id !== person.id));
        setRemoving(null);
      }
    },
    onError: (err) => setError(friendlyError(err, "Something went wrong. Try again.")),
  });
  const busy = mutation.isPending;
  const act = (person: FriendPerson, action: Action) => mutation.mutate({ person, action });

  const followBack = (person: FriendPerson) =>
    !person.you_follow && <FollowButton username={person.username} initialIsFollowing={false} />;

  return (
    <div className="flex flex-col gap-8">
      {error && (
        <p role="alert" className="text-destructive text-xs">
          {error}
        </p>
      )}

      {incoming.length > 0 && (
        <section aria-labelledby="friends-incoming">
          <h2
            id="friends-incoming"
            className="font-display text-tertiary mb-2 text-xs font-medium tracking-wide uppercase"
          >
            Requests
          </h2>
          <ul>
            {incoming.map((person) => (
              <Person key={person.id} person={person}>
                <button className={quiet} disabled={busy} onClick={() => act(person, "accept")}>
                  Accept
                </button>
                <button className={quiet} disabled={busy} onClick={() => act(person, "decline")}>
                  Not now
                </button>
                {followBack(person)}
              </Person>
            ))}
          </ul>
        </section>
      )}

      <section aria-labelledby="friends-all">
        <h2
          id="friends-all"
          className="font-display text-tertiary mb-2 text-xs font-medium tracking-wide uppercase"
        >
          Friends
        </h2>
        {friends.length === 0 ? (
          <p className="text-tertiary text-sm">
            No friends yet. Add someone from their profile when you trust their taste.
          </p>
        ) : (
          <ul>
            {friends.map((person) => (
              <Person key={person.id} person={person}>
                {followBack(person)}
                {removing === person.id ? (
                  <>
                    <span className="text-secondary text-xs">Remove from friends?</span>
                    <button className={quiet} disabled={busy} onClick={() => act(person, "remove")}>
                      Remove
                    </button>
                    <button className={quiet} disabled={busy} onClick={() => setRemoving(null)}>
                      Keep
                    </button>
                  </>
                ) : (
                  <button
                    className={quiet}
                    aria-label={`Remove ${person.display_name} from friends`}
                    onClick={() => setRemoving(person.id)}
                  >
                    Remove
                  </button>
                )}
              </Person>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
