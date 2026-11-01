"""Wiring for FastAPI: session → Repositories → Services (Principle I)."""

from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import Settings, build_info
from src.database.session import get_session
from src.repositories.database_health_repository import DatabaseHealthRepository
from src.repositories.module_repository import ModuleRepository
from src.repositories.subscription_repository import SubscriptionRepository
from src.services.health_service import HealthService
from src.services.subscription_catalog_service import SubscriptionCatalogService


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


SettingsDep = Annotated[Settings, Depends(get_settings)]
SessionDep = Annotated[AsyncSession, Depends(get_session)]


def get_subscription_repository(session: SessionDep) -> SubscriptionRepository:
    return SubscriptionRepository(session)


def get_module_repository(session: SessionDep) -> ModuleRepository:
    return ModuleRepository(session)


def get_subscription_catalog_service(
    subscriptions: Annotated[SubscriptionRepository, Depends(get_subscription_repository)],
    modules: Annotated[ModuleRepository, Depends(get_module_repository)],
    settings: SettingsDep,
) -> SubscriptionCatalogService:
    # Both Repositories share the request's session: one READ ONLY transaction, one snapshot.
    return SubscriptionCatalogService(
        subscriptions=subscriptions,
        modules=modules,
        query_timeout_seconds=settings.database_query_timeout_seconds,
    )


CatalogServiceDep = Annotated[SubscriptionCatalogService, Depends(get_subscription_catalog_service)]


def get_database_health_repository(session: SessionDep) -> DatabaseHealthRepository:
    return DatabaseHealthRepository(session)


def get_health_service(
    repository: Annotated[DatabaseHealthRepository, Depends(get_database_health_repository)],
    settings: SettingsDep,
) -> HealthService:
    return HealthService(
        repository,
        ready_timeout_seconds=settings.health_ready_timeout_seconds,
        build_info=build_info(settings),
    )


HealthServiceDep = Annotated[HealthService, Depends(get_health_service)]
