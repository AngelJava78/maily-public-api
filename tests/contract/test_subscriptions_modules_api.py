"""`modules` in the contract of the catalog (contracts/subscriptions-catalog.md, second example)."""

from decimal import Decimal
from types import SimpleNamespace

from fastapi import FastAPI

from src.dependencies import get_module_repository, get_subscription_repository
from tests.helpers import (
    FakeModules,
    FakeSubscriptions,
    api_client,
    make_module,
    make_subscription,
)


async def test_modules_of_the_contract_example(app: FastAPI) -> None:
    professional = make_subscription(
        id=3,
        name="Profesional",
        description=None,
        subscription_type=SimpleNamespace(id=2, name="Empresarial"),
        monthly_price=Decimal("1299.00"),
        annual_price=Decimal("12990.00"),
        trial_days=0,
        module_keys=["clinical_records", "legacy_reports", "patients", "scheduling"],
        other_features=[],
        consulting_rooms_limit=5,
        doctors_limit=10,
        assistants_limit=10,
        new_patients_per_year_limit=5000,
        clinics_limit=5,
    )
    catalog_modules = [
        make_module("patients", "Pacientes", sort_order=1),
        make_module("scheduling", "Agenda", sort_order=2),
        make_module("clinical_records", "Expediente clínico", sort_order=3),
    ]
    app.dependency_overrides[get_subscription_repository] = lambda: FakeSubscriptions([professional])
    app.dependency_overrides[get_module_repository] = lambda: FakeModules(catalog_modules)

    async with api_client(app) as client:
        response = await client.get("/api/v1/subscriptions")

    assert response.status_code == 200
    [plan] = response.json()
    assert plan["module_keys"] == ["clinical_records", "legacy_reports", "patients", "scheduling"]
    assert plan["modules"] == [
        {"key": "patients", "name": "Pacientes"},
        {"key": "scheduling", "name": "Agenda"},
        {"key": "clinical_records", "name": "Expediente clínico"},
    ]
    for module in plan["modules"]:
        assert set(module) == {"key", "name"}
