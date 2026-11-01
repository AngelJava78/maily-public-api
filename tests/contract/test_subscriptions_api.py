"""Contract of `GET /api/v1/subscriptions` (contracts/subscriptions-catalog.md) with a Repository double."""

from decimal import Decimal

import pytest
from fastapi import FastAPI

from src.dependencies import get_module_repository, get_subscription_repository
from src.main import create_app
from src.repositories.errors import DatabaseUnavailableError
from tests.helpers import (
    FORBIDDEN_FIELDS,
    PUBLIC_SUBSCRIPTION_FIELDS,
    FakeModules,
    FakeSubscriptions,
    api_client,
    make_settings,
    make_subscription,
)

URL = "/api/v1/subscriptions"


def with_repository(app: FastAPI, repository: FakeSubscriptions) -> FastAPI:
    # An empty module catalog: the module names are covered by test_subscriptions_modules_api.py.
    app.dependency_overrides[get_subscription_repository] = lambda: repository
    app.dependency_overrides[get_module_repository] = lambda: FakeModules()
    return app


@pytest.fixture
def two_plans() -> FakeSubscriptions:
    return FakeSubscriptions(
        [
            make_subscription(id=1, name="Consultorio"),
            make_subscription(
                id=3,
                name="Profesional",
                description=None,
                monthly_price=Decimal("1299"),
                annual_price=Decimal("12990.00"),
            ),
        ]
    )


async def test_catalog_without_token(app: FastAPI, two_plans: FakeSubscriptions) -> None:
    async with api_client(with_repository(app, two_plans)) as client:
        response = await client.get(URL)

    assert response.status_code == 200
    body = response.json()
    assert [item["id"] for item in body] == [1, 3]
    for item in body:
        assert set(item) == PUBLIC_SUBSCRIPTION_FIELDS
        assert not FORBIDDEN_FIELDS & set(item)
    assert body[1]["description"] is None
    assert body[1]["monthly_price"] == "1299.00"
    assert body[1]["annual_price"] == "12990.00"
    assert body[0]["subscription_type"] == {"id": 1, "name": "Individual"}


async def test_empty_catalog_is_an_empty_list(app: FastAPI) -> None:
    async with api_client(with_repository(app, FakeSubscriptions())) as client:
        response = await client.get(URL)

    assert response.status_code == 200
    assert response.json() == []


async def test_public_cache_and_vary_origin(app: FastAPI, two_plans: FakeSubscriptions) -> None:
    async with api_client(with_repository(app, two_plans)) as client:
        response = await client.get(URL)

    assert response.headers["cache-control"] == "public, max-age=300"
    assert "Origin" in [value.strip() for value in response.headers["vary"].split(",")]


async def test_cache_time_is_configurable(two_plans: FakeSubscriptions) -> None:
    app = create_app(make_settings(catalog_cache_max_age_seconds=120))

    async with api_client(with_repository(app, two_plans)) as client:
        response = await client.get(URL)

    assert response.headers["cache-control"] == "public, max-age=120"


async def test_credentials_and_query_parameters_are_ignored(
    app: FastAPI, two_plans: FakeSubscriptions
) -> None:
    async with api_client(with_repository(app, two_plans)) as client:
        plain = await client.get(URL)
        with_credentials = await client.get(
            URL, headers={"Authorization": "Bearer x", "Cookie": "a=b"}, params={"page": 2}
        )

    assert with_credentials.status_code == 200
    assert with_credentials.json() == plain.json()


async def test_database_unavailable_is_503_without_details(app: FastAPI) -> None:
    repository = FakeSubscriptions(error=DatabaseUnavailableError("connection_error"))

    async with api_client(with_repository(app, repository)) as client:
        response = await client.get(URL)

    assert response.status_code == 503
    assert response.json() == {
        "code": "service_unavailable",
        "message": (
            "El catálogo de suscripciones no está disponible por el momento. "
            "Inténtelo de nuevo más tarde."
        ),
    }
    assert response.headers["cache-control"] == "no-store"
    assert "127.0.0.1" not in response.text
    assert "postgresql" not in response.text


async def test_unexpected_error_is_500(app: FastAPI) -> None:
    repository = FakeSubscriptions(error=RuntimeError("permission denied for table subscriptions"))

    async with api_client(with_repository(app, repository)) as client:
        response = await client.get(URL)

    assert response.status_code == 500
    assert response.json()["code"] == "internal_error"
    assert "permission" not in response.text
    assert response.headers["cache-control"] == "no-store"
