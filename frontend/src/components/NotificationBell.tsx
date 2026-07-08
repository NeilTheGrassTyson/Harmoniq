"use client";

import { useAuth } from "@clerk/nextjs";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import CoverArt from "@/components/CoverArt";
import {
  getNotifications,
  getUnreadCount,
  markAllNotificationsRead,
  markNotificationRead,
} from "@/lib/notifications";
import type { NotificationItem } from "@/types";

const POLL_INTERVAL_MS = 60_000; // calm, not real-time — by design

function IconBell({ size = 18 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path
        d="M18 8a6 6 0 0 0-12 0c0 7-3 9-3 9h18s-3-2-3-9"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <path
        d="M13.73 21a2 2 0 0 1-3.46 0"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
      />
    </svg>
  );
}

function timeAgo(iso: string): string {
  const seconds = Math.floor((Date.now() - new Date(iso).getTime()) / 1000);
  if (seconds < 60) return "just now";
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  return `${Math.floor(hours / 24)}d ago`;
}

export default function NotificationBell() {
  const { getToken, isSignedIn } = useAuth();
  const router = useRouter();
  const [unread, setUnread] = useState(0);
  const [open, setOpen] = useState(false);
  const [items, setItems] = useState<NotificationItem[] | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  const refreshCount = useCallback(async () => {
    try {
      const token = await getToken();
      if (!token) return;
      const { count } = await getUnreadCount(token);
      setUnread(count);
    } catch {
      // Quietly skip — the bell must never surface an error state.
    }
  }, [getToken]);

  useEffect(() => {
    if (!isSignedIn) return;
    // Initial fetch is deferred a tick so no state update fires synchronously
    // inside the effect body (react-hooks/set-state-in-effect; same pattern
    // as AppShell's collapse check).
    const initial = setTimeout(() => void refreshCount(), 0);
    const interval = setInterval(() => void refreshCount(), POLL_INTERVAL_MS);
    return () => {
      clearTimeout(initial);
      clearInterval(interval);
    };
  }, [isSignedIn, refreshCount]);

  // Close on outside click.
  useEffect(() => {
    if (!open) return;
    const onClick = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", onClick);
    return () => document.removeEventListener("mousedown", onClick);
  }, [open]);

  if (!isSignedIn) return null;

  const toggle = async () => {
    const next = !open;
    setOpen(next);
    if (next) {
      try {
        const token = await getToken();
        if (!token) return;
        const page = await getNotifications(token);
        setItems(page.items);
      } catch {
        setItems([]);
      }
    }
  };

  const handleItemClick = async (item: NotificationItem) => {
    setOpen(false);
    setItems((prev) =>
      prev ? prev.map((n) => (n.id === item.id ? { ...n, read: true } : n)) : prev
    );
    if (!item.read) {
      setUnread((c) => Math.max(0, c - 1));
      try {
        const token = await getToken();
        if (token) await markNotificationRead(token, item.id);
      } catch {
        // Non-fatal; the row re-appears unread next fetch.
      }
    }
    router.push(item.type === "melody_received" ? "/melodies" : `/u/${item.actor.username}`);
  };

  const handleMarkAll = async () => {
    setUnread(0);
    setItems((prev) => (prev ? prev.map((n) => ({ ...n, read: true })) : prev));
    try {
      const token = await getToken();
      if (token) await markAllNotificationsRead(token);
    } catch {
      // Non-fatal.
    }
  };

  return (
    <div ref={containerRef} style={{ position: "relative" }}>
      <button
        onClick={() => void toggle()}
        aria-label={unread > 0 ? "Notifications — new activity" : "Notifications"}
        aria-expanded={open}
        className="rounded-nav text-secondary hover:text-primary flex items-center justify-center"
        style={{ width: 30, height: 30, position: "relative" }}
        data-testid="notification-bell"
      >
        <IconBell size={17} />
        {unread > 0 && (
          <span
            data-testid="unread-dot"
            aria-hidden="true"
            style={{
              position: "absolute",
              top: 5,
              right: 6,
              width: 6,
              height: 6,
              borderRadius: "50%",
              background: "#2f8cff",
            }}
          />
        )}
      </button>

      {open && (
        <div
          className="border-hairline border"
          role="region"
          aria-label="Notifications"
          style={{
            position: "absolute",
            right: 0,
            top: 38,
            width: 340,
            maxHeight: 420,
            overflowY: "auto",
            borderRadius: 14,
            background: "#0e1015",
            boxShadow: "0 8px 24px rgba(0,0,0,0.5)",
            zIndex: 50,
          }}
        >
          {items === null ? (
            <p className="text-tertiary" style={{ fontSize: 13, padding: 16 }}>
              Loading…
            </p>
          ) : items.length === 0 ? (
            <p className="text-tertiary" style={{ fontSize: 13, padding: 16 }}>
              Nothing new. When someone sends you a Melody or follows you, it shows here.
            </p>
          ) : (
            <>
              <ul style={{ padding: 6 }}>
                {items.map((item) => (
                  <li key={item.id}>
                    <button
                      onClick={() => void handleItemClick(item)}
                      className="rounded-nav flex w-full items-center text-left"
                      style={{
                        gap: 10,
                        padding: "10px 10px",
                        background: "transparent",
                        opacity: item.read ? 0.55 : 1,
                      }}
                      onMouseEnter={(e) => {
                        e.currentTarget.style.background = "rgba(255,255,255,0.04)";
                      }}
                      onMouseLeave={(e) => {
                        e.currentTarget.style.background = "transparent";
                      }}
                    >
                      {item.type === "melody_received" && item.melody ? (
                        <CoverArt
                          src={item.melody.track.cover_art_url}
                          alt={item.melody.track.title}
                          size={36}
                        />
                      ) : (
                        <span
                          className="bg-tile flex shrink-0 items-center justify-center rounded-full"
                          style={{ width: 36, height: 36, fontSize: 13 }}
                        >
                          {item.actor.display_name.slice(0, 1).toUpperCase()}
                        </span>
                      )}
                      <span className="min-w-0 flex-1">
                        <span className="text-primary block truncate" style={{ fontSize: 13 }}>
                          {item.type === "melody_received" && item.melody ? (
                            <>
                              {item.actor.display_name} sent you a Melody —{" "}
                              <em>{item.melody.track.title}</em>
                            </>
                          ) : (
                            <>{item.actor.display_name} followed you</>
                          )}
                        </span>
                        <span
                          className="text-tertiary block"
                          style={{ fontSize: 11, marginTop: 2 }}
                        >
                          {timeAgo(item.created_at)}
                        </span>
                      </span>
                    </button>
                  </li>
                ))}
              </ul>
              <div
                className="border-hairline flex items-center justify-between border-t"
                style={{ padding: "8px 12px" }}
              >
                <Link
                  href="/melodies"
                  onClick={() => setOpen(false)}
                  className="text-tertiary hover:text-secondary"
                  style={{ fontSize: 12 }}
                >
                  Open Melodies
                </Link>
                <button
                  onClick={() => void handleMarkAll()}
                  className="text-tertiary hover:text-secondary"
                  style={{ fontSize: 12 }}
                >
                  Mark all read
                </button>
              </div>
            </>
          )}
        </div>
      )}
    </div>
  );
}
