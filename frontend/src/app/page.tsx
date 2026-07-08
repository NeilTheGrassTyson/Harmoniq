import { auth } from "@clerk/nextjs/server";
import AppShell from "@/components/AppShell";
import TrackTile from "@/components/TrackTile";
import EqualizerGlyph from "@/components/EqualizerGlyph";
import { getHome } from "@/lib/home";
import type { FriendEntry, HomeResponse, TrendingEntry } from "@/types";

// ── Section label ─────────────────────────────────────────────────────────────

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

function EmptyState({ children }: { children: React.ReactNode }) {
  return (
    <p className="text-tertiary" style={{ fontSize: 13 }}>
      {children}
    </p>
  );
}

// ── Tile grids ────────────────────────────────────────────────────────────────

function TrendingGrid({ entries, error }: { entries: TrendingEntry[]; error: boolean }) {
  return (
    <section style={{ marginBottom: 34 }}>
      <SectionLabel>Trending</SectionLabel>
      {error ? (
        <EmptyState>Couldn&rsquo;t load this right now.</EmptyState>
      ) : entries.length === 0 ? (
        <EmptyState>No songs are trending yet.</EmptyState>
      ) : (
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fill, minmax(130px, 1fr))",
            gap: 20,
          }}
        >
          {entries.map((entry) => (
            <TrackTile
              key={entry.track.mbid}
              title={entry.track.title}
              artistName={entry.track.artist_name ?? null}
              coverArtUrl={entry.track.cover_art_url ?? null}
              href={`/track/${entry.track.mbid}`}
            />
          ))}
        </div>
      )}
    </section>
  );
}

function FriendsGrid({
  entries,
  error,
  hasMutualFollows,
}: {
  entries: FriendEntry[];
  error: boolean;
  hasMutualFollows: boolean;
}) {
  const emptyMsg = hasMutualFollows
    ? "Your friends haven't rated anything recently."
    : "Follow some people to see what they're into.";

  return (
    <section>
      <SectionLabel>Top songs from friends</SectionLabel>
      {error ? (
        <EmptyState>Couldn&rsquo;t load this right now.</EmptyState>
      ) : entries.length === 0 ? (
        <EmptyState>{emptyMsg}</EmptyState>
      ) : (
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fill, minmax(130px, 1fr))",
            gap: 20,
          }}
        >
          {entries.map((entry) => (
            <TrackTile
              key={`${entry.rated_by.username}-${entry.track.mbid}`}
              title={entry.track.title}
              artistName={entry.track.artist_name ?? null}
              coverArtUrl={entry.track.cover_art_url ?? null}
              href={`/track/${entry.track.mbid}`}
              sharedBy={{ username: entry.rated_by.username }}
            />
          ))}
        </div>
      )}
    </section>
  );
}

// ── Signed-out landing ────────────────────────────────────────────────────────

function SignedOutLanding() {
  return (
    <div className="flex flex-col items-center justify-center" style={{ paddingTop: 80, gap: 16 }}>
      <EqualizerGlyph fill="#2f8cff" size={36} />
      <p className="font-display text-primary" style={{ fontSize: 14, fontWeight: 500 }}>
        harmoniq
      </p>
      <p className="text-secondary" style={{ fontSize: 13 }}>
        Sign in to see what&rsquo;s trending.
      </p>
    </div>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

const _EMPTY_HOME: HomeResponse = {
  trending: [],
  trending_error: false,
  friends: [],
  friends_error: false,
  has_mutual_follows: false,
};

export default async function Home() {
  const { userId, getToken } = await auth();

  if (!userId) {
    return (
      <AppShell>
        <SignedOutLanding />
      </AppShell>
    );
  }

  const token = await getToken().catch(() => null);

  let home = _EMPTY_HOME;
  if (token) {
    try {
      home = await getHome(token);
    } catch {
      // Sections render their own error states via the error flags.
    }
  }

  return (
    <AppShell>
      <div style={{ padding: "26px 22px 30px" }}>
        <TrendingGrid entries={home.trending} error={home.trending_error} />
        <FriendsGrid
          entries={home.friends}
          error={home.friends_error}
          hasMutualFollows={home.has_mutual_follows}
        />
      </div>
    </AppShell>
  );
}
