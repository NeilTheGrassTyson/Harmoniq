"""
Test configuration: two-tier strategy per ADR 0007.

Unit tier  — no database; fast.
Integration tier — Postgres via Testcontainers, Alembic migrations applied
once per session, per-test transaction rollback for isolation.
"""

import asyncio
import os
import subprocess
import sys
from collections.abc import AsyncGenerator, Generator
from pathlib import Path

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from app.auth import get_current_user, get_optional_clerk_id
from app.database import get_db
from app.main import app

_BACKEND_DIR = Path(__file__).parent.parent


# ── Unit-tier: no database ────────────────────────────────────────────────────


@pytest_asyncio.fixture
async def http_client() -> AsyncGenerator[AsyncClient, None]:
    """Lightweight in-process ASGI client with no DB override. Unit-tier only."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac


# ── Integration-tier: container + migrations (session-scoped, sync) ───────────


@pytest.fixture(scope="session")
def postgres_container() -> Generator[str, None, None]:
    """Start a Postgres 16 container once per session; yield its asyncpg URL."""
    from testcontainers.postgres import PostgresContainer

    with PostgresContainer("postgres:16-alpine") as pg:
        sync_url = pg.get_connection_url()
        # testcontainers returns e.g. "postgresql+psycopg2://user:pass@host/db".
        # Don't assume the exact driver string — strip everything before "://"
        # and force asyncpg, so this still works if testcontainers' default
        # driver ever changes.
        _, rest = sync_url.split("://", 1)
        async_url = f"postgresql+asyncpg://{rest}"
        yield async_url


@pytest.fixture(scope="session")
def _run_migrations(postgres_container: str) -> None:
    """Run `alembic upgrade head` against the container DB once per session."""
    env = {
        **os.environ,
        "DATABASE_URL": postgres_container,
        # Provide stubs for required settings if the environment doesn't have them.
        "CLERK_JWKS_URL": os.environ.get(
            "CLERK_JWKS_URL",
            "https://example.clerk.accounts.dev/.well-known/jwks.json",
        ),
        "MUSICBRAINZ_USER_AGENT": os.environ.get(
            "MUSICBRAINZ_USER_AGENT",
            "Harmoniq/test ci@harmoniq.test",
        ),
    }
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=str(_BACKEND_DIR),
        env=env,
        check=True,
    )


@pytest.fixture(scope="session")
def migrated_engine(
    postgres_container: str, _run_migrations: None
) -> Generator[AsyncEngine, None, None]:
    """
    Async engine pointed at the migrated container DB.

    NullPool is required: pytest-asyncio opens a new event loop per async
    test by default, but asyncpg connections are bound to the loop that
    created them. A pooled connection reused across tests on different
    loops fails with "cannot perform operation: another operation is in
    progress" — NullPool disables reuse, so every connect() is fresh.
    """
    engine = create_async_engine(postgres_container, echo=False, poolclass=NullPool)
    yield engine
    asyncio.run(engine.dispose())


# ── Integration-tier: per-test session + clients (function-scoped, async) ─────


@pytest_asyncio.fixture
async def db_session(
    migrated_engine: AsyncEngine,
) -> AsyncGenerator[AsyncSession, None]:
    """
    Function-scoped session joined to an outer transaction that rolls back at
    teardown. Isolation: no re-migration or re-seeding between tests.

    SQLAlchemy's default join_transaction_mode="conditional_savepoint" means
    explicit session.commit() calls inside handlers release a SAVEPOINT rather
    than the outer transaction, so teardown rollback covers all writes.
    """
    conn = await migrated_engine.connect()
    await conn.begin()
    session = AsyncSession(bind=conn, expire_on_commit=False)
    try:
        yield session
    finally:
        await session.close()
        await conn.rollback()
        await conn.close()


def _db_override(session: AsyncSession):
    """Return a get_db override generator that yields the test session."""

    async def _override() -> AsyncGenerator[AsyncSession, None]:
        yield session

    return _override


@pytest_asyncio.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Integration ASGI client: get_db overridden to the test session, no auth."""
    app.dependency_overrides[get_db] = _db_override(db_session)
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def authed_client(
    db_session: AsyncSession,
) -> AsyncGenerator[tuple[AsyncClient, str], None]:
    """
    Integration ASGI client authenticated as a fixed test Clerk ID.
    Yields (client, clerk_id) so the test can create a matching user record.
    """
    clerk_id = "user_test_authed_fixture_001"

    async def _current_user() -> str:
        return clerk_id

    async def _optional_id() -> str | None:
        return clerk_id

    app.dependency_overrides[get_db] = _db_override(db_session)
    app.dependency_overrides[get_current_user] = _current_user
    app.dependency_overrides[get_optional_clerk_id] = _optional_id
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac, clerk_id
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def anon_client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Integration ASGI client with no auth (anonymous viewer)."""

    async def _optional_id() -> str | None:
        return None

    app.dependency_overrides[get_db] = _db_override(db_session)
    app.dependency_overrides[get_optional_clerk_id] = _optional_id
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac
    app.dependency_overrides.clear()
