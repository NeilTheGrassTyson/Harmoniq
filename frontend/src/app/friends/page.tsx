import { redirect } from "next/navigation";
import { auth } from "@clerk/nextjs/server";
import AppShell from "@/components/AppShell";
import FriendsList from "@/components/FriendsList";
import { getFriends } from "@/lib/friends";
import { errorStatus } from "@/lib/apiBase";
import type { FriendsOverview } from "@/types";

export default async function FriendsPage() {
  const { userId, getToken } = await auth();
  if (!userId) redirect("/sign-in");
  const token = await getToken().catch(() => null);
  if (!token) redirect("/sign-in");

  let overview: FriendsOverview | null = null;
  let unavailable = false;
  try {
    overview = await getFriends(token);
  } catch (err) {
    // 404 means the feature is switched off on the backend.
    unavailable = errorStatus(err) === 404;
  }

  return (
    <AppShell>
      <main className="mx-auto max-w-2xl px-4 py-10">
        <h1 className="font-display text-primary" style={{ fontSize: 20, fontWeight: 500 }}>
          Friends
        </h1>
        <p className="text-tertiary" style={{ fontSize: 13, marginTop: 4, marginBottom: 20 }}>
          People you trust with what you&apos;ve shared as friends-only. Only you can see this list.
        </p>
        {overview ? (
          <FriendsList initial={overview} />
        ) : (
          <p className="text-tertiary" style={{ fontSize: 13 }}>
            {unavailable
              ? "Friends aren't available right now."
              : "Couldn't load your friends right now. Try again in a moment."}
          </p>
        )}
      </main>
    </AppShell>
  );
}
