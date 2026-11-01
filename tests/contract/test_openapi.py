"""Published documentation in Spanish, switchable off (FR-021, FR-022)."""

from fastapi import FastAPI

from src import VERSION
from src.main import create_app
from tests.helpers import api_client, make_settings

NOT_FOUND = {"code": "not_found", "message": "No existe el recurso solicitado."}


def test_info_and_description(app: FastAPI) -> None:
    schema = app.openapi()

    assert schema["info"]["title"] == "MailySoft Public API"
    assert schema["info"]["version"] == VERSION == "1.0.0"
    assert "solo lectura" in schema["info"]["description"]
    assert {tag["name"] for tag in schema["tags"]} == {"subscriptions", "Salud"}


def test_catalog_operation_is_documented(app: FastAPI) -> None:
    operation = app.openapi()["paths"]["/api/v1/subscriptions"]["get"]

    assert operation["operationId"] == "list_subscriptions"
    assert operation["tags"] == ["subscriptions"]
    assert "Activas de autoservicio" in operation["description"]
    assert set(operation["responses"]) == {"200", "405", "429", "500", "503"}
    assert operation["responses"]["200"]["content"]["application/json"]["examples"]
    for status in ("405", "429", "500", "503"):
        content = operation["responses"][status]["content"]["application/json"]
        assert content["schema"]["$ref"] == "#/components/schemas/ErrorResponse"
        assert content["examples"]
    assert "Retry-After" in operation["responses"]["429"]["headers"]


def test_health_routes_are_documented(app: FastAPI) -> None:
    paths = app.openapi()["paths"]

    for path in ("/health/live", "/health/ready", "/info"):
        assert paths[path]["get"]["tags"] == ["Salud"]
    assert "503" in paths["/health/ready"]["get"]["responses"]


async def test_docs_published_and_no_redoc(app: FastAPI) -> None:
    async with api_client(app) as client:
        docs = await client.get("/docs")
        redoc = await client.get("/redoc")
        openapi = await client.get("/openapi.json")

    assert docs.status_code == 200
    assert "text/html" in docs.headers["content-type"]
    assert openapi.status_code == 200
    assert redoc.status_code == 404
    assert redoc.json() == NOT_FOUND


async def test_docs_can_be_switched_off() -> None:
    app = create_app(make_settings(docs_enabled=False))

    async with api_client(app) as client:
        docs = await client.get("/docs")
        openapi = await client.get("/openapi.json")

    assert (docs.status_code, openapi.status_code) == (404, 404)
    assert docs.json() == openapi.json() == NOT_FOUND
