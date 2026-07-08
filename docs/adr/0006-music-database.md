# ADR 0006 — Canonical Music Database: MusicBrainz

**Date:** 2026-06-18
**Status:** Accepted
**Deciders:** Founder

---

## Context

Every rating, review, Melody, and highlight in Harmoniq attaches to a music
entity — a track, album, or artist. The canonical database that provides
these entities must have stable, permanent identifiers. Switching the
canonical source later requires re-keying the entire user-generated content
layer.

Requirements:

- Stable identifiers for tracks, albums, and artists
- Comprehensive global catalog
- No licensing restriction on commercial use or ML training
- Independence from Spotify (documented in CLAUDE.md)

## Decision

Use **MusicBrainz** as the canonical music database. MusicBrainz IDs (MBIDs)
are Harmoniq's canonical identifiers for all music entities. Artwork is
served from **Cover Art Archive** (MusicBrainz's associated image service).

Audio previews are **deferred** to Phase NEXT via the **Deezer API** (the
Demo + Open Melody enhancement). Not present in Phase 0 or Phase 1.

## Rationale

- **Open license (CC0):** MusicBrainz data is public domain. There are no
  ToS restrictions on commercial use, derivative works, or ML training —
  a direct contrast to Spotify (CLAUDE.md).
- **Stable MBIDs:** MusicBrainz IDs are the industry standard for music
  metadata interoperability. They are permanent, globally unique, and used
  by Wikipedia, Wikidata, and hundreds of other services. Our data will
  never need to be re-keyed due to a provider's business decision.
- **Comprehensive:** 2M+ artists, 30M+ recordings, all release formats.
- **Self-hostable:** The full PostgreSQL database dump (~30 GB compressed)
  can be mirrored for unlimited queries if needed at scale. Phase 0/1 uses
  the MetaBrainz API (1 req/sec without key, higher with a free API key).
- **Track record:** Non-profit MetaBrainz Foundation, 20+ years of operation.

## Ingestion Strategy (Phase 0/1: API-only)

- When a user searches for a track not in our local catalog, the backend
  queries MusicBrainz via HTTP, normalizes the response into our schema,
  and upserts into our local `tracks`, `albums`, `artists` tables.
- Our local catalog is a cache of MusicBrainz data. The MBID is always
  stored as the authoritative external key.
- Artwork: Cover Art Archive provides CDN URLs for album art. We store the
  URL, not the binary.

## Alternatives Considered

- **Spotify Web API:** Rejected. CLAUDE.md documents that Spotify's ToS
  prohibits using their metadata to train ML models — directly conflicting
  with Harmoniq's long-term recommendation engine. Additionally capped at 5
  developer-mode users, recommendations endpoint removed Feb 2026.
- **Discogs:** Vinyl/physical-media focus. Not well-suited to digital-first
  discovery. Commercial licensing unclear.
- **Apple Music API:** Requires Apple Developer enrollment. No clear
  advantage over MusicBrainz for metadata purposes.
- **Deezer as canonical:** Deezer IDs are not portable across services.
  Useful only as an audio preview supplement.

## Consequences

- `mbid` columns (UUID type) exist on `tracks`, `albums`, and `artists`.
- `MUSICBRAINZ_USER_AGENT` env var is required (MetaBrainz API requires a
  meaningful User-Agent header).
- The MusicBrainz API rate limit (1 req/sec without key) is enforced in
  the catalog service with a token-bucket limiter.
- Self-hosting the full DB dump is a Phase NEXT decision. If queries
  exceed API limits, this ADR should be revisited.
