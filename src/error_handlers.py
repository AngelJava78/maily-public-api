"""Every error answers `{code, message}` with `Cache-Control: no-store` (FR-013, FR-014, FR-017).

No response uses FastAPI's `{"detail": ...}` and none carries a host, an address, a driver message or a
trace. A 500 is logged by the server: Starlette's `ServerErrorMiddleware` sends this handler's response
and then re-raises the exception for uvicorn to log it (research R8).
"""

import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from src.dtos.errors import ErrorResponse
from src.exceptions import AppError
from src.messages import (
    INTERNAL_ERROR_MESSAGE,
    METHOD_NOT_ALLOWED_MESSAGE,
    NOT_FOUND_MESSAGE,
    ErrorCode,
)

logger = logging.getLogger(__name__)

NO_STORE = "no-store"


def error_response(
    status_code: int, code: ErrorCode, message: str, headers: dict[str, str] | None = None
) -> JSONResponse:
    body = ErrorResponse(code=code, message=message).model_dump(mode="json")
    return JSONResponse(
        status_code=status_code,
        content=body,
        headers={**(headers or {}), "Cache-Control": NO_STORE},
    )


async def app_error_handler(request: Request, error: AppError) -> JSONResponse:
    return error_response(error.status_code, error.code, error.message, error.headers)


async def http_error_handler(request: Request, error: StarletteHTTPException) -> JSONResponse:
    if error.status_code == 404:
        return error_response(404, ErrorCode.NOT_FOUND, NOT_FOUND_MESSAGE)
    if error.status_code == 405:
        # Starlette sets `Allow` with the methods of the route: `GET` for every route of this API.
        return error_response(
            405, ErrorCode.METHOD_NOT_ALLOWED, METHOD_NOT_ALLOWED_MESSAGE, dict(error.headers or {})
        )
    logger.error("Unexpected HTTP error %s on %s %s", error.status_code, request.method, request.url.path)
    return error_response(500, ErrorCode.INTERNAL_ERROR, INTERNAL_ERROR_MESSAGE)


async def unexpected_error_handler(request: Request, error: Exception) -> JSONResponse:
    return error_response(500, ErrorCode.INTERNAL_ERROR, INTERNAL_ERROR_MESSAGE)


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppError, app_error_handler)
    app.add_exception_handler(StarletteHTTPException, http_error_handler)
    app.add_exception_handler(Exception, unexpected_error_handler)
