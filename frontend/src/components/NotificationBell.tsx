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
    <div ref={containerRef} className="relative">
      <button
        onClick={() => void toggle()}
        aria-label={unread > 0 ? "Notifications — new activity" : "Notifications"}
        aria-expanded={open}
        className="rounded-nav text-secondary hover:text-primary relative flex size-[30px] items-center justify-center"
        data-testid="notification-bell"
      >
        <IconBell size={17} />
        {unread > 0 && (
          <span
            data-testid="unread-dot"
            aria-hidden="true"
            className="bg-accent absolute top-[5px] right-[6px] size-1.5 rounded-full"
          />
        )}
      </button>

      {open && (
        // Separation from the content beneath comes from the hairline border
        // and the sidebar surface — not a drop shadow (DESIGN_SYSTEM §8).
        <div
          className="border-hairline rounded-frame bg-sidebar absolute top-[38px] right-0 z-50 max-h-[420px] w-[340px] overflow-y-auto border"
          role="region"
          aria-label="Notifications"
        >
          {items === null ? (
            <p className="text-tertiary p-4 text-[13px]">Loading…</p>
          ) : items.length === 0 ? (
            <p className="text-tertiary p-4 text-[13px]">
              Nothing new. When someone sends you a Melody or follows you, it shows here.
            </p>
          ) : (
            <>
              <ul className="p-1.5">
                {items.map((item) => (
                  <li key={item.id}>
                    <button
                      onClick={() => void handleItemClick(item)}
                      className={`rounded-nav hover:bg-nav-hover flex w-full items-center gap-[10px] p-[10px] text-left ${
                        item.read ? "opacity-55" : ""
                      }`}
                    >
                      {item.type === "melody_received" && item.melody ? (
                        <CoverArt
                          src={item.melody.track.cover_art_url}
                          alt={item.melody.track.title}
                          size={36}
                        />
                      ) : (
                        <span className="bg-tile flex size-9 shrink-0 items-center justify-center rounded-full text-[13px]">
                          {item.actor.display_name.slice(0, 1).toUpperCase()}
                        </span>
                      )}
                      <span className="min-w-0 flex-1">
                        <span className="text-primary block truncate text-[13px]">
                          {item.type === "melody_received" && item.melody ? (
                            <>
                              {item.actor.display_name} sent you a Melody —{" "}
                              <em>{item.melody.track.title}</em>
                            </>
                          ) : (
                            <>{item.actor.display_name} followed you</>
                          )}
                        </span>
                        <span className="text-tertiary mt-0.5 block text-[11px]">
                          {timeAgo(item.created_at)}
                        </span>
                      </span>
                    </button>
                  </li>
                ))}
              </ul>
              <div className="border-hairline flex items-center justify-between border-t px-3 py-2">
                <Link
                  href="/melodies"
                  onClick={() => setOpen(false)}
                  className="text-tertiary hover:text-secondary text-xs"
                >
                  Open Melodies
                </Link>
                <button
                  onClick={() => void handleMarkAll()}
                  className="text-tertiary hover:text-secondary text-xs"
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
