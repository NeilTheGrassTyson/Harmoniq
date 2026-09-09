"use client";

import { useAuth } from "@clerk/nextjs";
import { useMutation } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useState } from "react";
import MelodyCard from "@/components/MelodyCard";
import { getInbox, respondToMelody, reactToMelody, REACTION_LABELS } from "@/lib/melodies";
import type { MelodyInboxItem, MelodyRespondAction, MelodyReaction } from "@/types";
import { friendlyError } from "@/lib/apiBase";

interface MelodyInboxProps {
  initialItems: MelodyInboxItem[];
  initialCursor: string | null;
  reactionsEnabled?: boolean;
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
  if (item.reaction) return `Your reaction: ${REACTION_LABELS[item.reaction]}`;
  switch (item.status) {
    case "accepted":
      return "You took this one.";
    case "opened":
      return "You opened this track.";
    case "rejected":
      return "You passed on this.";
    default:
      return undefined;
  }
}

export default function MelodyInbox({
  initialItems,
  initialCursor,
  reactionsEnabled = false,
}: MelodyInboxProps) {
  const { getToken } = useAuth();
  const router = useRouter();
  const [items, setItems] = useState(initialItems);
  const [cursor, setCursor] = useState(initialCursor);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const respondMutation = useMutation({
    mutationFn: async ({
      item,
      action,
    }: {
      item: MelodyInboxItem;
      action: MelodyRespondAction;
    }) => {
      const token = await getToken();
      if (!token) throw new Error("Not signed in.");
      return { updated: await respondToMelody(token, item.id, action), action };
    },
    onSuccess: ({ updated, action }) => {
      setItems((prev) => prev.map((m) => (m.id === updated.id ? updated : m)));
      router.refresh();
      if (action === "open") {
        router.push(`/track/${updated.track.mbid}`);
      }
    },
    onError: (err) => {
      setError(friendlyError(err, "Something went wrong. Try again."));
    },
    onSettled: () => setBusyId(null),
  });

  const respond = (item: MelodyInboxItem, action: MelodyRespondAction) => {
    if (busyId) return;
    if (action === "open" && item.status === "opened") {
      router.push(`/track/${item.track.mbid}`);
      return;
    }
    setBusyId(item.id);
    setError(null);
    respondMutation.mutate({ item, action });
  };

  const reactionMutation = useMutation({
    mutationFn: async ({ item, reaction }: { item: MelodyInboxItem; reaction: MelodyReaction }) => {
      const token = await getToken();
      if (!token) throw new Error("Not signed in.");
      return reactToMelody(token, item.id, reaction);
    },
    onSuccess: (updated) => {
      setItems((prev) => prev.map((item) => (item.id === updated.id ? updated : item)));
      router.refresh();
    },
    onError: () => setError("Couldn't confirm your reaction. Try again."),
    onSettled: () => setBusyId(null),
    retry: false,
  });

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
      {reactionsEnabled && (
        <p className="text-tertiary text-xs">
          Tell the sender how the song landed. Positive responses can contribute to their Harmony
          summary. Your individual reaction stays between you and the sender.
        </p>
      )}
      {error && (
        <p className="text-destructive text-[13px]" role="alert">
          {error}
        </p>
      )}
      {items.map((item) => {
        const responded = item.status === "accepted" || item.status === "opened";
        const busy = busyId !== null;
        return (
          <MelodyCard
            key={item.id}
            track={item.track}
            person={item.sender}
            direction="from"
            statusLabel={statusLabel(item)}
            feedback={
              reactionsEnabled ? (
                <fieldset disabled={busy} className="min-w-0">
                  <legend className="text-tertiary mb-2 text-xs">
                    Your reaction to {item.track.title}
                  </legend>
                  <div className="flex flex-wrap gap-2">
                    {(Object.keys(REACTION_LABELS) as MelodyReaction[]).map((reaction) => (
                      <button
                        key={reaction}
                        type="button"
                        aria-pressed={item.reaction === reaction}
                        disabled={busy || item.reaction === reaction}
                        className={`rounded-control border px-3 py-2 text-xs disabled:opacity-60 ${item.reaction === reaction ? "border-accent text-primary" : "border-hairline text-secondary hover:text-primary"}`}
                        onClick={() => {
                          if (busyId) return;
                          setBusyId(item.id);
                          setError(null);
                          reactionMutation.mutate({ item, reaction });
                        }}
                      >
                        {REACTION_LABELS[reaction]}
                      </button>
                    ))}
                  </div>
                </fieldset>
              ) : undefined
            }
            actions={
              reactionsEnabled ? (
                <ActionButton
                  label="Listen"
                  emphasis
                  disabled={busy}
                  onClick={() => respond(item, "open")}
                />
              ) : !responded ? (
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
