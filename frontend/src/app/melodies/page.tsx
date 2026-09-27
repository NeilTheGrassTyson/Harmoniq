import { Suspense } from "react";
import { redirect } from "next/navigation";
import { auth } from "@clerk/nextjs/server";
import AppShell from "@/components/AppShell";
import { FriendsRailPlaceholder } from "@/components/FriendsRail";
import FriendsRailSection from "./FriendsRailSection";
import MelodiesTabs from "@/components/MelodiesTabs";
import { getInbox, getSentMelodies } from "@/lib/melodies";
import type { MelodyInboxResponse, MelodySentResponse } from "@/types";

export default async function MelodiesPage() {
  const { userId, getToken } = await auth();
  if (!userId) redirect("/sign-in");
  const token = await getToken().catch(() => null);
  if (!token) redirect("/sign-in");

  // Sections fail independently — an empty inbox is not an error state.
  let inbox: MelodyInboxResponse = { items: [], next_cursor: null };
  let sent: MelodySentResponse = { items: [], next_cursor: null };
  let loadFailed = false;
  try {
    [inbox, sent] = await Promise.all([getInbox(token), getSentMelodies(token)]);
  } catch {
    loadFailed = true;
  }

  return (
    <AppShell>
      <div className="flex min-h-full">
        <main className="mx-auto w-full max-w-2xl min-w-0 flex-1 px-4 py-10">
          <h1 className="font-display text-primary" style={{ fontSize: 20, fontWeight: 500 }}>
            Melodies
          </h1>
          <p className="text-tertiary" style={{ fontSize: 13, marginTop: 4, marginBottom: 20 }}>
            Songs sent to you, from people — one track at a time.
          </p>
          {loadFailed ? (
            <p className="text-tertiary" style={{ fontSize: 13 }}>
              Couldn&apos;t load your Melodies right now. Try again in a moment.
            </p>
          ) : (
            <MelodiesTabs
              inboxItems={inbox.items}
              inboxCursor={inbox.next_cursor}
              sentItems={sent.items}
              sentCursor={sent.next_cursor}
            />
          )}
        </main>
        <Suspense fallback={<FriendsRailPlaceholder />}>
          <FriendsRailSection />
        </Suspense>
      </div>
    </AppShell>
  );
}
