"""The service is read-only by construction (Principle V of the constitution, FR-003)."""

from fastapi import FastAPI
from fastapi.routing import iter_route_contexts

# The documentation and the health contract are GET too, but the framework may add HEAD to the
# documentation routes: they are the only routes left out of this check.
EXCLUDED = {"/docs", "/openapi.json", "/health/live", "/health/ready", "/info"}


def test_every_route_accepts_only_get(app: FastAPI) -> None:
    checked = []
    # The effective routes: an included router is expanded with its prefix.
    for route in iter_route_contexts(app.routes):
        path = route.path
        methods = route.methods
        if path in EXCLUDED or methods is None:
            continue
        assert methods == {"GET"}, f"{path} accepts {sorted(methods)}"
        checked.append(path)

    assert "/api/v1/subscriptions" in checked


def test_the_openapi_has_only_get_and_no_security(app: FastAPI) -> None:
    schema = app.openapi()

    for path, operations in schema["paths"].items():
        assert set(operations) <= {"get"}, f"{path} has {sorted(operations)}"
    assert "securitySchemes" not in schema.get("components", {})
    assert "security" not in schema
