"use client";

import { useAuth } from "@clerk/nextjs";
import { useMutation } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useState } from "react";
import MelodyCard from "@/components/MelodyCard";
import { getInbox, respondToMelody } from "@/lib/melodies";
import type { MelodyInboxItem, MelodyRespondAction } from "@/types";

interface MelodyInboxProps {
  initialItems: MelodyInboxItem[];
  initialCursor: string | null;
}

function ActionButton({
  label,
  onClick,
  disabled,
  emphasis = false,
}: {
  label: string;
  onClick: () => void;
  disabled?: boolean;
  emphasis?: boolean;
}) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      className={
        emphasis
          ? "bg-primary text-canvas rounded-control disabled:opacity-50"
          : "border-hairline text-secondary hover:text-primary rounded-control border disabled:opacity-50"
      }
      style={{ padding: "6px 12px", fontSize: 12, fontWeight: emphasis ? 500 : 400 }}
    >
      {label}
    </button>
  );
}

/** Socially neutral outcome copy — never "declined", never "ignored". */
function statusLabel(item: MelodyInboxItem): string | undefined {
  switch (item.status) {
    case "accepted":
      return "You took this one.";
    case "opened":
      return "You listened.";
    case "rejected":
      return "You passed on this.";
    default:
      return undefined;
  }
}

export default function MelodyInbox({ initialItems, initialCursor }: MelodyInboxProps) {
  const { getToken } = useAuth();
  const router = useRouter();
  const [items, setItems] = useState(initialItems);
  const [cursor, setCursor] = useState(initialCursor);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const respondMutation = useMutation({
    mutationFn: async ({ item, action }: { item: MelodyInboxItem; action: MelodyRespondAction }) => {
      const token = await getToken();
      if (!token) throw new Error("Not signed in.");
      return { updated: await respondToMelody(token, item.id, action), action };
    },
    onSuccess: ({ updated, action }) => {
      setItems((prev) => prev.map((m) => (m.id === updated.id ? updated : m)));
      if (action === "open") {
        router.push(`/track/${updated.track.mbid}`);
      }
    },
    onError: (err) => {
      setError(err instanceof Error ? err.message : "Something went wrong. Try again.");
    },
    onSettled: () => setBusyId(null),
  });

  const respond = (item: MelodyInboxItem, action: MelodyRespondAction) => {
    if (busyId) return;
    setBusyId(item.id);
    setError(null);
    respondMutation.mutate({ item, action });
  };

  const loadMoreMutation = useMutation({
    mutationFn: async (afterCursor: string) => {
      const token = await getToken();
      if (!token) throw new Error("Not signed in.");
      return getInbox(token, afterCursor);
    },
    onSuccess: (page) => {
      setItems((prev) => [...prev, ...page.items]);
      setCursor(page.next_cursor);
    },
    onError: () => setError("Couldn't load more. Try again."),
  });

  const loadingMore = loadMoreMutation.isPending;
  const loadMore = () => {
    if (!cursor || loadingMore) return;
    setError(null);
    loadMoreMutation.mutate(cursor);
  };

  if (items.length === 0) {
    return (
      <p className="text-tertiary" style={{ fontSize: 13, padding: "24px 0" }}>
        No Melodies yet. When someone sends you a song, it lands here.
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
      {items.map((item) => {
        const responded = item.status === "accepted" || item.status === "opened";
        const busy = busyId === item.id;
        return (
          <MelodyCard
            key={item.id}
            track={item.track}
            person={item.sender}
            direction="from"
            statusLabel={statusLabel(item)}
            actions={
              !responded ? (
                <>
                  <ActionButton
                    label="Listen"
                    emphasis
                    disabled={busy}
                    onClick={() => void respond(item, "open")}
                  />
                  <ActionButton
                    label="Take it"
                    disabled={busy}
                    onClick={() => void respond(item, "accept")}
                  />
                  {item.status !== "rejected" && (
                    <ActionButton
                      label="Not for me"
                      disabled={busy}
                      onClick={() => void respond(item, "reject")}
                    />
                  )}
                </>
              ) : undefined
            }
          />
        );
      })}
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
