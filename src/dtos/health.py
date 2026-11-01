"""Responses of the health contract v1 (contracts/health-v1.md).

The field names are part of the agreement with the other MailySoft services and the Backoffice. No DTO
here has a field for an address, a host, a connection string or the text of an exception.
"""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

Latency = Annotated[int, Field(ge=0)]
CheckError = Literal["timeout", "connection_error", "unexpected_error"]


class LiveResponse(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={"description": "El proceso está vivo y atiende HTTP."}
    )

    status: Literal["ok"] = Field(description="Siempre `ok`.")


class CheckResult(BaseModel):
    model_config = ConfigDict(json_schema_extra={"description": "Un chequeo de disponibilidad."})

    name: Literal["database"] = Field(description="Nombre del chequeo: la base de datos compartida.")
    status: Literal["ok", "error"] = Field(description="`ok` o `error`.")
    latency_ms: Latency = Field(
        description="Duración del chequeo en milisegundos, también si falló.", examples=[12]
    )
    error: CheckError | None = Field(
        description="`null` si está `ok`; si no, `timeout`, `connection_error` o `unexpected_error`."
    )


class ReadyResponse(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "description": "Si el servicio puede leer la base de datos (200 `ok` o 503 `unavailable`)."
        }
    )

    status: Literal["ok", "unavailable"] = Field(description="`ok` o `unavailable`.")
    checks: list[CheckResult] = Field(description="Un único chequeo: `database`.")


class InfoResponse(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={"description": "Identificación del servicio y de su build."},
    )

    service: str = Field(description="Siempre `maily-public-api`.", examples=["maily-public-api"])
    version: str = Field(description="Versión del servicio.", examples=["1.0.0"])
    commit: str = Field(description="Commit del build o `unknown`.", examples=["3f9c2ab"])
    build_date: str = Field(
        description="Fecha del build en ISO 8601 UTC o `unknown`.", examples=["2026-11-01T18:00:00Z"]
    )
    environment: str = Field(description="Ambiente o `unknown`.", examples=["dev"])
