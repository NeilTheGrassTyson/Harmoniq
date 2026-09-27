"use client";

import Link from "next/link";
import { useAuth } from "@clerk/nextjs";
import { useQuery } from "@tanstack/react-query";
import AvatarImage from "@/components/AvatarImage";
import EqualizerGlyph from "@/components/EqualizerGlyph";
import { getFriendsPresence } from "@/lib/presence";
import type { FriendPresence, FriendsPresenceResponse, PresenceState } from "@/types";

const POLL_MS = 30_000;

const GROUPS: { state: PresenceState; label: string }[] = [
  { state: "listening", label: "Listening now" },
  { state: "online", label: "Online" },
  { state: "offline", label: "Offline" },
  // Online status Private: shown with nothing about being online, not as
  // Offline (Founder, 2026-09-27). The label names the relationship only.
  { state: null, label: "Friends" },
];

/**
 * The people you mutually follow, and what the ones who share it are up to
 * (docs/specs/beta-ui-phase-5-presence.md). Every consent decision is made by
 * the server; this renders the groups in the order it sends them. Rows are
 * people — a track is only ever a subtitle — and nothing is sorted by any
 * measure of a person.
 */
export default function FriendsRail({
  initial = null,
}: {
  /** Server-rendered first read, so the rail paints with people in it. */
  initial?: FriendsPresenceResponse | null;
}) {
  const { getToken, isSignedIn } = useAuth();
  const { data, isError } = useQuery({
    queryKey: ["presence", "friends"],
    queryFn: async () => {
      const token = await getToken();
      if (!token) throw new Error("Not signed in.");
      return getFriendsPresence(token);
    },
    enabled: Boolean(isSignedIn),
    initialData: initial ?? undefined,
    // The server just read it; the first refresh belongs to the interval.
    refetchOnMount: initial === null,
    staleTime: POLL_MS,
    refetchInterval: POLL_MS,
    refetchIntervalInBackground: false,
    refetchOnWindowFocus: true,
    retry: false,
  });

  return (
    <aside
      aria-label="Friends"
      className="bg-sidebar border-hairline hidden w-[280px] shrink-0 border-l px-3.5 py-5 lg:block"
      data-testid="friends-rail"
    >
      {!data ? (
        isError && (
          <p className="text-tertiary px-2 text-[12px]">
            Couldn&apos;t load your friends right now.
          </p>
        )
      ) : data.friends.length === 0 ? (
        <p className="text-tertiary px-2 text-[12px]">
          When you and someone follow each other, they&apos;ll show up here.
        </p>
      ) : (
        GROUPS.map(({ state, label }) => {
          const people = data.friends.filter((f) => f.state === state);
          if (people.length === 0) return null;
          const headingId = `friends-rail-${state ?? "friends"}`;
          return (
            <section key={label} aria-labelledby={headingId} className="mb-6">
              <div className="mb-3 flex items-center justify-between px-2">
                <h2
                  id={headingId}
                  className="font-label text-tertiary text-[10.5px] font-bold tracking-[1.1px] uppercase"
                >
                  {label}
                </h2>
                <span
                  className={`font-label text-[10.5px] ${
                    state === "listening" ? "text-accent" : "text-tertiary"
                  }`}
                >
                  {people.length}
                </span>
              </div>
              <ul className="flex flex-col gap-0.5">
                {people.map((friend) => (
                  <FriendRow key={friend.username} friend={friend} />
                ))}
              </ul>
            </section>
          );
        })
      )}
    </aside>
  );
}

function FriendRow({ friend }: { friend: FriendPresence }) {
  return (
    <li className="group rounded-nav hover:bg-nav-hover focus-within:bg-nav-hover flex items-center gap-2.5 px-2 py-1.5">
      <Link href={`/u/${friend.username}`} className="flex min-w-0 flex-1 items-center gap-2.5">
        <AvatarImage src={friend.avatar_url} username={friend.username} size={28} />
        <span className="min-w-0 flex-1">
          <span className="text-primary block truncate text-[13px]">{friend.display_name}</span>
          {friend.track && (
            <span className="text-tertiary block truncate text-[11.5px]">
              {friend.track.title} — {friend.track.artist_name}
            </span>
          )}
        </span>
      </Link>
      {friend.state === "listening" && (
        <EqualizerGlyph
          size={12}
          animated
          className="text-accent shrink-0 group-focus-within:hidden group-hover:hidden"
        />
      )}
      {/* The one action on this surface. Revealed on hover, and on keyboard
          focus — opacity rather than display, so it stays reachable by Tab. */}
      <Link
        href={`/search?to=${encodeURIComponent(friend.username)}`}
        aria-label={`Send ${friend.display_name} a Melody`}
        className="font-label bg-accent text-canvas shrink-0 rounded-[5px] px-[7px] py-1 text-[10px] font-bold uppercase opacity-0 group-focus-within:opacity-100 group-hover:opacity-100"
      >
        Send
      </Link>
    </li>
  );
}

/** Same footprint as the rail, empty — shown while the server read streams in. */
export function FriendsRailPlaceholder() {
  return (
    <aside
      aria-hidden="true"
      className="bg-sidebar border-hairline hidden w-[280px] shrink-0 border-l lg:block"
    />
  );
}
