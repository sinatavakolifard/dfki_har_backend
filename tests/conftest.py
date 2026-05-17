"""Test fixtures.

Tests that need a database expect a Postgres instance reachable at
`TEST_DATABASE_URL`. The easiest way is to bring the dev stack up
(`docker compose up -d db`) and point the tests at it:

    export TEST_DATABASE_URL=postgresql+asyncpg://har:har-dev-password@localhost:5432/har_test
    createdb -h localhost -U har har_test   # one-time
    pytest

Tests that hit the DB will be skipped automatically if the variable is not
set so a bare `pytest` run still exercises the auth / schema-only checks.
"""
from __future__ import annotations

import os

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

os.environ.setdefault("HAR_API_KEY", "test-api-key")
TEST_DB_URL = os.environ.get("TEST_DATABASE_URL")
if TEST_DB_URL:
    os.environ["DATABASE_URL"] = TEST_DB_URL


API_KEY = os.environ["HAR_API_KEY"]


@pytest_asyncio.fixture
async def client() -> AsyncClient:
    from app.main import app  # imported here so env vars are set first

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.fixture
def auth_headers() -> dict[str, str]:
    return {"X-API-Key": API_KEY}


requires_db = pytest.mark.skipif(
    TEST_DB_URL is None,
    reason="TEST_DATABASE_URL not set; skipping DB-backed test",
)


@pytest_asyncio.fixture
async def db_schema():
    """Create schema once per test, tear down after."""
    from app.db import Base, get_engine

    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
