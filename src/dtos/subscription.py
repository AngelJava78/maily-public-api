from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_serializer


class SubscriptionTypeRead(BaseModel):
    """Who a subscription is for, taken from its type catalog (the same as maily-system-api)."""

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "description": "A quién va dirigida la suscripción, tomado de su catálogo."
        },
    )

    id: int = Field(
        ge=1,
        description=(
            "Identificador del tipo en el catálogo (hoy, 1 Individual, 2 Empresarial). Es el valor "
            "estable en el que debe basarse quien consume la API."
        ),
        examples=[1],
    )
    name: str = Field(
        description="Nombre del tipo (en español). Es un dato del catálogo y puede cambiar.",
        examples=["Individual"],
    )


class ModuleRead(BaseModel):
    """A module included in a plan, with the name people read (FR-011)."""

    model_config = ConfigDict(
        json_schema_extra={"description": "Un módulo incluido en el plan, con su nombre legible."}
    )

    key: str = Field(
        pattern=r"^[a-z][a-z0-9_]*$",
        description="Clave del módulo (la misma que en `module_keys`).",
        examples=["patients"],
    )
    name: str = Field(description="Nombre del módulo para mostrar.", examples=["Pacientes"])


class PublicSubscriptionRead(BaseModel):
    """A subscription of the public catalog (FR-008): only public data, never status or dates."""

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "description": (
                "Una suscripción (plan) Activa de autoservicio, con sus precios, módulos y límites. "
                "Solo datos públicos: nunca su estatus, sus fechas ni su número de clínicas."
            )
        },
    )

    id: int = Field(ge=1, description="Identificador de la suscripción.", examples=[1])
    name: str = Field(description="Nombre de la suscripción.", examples=["Consultorio"])
    description: str | None = Field(
        description="Descripción de la suscripción, o `null` si no tiene.",
        examples=["Para un médico que empieza a digitalizar su consultorio."],
    )
    subscription_type: SubscriptionTypeRead = Field(
        description="A quién va dirigida la suscripción: quien consume la API debe basarse en su `id`."
    )
    monthly_price: Decimal = Field(
        description=(
            "Precio mensual en pesos mexicanos sin IVA, con dos decimales (cadena para no perder "
            "precisión)."
        ),
        examples=["499.00"],
    )
    annual_price: Decimal = Field(
        description="Precio anual en pesos mexicanos sin IVA, con dos decimales.",
        examples=["4990.00"],
    )
    trial_days: int = Field(
        ge=0, le=3650, description="Días de prueba del plan. `0` = sin periodo de prueba.", examples=[14]
    )
    module_keys: list[str] = Field(
        description=(
            "Claves de todos los módulos de clínica que incluye, en orden alfabético (las mismas que "
            "en maily-system-api)."
        ),
        examples=[["patients", "scheduling"]],
    )
    modules: list[ModuleRead] = Field(
        description=(
            "Los módulos Activos de `module_keys` con su nombre para mostrar, en el orden de "
            "presentación del catálogo de módulos. Una clave que no corresponde a un módulo Activo "
            "de clínica no aparece aquí (sigue en `module_keys`)."
        ),
        examples=[[{"key": "patients", "name": "Pacientes"}, {"key": "scheduling", "name": "Agenda"}]],
    )
    other_features: list[str] = Field(
        description=(
            "Otras funcionalidades del plan que no son módulos (soporte, capacitación…), en el orden "
            "en que se guardaron."
        ),
        examples=[["Soporte por correo"]],
    )
    consulting_rooms_limit: int = Field(
        ge=0, le=1_000_000, description="Techo de consultorios que puede dar de alta la clínica."
    )
    doctors_limit: int = Field(
        ge=0, le=1_000_000, description="Techo de doctores que puede dar de alta la clínica."
    )
    assistants_limit: int = Field(
        ge=0, le=1_000_000, description="Techo de asistentes que puede dar de alta la clínica."
    )
    new_patients_per_year_limit: int = Field(
        ge=0,
        le=1_000_000,
        description="Techo de pacientes nuevos que puede registrar la clínica cada año.",
    )
    clinics_limit: int = Field(
        ge=1,
        le=100,
        description="Techo de clínicas que puede tener asociadas la suscripción.",
        examples=[1],
    )

    @field_serializer("monthly_price", "annual_price")
    def _two_decimals(self, value: Decimal) -> str:
        # The same format as maily-system-api: always two decimals ("4500" → "4500.00").
        return format(value.quantize(Decimal("0.01")), "f")
