"""`GET /api/v1/subscriptions` end to end against PostgreSQL 18, as the read-only role (slow)."""

from datetime import UTC, datetime
from decimal import Decimal

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.helpers import FORBIDDEN_FIELDS
from tests.integration.seed import insert_subscription, insert_subscription_module


async def test_catalog_with_the_real_database(admin_engine: AsyncEngine, db_api: AsyncClient) -> None:
    async with admin_engine.begin() as connection:
        public = await insert_subscription(
            connection,
            "Consultorio",
            description="Para un médico que empieza.",
            monthly_price=Decimal("4500"),
            annual_price=Decimal("45000.00"),
            trial_days=14,
            other_features=["Soporte por correo", "Capacitación"],
            new_patients_per_year_limit=1500,
        )
        await insert_subscription_module(connection, public, "patients")
        await insert_subscription(connection, "Oculto", self_service=False)
        await insert_subscription(
            connection, "Inactivo", status_id=2, created_at=datetime(2027, 1, 1, tzinfo=UTC)
        )

    response = await db_api.get("/api/v1/subscriptions")

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    plan = body[0]
    assert not FORBIDDEN_FIELDS & set(plan)
    assert plan["id"] == public
    assert plan["name"] == "Consultorio"
    assert plan["description"] == "Para un médico que empieza."
    assert plan["subscription_type"]["id"] == 1
    assert plan["monthly_price"] == "4500.00"
    assert plan["annual_price"] == "45000.00"
    assert plan["trial_days"] == 14
    assert plan["module_keys"] == ["patients"]
    assert plan["other_features"] == ["Soporte por correo", "Capacitación"]
    assert plan["new_patients_per_year_limit"] == 1500
    assert plan["clinics_limit"] == 1
