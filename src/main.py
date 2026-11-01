"""FastAPI application: `uvicorn src.main:create_app_from_environment --factory`.

`create_app(settings)` has no side effects (it reads no variable and opens no connection: the engine
connects on first use), so the tests build the application with any configuration. The factory
`create_app_from_environment()` is the only entry point that reads the environment (research R10).
"""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src import VERSION
from src.config import InvalidSettingsError, Settings, load_settings
from src.database.session import create_engine, create_session_factory
from src.error_handlers import register_error_handlers
from src.rate_limit import TokenBucketLimiter, enforce_rate_limit
from src.routers import health, subscriptions

logger = logging.getLogger(__name__)

TITLE = "MailySoft Public API"
DESCRIPTION = """\
API pública de MailySoft, de **solo lectura** y **sin autenticación**: publica el catálogo de
suscripciones (planes) que muestra la página pública «Suscripciones» del Frontend de Maily.

- `GET /api/v1/subscriptions` devuelve completo, sin paginar, el catálogo de suscripciones **Activas
  de autoservicio**, con sus precios, módulos y límites. Nunca publica estatus, fechas, número de
  clínicas ni suscripciones que no estén a la venta.
- Ninguna operación exige token: no se envía `Authorization` y, si llega, se ignora. Solo existen
  operaciones GET; cualquier otro método responde `405`.
- El catálogo se puede guardar en caché (`Cache-Control: public, max-age=…`); los errores nunca
  (`no-store`). Cada IP tiene un límite de peticiones por minuto; al superarlo responde `429` con
  `Retry-After`.
- Todos los errores tienen el mismo formato (`code` en inglés y `message` en español) y nunca
  incluyen detalles técnicos.
- La salud cumple el contrato de salud v1 de MailySoft en la raíz (`/health/live`, `/health/ready` e
  `/info`), sin token y sin límite de peticiones.
"""

OPENAPI_TAGS = [
    {
        "name": "subscriptions",
        "description": "Catálogo público de suscripciones (planes). Se devuelve completo, sin paginar.",
    },
    {
        "name": "Salud",
        "description": "Contrato de salud v1 de los servicios de MailySoft (público, sin caché).",
    },
]


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    yield
    await app.state.engine.dispose()


def create_app(settings: Settings) -> FastAPI:
    docs = settings.docs_enabled
    app = FastAPI(
        title=TITLE,
        version=VERSION,
        description=DESCRIPTION,
        openapi_tags=OPENAPI_TAGS,
        docs_url="/docs" if docs else None,
        openapi_url="/openapi.json" if docs else None,
        redoc_url=None,
        swagger_ui_oauth2_redirect_url=None,
        lifespan=lifespan,
    )
    app.state.settings = settings
    app.state.engine = create_engine(settings)
    app.state.session_factory = create_session_factory(app.state.engine)
    app.state.rate_limiter = TokenBucketLimiter(settings.rate_limit_per_minute)

    # Only the Frontend's origins, only GET, never credentials or cookies (FR-018).
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["GET"],
        allow_headers=[],
        allow_credentials=False,
    )
    register_error_handlers(app)
    # The limit per IP applies to the business routes only (FR-019).
    app.include_router(subscriptions.router, dependencies=[Depends(enforce_rate_limit)])
    app.include_router(health.router)
    return app


def create_app_from_environment() -> FastAPI:
    """Entry point of uvicorn: without a valid configuration the service does not start (FR-024)."""
    try:
        settings = load_settings()
    except InvalidSettingsError as error:
        # The message names the variables, never their values.
        logger.critical("%s", error)
        raise SystemExit(1) from None
    return create_app(settings)
