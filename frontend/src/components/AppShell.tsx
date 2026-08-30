"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import SearchBar, { SearchBarFallback } from "@/components/SearchBar";
import NavAuth from "@/components/NavAuth";
import { useViewer } from "@/components/ViewerProvider";
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
  // Hover is a CSS concern: an active row keeps --color-nav-active and ignores
  // hover, an inactive row picks up --color-nav-hover. Expressing it in classes
  // instead of onMouseEnter/onMouseLeave also makes it work for touch and
  // keyboard focus, which the JS handlers never covered.
  return (
    <Link
      href={href}
      aria-current={active ? "page" : undefined}
      className={`rounded-nav text-secondary hover:text-primary flex items-center gap-[10px] px-[10px] py-[7px] text-[13px] transition-colors duration-100 ${
        active ? "bg-nav-active" : "hover:bg-nav-hover"
      }`}
    >
      {icon}
      <span>{label}</span>
    </Link>
  );
}

interface AppShellProps {
  children: React.ReactNode;
}

const MOBILE_BREAKPOINT_QUERY = "(min-width: 768px)";

export default function AppShell({ children }: AppShellProps) {
  // null = "no explicit choice yet", so the CSS default for the current
  // breakpoint applies (see .sidebar-panel in globals.css). Once the user
  // toggles, their choice wins at every width.
  const [open, setOpen] = useState<boolean | null>(null);
  const pathname = usePathname();
  // Server-resolved, so the nav is correct on first paint rather than after
  // hydration — and `username` is the Harmoniq handle profile routes are keyed
  // by, not Clerk's unsynced copy. See lib/viewer.ts.
  const { signedIn, username } = useViewer();

  // Mirrors the CSS breakpoint purely so aria-expanded and the button label
  // can describe the sidebar's actual state. It drives no layout — the panel
  // is sized by CSS — so settling one paint after mount is harmless, and
  // matchMedia fires only when the breakpoint is crossed rather than on every
  // resize frame.
  const [wideViewport, setWideViewport] = useState(false);
  useEffect(() => {
    const mq = window.matchMedia(MOBILE_BREAKPOINT_QUERY);
    const sync = () => setWideViewport(mq.matches);
    sync();
    mq.addEventListener("change", sync);
    return () => mq.removeEventListener("change", sync);
  }, []);

  const effectiveOpen = open ?? wideViewport;

  const isHomeActive = pathname === "/";
  const isSearchActive = pathname.startsWith("/search");
  const isMelodiesActive = pathname.startsWith("/melodies");
  const isProfileActive = !!username && pathname.startsWith(`/u/${username}`);
  const isSettingsActive = pathname.startsWith("/settings");

  return (
    <div className="flex h-full flex-col">
      {/* ── Header (3-column grid) ─────────────────────────────────────── */}
      <header className="border-hairline bg-canvas relative z-1 grid h-[52px] shrink-0 grid-cols-[1fr_auto_1fr] items-center gap-3 border-b px-5">
        {/* Left: toggle + logo */}
        <div className="flex items-center gap-3">
          <button
            onClick={() => setOpen(!effectiveOpen)}
            aria-label={effectiveOpen ? "Collapse sidebar" : "Expand sidebar"}
            aria-expanded={effectiveOpen}
            className="rounded-nav text-secondary hover:text-primary flex size-[30px] items-center justify-center"
          >
            <IconMenu />
          </button>
          <Link href="/" className="flex items-center gap-2">
            <EqualizerGlyph className="text-accent" size={16} />
            {/* Below sm the glyph carries the mark alone — at 390px the
                wordmark competes with the search field for the same row. */}
            <span className="font-display text-primary hidden text-sm font-medium tracking-normal select-none sm:inline">
              harmoniq
            </span>
          </Link>
        </div>

        {/* Center: search */}
        <div className="w-full max-w-[360px]">
          {/* SearchBar reads ?q= so the field tracks the URL through history
              moves; useSearchParams bails its subtree out of prerendering, and
              a static route (not-found) fails to build without a boundary. */}
          <Suspense fallback={<SearchBarFallback />}>
            <SearchBar />
          </Suspense>
        </div>

        {/* Right: notifications + profile */}
        <div className="flex items-center justify-end gap-2">
          <NotificationBell />
          <NavAuth />
        </div>
      </header>

      {/* ── Body (sidebar + content) ───────────────────────────────────── */}
      <div className="flex flex-1 overflow-hidden">
        {/* Sidebar */}
        <aside
          className="sidebar-panel bg-sidebar border-hairline shrink-0 border-r"
          // Absent until the user chooses, so the CSS breakpoint default holds.
          data-open={open === null ? undefined : open}
        >
          <nav className="flex min-w-[var(--sidebar-width)] flex-col gap-0.5 px-[10px] py-4">
            <NavLink href="/" icon={<IconHome size={16} />} label="Home" active={isHomeActive} />
            <NavLink
              href="/search"
              icon={<IconSearch size={16} />}
              label="Search"
              active={isSearchActive}
            />
            {signedIn && (
              <NavLink
                href="/melodies"
                icon={<IconMelody size={16} />}
                label="Melodies"
                active={isMelodiesActive}
              />
            )}
            {signedIn && username && (
              <NavLink
                href={`/u/${username}`}
                icon={<IconUser size={16} />}
                label="Profile"
                active={isProfileActive}
              />
            )}
            {/* Settings is an account page — offering it to a signed-out
                visitor only sends them to the sign-in wall. Search stays
                visible to everyone: it is a browse surface (ADR 0012). */}
            {signedIn && (
              <NavLink
                href="/settings"
                icon={<IconSettings size={16} />}
                label="Settings"
                active={isSettingsActive}
              />
            )}
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
