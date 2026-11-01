"""Dependencies flow one way (Principle I) and the service calls no other API (Principle IX)."""

import ast
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[2] / "src"

# Layer → packages of `src` it must never import.
FORBIDDEN = {
    "models": ("src.dtos", "src.services", "src.repositories", "src.routers"),
    "repositories": ("src.services", "src.routers", "src.dtos"),
    "services": ("src.routers",),
    "database": ("src.services", "src.repositories", "src.routers"),
    "dtos": ("src.services", "src.repositories", "src.routers", "src.models"),
}
# Not a dependency of the service: no HTTP client, no migrations (Principles VI and IX).
FORBIDDEN_EVERYWHERE = ("httpx", "requests", "alembic")


def imports_of(path: Path) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


def modules_of(layer: str) -> list[Path]:
    return sorted((SRC / layer).glob("*.py"))


@pytest.mark.parametrize("layer", sorted(FORBIDDEN))
def test_a_lower_layer_never_imports_an_upper_one(layer: str) -> None:
    for path in modules_of(layer):
        for name in imports_of(path):
            assert not name.startswith(FORBIDDEN[layer]), f"src/{layer}/{path.name} imports {name}"


def test_no_http_client_nor_migrations_in_the_service() -> None:
    for path in sorted(SRC.rglob("*.py")):
        for name in imports_of(path):
            root = name.split(".")[0]
            assert root not in FORBIDDEN_EVERYWHERE, f"{path.relative_to(SRC)} imports {name}"
