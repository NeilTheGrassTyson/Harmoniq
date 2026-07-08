"use client";

import { useAuth, useUser } from "@clerk/nextjs";
import { useState } from "react";
import MelodyCard from "@/components/MelodyCard";
import { sendMelody } from "@/lib/melodies";
import type { TrackSummary } from "@/types";

interface SendMelodyPanelProps {
  track: Omit<TrackSummary, "id">;
}

/**
 * Inline expandable panel on the track page. The only input is the
 * recipient — the Melody itself is the embed card previewed below.
 */
export default function SendMelodyPanel({ track }: SendMelodyPanelProps) {
  const { getToken } = useAuth();
  const { isSignedIn } = useUser();
  const [open, setOpen] = useState(false);
  const [recipient, setRecipient] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sentTo, setSentTo] = useState<string | null>(null);

  if (!isSignedIn) return null;

  const trimmed = recipient.trim().replace(/^@/, "");

  const handleSend = async () => {
    if (!trimmed || sending) return;
    setSending(true);
    setError(null);
    try {
      const token = await getToken();
      if (!token) throw new Error("Not signed in.");
      const item = await sendMelody(token, trimmed, track.mbid);
      setSentTo(item.recipient.username);
      setRecipient("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong. Try again.");
    } finally {
      setSending(false);
    }
  };

  return (
    <section className="mt-8" data-testid="send-melody-panel">
      {!open ? (
        <button
          onClick={() => {
            setOpen(true);
            setSentTo(null);
          }}
          className="border-hairline text-secondary hover:text-primary rounded-control border"
          style={{ padding: "7px 14px", fontSize: 13 }}
        >
          Send a Melody
        </button>
      ) : (
        <div className="border-hairline rounded-control border" style={{ padding: 16 }}>
          <div className="flex items-center justify-between">
            <h2 className="text-primary" style={{ fontSize: 14, fontWeight: 500 }}>
              Send a Melody
            </h2>
            <button
              onClick={() => setOpen(false)}
              aria-label="Close"
              className="text-tertiary hover:text-secondary"
              style={{ fontSize: 13 }}
            >
              Close
            </button>
          </div>

          <div className="mt-4">
            <MelodyCard
              track={track}
              person={{
                username: trimmed || "…",
                display_name: trimmed || "someone",
                avatar_url: null,
              }}
              direction="to"
            />
          </div>

          <div className="mt-4 flex items-center" style={{ gap: 10 }}>
            <input
              type="text"
              value={recipient}
              onChange={(e) => setRecipient(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") void handleSend();
              }}
              placeholder="username"
              aria-label="Recipient username"
              className="bg-control text-primary rounded-control flex-1 border-none outline-none"
              style={{ padding: "8px 12px", fontSize: 13 }}
            />
            <button
              onClick={() => void handleSend()}
              disabled={!trimmed || sending}
              className="bg-primary text-canvas rounded-control disabled:opacity-50"
              style={{ padding: "8px 16px", fontSize: 13, fontWeight: 500 }}
            >
              {sending ? "Sending…" : "Send"}
            </button>
          </div>

          {error && (
            <p className="mt-3" style={{ color: "#f87171", fontSize: 13 }} role="alert">
              {error}
            </p>
          )}
          {sentTo && !error && (
            <p className="text-secondary mt-3" style={{ fontSize: 13 }}>
              Melody sent to @{sentTo}.
            </p>
          )}
        </div>
      )}
    </section>
  );
}
