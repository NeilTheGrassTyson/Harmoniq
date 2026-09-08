"""Disposable migration compatibility and actual Harmony query-plan audit."""

# Fixed local Alembic invocation; no shell or user-supplied commands.
# ruff: noqa: S603
import asyncio
import json
import os
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import event, text
from sqlalchemy.dialects import postgresql
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from testcontainers.postgres import PostgresContainer

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
NOW = datetime(2026, 9, 8, tzinfo=UTC)


async def seed(url: str) -> None:
    engine = create_async_engine(url)
    async with engine.begin() as connection:
        # Only columns available before this PR. The new defaults must also
        # allow an old application to insert accounts after the migration.
        await connection.execute(
            text("""
            INSERT INTO users (id, clerk_id, username, display_name)
            SELECT md5(i::text)::uuid, 'audit' || i, 'audit' || i, 'Audit'
            FROM generate_series(1, 100) AS i
        """)
        )
        await connection.execute(
            text("""
            INSERT INTO tracks (id, mbid, title, last_fetched_at)
            SELECT md5('track' || i)::uuid, md5('track' || i)::uuid::text,
                   'Audit', now()
            FROM generate_series(0, 101) AS i
        """)
        )
        await connection.execute(
            text("""
            INSERT INTO melodies (id, sender_id, recipient_id, track_id,
                                  status, created_at, responded_at)
            SELECT md5('melody' || i)::uuid,
                   md5(((i % 99) + 1)::text)::uuid, md5('100')::uuid,
                   md5('track' || (i / 99))::uuid,
                   (ARRAY['sent','received','accepted','opened','rejected'])
                       [(i % 5) + 1],
                   '2026-09-08'::timestamptz - (i % 240) * interval '1 day',
                   CASE WHEN i % 5 >= 2 THEN '2026-09-08'::timestamptz END
            FROM generate_series(1, 10000) AS i
        """)
        )
    await engine.dispose()


async def inspect(url: str) -> None:
    from app.services.harmony import get_harmony

    engine = create_async_engine(url)
    async with engine.begin() as connection:
        assert (
            await connection.execute(
                text("""
            SELECT count(*) FROM users WHERE visibility_harmony = 'private'
        """)
            )
        ).scalar_one() == 100
        assert (
            await connection.execute(
                text("""
            SELECT count(*) FROM melodies
            WHERE reaction IS NULL AND reacted_at IS NULL
        """)
            )
        ).scalar_one() == 10000
        assert (
            await connection.execute(
                text("""
            SELECT count(*) FROM melodies
            WHERE status IN ('accepted','opened','rejected')
                AND responded_at IS NOT NULL
        """)
            )
        ).scalar_one() == 6000
        await connection.execute(
            text("""
            INSERT INTO users (id, clerk_id, username, display_name)
            VALUES (md5('old-write')::uuid, 'old-write', 'old-write', 'Old write')
        """)
        )
        assert (
            await connection.execute(
                text("""
            SELECT visibility_harmony FROM users WHERE clerk_id = 'old-write'
        """)
            )
        ).scalar_one() == "private"
        # Simulate an old application changing status on a reacted row: its
        # UPDATE cannot erase the new opinion or timestamps during rollback.
        await connection.execute(
            text("""
            UPDATE melodies SET reaction = 'not_for_me', reacted_at = now()
            WHERE id = md5('melody1')::uuid
        """)
        )
        await connection.execute(
            text("""
            UPDATE melodies SET status = 'opened', responded_at = now()
            WHERE id = md5('melody1')::uuid
        """)
        )
        assert (
            await connection.execute(
                text("""
            SELECT reaction FROM melodies WHERE id = md5('melody1')::uuid
        """)
            )
        ).scalar_one() == "not_for_me"
        await connection.execute(
            text(
                "UPDATE users SET visibility_harmony = 'public' "
                "WHERE username = 'audit1'"
            )
        )
        await connection.execute(text("ANALYZE users"))
        await connection.execute(text("ANALYZE melodies"))

    statements = []

    def capture(conn, clause, multiparams, params, execution_options):
        compiled = str(
            clause.compile(
                dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}
            )
        )
        if "FROM melodies" in compiled:
            statements.append(compiled)

    event.listen(engine.sync_engine, "before_execute", capture)
    try:
        async with AsyncSession(engine) as session:
            owner = await get_harmony(session, "audit1", "audit1", now=NOW)
            assert owner and owner.kind == "owner" and owner.resolved_count > 0
            shared = await get_harmony(session, "audit1", None, now=NOW)
            assert shared and shared.kind == "shared"
    finally:
        event.remove(engine.sync_engine, "before_execute", capture)
    assert len(statements) == 2
    print(
        "Migration: 100 synthetic users private; 10,000 synthetic pre-migration "
        "rows retained; "
        "old inserts/status updates compatible."
    )
    async with engine.connect() as connection:
        for label, statement in zip(("owner", "shared"), statements, strict=True):
            plan = (
                await connection.execute(
                    text("EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) " + statement)
                )
            ).scalar_one()
            print(label + " aggregate: " + json.dumps(plan))
    await engine.dispose()


def main() -> None:
    # The URL always comes from this new container, never DATABASE_URL or .env.
    with PostgresContainer("postgres:16-alpine") as container:
        url = (
            "postgresql+asyncpg://" + container.get_connection_url().split("://", 1)[1]
        )
        os.environ.update(
            {
                "DATABASE_URL": url,
                "CLERK_JWKS_URL": "https://example.clerk.accounts.dev/.well-known/jwks.json",
                "MUSICBRAINZ_USER_AGENT": "Harmoniq/audit (ci@harmoniq.test)",
                "APP_ENV": "test",
            }
        )
        for revision in ("f8a9b0c1d2e3", "head"):
            subprocess.run(
                [sys.executable, "-m", "alembic", "upgrade", revision],
                cwd=ROOT / "backend",
                check=True,
            )
            if revision != "head":
                asyncio.run(seed(url))
        asyncio.run(inspect(url))


if __name__ == "__main__":
    main()
