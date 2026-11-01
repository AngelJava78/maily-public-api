"""Error codes (English, stable) and the messages people read (Spanish) — Principle VII.

The texts are the ones of specs/001-public-subscriptions-catalog/contracts/error-catalog.md.
"""

from enum import StrEnum


class ErrorCode(StrEnum):
    SERVICE_UNAVAILABLE = "service_unavailable"
    RATE_LIMIT_EXCEEDED = "rate_limit_exceeded"
    METHOD_NOT_ALLOWED = "method_not_allowed"
    NOT_FOUND = "not_found"
    INTERNAL_ERROR = "internal_error"


SERVICE_UNAVAILABLE_MESSAGE = (
    "El catálogo de suscripciones no está disponible por el momento. Inténtelo de nuevo más tarde."
)
RATE_LIMIT_EXCEEDED_MESSAGE = (
    "Se hicieron demasiadas solicitudes. Espere un momento e inténtelo de nuevo."
)
METHOD_NOT_ALLOWED_MESSAGE = "Esta operación no está permitida: el servicio es de solo lectura."
NOT_FOUND_MESSAGE = "No existe el recurso solicitado."
# The same text as maily-system-api.
INTERNAL_ERROR_MESSAGE = "Ocurrió un error inesperado. Inténtelo de nuevo más tarde."
