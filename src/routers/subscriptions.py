from fastapi import APIRouter, Response

from src.dependencies import CatalogServiceDep, SettingsDep
from src.dtos.subscription import PublicSubscriptionRead
from src.routers.openapi_docs import (
    INTERNAL_ERROR,
    METHOD_NOT_ALLOWED,
    RATE_LIMITED,
    SERVICE_UNAVAILABLE,
    example_response,
)

router = APIRouter(prefix="/api/v1", tags=["subscriptions"])

CATALOG_EXAMPLE = [
    {
        "id": 1,
        "name": "Consultorio",
        "description": "Para un médico que empieza a digitalizar su consultorio.",
        "subscription_type": {"id": 1, "name": "Individual"},
        "monthly_price": "499.00",
        "annual_price": "4990.00",
        "trial_days": 14,
        "module_keys": ["patients", "scheduling"],
        "modules": [
            {"key": "patients", "name": "Pacientes"},
            {"key": "scheduling", "name": "Agenda"},
        ],
        "other_features": ["Soporte por correo"],
        "consulting_rooms_limit": 1,
        "doctors_limit": 1,
        "assistants_limit": 1,
        "new_patients_per_year_limit": 500,
        "clinics_limit": 1,
    },
    {
        "id": 3,
        "name": "Profesional",
        "description": None,
        "subscription_type": {"id": 2, "name": "Empresarial"},
        "monthly_price": "1299.00",
        "annual_price": "12990.00",
        "trial_days": 0,
        "module_keys": ["clinical_records", "legacy_reports", "patients", "scheduling"],
        "modules": [
            {"key": "patients", "name": "Pacientes"},
            {"key": "scheduling", "name": "Agenda"},
            {"key": "clinical_records", "name": "Expediente clínico"},
        ],
        "other_features": [],
        "consulting_rooms_limit": 5,
        "doctors_limit": 10,
        "assistants_limit": 10,
        "new_patients_per_year_limit": 5000,
        "clinics_limit": 5,
    },
]


@router.get(
    "/subscriptions",
    operation_id="list_subscriptions",
    summary="Catálogo público de suscripciones (sin paginar)",
    description=(
        "Devuelve, sin token y sin paginar, las suscripciones **Activas de autoservicio**: las que "
        "se pueden contratar desde la página pública «Suscripciones». Nunca devuelve las Inactivas, "
        "Bloqueadas, Eliminadas ni las que no son de autoservicio, ni su estatus, sus fechas o su "
        "número de clínicas.\n\n"
        "Orden: fecha de creación ascendente y, a igualdad, identificador ascendente. Sin "
        "suscripciones públicas responde `[]`. La respuesta se puede guardar en caché "
        "(`Cache-Control: public, max-age=…`)."
    ),
    response_model=list[PublicSubscriptionRead],
    responses={
        200: example_response("El catálogo público completo.", "catalogo", CATALOG_EXAMPLE),
        405: METHOD_NOT_ALLOWED,
        429: RATE_LIMITED,
        500: INTERNAL_ERROR,
        503: SERVICE_UNAVAILABLE,
    },
)
async def list_subscriptions(
    response: Response, service: CatalogServiceDep, settings: SettingsDep
) -> list[PublicSubscriptionRead]:
    catalog = await service.list_catalog()
    response.headers["Cache-Control"] = f"public, max-age={settings.catalog_cache_max_age_seconds}"
    # Always, even without an `Origin` header: a shared cache must not hand the CORS answer of one
    # origin to another (research R9).
    response.headers["Vary"] = "Origin"
    return catalog
