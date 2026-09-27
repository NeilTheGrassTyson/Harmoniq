"use client";

import { useAuth } from "@clerk/nextjs";
import { useEffect } from "react";
import { sendHeartbeat } from "@/lib/presence";

const BEAT_MS = 60_000;

/**
 * Tells the server this person has Harmoniq open, once a minute and only
 * while the tab is visible (docs/specs/beta-ui-phase-5-presence.md). The
 * server keeps nothing for anyone whose Online status is Private and answers
 * `recorded: false`; after that this page sends nothing more.
 */
export default function PresenceHeartbeat() {
  const { getToken, isSignedIn } = useAuth();

  useEffect(() => {
    if (!isSignedIn) return;
    let stopped = false;

    function stop() {
      stopped = true;
      window.clearInterval(timer);
      document.removeEventListener("visibilitychange", onVisibility);
    }

    async function beat() {
      if (stopped || document.visibilityState !== "visible") return;
      try {
        const token = await getToken();
        if (!token || stopped) return;
        if (!(await sendHeartbeat(token))) stop();
      } catch {
        // A missed beat only means offline sooner; nothing to surface.
      }
    }

    function onVisibility() {
      void beat();
    }

    const timer = window.setInterval(() => void beat(), BEAT_MS);
    document.addEventListener("visibilitychange", onVisibility);
    void beat();
    return stop;
  }, [getToken, isSignedIn]);

  return null;
}
