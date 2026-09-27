import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock

import httpx
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.catalog import Artist, Track
from app.services import streaming

pytestmark = pytest.mark.integration


async def test_public_links_are_separate_from_catalog_and_survive_upstream_failure(
    db_session: AsyncSession, anon_client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    artist = Artist(
        mbid=str(uuid.uuid4()), name="A & B", last_fetched_at=datetime.now(UTC)
    )
    db_session.add(artist)
    await db_session.flush()
    track = Track(
        mbid=str(uuid.uuid4()),
        title="青い空 / Song",
        artist_id=artist.id,
        last_fetched_at=datetime.now(UTC),
    )
    db_session.add(track)
    await db_session.flush()
    lookup = AsyncMock(side_effect=httpx.ReadTimeout("unavailable"))
    monkeypatch.setattr(streaming.musicbrainz, "lookup_recording_links", lookup)
    streaming._cache.clear()
    response = await anon_client.get(f"/api/v1/streaming/{track.mbid}")
    assert response.status_code == 200
    payload = response.json()
    assert payload["mapping_status"] == "unavailable"
    assert len(payload["links"]) == 6 and all(
        link["kind"] == "search" for link in payload["links"]
    )
    assert response.headers["cache-control"] == "no-store"
    catalog = await anon_client.get(f"/api/v1/catalog/tracks/{track.mbid}")
    assert catalog.status_code == 200 and catalog.json()["title"] == track.title
    lookup.side_effect = None
    lookup.return_value = {
        "relations": [
            {
                "target-type": "url",
                "type": "streaming",
                "url": {
                    "resource": "https://open.spotify.com/track/0123456789abcdefghijkl"
                },
            }
        ]
    }
    response = await anon_client.get(f"/api/v1/streaming/{track.mbid}")
    assert response.status_code == 200
    assert response.json()["links"][0]["kind"] == "exact"
    assert response.headers["cache-control"] == "public, max-age=300"
    monkeypatch.setattr(settings, "streaming_links_enabled", False)
    assert (await anon_client.get(f"/api/v1/streaming/{track.mbid}")).status_code == 404
    assert (
        await anon_client.get(f"/api/v1/catalog/tracks/{track.mbid}")
    ).status_code == 200
    streaming._cache.clear()


async def test_invalid_or_unknown_ids_never_trigger_provider_requests(
    anon_client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    lookup = AsyncMock()
    monkeypatch.setattr(streaming.musicbrainz, "lookup_recording_links", lookup)
    assert (
        await anon_client.get("/api/v1/streaming/not-a-recording-id")
    ).status_code == 422
    assert (
        await anon_client.get(f"/api/v1/streaming/{uuid.uuid4()}")
    ).status_code == 404
    lookup.assert_not_awaited()
