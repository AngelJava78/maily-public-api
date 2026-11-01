"""Test data, written as the administrator of the disposable database (never as the read-only role)."""

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

_SUBSCRIPTION_DEFAULTS: dict[str, Any] = {
    "description": None,
    "subscription_type_id": 1,
    "monthly_price": Decimal("499.00"),
    "annual_price": Decimal("4990.00"),
    "trial_days": 0,
    "self_service": True,
    "status_id": 1,
    "other_features": [],
    "consulting_rooms_limit": 1,
    "doctors_limit": 1,
    "assistants_limit": 1,
    "new_patients_per_year_limit": 500,
    "clinics_limit": 1,
    "created_at": datetime(2026, 1, 1, tzinfo=UTC),
}


async def insert_subscription(connection: AsyncConnection, name: str, **fields: Any) -> int:
    values = {**_SUBSCRIPTION_DEFAULTS, **fields, "name": name}
    result = await connection.execute(
        text(
            "INSERT INTO subscriptions (name, description, subscription_type_id, monthly_price,"
            " annual_price, trial_days, self_service, status_id, other_features,"
            " consulting_rooms_limit, doctors_limit, assistants_limit, new_patients_per_year_limit,"
            " clinics_limit, created_at)"
            " VALUES (:name, :description, :subscription_type_id, :monthly_price, :annual_price,"
            " :trial_days, :self_service, :status_id, :other_features, :consulting_rooms_limit,"
            " :doctors_limit, :assistants_limit, :new_patients_per_year_limit, :clinics_limit,"
            " :created_at)"
            " RETURNING id"
        ),
        values,
    )
    return result.scalar_one()


async def insert_subscription_module(
    connection: AsyncConnection, subscription_id: int, module_key: str
) -> None:
    await connection.execute(
        text(
            "INSERT INTO subscription_modules (subscription_id, module_key)"
            " VALUES (:subscription_id, :module_key)"
        ),
        {"subscription_id": subscription_id, "module_key": module_key},
    )


async def insert_module(
    connection: AsyncConnection,
    key: str,
    name: str,
    *,
    sort_order: int = 0,
    status_id: int = 1,
    type_id: int = 2,
) -> None:
    await connection.execute(
        text(
            "INSERT INTO modules (key, name, sort_order, status_id, type_id)"
            " VALUES (:key, :name, :sort_order, :status_id, :type_id)"
        ),
        {"key": key, "name": name, "sort_order": sort_order, "status_id": status_id, "type_id": type_id},
    )
