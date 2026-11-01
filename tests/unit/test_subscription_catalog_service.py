"""Rules of the public catalog in the Service (FR-004 to FR-010, FR-015), with a Repository double."""

import logging
from decimal import Decimal
from types import SimpleNamespace

import pytest

from src.exceptions import ServiceUnavailableError
from src.repositories.errors import DatabaseUnavailableError
from src.services import subscription_catalog_service as catalog
from src.services.subscription_catalog_service import SubscriptionCatalogService
from tests.helpers import FakeModules, FakeSubscriptions, make_subscription


def make_service(
    subscriptions: FakeSubscriptions, timeout: float = 3, modules: FakeModules | None = None
) -> SubscriptionCatalogService:
    return SubscriptionCatalogService(
        subscriptions=subscriptions,
        modules=modules or FakeModules(),
        query_timeout_seconds=timeout,
    )


@pytest.fixture(autouse=True)
def fresh_warnings(monkeypatch: pytest.MonkeyPatch) -> None:
    # The warnings are logged once per process; every test starts as a new process.
    monkeypatch.setattr(catalog, "_once", catalog.OncePerProcess())


async def test_asks_only_for_active_self_service_subscriptions() -> None:
    subscriptions = FakeSubscriptions()

    await make_service(subscriptions).list_catalog()

    assert subscriptions.calls == [(1, True)]


async def test_keeps_the_order_of_the_repository_and_maps_every_public_field() -> None:
    first = make_subscription(id=7, name="Uno")
    second = make_subscription(
        id=3,
        name="Dos",
        description=None,
        subscription_type=SimpleNamespace(id=2, name="Empresarial"),
        monthly_price=Decimal("4500"),
        annual_price=Decimal("45000.5"),
        module_keys=[],
        other_features=[],
        clinics_limit=5,
    )

    result = await make_service(FakeSubscriptions([first, second])).list_catalog()

    assert [item.id for item in result] == [7, 3]
    assert result[1].model_dump(mode="json") == {
        "id": 3,
        "name": "Dos",
        "description": None,
        "subscription_type": {"id": 2, "name": "Empresarial"},
        "monthly_price": "4500.00",
        "annual_price": "45000.50",
        "trial_days": 14,
        "module_keys": [],
        "modules": [],
        "other_features": [],
        "consulting_rooms_limit": 1,
        "doctors_limit": 1,
        "assistants_limit": 1,
        "new_patients_per_year_limit": 500,
        "clinics_limit": 5,
    }


async def test_more_than_500_are_all_returned_and_warned_once(caplog: pytest.LogCaptureFixture) -> None:
    items = [
        make_subscription(id=number, name=f"Plan {number}", module_keys=[]) for number in range(1, 502)
    ]
    service = make_service(FakeSubscriptions(items))

    with caplog.at_level(logging.WARNING, logger=catalog.__name__):
        first = await service.list_catalog()
        second = await service.list_catalog()

    assert len(first) == len(second) == 501
    warnings = [record for record in caplog.records if record.levelno == logging.WARNING]
    assert len(warnings) == 1
    assert "501" in warnings[0].getMessage()


async def test_database_unavailable_becomes_service_unavailable() -> None:
    subscriptions = FakeSubscriptions(error=DatabaseUnavailableError("connection_error"))

    with pytest.raises(ServiceUnavailableError):
        await make_service(subscriptions).list_catalog()


async def test_a_read_slower_than_the_limit_becomes_service_unavailable() -> None:
    subscriptions = FakeSubscriptions(delay=1)

    with pytest.raises(ServiceUnavailableError):
        await make_service(subscriptions, timeout=0.05).list_catalog()


async def test_unexpected_errors_rise_untouched() -> None:
    subscriptions = FakeSubscriptions(error=RuntimeError("permission denied for table subscriptions"))

    with pytest.raises(RuntimeError):
        await make_service(subscriptions).list_catalog()
