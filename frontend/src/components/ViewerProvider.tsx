"use client";

import { createContext, useContext } from "react";
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
  return <ViewerContext.Provider value={value}>{children}</ViewerContext.Provider>;
}

export function useViewer(): Viewer {
  return useContext(ViewerContext);
}
