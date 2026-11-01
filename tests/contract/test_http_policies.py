"""Methods, CORS and the limit per IP (contracts/http-policies.md, FR-003, FR-018, FR-019)."""

import pytest
from fastapi import FastAPI

from src.main import create_app
from tests.helpers import FRONTEND_ORIGIN, api_client, make_settings, with_catalog

URL = "/api/v1/subscriptions"


@pytest.mark.parametrize("method", ["POST", "PUT", "PATCH", "DELETE", "HEAD"])
async def test_only_get(app: FastAPI, method: str) -> None:
    async with api_client(with_catalog(app)) as client:
        response = await client.request(method, URL)

    assert response.status_code == 405
    assert response.headers["allow"] == "GET"
    assert response.headers["cache-control"] == "no-store"
    if method != "HEAD":
        assert response.json() == {
            "code": "method_not_allowed",
            "message": "Esta operación no está permitida: el servicio es de solo lectura.",
        }


async def test_cors_for_an_allowed_origin(app: FastAPI) -> None:
    async with api_client(with_catalog(app)) as client:
        response = await client.get(URL, headers={"Origin": FRONTEND_ORIGIN})

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == FRONTEND_ORIGIN
    assert "access-control-allow-credentials" not in response.headers


async def test_no_cors_for_another_origin(app: FastAPI) -> None:
    async with api_client(with_catalog(app)) as client:
        response = await client.get(URL, headers={"Origin": "https://otro.example"})

    # The catalog is public: a client that is not a browser still gets it.
    assert response.status_code == 200
    assert "access-control-allow-origin" not in response.headers


async def test_preflight_allows_only_get(app: FastAPI) -> None:
    async with api_client(with_catalog(app)) as client:
        allowed = await client.options(
            URL, headers={"Origin": FRONTEND_ORIGIN, "Access-Control-Request-Method": "GET"}
        )
        refused = await client.options(
            URL, headers={"Origin": FRONTEND_ORIGIN, "Access-Control-Request-Method": "DELETE"}
        )

    assert allowed.status_code == 200
    assert allowed.headers["access-control-allow-origin"] == FRONTEND_ORIGIN
    assert allowed.headers["access-control-allow-methods"] == "GET"
    assert "access-control-allow-credentials" not in allowed.headers
    assert refused.status_code == 400
    assert "DELETE" not in refused.headers.get("access-control-allow-methods", "")


async def test_the_limit_per_ip() -> None:
    app = with_catalog(create_app(make_settings(rate_limit_per_minute=3)))

    async with api_client(app, client_ip="203.0.113.9") as client:
        passed = [(await client.get(URL)).status_code for _ in range(3)]
        limited = await client.get(URL)
    async with api_client(app, client_ip="198.51.100.7") as other:
        other_ip = await other.get(URL)

    assert passed == [200, 200, 200]
    assert limited.status_code == 429
    assert limited.json() == {
        "code": "rate_limit_exceeded",
        "message": "Se hicieron demasiadas solicitudes. Espere un momento e inténtelo de nuevo.",
    }
    assert int(limited.headers["retry-after"]) >= 1
    assert limited.headers["cache-control"] == "no-store"
    assert other_ip.status_code == 200


async def test_forwarded_ips_behind_a_trusted_proxy() -> None:
    app = with_catalog(create_app(make_settings(rate_limit_per_minute=1, trusted_proxy_hops=1)))
    first = {"X-Forwarded-For": "1.2.3.4, 203.0.113.9"}
    second = {"X-Forwarded-For": "1.2.3.4, 198.51.100.7"}

    async with api_client(app) as client:
        assert (await client.get(URL, headers=first)).status_code == 200
        assert (await client.get(URL, headers=first)).status_code == 429
        # Same connection (the proxy), another client: its own bucket. The left entry is ignored.
        assert (await client.get(URL, headers=second)).status_code == 200


async def test_zero_disables_the_limit() -> None:
    app = with_catalog(create_app(make_settings(rate_limit_per_minute=0)))

    async with api_client(app) as client:
        statuses = {(await client.get(URL)).status_code for _ in range(100)}

    assert statuses == {200}
