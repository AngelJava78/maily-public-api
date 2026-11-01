"""`modules` of every subscription: Active modules of type Clinic, with their name (FR-011, FR-012)."""

import logging

import pytest

from src.services import subscription_catalog_service as catalog
from src.services.subscription_catalog_service import SubscriptionCatalogService
from tests.helpers import FakeModules, FakeSubscriptions, make_module, make_subscription


@pytest.fixture(autouse=True)
def fresh_warnings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(catalog, "_once", catalog.OncePerProcess())


def make_service(subscriptions: list, modules: list) -> tuple[SubscriptionCatalogService, FakeModules]:
    module_repository = FakeModules(modules)
    service = SubscriptionCatalogService(
        subscriptions=FakeSubscriptions(subscriptions),
        modules=module_repository,
        query_timeout_seconds=3,
    )
    return service, module_repository


async def test_one_query_for_every_key_with_the_publication_criterion() -> None:
    service, modules = make_service(
        [
            make_subscription(id=1, module_keys=["patients", "scheduling"]),
            make_subscription(id=2, module_keys=["clinical_records", "patients"]),
        ],
        [],
    )

    await service.list_catalog()

    assert modules.calls == [({"patients", "scheduling", "clinical_records"}, 1, 2)]


async def test_modules_ordered_by_sort_order_then_key() -> None:
    service, _ = make_service(
        [make_subscription(module_keys=["clinical_records", "patients", "reminders", "scheduling"])],
        [
            make_module("patients", "Pacientes", sort_order=1),
            make_module("scheduling", "Agenda", sort_order=2),
            make_module("reminders", "Recordatorios", sort_order=2),
            make_module("clinical_records", "Expediente clínico", sort_order=3),
        ],
    )

    [plan] = await service.list_catalog()

    assert [module.model_dump() for module in plan.modules] == [
        {"key": "patients", "name": "Pacientes"},
        {"key": "reminders", "name": "Recordatorios"},
        {"key": "scheduling", "name": "Agenda"},
        {"key": "clinical_records", "name": "Expediente clínico"},
    ]
    assert plan.module_keys == ["clinical_records", "patients", "reminders", "scheduling"]


async def test_a_key_without_module_is_omitted_and_warned_once(caplog: pytest.LogCaptureFixture) -> None:
    service, _ = make_service(
        [make_subscription(id=3, module_keys=["legacy_reports", "patients"])],
        [make_module("patients", "Pacientes")],
    )

    with caplog.at_level(logging.WARNING, logger=catalog.__name__):
        [first] = await service.list_catalog()
        await service.list_catalog()

    assert first.module_keys == ["legacy_reports", "patients"]
    assert [module.key for module in first.modules] == ["patients"]
    warnings = [record.getMessage() for record in caplog.records if record.levelno == logging.WARNING]
    assert len(warnings) == 1
    assert "3" in warnings[0] and "legacy_reports" in warnings[0]


async def test_subscription_without_modules() -> None:
    service, _ = make_service([make_subscription(module_keys=[])], [make_module("patients", "Pacientes")])

    [plan] = await service.list_catalog()

    assert plan.module_keys == []
    assert plan.modules == []


def test_once_per_process_is_bounded() -> None:
    once = catalog.OncePerProcess(capacity=2)

    assert once.first_time("a") and once.first_time("b")
    assert not once.first_time("a")
    # Beyond its capacity it stops remembering (it may repeat a warning, it never grows).
    assert once.first_time("c") and once.first_time("c")
