"""Fixtures of the `slow` tests: a disposable PostgreSQL 18 with the mailySoft-DB schema (research R11).

The schema never comes from DDL written in this repository (Principle VI): it is mailySoft-DB's
`schema/current_schema.sql` plus the repeatable catalogs the catalog needs. The read-only role is
created with `docs/database/read-only-role.sql`, the same file proposed to mailySoft-DB, and the tests
read as that role, so a query outside its grants fails here and not in production. The data is seeded
as the administrator.
"""

import secrets
from collections.abc import AsyncIterator
from pathlib import Path

import asyncpg
import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import AsyncClient
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import text
from sqlalchemy.engine import URL, make_url
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine

from src.config import Settings
from src.database.session import create_engine, create_session_factory
from src.main import create_app
from tests.helpers import api_client, make_settings

ROOT = Path(__file__).resolve().parents[2]
READ_ONLY_ROLE_SQL = ROOT / "docs" / "database" / "read-only-role.sql"
READER_ROLE = "maily_public_api"
CATALOGS = (
    "R__40_cat_subscription_statuses.sql",
    "R__40_cat_subscription_types.sql",
    "R__40_cat_module_statuses.sql",
    "R__40_cat_module_types.sql",
)


class _TestEnvironment(BaseSettings):
    """The variables only the tests read (contracts/environment.md, «Solo pruebas»)."""

    test_database_url: str | None = None
    mailysoft_db_dir: Path = ROOT.parent / "mailySoft-DB"

    model_config = SettingsConfigDict(env_file=ROOT / ".env", extra="ignore", env_ignore_empty=True)


def _asyncpg_dsn(url: URL) -> str:
    return url.set(drivername="postgresql").render_as_string(hide_password=False)


@pytest.fixture(scope="session")
def admin_url() -> URL:
    environment = _TestEnvironment()
    if not environment.test_database_url:
        pytest.fail(
            "TEST_DATABASE_URL is not set: start `docker compose --profile test up -d db-test` and set "
            "it (see .env.example)"
        )
    url = make_url(environment.test_database_url)
    if not (url.database or "").endswith("_test"):
        pytest.fail("The database of TEST_DATABASE_URL must end in `_test`: the tests drop its schema")
    return url


@pytest_asyncio.fixture(scope="session")
async def database_ready(admin_url: URL) -> str:
    """Rebuild the schema from mailySoft-DB and create the read-only role; return its URL."""
    mailysoft_db = _TestEnvironment().mailysoft_db_dir
    schema_file = mailysoft_db / "schema" / "current_schema.sql"
    if not schema_file.is_file():
        pytest.fail(
            f"mailySoft-DB was not found at {mailysoft_db}: clone it next to this repository or set "
            "MAILYSOFT_DB_DIR"
        )
    password = secrets.token_urlsafe(24)

    # A dedicated connection: the schema dump empties `search_path` for the rest of the session.
    connection = await asyncpg.connect(_asyncpg_dsn(admin_url))
    try:
        await connection.execute("DROP SCHEMA IF EXISTS public CASCADE; CREATE SCHEMA public;")
        await connection.execute(schema_file.read_text(encoding="utf-8"))
        for catalog in CATALOGS:
            path = mailysoft_db / "migrations" / "repeatable" / catalog
            await connection.execute(path.read_text(encoding="utf-8"))
        ready = await connection.fetchval(
            "SELECT to_regclass('public.subscription_modules') IS NOT NULL AND EXISTS ("
            " SELECT 1 FROM information_schema.columns WHERE table_schema = 'public'"
            " AND table_name = 'subscriptions' AND column_name = 'clinics_limit')"
        )
        if not ready:
            pytest.fail(
                "The mailySoft-DB schema has no `subscription_modules` or `subscriptions.clinics_limit` "
                "yet (FR-027 of specs/001-public-subscriptions-catalog)"
            )
        await connection.execute(READ_ONLY_ROLE_SQL.read_text(encoding="utf-8"))
        # token_urlsafe has no quotes; ALTER ROLE takes no parameters.
        await connection.execute(f"ALTER ROLE {READER_ROLE} PASSWORD '{password}'")
    finally:
        await connection.close()

    return admin_url.set(username=READER_ROLE, password=password).render_as_string(hide_password=False)


@pytest_asyncio.fixture(scope="session")
async def admin_engine(admin_url: URL, database_ready: str) -> AsyncIterator[AsyncEngine]:
    engine = create_async_engine(admin_url)
    yield engine
    await engine.dispose()


@pytest.fixture(scope="session")
def reader_settings(database_ready: str) -> Settings:
    return make_settings(database_url=database_ready)


@pytest_asyncio.fixture(scope="session")
async def reader_engine(reader_settings: Settings) -> AsyncIterator[AsyncEngine]:
    engine = create_engine(reader_settings)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def reader_session(reader_engine: AsyncEngine) -> AsyncIterator[AsyncSession]:
    async with create_session_factory(reader_engine)() as session:
        yield session


@pytest_asyncio.fixture
async def db_api(reader_settings: Settings) -> AsyncIterator[AsyncClient]:
    app: FastAPI = create_app(reader_settings)
    async with api_client(app) as client:
        yield client
    await app.state.engine.dispose()


@pytest_asyncio.fixture(autouse=True)
async def _empty_catalog(admin_engine: AsyncEngine) -> None:
    """Every test starts without subscriptions or modules (the catalogs stay)."""
    async with admin_engine.begin() as connection:
        await connection.execute(
            text("TRUNCATE subscription_modules, subscriptions, modules RESTART IDENTITY CASCADE")
        )
