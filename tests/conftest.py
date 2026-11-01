"""Fixtures of the tests.

The default run (`uv run pytest`) needs no database: the routes are tested against the real
application with the Repositories replaced by doubles. The tests that need a real PostgreSQL with the
mailySoft-DB schema use the fixtures of `tests/integration/conftest.py` and are marked `slow`
automatically (Principle V).
"""

import pytest
from fastapi import FastAPI

from src.config import Settings
from src.main import create_app
from tests.helpers import make_settings

# Fixtures that need a real PostgreSQL, directly or transitively (Principle V). Kept as a set of
# names, not a directory check, so a test anywhere that asks for one of them is marked.
_NEEDS_REAL_DATABASE = {
    "admin_engine",
    "database_ready",
    "reader_settings",
    "reader_engine",
    "reader_session",
    "db_api",
}


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Mark `slow` every test that needs a real PostgreSQL (Principle V).

    `pyproject.toml` excludes `slow` by default (`addopts = "-m 'not slow'"`), so the local loop of a
    feature (`/speckit-implement`) only runs what needs no database. The full suite is the gate before
    merging into `main`: `uv run pytest -m ""`.
    """
    for item in items:
        if _NEEDS_REAL_DATABASE.intersection(getattr(item, "fixturenames", ())):
            item.add_marker(pytest.mark.slow)


@pytest.fixture
def settings() -> Settings:
    return make_settings()


@pytest.fixture
def app(settings: Settings) -> FastAPI:
    return create_app(settings)
