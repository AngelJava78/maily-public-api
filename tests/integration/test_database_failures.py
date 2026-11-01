"""A slow database answers 503 in time; a missing grant answers a generic 500 (FR-015, R5). Slow."""

import time

from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from src.main import create_app
from tests.helpers import api_client, make_settings

URL = "/api/v1/subscriptions"


async def test_a_blocked_query_is_503_within_the_limit(
    admin_engine: AsyncEngine, database_ready: str
) -> None:
    app = create_app(make_settings(database_url=database_ready, database_query_timeout_seconds=1))
    try:
        async with admin_engine.connect() as admin, api_client(app) as client:
            transaction = await admin.begin()
            await admin.execute(text("LOCK TABLE subscriptions IN ACCESS EXCLUSIVE MODE"))
            started = time.monotonic()
            blocked = await client.get(URL)
            elapsed = time.monotonic() - started
            await transaction.rollback()

            released = await client.get(URL)
    finally:
        await app.state.engine.dispose()

    assert blocked.status_code == 503
    assert blocked.json()["code"] == "service_unavailable"
    assert elapsed <= 2
    assert released.status_code == 200


async def test_a_missing_grant_is_a_generic_500(admin_engine: AsyncEngine, db_api: AsyncClient) -> None:
    async with admin_engine.begin() as connection:
        await connection.execute(
            text("REVOKE SELECT (clinics_limit) ON subscriptions FROM maily_public_api")
        )
    try:
        response = await db_api.get(URL)
    finally:
        async with admin_engine.begin() as connection:
            await connection.execute(
                text("GRANT SELECT (clinics_limit) ON subscriptions TO maily_public_api")
            )

    assert response.status_code == 500
    assert response.json() == {
        "code": "internal_error",
        "message": "Ocurrió un error inesperado. Inténtelo de nuevo más tarde.",
    }
    assert "permission" not in response.text
