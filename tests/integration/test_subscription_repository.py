"""`SubscriptionRepository` against PostgreSQL 18, reading as the read-only role (slow)."""

from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from src.repositories.subscription_repository import SubscriptionRepository
from tests.integration.seed import insert_subscription, insert_subscription_module


async def test_only_active_self_service_subscriptions(
    admin_engine: AsyncEngine, reader_session: AsyncSession
) -> None:
    async with admin_engine.begin() as connection:
        expected = None
        for status_id in (1, 2, 3, 4):
            for self_service in (True, False):
                created = await insert_subscription(
                    connection,
                    f"Plan {status_id} {self_service}",
                    status_id=status_id,
                    self_service=self_service,
                )
                if (status_id, self_service) == (1, True):
                    expected = created

    result = await SubscriptionRepository(reader_session).list_by_publication(
        status_id=1, self_service=True
    )

    assert [subscription.id for subscription in result] == [expected]


async def test_order_by_creation_then_identifier(
    admin_engine: AsyncEngine, reader_session: AsyncSession
) -> None:
    early = datetime(2026, 1, 1, tzinfo=UTC)
    late = datetime(2026, 6, 1, tzinfo=UTC)
    async with admin_engine.begin() as connection:
        newest = await insert_subscription(connection, "Nuevo", created_at=late)
        tie_a = await insert_subscription(connection, "Empate A", created_at=early)
        tie_b = await insert_subscription(connection, "Empate B", created_at=early)

    result = await SubscriptionRepository(reader_session).list_by_publication(1, True)

    assert [subscription.id for subscription in result] == [tie_a, tie_b, newest]


async def test_type_and_module_keys_are_loaded(
    admin_engine: AsyncEngine, reader_session: AsyncSession
) -> None:
    async with admin_engine.begin() as connection:
        with_modules = await insert_subscription(
            connection, "Con módulos", subscription_type_id=2, clinics_limit=5
        )
        for key in ("scheduling", "patients", "clinical_records"):
            await insert_subscription_module(connection, with_modules, key)
        await insert_subscription(connection, "Sin módulos", created_at=datetime(2027, 1, 1, tzinfo=UTC))

    result = await SubscriptionRepository(reader_session).list_by_publication(1, True)

    by_name = {subscription.name: subscription for subscription in result}
    assert by_name["Con módulos"].subscription_type.id == 2
    assert by_name["Con módulos"].subscription_type.name
    assert by_name["Con módulos"].module_keys == ["clinical_records", "patients", "scheduling"]
    assert by_name["Sin módulos"].module_keys == []
