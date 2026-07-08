import { notFound } from "next/navigation";
import { auth } from "@clerk/nextjs/server";
import AppShell from "@/components/AppShell";
import ModerationQueue from "@/components/ModerationQueue";
import { getReports } from "@/lib/moderation";
import { getOwnProfile } from "@/lib/users";

// Not linked from the nav — moderators navigate here directly, and the page
// 404s for everyone else, mirroring the API's existence-hiding behavior.
export default async function ModerationPage() {
  const { userId, getToken } = await auth();
  if (!userId) notFound();
  const token = await getToken().catch(() => null);
  if (!token) notFound();

  let isModerator = false;
  try {
    const profile = await getOwnProfile(token);
    isModerator = profile.is_moderator;
  } catch {
    notFound();
  }
  if (!isModerator) notFound();

  const queue = await getReports(token).catch(() => ({
    items: [],
    next_cursor: null,
  }));

  return (
    <AppShell>
      <main className="mx-auto max-w-2xl px-4 py-10">
        <h1 className="font-display text-primary" style={{ fontSize: 20, fontWeight: 500 }}>
          Moderation
        </h1>
        <p className="text-tertiary" style={{ fontSize: 13, marginTop: 4, marginBottom: 12 }}>
          Open reports on reviews. Actions here are logged.
        </p>
        <ModerationQueue initialItems={queue.items} initialCursor={queue.next_cursor} />
      </main>
    </AppShell>
  );
}
