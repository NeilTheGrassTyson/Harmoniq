import Link from "next/link";
import { notFound } from "next/navigation";
import { auth } from "@clerk/nextjs/server";
import AppShell from "@/components/AppShell";
import ListeningSection from "@/components/ListeningSection";
import ProfileHeader from "@/components/ProfileHeader";
import { getProfile } from "@/lib/users";
import { getUserRatings } from "@/lib/ratings";
import { getListening } from "@/lib/spotify";

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

export default async function ProfilePage(props: {
  params: Promise<{ username: string }>;
  searchParams: Promise<{ spotify?: string }>;
}) {
  const { username } = await props.params;
  const { spotify } = await props.searchParams;
  const spotifyJustConnected = spotify === "connected";
  const { getToken } = await auth();
  const token = await getToken().catch(() => null);

  let profile;
  try {
    profile = await getProfile(username, token ?? undefined);
  } catch (err: unknown) {
    const status =
      err instanceof Error && (err as Error & { status?: number }).status === 404 ? 404 : 503;
    if (status === 404) notFound();
    throw err;
  }

  const ratingsData = await getUserRatings(username, token ?? undefined).catch(() => ({
    reviews: [],
  }));

  // Section independence: a listening failure renders nothing, it never
  // breaks the page. The backend re-enforces visibility regardless of the
  // activity_placeholder flag.
  const listening =
    "activity_placeholder" in profile && profile.activity_placeholder
      ? await getListening(username, token ?? undefined).catch(() => null)
      : null;

  return (
    <AppShell>
      <div style={{ padding: "26px 22px 30px", maxWidth: 720 }}>
        <ProfileHeader
          profile={profile}
          autoOpenEdit={spotifyJustConnected && profile.is_own_profile}
        />

        {/* ── Listening activity (Spotify, display-only) ─────────────────── */}
        {listening !== null && (
          <section style={{ marginBottom: 32 }}>
            <SectionLabel>Listening</SectionLabel>
            <ListeningSection
              username={profile.username}
              token={token ?? undefined}
              initial={listening}
            />
          </section>
        )}

        {/* ── Ratings ────────────────────────────────────────────────────── */}
        {"ratings_count" in profile && (
          <section>
            <SectionLabel>Ratings</SectionLabel>
            {ratingsData.reviews.length === 0 ? (
              <p className="text-tertiary" style={{ fontSize: 13 }}>
                No reviews yet.
              </p>
            ) : (
              <ul style={{ listStyle: "none", padding: 0, margin: 0 }}>
                {ratingsData.reviews.map((r, idx) => (
                  <li
                    key={r.id}
                    style={{
                      paddingBottom: 20,
                      marginBottom: 20,
                      borderBottom:
                        idx < ratingsData.reviews.length - 1
                          ? "1px solid rgba(255,255,255,0.07)"
                          : "none",
                    }}
                  >
                    <div
                      style={{
                        display: "flex",
                        alignItems: "baseline",
                        justifyContent: "space-between",
                        gap: 12,
                        marginBottom: 4,
                      }}
                    >
                      <div style={{ minWidth: 0 }}>
                        {r.entity_mbid ? (
                          <Link
                            href={`/${r.entity_type}/${r.entity_mbid}`}
                            className="text-primary hover:text-accent"
                            style={{ fontSize: 14, fontWeight: 500 }}
                          >
                            {r.entity_title ?? r.entity_mbid}
                          </Link>
                        ) : (
                          <span className="text-primary" style={{ fontSize: 14, fontWeight: 500 }}>
                            {r.entity_title ?? "Unknown"}
                          </span>
                        )}
                        <span className="text-tertiary" style={{ fontSize: 11, marginLeft: 8 }}>
                          {r.entity_type}
                        </span>
                      </div>
                      <span
                        className="text-primary font-display"
                        style={{ fontSize: 13, fontWeight: 500, flexShrink: 0 }}
                      >
                        {r.score}/10
                      </span>
                    </div>
                    <p className="text-secondary" style={{ fontSize: 13, lineHeight: 1.6 }}>
                      {r.review_text}
                    </p>
                    <p className="text-tertiary" style={{ fontSize: 11, marginTop: 4 }}>
                      {formatDate(r.created_at)}
                    </p>
                  </li>
                ))}
              </ul>
            )}
          </section>
        )}
      </div>
    </AppShell>
  );
}

function SectionLabel({ children }: { children: React.ReactNode }) {
  return (
    <h2
      className="font-display text-tertiary"
      style={{
        fontSize: 11,
        fontWeight: 500,
        textTransform: "uppercase",
        letterSpacing: "0.6px",
        marginBottom: 14,
      }}
    >
      {children}
    </h2>
  );
}
