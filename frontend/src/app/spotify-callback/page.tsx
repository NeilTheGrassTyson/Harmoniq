"use client";

// Landing route for the Spotify OAuth redirect.
//
// Spotify (2025 policy) only accepts loopback IP literals for http redirect
// URIs, so it sends the user to 127.0.0.1 — but Clerk dev sessions live on
// the localhost origin. This page therefore bounces itself from 127.0.0.1
// to localhost (query string intact) before doing anything, then performs
// the authed code exchange. The route is public in proxy.ts; the backend
// still requires auth plus a user-bound signed state for the exchange.

import Link from "next/link";
import { Suspense, useEffect, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useAuth } from "@clerk/nextjs";
import AppShell from "@/components/AppShell";
import { completeSpotifyCallback } from "@/lib/spotify";
import { getOwnProfile } from "@/lib/users";

type CallbackState = "working" | "denied" | "error";

function SpotifyCallbackContent() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const { getToken } = useAuth();
  const [exchangeFailed, setExchangeFailed] = useState(false);
  // Spotify authorization codes are single-use; React strict-mode double
  // invocation must not fire the exchange twice.
  const firedRef = useRef(false);

  const code = searchParams.get("code");
  const stateParam = searchParams.get("state");
  const errorParam = searchParams.get("error");

  // Derived at render — only the async exchange outcome needs state.
  const state: CallbackState = exchangeFailed
    ? "error"
    : errorParam === "access_denied"
      ? "denied"
      : errorParam || !code || !stateParam
        ? "error"
        : "working";

  useEffect(() => {
    // proxy.ts normalizes 127.0.0.1 → localhost server-side before this page
    // renders; this client-side bounce is a fallback in case the request
    // bypassed the middleware.
    if (window.location.hostname === "127.0.0.1") {
      window.location.replace(window.location.href.replace("//127.0.0.1", "//localhost"));
      return;
    }

    if (firedRef.current || !code || !stateParam || errorParam) return;
    firedRef.current = true;

    (async () => {
      try {
        const token = await getToken();
        if (!token) throw new Error("Not signed in.");
        await completeSpotifyCallback(token, code, stateParam);
        const { username } = await getOwnProfile(token);
        router.replace(`/u/${username}?spotify=connected`);
      } catch {
        setExchangeFailed(true);
      }
    })();
  }, [code, stateParam, errorParam, getToken, router]);

  return (
    <main className="mx-auto max-w-2xl px-4 py-16">
      {state === "working" && (
        <p className="text-secondary text-sm">Connecting your Spotify account…</p>
      )}
      {state === "denied" && (
        <div className="space-y-2">
          <p className="text-secondary text-sm">
            No problem — your Spotify account wasn&rsquo;t connected.
          </p>
          <Link href="/settings" className="text-tertiary hover:text-secondary text-sm">
            Back to settings
          </Link>
        </div>
      )}
      {state === "error" && (
        <div className="space-y-2">
          <p className="text-secondary text-sm">
            Couldn&rsquo;t connect your Spotify account. Try again.
          </p>
          <Link href="/settings" className="text-tertiary hover:text-secondary text-sm">
            Back to settings
          </Link>
        </div>
      )}
    </main>
  );
}

// useSearchParams requires a Suspense boundary above it for the static
// prerender of this route to succeed (same pattern as /search).
export default function SpotifyCallbackPage() {
  return (
    <AppShell>
      <Suspense
        fallback={
          <main className="mx-auto max-w-2xl px-4 py-16">
            <p className="text-secondary text-sm">Connecting your Spotify account…</p>
          </main>
        }
      >
        <SpotifyCallbackContent />
      </Suspense>
    </AppShell>
  );
}
