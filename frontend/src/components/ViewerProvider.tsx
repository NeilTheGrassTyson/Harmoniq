"use client";

import { createContext, useContext, useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@clerk/nextjs";
import type { Viewer } from "@/lib/viewer";

/**
 * Carries the server-resolved viewer down to the client chrome.
 *
 * The nav used to derive both "am I signed in" and "what is my username" from
 * `useUser()`, which is only populated after hydration. Every server-rendered
 * page therefore shipped signed-out chrome — no Profile link, no Melodies, no
 * notification bell — and popped them in a moment later. Passing the answer
 * down from the root layout means the first paint is already correct.
 */
const ViewerContext = createContext<Viewer>({ signedIn: false, username: null });

export function ViewerProvider({ value, children }: { value: Viewer; children: React.ReactNode }) {
  const { isLoaded, isSignedIn } = useAuth();
  const router = useRouter();

  // `value` is fixed for the lifetime of this render — it's the result of
  // getViewer() in the root layout, resolved once per navigation. Signing in
  // through the <SignInButton> modal changes Clerk's client-side session
  // without triggering a Next.js navigation, so `value.signedIn` stays false
  // and every consumer (Profile link, avatar, notification bell) keeps
  // rendering its signed-out shape until something forces a re-render of the
  // server tree. router.refresh() is that trigger; without it, the fix was
  // "reload the page", which is exactly the bug being reported.
  useEffect(() => {
    if (isLoaded && isSignedIn && !value.signedIn) {
      router.refresh();
    }
  }, [isLoaded, isSignedIn, value.signedIn, router]);

  return <ViewerContext.Provider value={value}>{children}</ViewerContext.Provider>;
}

export function useViewer(): Viewer {
  return useContext(ViewerContext);
}
