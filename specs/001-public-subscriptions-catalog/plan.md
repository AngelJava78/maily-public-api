# Implementation Plan: Catálogo público de suscripciones

**Branch**: `001-public-subscriptions-catalog` | **Date**: 2026-11-01 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/001-public-subscriptions-catalog/spec.md`

**Note**: This template is filled in by the `/speckit-plan` command; its definition describes the execution workflow.

## Summary

Primer servicio de maily-public-api: `GET /api/v1/subscriptions`, sin autenticación, devuelve completo y
sin paginar el catálogo de suscripciones Activas de autoservicio, con los mismos campos públicos que el
`SubscriptionRead` de maily-system-api y un campo nuevo `modules` (clave y nombre legible de cada módulo
Activo de tipo Clínica). Lee la base compartida de MailySoft con un usuario propio de solo lectura con
permisos por columna (propuesto a mailySoft-DB), en transacciones `REPEATABLE READ READ ONLY` con tiempo
máximo de consulta. Se protege con CORS restringido, `Cache-Control` público configurable, un límite por
IP en la aplicación (cubeta de fichas, porque Railway no ofrece uno configurable) y respuestas de error
sin detalles. Cumple el contrato de salud v1 y publica su OpenAPI en español, desactivable. Bloqueante
externo: mailySoft-DB aún no tiene `subscription_modules` ni `subscriptions.clinics_limit` (FR-027).

## Technical Context

**Language/Version**: Python 3.14

**Primary Dependencies**: FastAPI (≥ 0.143), uvicorn (≥ 0.30), SQLAlchemy 2.0 async (`<2.1`) con asyncpg
(≥ 0.30), Pydantic v2 con pydantic-settings (≥ 2.6). Desarrollo: pytest (≥ 8.3), pytest-asyncio (≥ 1.0),
httpx (≥ 0.28, solo cliente de pruebas). Sin Alembic ni cliente HTTP en el servicio (research R14).

**Storage**: base compartida de MailySoft en PostgreSQL 18 (esquema de mailySoft-DB); solo lectura de
`subscriptions`, `subscription_types`, `subscription_modules` y `modules` con permisos por columna
([data-model.md](data-model.md), [contracts/database-permissions.md](contracts/database-permissions.md)).

**Testing**: pytest + pytest-asyncio; httpx `ASGITransport` para el contrato de las rutas. Corrida por
defecto sin PostgreSQL (Services, configuración, limitador, contrato con Repositories sustituidos); `slow`
contra PostgreSQL 18 desechable con el esquema de mailySoft-DB y conectado como el rol de solo lectura
(research R11, R12).

**Target Platform**: contenedor Linux (`python:3.14-slim`); Railway en la fase 1 de
mailysoft-infrastructure; local con Docker Compose (puerto 8006).

**Project Type**: web-service (API REST de solo lectura).

**Performance Goals**: p95 < 1 s del catálogo con la base disponible y hasta 500 suscripciones públicas
(SC-006); tres consultas acotadas por petición (research R6).

**Constraints**: ninguna escritura posible (permisos + `READ ONLY` + `default_transaction_read_only`);
503 en ≤ `DATABASE_QUERY_TIMEOUT_SECONDS` + 1 s con la base caída (SC-007); a lo más 10 conexiones por
réplica a la base compartida; 60 peticiones por minuto por IP por omisión; ningún secreto en respuestas
ni registros.

**Scale/Scope**: catálogo público esperado ≤ 100 suscripciones (máximo 500 sin paginar); una operación de
negocio, tres rutas de salud y la documentación; tráfico de una página pública con caché de 5 minutos.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Constitución v1.0.0. Evaluación inicial y después del diseño (Fase 1): **pasa, sin desviaciones**.

| Principio | Cómo lo cumple el diseño | Estado |
|---|---|---|
| I. Capas | Routers (`subscriptions`, `health`) → Services (`SubscriptionCatalogService`, `HealthService`) → Repositories (`SubscriptionRepository`, `ModuleRepository`, `DatabaseHealthRepository`) → `src/database/session.py`. El criterio de publicación lo fija el Service y el Repository lo aplica en la consulta (R6). Sin `src/integrations/` ni `alembic/`. | ✅ |
| II. ORM y DTOs | Modelos solo con las columnas concedidas; `PublicSubscriptionRead`, `SubscriptionTypeRead`, `ModuleRead` sin estatus, fechas, conteos ni datos personales; conversión explícita en el Service; prueba de contrato de campos exactos y prohibidos ([data-model.md](data-model.md) §3). | ✅ |
| III. Asincronía | asyncpg + `AsyncSession`; `asyncio.timeout` para los límites; ninguna llamada bloqueante. | ✅ |
| IV. OpenAPI | Solo GET; `/api/v1`; catálogo completo con máximo 500 y orden `created_at, id`; errores `{code, message}`; 404/405/429/500/503 documentados; sin 401/403 ([contracts/](contracts/)). | ✅ |
| V. Pruebas | Unitarias de Services con dobles; contrato de cada ruta; Repositories contra PostgreSQL 18 real como el rol de solo lectura, `slow` por hook; corrida por defecto sin base; prueba de rutas solo GET (R12). | ✅ |
| VI. Sin esquema propio | Sin migraciones ni DDL en el servicio; rol propio de solo lectura definido para mailySoft-DB; `READ ONLY` + `statement_timeout`; modelos alineados a `current_schema.sql`; estatus por identificador; `Decimal` (R3, R4, R11). | ✅ |
| VII. Idioma | Código, campos y códigos en inglés; mensajes, OpenAPI y documentos en español. | ✅ |
| VIII. Acceso público | Sin token ni `securitySchemes`; `Authorization`/cookies ignorados y no registrados; único secreto `DATABASE_URL`; solo Activas de autoservicio; CORS por lista, solo GET, sin credenciales; `Cache-Control` configurable y `no-store` en errores; límite por IP en la aplicación justificado (R1) con IP por saltos de confianza (R2); salud fuera del límite. | ✅ |
| IX. Sin integraciones | Ninguna llamada a otras APIs; `clinics_count` no se publica; httpx solo en desarrollo. | ✅ |
| Salud y Monitoreo | `/health/live`, `/health/ready` (`SELECT 1` con el rol), `/info` según v1, `no-store`, mismos nombres de variables ([contracts/health-v1.md](contracts/health-v1.md)). | ✅ |
| Stack y Restricciones | Tecnologías de la tabla; PostgreSQL 18; Docker + Compose unido a la red de mailySoft-DB; puerto 8006; variables validadas al arrancar; pytest/httpx fuera de la imagen (R13). | ✅ |
| Flujo | Dependencia de mailySoft-DB declarada (FR-027 y rol); puerta de `main` = suite completa + OpenAPI solo GET + prueba de rutas + modelos alineados. | ✅ |

## Project Structure

### Documentation (this feature)

```text
specs/001-public-subscriptions-catalog/
├── plan.md              # Este archivo
├── research.md          # Fase 0: decisiones R1–R14
├── data-model.md        # Fase 1: columnas leídas, modelos, DTOs y reglas
├── quickstart.md        # Fase 1: guía de validación
├── contracts/
│   ├── subscriptions-catalog.md   # GET /api/v1/subscriptions
│   ├── error-catalog.md           # códigos y mensajes
│   ├── http-policies.md           # rutas, métodos, CORS, caché, límite por IP
│   ├── health-v1.md               # salud v1 en este servicio
│   ├── database-permissions.md    # rol de solo lectura (consumido de mailySoft-DB)
│   └── environment.md             # variables de entorno
├── checklists/requirements.md
└── tasks.md             # Fase 2 (/speckit-tasks; no lo crea /speckit-plan)
```

### Source Code (repository root)

```text
src/
├── __init__.py                     # VERSION = "1.0.0"
├── main.py                         # create_app() sin efectos secundarios, lifespan, CORS, docs
├── config.py                       # Settings (pydantic-settings) y validación (contracts/environment.md)
├── dependencies.py                 # sesión → Repositories → Services para FastAPI
├── exceptions.py                   # AppError, ServiceUnavailableError, RateLimitExceededError
├── messages.py                     # ErrorCode y mensajes en español
├── error_handlers.py               # AppError, HTTPException (404/405) y Exception → {code, message}, no-store
├── rate_limit.py                   # cubeta de fichas, IP por saltos de confianza, dependencia del router
├── database/
│   └── session.py                  # engine de solo lectura (REPEATABLE READ READ ONLY, timeouts, pool)
├── models/
│   ├── base.py
│   ├── subscription.py
│   ├── subscription_type.py
│   ├── subscription_module.py
│   └── module.py
├── dtos/
│   ├── errors.py
│   ├── health.py
│   └── subscription.py             # PublicSubscriptionRead, SubscriptionTypeRead, ModuleRead
├── repositories/
│   ├── errors.py                   # DatabaseUnavailableError y clasificación (research R5)
│   ├── subscription_repository.py
│   ├── module_repository.py
│   └── database_health_repository.py
├── services/
│   ├── subscription_catalog_service.py
│   └── health_service.py
└── routers/
    ├── openapi_docs.py             # respuestas de error documentadas con ejemplos en español
    ├── subscriptions.py
    └── health.py

tests/
├── conftest.py                     # hook slow, base desechable, rol de solo lectura, clientes ASGI
├── helpers.py                      # fábricas de datos y dobles de Repositories
├── unit/                           # Services, config, limitador, IP del cliente
├── contract/                       # rutas con Repositories sustituidos, OpenAPI, rutas solo GET
└── integration/                    # slow: Repositories, permisos del rol, timeout, punta a punta

docs/database/read-only-role.sql    # propuesta para mailySoft-DB (contracts/database-permissions.md)
Dockerfile
docker-compose.yml                  # api (8006, red mailysoft-db_default) y db-test (perfil test)
pyproject.toml / uv.lock
.env.example / .dockerignore
README.md
```

**Structure Decision**: proyecto único de servicio web con la estructura en capas que fija el Principio I
(la misma de maily-system-api sin `src/integrations/`, `src/security.py` ni `alembic/`). Los módulos
transversales (`config`, `error_handlers`, `rate_limit`, `messages`) viven en la raíz de `src/` como en
maily-system-api. `docs/database/` guarda la única copia del SQL propuesto a mailySoft-DB, que las pruebas
también aplican (research R3).

## Complexity Tracking

Sin violaciones de la constitución que justificar.
