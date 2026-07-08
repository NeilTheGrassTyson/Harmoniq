"use client";

import { useAuth } from "@clerk/nextjs";
import { useState } from "react";
import MelodyCard from "@/components/MelodyCard";
import { getSentMelodies } from "@/lib/melodies";
import type { MelodySentItem } from "@/types";

interface MelodySentListProps {
  initialItems: MelodySentItem[];
  initialCursor: string | null;
}

/** Sender-visible outcomes. "Passed" is visible to the sender only. */
const SENT_LABELS: Record<string, string> = {
  sent: "Sent",
  accepted: "Taken",
  opened: "Listened",
  rejected: "Passed",
};

export default function MelodySentList({
  initialItems,
  initialCursor,
}: MelodySentListProps) {
  const { getToken } = useAuth();
  const [items, setItems] = useState(initialItems);
  const [cursor, setCursor] = useState(initialCursor);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadMore = async () => {
    if (!cursor || loadingMore) return;
    setLoadingMore(true);
    try {
      const token = await getToken();
      if (!token) throw new Error("Not signed in.");
      const page = await getSentMelodies(token, cursor);
      setItems((prev) => [...prev, ...page.items]);
      setCursor(page.next_cursor);
    } catch {
      setError("Couldn't load more. Try again.");
    } finally {
      setLoadingMore(false);
    }
  };

  if (items.length === 0) {
    return (
      <p className="text-tertiary" style={{ fontSize: 13, padding: "24px 0" }}>
        Nothing sent yet. Find a track and send someone a Melody.
      </p>
    );
  }

  return (
    <div className="flex flex-col" style={{ gap: 10, paddingTop: 16 }}>
      {error && (
        <p style={{ color: "#f87171", fontSize: 13 }} role="alert">
          {error}
        </p>
      )}
      {items.map((item) => (
        <MelodyCard
          key={item.id}
          track={item.track}
          person={item.recipient}
          direction="to"
          statusLabel={SENT_LABELS[item.status] ?? item.status}
        />
      ))}
      {cursor && (
        <button
          onClick={() => void loadMore()}
          disabled={loadingMore}
          className="text-tertiary hover:text-secondary self-start disabled:opacity-50"
          style={{ fontSize: 13, padding: "6px 0" }}
        >
          {loadingMore ? "Loading…" : "Show more"}
        </button>
      )}
    </div>
  );
}
