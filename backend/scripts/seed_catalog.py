"""
Seed the catalog with a curated artist list via the normal ingestion path.

Runs the exact same code the live Search feature runs — search_and_ingest
for the artist plus get_artist to sync the full discography — so seeded
rows are indistinguishable from organically ingested ones. Idempotent:
everything upserts, so rerunning (or resuming after a crash) is safe.

No secrets live here; the database comes from DATABASE_URL. To seed the
production database, run from backend/ with the prod pooled string:

    DATABASE_URL="postgresql+asyncpg://...?ssl=require" \
        poetry run python scripts/seed_catalog.py

Useful flags:
    --dry-run       print the resolved artist list and exit (no network/DB)
    --limit N       only the first N artists (smoke-test with --limit 3)
    --tier X        "present" (top ~100 today), "alltime" (top ~200 ever),
                    or "all" (default: both, deduped)

Expect a full run to take ~30-60 minutes: MusicBrainz allows 1 request
per second (enforced by app.services.musicbrainz's shared limiter) and
each artist costs several requests. Progress logs per artist; a failure
on one artist is logged and skipped, never fatal.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database import AsyncSessionLocal, engine  # noqa: E402
from app.services import catalog as catalog_svc  # noqa: E402

logger = logging.getLogger("seed_catalog")

_ATTEMPTS = 3
_RETRY_DELAY_SECONDS = 10

# ── Curated lists ─────────────────────────────────────────────────────────────
# Editorial, not algorithmic (Founder decision 2026-07-09): ~100 artists with
# major present-day presence plus ~200 all-time greats across genres/eras.
# Names must match MusicBrainz canonical spellings closely enough for search
# to rank them first — the resolver below warns when the top hit disagrees.

PRESENT_DAY: list[str] = [
    "Taylor Swift",
    "Drake",
    "Bad Bunny",
    "The Weeknd",
    "Billie Eilish",
    "Olivia Rodrigo",
    "Dua Lipa",
    "Kendrick Lamar",
    "SZA",
    "Doja Cat",
    "Harry Styles",
    "Ariana Grande",
    "Post Malone",
    "Travis Scott",
    "21 Savage",
    "Morgan Wallen",
    "Zach Bryan",
    "Luke Combs",
    "Sabrina Carpenter",
    "Chappell Roan",
    "Charli XCX",
    "Tate McRae",
    "Gracie Abrams",
    "Noah Kahan",
    "Hozier",
    "Teddy Swims",
    "Benson Boone",
    "Shaboozey",
    "Tyla",
    "Peso Pluma",
    "Karol G",
    "Feid",
    "Rauw Alejandro",
    "J Balvin",
    "Rosalía",
    "Burna Boy",
    "Wizkid",
    "Rema",
    "Asake",
    "Tems",
    "BTS",
    "Blackpink",
    "Stray Kids",
    "Twice",
    "NewJeans",
    "Seventeen",
    "Ice Spice",
    "Cardi B",
    "Megan Thee Stallion",
    "Nicki Minaj",
    "Lil Baby",
    "Future",
    "Metro Boomin",
    "Playboi Carti",
    "Yeat",
    "Don Toliver",
    "Jack Harlow",
    "Central Cee",
    "Dave",
    "Stormzy",
    "Fred again..",
    "Calvin Harris",
    "David Guetta",
    "Kygo",
    "RÜFÜS DU SOL",
    "Ed Sheeran",
    "Justin Bieber",
    "Selena Gomez",
    "Miley Cyrus",
    "Lana Del Rey",
    "Lorde",
    "Phoebe Bridgers",
    "boygenius",
    "Mitski",
    "Clairo",
    "beabadoobee",
    "Laufey",
    "Conan Gray",
    "Troye Sivan",
    "Lil Nas X",
    "Bruno Mars",
    "Jelly Roll",
    "Lainey Wilson",
    "Kacey Musgraves",
    "Chris Stapleton",
    "Tyler Childers",
    "Turnstile",
    "Fontaines D.C.",
    "Wet Leg",
    "RAYE",
    "PinkPantheress",
    "GloRilla",
    "Jhené Aiko",
    "Summer Walker",
    "Brent Faiyaz",
    "Daniel Caesar",
    "Steve Lacy",
    "Dominic Fike",
    "Omar Apollo",
    "Tyler, the Creator",
]

ALL_TIME: list[str] = [
    "The Beatles",
    "The Rolling Stones",
    "Bob Dylan",
    "Led Zeppelin",
    "Pink Floyd",
    "Queen",
    "David Bowie",
    "Jimi Hendrix",
    "The Who",
    "The Beach Boys",
    "Elvis Presley",
    "Chuck Berry",
    "Little Richard",
    "Ray Charles",
    "Aretha Franklin",
    "Stevie Wonder",
    "Marvin Gaye",
    "Sam Cooke",
    "Otis Redding",
    "James Brown",
    "Prince",
    "Michael Jackson",
    "Madonna",
    "Whitney Houston",
    "Mariah Carey",
    "Elton John",
    "Billy Joel",
    "Bruce Springsteen",
    "Tom Petty",
    "Fleetwood Mac",
    "Eagles",
    "Creedence Clearwater Revival",
    "The Doors",
    "The Velvet Underground",
    "Lou Reed",
    "Neil Young",
    "Joni Mitchell",
    "Leonard Cohen",
    "Simon & Garfunkel",
    "Paul Simon",
    "Bob Marley & The Wailers",
    "Fela Kuti",
    "Miles Davis",
    "John Coltrane",
    "Louis Armstrong",
    "Duke Ellington",
    "Ella Fitzgerald",
    "Billie Holiday",
    "Nina Simone",
    "Frank Sinatra",
    "Nat King Cole",
    "Johnny Cash",
    "Hank Williams",
    "Willie Nelson",
    "Dolly Parton",
    "Merle Haggard",
    "Patsy Cline",
    "Waylon Jennings",
    "B.B. King",
    "Muddy Waters",
    "Howlin' Wolf",
    "Robert Johnson",
    "John Lee Hooker",
    "Eric Clapton",
    "Cream",
    "Black Sabbath",
    "Deep Purple",
    "AC/DC",
    "Guns N' Roses",
    "Aerosmith",
    "Van Halen",
    "Metallica",
    "Iron Maiden",
    "Judas Priest",
    "Megadeth",
    "Slayer",
    "Pantera",
    "Nirvana",
    "Pearl Jam",
    "Soundgarden",
    "Alice in Chains",
    "Red Hot Chili Peppers",
    "Rage Against the Machine",
    "Radiohead",
    "R.E.M.",
    "U2",
    "The Police",
    "Sting",
    "Talking Heads",
    "Blondie",
    "The Clash",
    "Sex Pistols",
    "Ramones",
    "The Cure",
    "Joy Division",
    "New Order",
    "Depeche Mode",
    "The Smiths",
    "Pixies",
    "Sonic Youth",
    "My Bloody Valentine",
    "Oasis",
    "Blur",
    "Pulp",
    "The Verve",
    "The Stone Roses",
    "Björk",
    "Portishead",
    "Massive Attack",
    "Aphex Twin",
    "The Prodigy",
    "The Chemical Brothers",
    "Daft Punk",
    "Kraftwerk",
    "Brian Eno",
    "Donna Summer",
    "Chic",
    "Bee Gees",
    "ABBA",
    "Earth, Wind & Fire",
    "Parliament",
    "Funkadelic",
    "Sly and the Family Stone",
    "Curtis Mayfield",
    "Al Green",
    "Isaac Hayes",
    "Barry White",
    "The Temptations",
    "The Supremes",
    "Smokey Robinson",
    "Four Tops",
    "The Jackson 5",
    "Diana Ross",
    "Tina Turner",
    "Janis Joplin",
    "Grateful Dead",
    "Jefferson Airplane",
    "Santana",
    "Crosby, Stills, Nash & Young",
    "The Byrds",
    "The Kinks",
    "The Animals",
    "Van Morrison",
    "Rod Stewart",
    "Genesis",
    "Peter Gabriel",
    "Phil Collins",
    "Yes",
    "King Crimson",
    "Rush",
    "Jethro Tull",
    "Dire Straits",
    "Supertramp",
    "Steely Dan",
    "Chicago",
    "Toto",
    "Journey",
    "Foreigner",
    "Boston",
    "Heart",
    "Pat Benatar",
    "Cyndi Lauper",
    "Bonnie Raitt",
    "Carole King",
    "James Taylor",
    "Cat Stevens",
    "Jackson Browne",
    "Linda Ronstadt",
    "Emmylou Harris",
    "Kris Kristofferson",
    "Townes Van Zandt",
    "The Band",
    "Bob Seger",
    "ZZ Top",
    "Lynyrd Skynyrd",
    "The Allman Brothers Band",
    "Wu-Tang Clan",
    "Nas",
    "The Notorious B.I.G.",
    "2Pac",
    "Jay-Z",
    "Eminem",
    "Dr. Dre",
    "Snoop Dogg",
    "Ice Cube",
    "N.W.A",
    "Public Enemy",
    "Run-D.M.C.",
    "Beastie Boys",
    "A Tribe Called Quest",
    "De La Soul",
    "OutKast",
    "Missy Elliott",
    "Lauryn Hill",
    "Fugees",
    "Erykah Badu",
    "D'Angelo",
    "Sade",
    "Luther Vandross",
    "Boyz II Men",
    "TLC",
    "Destiny's Child",
    "Beyoncé",
    "Rihanna",
    "Usher",
    "Alicia Keys",
    "Coldplay",
    "Green Day",
    "Weezer",
    "Foo Fighters",
    "No Doubt",
    "Alanis Morissette",
    "Amy Winehouse",
    "Adele",
    "Florence + the Machine",
    "Arcade Fire",
    "The Strokes",
    "The White Stripes",
    "The Black Keys",
    "Muse",
    "Linkin Park",
    "Nine Inch Nails",
    "Tool",
    "The Smashing Pumpkins",
    "Beck",
    "Gorillaz",
    "Frank Ocean",
    "Kanye West",
    "Arctic Monkeys",
]


def build_list(tier: str) -> list[str]:
    """Resolve the tier selection into a deduped, order-preserving list."""
    tiers = {
        "present": PRESENT_DAY,
        "alltime": ALL_TIME,
        "all": PRESENT_DAY + ALL_TIME,
    }
    seen: set[str] = set()
    result: list[str] = []
    for name in tiers[tier]:
        key = name.casefold()
        if key not in seen:
            seen.add(key)
            result.append(name)
    return result


async def seed_artist(name: str) -> bool:
    """Ingest one artist + full discography. Returns True on success."""
    async with AsyncSessionLocal() as session:
        response = await catalog_svc.search_and_ingest(name, session)
        if not response.artists:
            logger.warning("no MusicBrainz artist found for %r — skipped", name)
            return False

        # Prefer an exact (casefolded) name match in the ranked results;
        # otherwise trust MusicBrainz's top-scored hit but say so.
        match = next(
            (a for a in response.artists if a.name.casefold() == name.casefold()),
            None,
        )
        if match is None:
            match = response.artists[0]
            logger.warning(
                "no exact match for %r — using top hit %r (%s)",
                name,
                match.name,
                match.mbid,
            )

        # get_artist runs _sync_artist_discography — the full album pull.
        detail = await catalog_svc.get_artist(match.mbid, session)
        await session.commit()

        album_count = len(detail.albums) if detail else 0
        logger.info("seeded %r — %d albums", match.name, album_count)
        return True


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tier", choices=["present", "alltime", "all"], default="all")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    artists = build_list(args.tier)
    if args.limit is not None:
        artists = artists[: args.limit]

    if args.dry_run:
        for name in artists:
            print(name)
        print(f"-- {len(artists)} artists ({args.tier})")
        return

    started = time.monotonic()
    ok = failed = 0
    try:
        for i, name in enumerate(artists, 1):
            logger.info("[%d/%d] %s", i, len(artists), name)
            # Transient MusicBrainz connection drops are common over a long
            # run; retry per artist. Successful calls are cached (5-min TTL),
            # so a retry only repeats the request that actually failed.
            for attempt in range(1, _ATTEMPTS + 1):
                try:
                    if await seed_artist(name):
                        ok += 1
                    else:
                        failed += 1
                    break
                except Exception:
                    if attempt == _ATTEMPTS:
                        logger.exception(
                            "failed to seed %r after %d attempts — continuing",
                            name,
                            _ATTEMPTS,
                        )
                        failed += 1
                    else:
                        logger.warning(
                            "attempt %d/%d for %r failed — retrying in %ds",
                            attempt,
                            _ATTEMPTS,
                            name,
                            _RETRY_DELAY_SECONDS,
                        )
                        await asyncio.sleep(_RETRY_DELAY_SECONDS)
    finally:
        await engine.dispose()

    minutes = (time.monotonic() - started) / 60
    logger.info("done: %d seeded, %d failed, %.1f minutes", ok, failed, minutes)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s"
    )
    asyncio.run(main())
