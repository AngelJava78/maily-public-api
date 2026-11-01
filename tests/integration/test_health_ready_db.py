"""`/health/ready` with the real database, as the read-only role (slow)."""

import time

from httpx import AsyncClient

from src.main import create_app
from tests.helpers import api_client, make_settings


async def test_ready_with_the_real_database(db_api: AsyncClient) -> None:
    response = await db_api.get("/health/ready")

    assert response.status_code == 200
    assert response.json()["checks"][0]["status"] == "ok"


async def test_ready_without_a_database_is_503_in_time() -> None:
    # Port 1 of the local host: nothing listens there.
    app = create_app(
        make_settings(
            database_url="postgresql+asyncpg://maily_public_api:x@127.0.0.1:1/maily_test",
            health_ready_timeout_seconds=2,
        )
    )
    try:
        async with api_client(app) as client:
            started = time.monotonic()
            response = await client.get("/health/ready")
            elapsed = time.monotonic() - started
    finally:
        await app.state.engine.dispose()

    assert response.status_code == 503
    assert response.json()["checks"][0]["error"] in {"connection_error", "timeout"}
    assert elapsed <= 2.5
