"""Routes of the health contract v1 (contracts/health-v1.md), with a Repository double."""

from fastapi import FastAPI

from src.dependencies import get_database_health_repository
from src.main import create_app
from src.repositories.errors import DatabaseUnavailableError
from tests.helpers import FakeHealthRepository, api_client, make_settings, with_catalog


def with_health(app: FastAPI, repository: FakeHealthRepository) -> FastAPI:
    app.dependency_overrides[get_database_health_repository] = lambda: repository
    return app


async def test_live(app: FastAPI) -> None:
    async with api_client(app) as client:
        response = await client.get("/health/live")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert response.headers["cache-control"] == "no-store"


async def test_ready_ok(app: FastAPI) -> None:
    async with api_client(with_health(app, FakeHealthRepository())) as client:
        response = await client.get("/health/ready")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["checks"][0] | {"latency_ms": 0} == {
        "name": "database",
        "status": "ok",
        "latency_ms": 0,
        "error": None,
    }
    assert response.headers["cache-control"] == "no-store"


async def test_ready_unavailable(app: FastAPI) -> None:
    repository = FakeHealthRepository(error=DatabaseUnavailableError("connection_error"))

    async with api_client(with_health(app, repository)) as client:
        response = await client.get("/health/ready")

    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "unavailable"
    assert set(body["checks"][0]) == {"name", "status", "latency_ms", "error"}
    assert (body["checks"][0]["status"], body["checks"][0]["error"]) == ("error", "connection_error")
    assert response.headers["cache-control"] == "no-store"


async def test_info(app: FastAPI) -> None:
    async with api_client(app) as client:
        response = await client.get("/info")

    assert response.status_code == 200
    assert response.json() == {
        "service": "maily-public-api",
        "version": "1.0.0",
        "commit": "unknown",
        "build_date": "unknown",
        "environment": "unknown",
    }
    assert response.headers["cache-control"] == "no-store"


async def test_info_with_build_variables() -> None:
    app = create_app(
        make_settings(
            app_commit_sha="abcdef1", app_build_date="2026-11-01T18:00:00Z", app_environment="dev"
        )
    )

    async with api_client(app) as client:
        body = (await client.get("/info")).json()

    assert (body["commit"], body["build_date"], body["environment"]) == (
        "abcdef1",
        "2026-11-01T18:00:00Z",
        "dev",
    )


async def test_health_is_not_rate_limited() -> None:
    app = with_health(
        with_catalog(create_app(make_settings(rate_limit_per_minute=1))), FakeHealthRepository()
    )

    async with api_client(app) as client:
        assert (await client.get("/api/v1/subscriptions")).status_code == 200
        assert (await client.get("/api/v1/subscriptions")).status_code == 429
        statuses = {
            (await client.get(path)).status_code
            for path in ("/health/live", "/health/ready", "/info")
            for _ in range(5)
        }

    assert statuses == {200}


async def test_credentials_are_ignored(app: FastAPI) -> None:
    async with api_client(app) as client:
        response = await client.get("/health/live", headers={"Authorization": "Bearer x"})

    assert response.status_code == 200
