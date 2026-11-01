"""Helpers shared by the Routers to document their responses in OpenAPI (texts in Spanish)."""

from typing import Any

from src.dtos.errors import ErrorResponse
from src.messages import (
    INTERNAL_ERROR_MESSAGE,
    METHOD_NOT_ALLOWED_MESSAGE,
    RATE_LIMIT_EXCEEDED_MESSAGE,
    SERVICE_UNAVAILABLE_MESSAGE,
    ErrorCode,
)


def error_response(description: str, **examples: dict[str, Any]) -> dict[str, Any]:
    """OpenAPI entry for an error: the uniform `ErrorResponse` body plus Spanish examples."""
    return {
        "model": ErrorResponse,
        "description": description,
        "content": {
            "application/json": {
                "examples": {name: {"value": body} for name, body in examples.items()}
            }
        },
    }


def example_response(description: str, example_name: str, value: Any) -> dict[str, Any]:
    """OpenAPI entry for a success response, with one example body."""
    return {
        "description": description,
        "content": {"application/json": {"examples": {example_name: {"value": value}}}},
    }


SERVICE_UNAVAILABLE: dict[str, Any] = error_response(
    "La base de datos no respondió, rechazó la conexión o no terminó dentro del tiempo máximo de "
    "consulta. No se guarda en caché (`Cache-Control: no-store`).",
    base_no_disponible={
        "code": ErrorCode.SERVICE_UNAVAILABLE,
        "message": SERVICE_UNAVAILABLE_MESSAGE,
    },
)

RATE_LIMITED: dict[str, Any] = {
    **error_response(
        "La IP superó el límite de peticiones por minuto. La cabecera `Retry-After` dice en cuántos "
        "segundos se puede volver a intentar.",
        demasiadas_solicitudes={
            "code": ErrorCode.RATE_LIMIT_EXCEEDED,
            "message": RATE_LIMIT_EXCEEDED_MESSAGE,
        },
    ),
    "headers": {
        "Retry-After": {
            "description": "Segundos (entero ≥ 1) hasta que haya una petición disponible.",
            "schema": {"type": "integer", "minimum": 1},
        }
    },
}

METHOD_NOT_ALLOWED: dict[str, Any] = {
    **error_response(
        "El servicio es de solo lectura: cualquier método distinto de GET (POST, PUT, PATCH, DELETE, "
        "HEAD…) se rechaza. La cabecera `Allow` indica `GET`.",
        metodo_no_permitido={
            "code": ErrorCode.METHOD_NOT_ALLOWED,
            "message": METHOD_NOT_ALLOWED_MESSAGE,
        },
    ),
    "headers": {"Allow": {"description": "Siempre `GET`.", "schema": {"type": "string"}}},
}

INTERNAL_ERROR: dict[str, Any] = error_response(
    "Fallo inesperado, con el mensaje genérico de siempre y sin detalles técnicos.",
    error_inesperado={"code": ErrorCode.INTERNAL_ERROR, "message": INTERNAL_ERROR_MESSAGE},
)
