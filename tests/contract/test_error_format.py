"""Uniform error body, without details and never cached (FR-013, FR-014, FR-017)."""

from fastapi import FastAPI

from tests.helpers import api_client


async def test_unknown_route_is_not_found(app: FastAPI) -> None:
    async with api_client(app) as client:
        response = await client.get("/api/v1/subscriptions/1")

    assert response.status_code == 404
    assert response.json() == {"code": "not_found", "message": "No existe el recurso solicitado."}
    assert response.headers["cache-control"] == "no-store"


async def test_unexpected_error_is_generic(app: FastAPI) -> None:
    async def explode() -> None:
        raise RuntimeError("secreto de db.internal")

    app.add_api_route("/explode", explode, methods=["GET"])

    async with api_client(app) as client:
        response = await client.get("/explode")

    assert response.status_code == 500
    assert response.json() == {
        "code": "internal_error",
        "message": "Ocurrió un error inesperado. Inténtelo de nuevo más tarde.",
    }
    assert response.headers["cache-control"] == "no-store"
    assert "secreto" not in response.text
    assert "db.internal" not in response.text
