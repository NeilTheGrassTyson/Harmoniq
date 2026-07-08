"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useUser } from "@clerk/nextjs";
import { useLayoutEffect, useState } from "react";
import SearchBar from "@/components/SearchBar";
import NavAuth from "@/components/NavAuth";
import NotificationBell from "@/components/NotificationBell";
import EqualizerGlyph from "@/components/EqualizerGlyph";

function IconMenu({ size = 18 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <line
        x1="4"
        x2="20"
        y1="6"
        y2="6"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
      />
      <line
        x1="4"
        x2="20"
        y1="12"
        y2="12"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
      />
      <line
        x1="4"
        x2="20"
        y1="18"
        y2="18"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
      />
    </svg>
  );
}

function IconHome({ size = 18 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path
        d="m3 9 9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <polyline
        points="9 22 9 12 15 12 15 22"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

function IconSearch({ size = 18 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <circle cx="11" cy="11" r="8" stroke="currentColor" strokeWidth="2" />
      <line
        x1="21"
        y1="21"
        x2="16.65"
        y2="16.65"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
      />
    </svg>
  );
}

function IconUser({ size = 18 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <circle cx="12" cy="8" r="4" stroke="currentColor" strokeWidth="2" />
      <path
        d="M4 20c0-4 3.6-7 8-7s8 3 8 7"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
      />
    </svg>
  );
}

function IconMelody({ size = 18 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path
        d="M9 18V5l12-2v13"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <circle cx="6" cy="18" r="3" stroke="currentColor" strokeWidth="2" />
      <circle cx="18" cy="16" r="3" stroke="currentColor" strokeWidth="2" />
    </svg>
  );
}

function IconSettings({ size = 18 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <circle cx="12" cy="12" r="3" stroke="currentColor" strokeWidth="2" />
      <path
        d="M12 2v2m0 16v2M4.93 4.93l1.41 1.41m11.32 11.32 1.41 1.41M2 12h2m16 0h2M4.93 19.07l1.41-1.41M18.36 5.64l1.41-1.41"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
      />
    </svg>
  );
}

function NavLink({
  href,
  icon,
  label,
  active,
}: {
  href: string;
  icon: React.ReactNode;
  label: string;
  active: boolean;
}) {
  return (
    <Link
      href={href}
      aria-current={active ? "page" : undefined}
      className="rounded-nav text-secondary hover:text-primary flex items-center"
      style={{
        padding: "7px 10px",
        gap: 10,
        fontSize: 13,
        background: active ? "rgba(255,255,255,0.06)" : "transparent",
        transition: "background 100ms ease, color 100ms ease",
      }}
      onMouseEnter={(e) => {
        if (!active) {
          (e.currentTarget as HTMLElement).style.background = "rgba(255,255,255,0.04)";
        }
      }}
      onMouseLeave={(e) => {
        (e.currentTarget as HTMLElement).style.background = active
          ? "rgba(255,255,255,0.06)"
          : "transparent";
      }}
    >
      {icon}
      <span>{label}</span>
    </Link>
  );
}

interface AppShellProps {
  children: React.ReactNode;
}

const SIDEBAR_WIDTH = 220;
const MOBILE_BREAKPOINT = 768;

export default function AppShell({ children }: AppShellProps) {
  const [open, setOpen] = useState(true);
  const pathname = usePathname();
  const { isSignedIn, user } = useUser();
  const username = user?.username ?? null;

  // Auto-collapse on narrow viewports. SSR always starts open; the layout
  // effect corrects synchronously before first paint (a rAF callback proved
  // unreliable here — it can land after paint or be cancelled by a remount,
  // leaving the sidebar open at phone widths).
  useLayoutEffect(() => {
    const collapseIfNarrow = () => {
      if (window.innerWidth < MOBILE_BREAKPOINT) {
        setOpen(false);
      }
    };
    collapseIfNarrow();
    window.addEventListener("resize", collapseIfNarrow, { passive: true });
    return () => {
      window.removeEventListener("resize", collapseIfNarrow);
    };
  }, []);

  const isHomeActive = pathname === "/";
  const isSearchActive = pathname.startsWith("/search");
  const isMelodiesActive = pathname.startsWith("/melodies");
  const isProfileActive = !!username && pathname.startsWith(`/u/${username}`);
  const isSettingsActive = pathname.startsWith("/settings");

  return (
    <div className="flex h-full flex-col">
      {/* ── Header (3-column grid) ─────────────────────────────────────── */}
      <header
        className="shrink-0 border-b"
        style={{
          borderColor: "rgba(255,255,255,0.07)",
          padding: "0 20px",
          height: 52,
          display: "grid",
          gridTemplateColumns: "1fr auto 1fr",
          alignItems: "center",
          gap: 12,
          backgroundColor: "#0b0d12",
          position: "relative",
          zIndex: 1,
        }}
      >
        {/* Left: toggle + logo */}
        <div className="flex items-center gap-3">
          <button
            onClick={() => setOpen((v) => !v)}
            aria-label={open ? "Collapse sidebar" : "Expand sidebar"}
            aria-expanded={open}
            className="rounded-nav text-secondary hover:text-primary flex items-center justify-center"
            style={{ width: 30, height: 30, color: "#8b93a3" }}
          >
            <IconMenu />
          </button>
          <Link href="/" className="flex items-center gap-2">
            <EqualizerGlyph fill="#2f8cff" size={16} />
            <span
              className="font-display text-primary select-none"
              style={{ fontSize: 14, fontWeight: 500, letterSpacing: 0 }}
            >
              harmoniq
            </span>
          </Link>
        </div>

        {/* Center: search */}
        <div className="w-full" style={{ maxWidth: 360 }}>
          <SearchBar />
        </div>

        {/* Right: notifications + profile */}
        <div className="flex items-center justify-end" style={{ gap: 8 }}>
          <NotificationBell />
          <NavAuth />
        </div>
      </header>

      {/* ── Body (sidebar + content) ───────────────────────────────────── */}
      <div className="flex flex-1 overflow-hidden">
        {/* Sidebar */}
        <aside
          className="sidebar-panel shrink-0"
          style={{
            width: open ? SIDEBAR_WIDTH : 0,
            backgroundColor: "#0e1015",
            borderRight: "1px solid rgba(255,255,255,0.07)",
          }}
        >
          <nav
            className="flex flex-col"
            style={{ padding: "16px 10px", gap: 2, minWidth: SIDEBAR_WIDTH }}
          >
            <NavLink href="/" icon={<IconHome size={16} />} label="Home" active={isHomeActive} />
            <NavLink
              href="/search"
              icon={<IconSearch size={16} />}
              label="Search"
              active={isSearchActive}
            />
            {isSignedIn && (
              <NavLink
                href="/melodies"
                icon={<IconMelody size={16} />}
                label="Melodies"
                active={isMelodiesActive}
              />
            )}
            {isSignedIn && username && (
              <NavLink
                href={`/u/${username}`}
                icon={<IconUser size={16} />}
                label="Profile"
                active={isProfileActive}
              />
            )}
            <NavLink
              href="/settings"
              icon={<IconSettings size={16} />}
              label="Settings"
              active={isSettingsActive}
            />
          </nav>
        </aside>

        {/* Page content — div, not main, so each page can own its own <main>.
            min-w-0 lets the flex child shrink below content width instead of
            forcing horizontal overflow on narrow viewports. */}
        <div className="min-w-0 flex-1 overflow-x-hidden overflow-y-auto">{children}</div>
      </div>
    </div>
  );
}
