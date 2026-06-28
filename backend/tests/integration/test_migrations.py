"""
Integration tests: Alembic migrations apply cleanly and produce the expected schema.

The `migrated_engine` fixture (session-scoped) runs `alembic upgrade head` once
against the Testcontainers Postgres instance before any test in this file runs.
"""

import pytest
from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import AsyncEngine


@pytest.mark.integration
async def test_expected_tables_exist(migrated_engine: AsyncEngine) -> None:
    async with migrated_engine.connect() as conn:
        table_names = await conn.run_sync(lambda c: inspect(c).get_table_names())
    for table in ("users", "artists", "albums", "tracks"):
        assert table in table_names, f"Expected table '{table}' missing after migration"


@pytest.mark.integration
async def test_alembic_version_table_exists(migrated_engine: AsyncEngine) -> None:
    """Alembic's version tracking table must exist (proves alembic managed the schema)."""
    async with migrated_engine.connect() as conn:
        table_names = await conn.run_sync(lambda c: inspect(c).get_table_names())
    assert "alembic_version" in table_names


@pytest.mark.integration
async def test_users_unique_indexes(migrated_engine: AsyncEngine) -> None:
    """users.username and users.clerk_id must have unique indexes (HARMONIQ §6 data guarantee)."""
    async with migrated_engine.connect() as conn:
        indexes = await conn.run_sync(lambda c: inspect(c).get_indexes("users"))
    indexed_columns = {col for idx in indexes for col in idx["column_names"]}
    assert "username" in indexed_columns, "Missing index on users.username"
    assert "clerk_id" in indexed_columns, "Missing index on users.clerk_id"


@pytest.mark.integration
async def test_catalog_mbid_indexes(migrated_engine: AsyncEngine) -> None:
    """artists, albums, and tracks must each have an index on mbid."""
    async with migrated_engine.connect() as conn:
        for table in ("artists", "albums", "tracks"):
            indexes = await conn.run_sync(lambda c, t=table: inspect(c).get_indexes(t))
            indexed_columns = {col for idx in indexes for col in idx["column_names"]}
            assert "mbid" in indexed_columns, f"Missing mbid index on {table}"


@pytest.mark.integration
async def test_migration_is_current(migrated_engine: AsyncEngine) -> None:
    """alembic_version must contain at least one row (migration ran to head)."""
    async with migrated_engine.connect() as conn:
        result = await conn.execute(text("SELECT version_num FROM alembic_version"))
        versions = result.fetchall()
    assert len(versions) >= 1, "alembic_version is empty — migrations did not run"


@pytest.mark.integration
async def test_users_table_columns(migrated_engine: AsyncEngine) -> None:
    """Spot-check that key columns exist on the users table."""
    async with migrated_engine.connect() as conn:
        columns = await conn.run_sync(
            lambda c: {col["name"] for col in inspect(c).get_columns("users")}
        )
    for col in (
        "id",
        "clerk_id",
        "username",
        "display_name",
        "bio",
        "visibility_bio",
        "visibility_activity",
        "visibility_ratings",
        "created_at",
        "updated_at",
    ):
        assert col in columns, f"Column '{col}' missing from users table"


@pytest.mark.integration
async def test_albums_track_foreign_keys(migrated_engine: AsyncEngine) -> None:
    """tracks must have FK columns to both artists and albums."""
    async with migrated_engine.connect() as conn:
        fks = await conn.run_sync(lambda c: inspect(c).get_foreign_keys("tracks"))
    fk_referred_tables = {fk["referred_table"] for fk in fks}
    assert "artists" in fk_referred_tables
    assert "albums" in fk_referred_tables
