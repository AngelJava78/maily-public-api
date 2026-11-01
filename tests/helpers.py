"""Shared helpers of the tests: configuration, ASGI client and subscription doubles."""

import asyncio
from collections.abc import AsyncIterator, Iterable
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace
from typing import Any

import httpx
from fastapi import FastAPI

from src.config import Settings

FRONTEND_ORIGIN = "https://frontend.example"

# The fields of every element of the catalog (FR-008) and the ones that must never appear (FR-010).
PUBLIC_SUBSCRIPTION_FIELDS = {
    "id",
    "name",
    "description",
    "subscription_type",
    "monthly_price",
    "annual_price",
    "trial_days",
    "module_keys",
    "modules",
    "other_features",
    "consulting_rooms_limit",
    "doctors_limit",
    "assistants_limit",
    "new_patients_per_year_limit",
    "clinics_limit",
}
FORBIDDEN_FIELDS = {
    "status",
    "status_id",
    "self_service",
    "clinics_count",
    "created_at",
    "updated_at",
    "subscription_type_id",
}


def make_settings(**overrides: Any) -> Settings:
    """A valid configuration that never reads `.env` nor reaches a real database."""
    values: dict[str, Any] = {
        "database_url": "postgresql+asyncpg://test:test@127.0.0.1:1/unreachable_test",
        "cors_allowed_origins": FRONTEND_ORIGIN,
        "catalog_cache_max_age_seconds": 300,
        "database_query_timeout_seconds": 3,
        "docs_enabled": True,
        "rate_limit_per_minute": 60,
        "trusted_proxy_hops": 0,
        "health_ready_timeout_seconds": 2,
        "app_commit_sha": None,
        "app_build_date": None,
        "app_environment": None,
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)  # type: ignore[call-arg]


@asynccontextmanager
async def api_client(app: FastAPI, client_ip: str = "127.0.0.1") -> AsyncIterator[httpx.AsyncClient]:
    """An HTTP client against the ASGI application; a 500 is answered, not raised in the test."""
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False, client=(client_ip, 50000))
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client


def make_subscription(**fields: Any) -> SimpleNamespace:
    """An object with the shape of the `Subscription` model (what the Repository returns)."""
    values: dict[str, Any] = {
        "id": 1,
        "name": "Consultorio",
        "description": "Para un médico que empieza a digitalizar su consultorio.",
        "subscription_type": SimpleNamespace(id=1, name="Individual"),
        "monthly_price": Decimal("499.00"),
        "annual_price": Decimal("4990.00"),
        "trial_days": 14,
        "module_keys": ["patients", "scheduling"],
        "other_features": ["Soporte por correo"],
        "consulting_rooms_limit": 1,
        "doctors_limit": 1,
        "assistants_limit": 1,
        "new_patients_per_year_limit": 500,
        "clinics_limit": 1,
        # Read by the Repository for the filter and the order; never published.
        "status_id": 1,
        "self_service": True,
        "created_at": datetime(2026, 1, 1, tzinfo=UTC),
    }
    values.update(fields)
    return SimpleNamespace(**values)


class FakeSubscriptions:
    """Double of `SubscriptionRepository`: returns `items`, or waits `delay` seconds, or raises `error`."""

    def __init__(
        self, items: Iterable[Any] = (), *, error: Exception | None = None, delay: float = 0
    ) -> None:
        self.items = list(items)
        self.error = error
        self.delay = delay
        self.calls: list[tuple[int, bool]] = []

    async def list_by_publication(self, status_id: int, self_service: bool) -> list[Any]:
        self.calls.append((status_id, self_service))
        if self.delay:
            await asyncio.sleep(self.delay)
        if self.error:
            raise self.error
        return list(self.items)


def with_catalog(
    app: FastAPI,
    subscriptions: "FakeSubscriptions | None" = None,
    modules: "FakeModules | None" = None,
) -> FastAPI:
    """Replace both Repositories of the catalog with doubles (an empty catalog by default)."""
    from src.dependencies import get_module_repository, get_subscription_repository

    subscription_repository = subscriptions or FakeSubscriptions([make_subscription()])
    module_repository = modules or FakeModules()
    app.dependency_overrides[get_subscription_repository] = lambda: subscription_repository
    app.dependency_overrides[get_module_repository] = lambda: module_repository
    return app


class FakeHealthRepository:
    """Double of `DatabaseHealthRepository`: waits `delay` seconds and/or raises `error`."""

    def __init__(self, *, error: BaseException | None = None, delay: float = 0) -> None:
        self.error = error
        self.delay = delay

    async def ping(self) -> None:
        if self.delay:
            await asyncio.sleep(self.delay)
        if self.error:
            raise self.error


def make_module(key: str, name: str, sort_order: int = 0) -> SimpleNamespace:
    """An object with the shape of the `Module` model (an Active module of type Clinic)."""
    return SimpleNamespace(key=key, name=name, sort_order=sort_order)


class FakeModules:
    """Double of `ModuleRepository`: `modules` are the Active modules of type Clinic of the catalog."""

    def __init__(self, modules: Iterable[Any] = ()) -> None:
        self.modules = list(modules)
        self.calls: list[tuple[set[str], int, int]] = []

    async def list_by_keys(self, keys: Iterable[str], status_id: int, type_id: int) -> list[Any]:
        wanted = set(keys)
        self.calls.append((wanted, status_id, type_id))
        return [module for module in self.modules if module.key in wanted]
