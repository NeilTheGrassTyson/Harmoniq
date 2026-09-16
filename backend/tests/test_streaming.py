import asyncio
from unittest.mock import AsyncMock
from urllib.parse import unquote

import httpx
import pytest

from app.services import streaming

SPOTIFY = "https://open.spotify.com/track/0123456789abcdefghijkl"


@pytest.mark.parametrize(
    "url,provider,clean",
    [
        (SPOTIFY + "?si=tracking#fragment", "spotify", SPOTIFY),
        (
            "https://music.apple.com/us/album/song/123?i=456&app=music",
            "apple",
            "https://music.apple.com/us/album/song/123?i=456",
        ),
        (
            "https://music.apple.com/us/song/hello/456",
            "apple",
            "https://music.apple.com/us/song/hello/456",
        ),
        (
            "https://music.youtube.com/watch?v=abcdefghijk&list=private",
            "youtube",
            "https://music.youtube.com/watch?v=abcdefghijk",
        ),
        ("https://listen.tidal.com/track/123", "tidal", "https://tidal.com/track/123"),
        (
            "https://www.deezer.com/en/track/123",
            "deezer",
            "https://www.deezer.com/track/123",
        ),
        (
            "https://music.amazon.com/albums/B012345678?trackAsin=B012345679&ref=tracking",
            "amazon",
            "https://music.amazon.com/albums/B012345678?trackAsin=B012345679",
        ),
        (
            "https://music.amazon.co.uk/tracks/B012345678",
            "amazon",
            "https://music.amazon.co.uk/tracks/B012345678",
        ),
    ],
)
def test_exact_recording_links(url: str, provider: str, clean: str) -> None:
    assert streaming.exact_link(url) == (provider, clean)


@pytest.mark.parametrize(
    "url",
    [
        "javascript:alert(1)",
        "http://open.spotify.com/track/0123456789abcdefghijkl",
        "//open.spotify.com/track/0123456789abcdefghijkl",
        SPOTIFY.replace(".com", ".com.evil.test"),
        SPOTIFY.replace(".com", ".com:443"),
        SPOTIFY.replace("https://", "https://me:password@"),
        SPOTIFY.replace(".com", ".com@evil.test"),
        SPOTIFY + "\n",
        SPOTIFY.replace("/track/", "/album/"),
        SPOTIFY.replace("/track/", "/%2e%2e/track/"),
        "https://127.0.0.1/track/123",
        "https://[::1]/track/123",
        SPOTIFY.replace(".com", ".com\\@evil.test"),
        "https://music.apple.com/us/album/title/123",
        "https://music.apple.com/us/album/title/123?i=456&i=789",
        "https://music.youtube.com/watch?v=invalid",
        "https://music.youtube.com/watch?v=abcdefghijk&v=12345678901",
        "https://tidal.com/artist/123",
        "https://music.amazon.com/albums/B012345678",
        "https://music.amazon.com/tracks/%2e%2e",
        "https://open.spotify.com:invalid/track/0123456789abcdefghijkl",
    ],
)
def test_hostile_or_non_song_urls_are_rejected(url: str) -> None:
    assert streaming.exact_link(url) is None


def test_six_searches_encode_title_and_artist_without_private_parameters() -> None:
    links = streaming.search_links("青い空 / & ?#", "A + B")
    assert len(links) == 6
    for url in links.values():
        assert "青い空" in unquote(url) and "#" not in url
        assert "A" in unquote(url) and "B" in unquote(url)
    # Apple treats '+' as literal during its redirect, unlike form decoders.
    assert unquote(links["apple"].partition("term=")[2]) == "青い空 / & ?# A + B"
    assert "+" not in links["apple"]


@pytest.fixture(autouse=True)
def clear_cache():
    streaming._cache.clear()
    streaming._inflight.clear()
    yield
    streaming._cache.clear()
    streaming._inflight.clear()


def relation(url: str) -> dict:
    return {"target-type": "url", "type": "streaming", "url": {"resource": url}}


async def test_ambiguity_album_and_bad_relations_fall_back(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    lookup = AsyncMock(
        return_value={
            "relations": [
                relation(SPOTIFY),
                relation(SPOTIFY[:-1] + "m"),
                relation("https://tidal.com/album/123"),
                relation("https://www.deezer.com/track/123"),
                None,
                {},
            ]
        }
    )
    monkeypatch.setattr(streaming.musicbrainz, "lookup_recording_links", lookup)
    assert await streaming.mappings("recording") == {
        "deezer": "https://www.deezer.com/track/123"
    }


async def test_lookup_coalesces_and_cache_is_bounded(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    lookup = AsyncMock(return_value={"relations": [relation(SPOTIFY)]})
    monkeypatch.setattr(streaming.musicbrainz, "lookup_recording_links", lookup)
    monkeypatch.setattr(streaming, "_CACHE_LIMIT", 2)
    responses = await asyncio.gather(*(streaming.mappings("same") for _ in range(10)))
    assert all(value == {"spotify": SPOTIFY} for value in responses)
    assert lookup.await_count == 1
    await streaming.mappings("second")
    await streaming.mappings("third")
    assert len(streaming._cache) == 2 and "same" not in streaming._cache
    assert not streaming._inflight


async def test_transient_failure_is_not_cached_and_saturated_queue_does_not_grow(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    lookup = AsyncMock(
        side_effect=[httpx.ReadTimeout("unavailable"), {"relations": []}]
    )
    monkeypatch.setattr(streaming.musicbrainz, "lookup_recording_links", lookup)
    assert await streaming.mappings("same") is None
    assert await streaming.mappings("same") == {}
    monkeypatch.setattr(streaming, "_INFLIGHT_LIMIT", 0)
    assert await streaming.mappings("new") is None
    assert lookup.await_count == 2


async def test_expired_mapping_is_refetched(monkeypatch: pytest.MonkeyPatch) -> None:
    streaming._cache["old"] = (-100000, {"spotify": SPOTIFY})
    lookup = AsyncMock(return_value={"relations": []})
    monkeypatch.setattr(streaming.musicbrainz, "lookup_recording_links", lookup)
    assert await streaming.mappings("old") == {}
    lookup.assert_awaited_once()
