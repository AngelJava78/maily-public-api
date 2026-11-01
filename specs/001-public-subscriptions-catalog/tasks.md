---

description: "Lista de tareas de la feature 001-public-subscriptions-catalog"
---

# Tasks: Catálogo público de suscripciones

**Input**: Design documents from `/specs/001-public-subscriptions-catalog/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: obligatorias por la constitución (Principio V). Dentro de cada historia, las pruebas se escriben
primero y deben fallar antes de implementar. Las pruebas `slow` (PostgreSQL real) se **escriben** en su
historia pero **no se ejecutan** durante `/speckit-implement`, que solo corre `uv run pytest` (corrida por
defecto); la suite completa es la puerta de T066.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

**Bloqueo externo (FR-027)**: mailySoft-DB aún no tiene `subscription_modules` ni
`subscriptions.clinics_limit`. Todo el código y las pruebas por defecto se pueden completar; las pruebas
`slow` y la validación del quickstart quedan bloqueadas hasta que mailySoft-DB los incorpore.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1–US4)
- Include exact file paths in descriptions

## Path Conventions

Proyecto único: `src/` y `tests/` en la raíz del repositorio (plan.md, «Project Structure»).

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Inicializar el proyecto, el contenedor y la propuesta de rol de base de datos.

- [X] T001 Crear el esqueleto de paquetes: `src/__init__.py` con un docstring y `VERSION = "1.0.0"`, y archivos `__init__.py` vacíos en `src/database/`, `src/models/`, `src/dtos/`, `src/repositories/`, `src/services/`, `src/routers/`, `tests/`, `tests/unit/`, `tests/contract/` y `tests/integration/`
- [X] T002 Crear `pyproject.toml`: `name = "maily-public-api"`, `version = "1.0.0"`, descripción en español, `requires-python = ">=3.14"`; dependencias `asyncpg>=0.30`, `fastapi>=0.143`, `pydantic-settings>=2.6`, `sqlalchemy[asyncio]>=2.0,<2.1`, `uvicorn>=0.30` (sin Alembic ni httpx); grupo `dev` con `pytest>=8.3`, `pytest-asyncio>=1.0`, `httpx>=0.28`; `[tool.uv] package = false`; `[tool.pytest.ini_options]` con `testpaths = ["tests"]`, `pythonpath = ["."]`, `asyncio_mode = "auto"`, `asyncio_default_fixture_loop_scope = "session"`, `asyncio_default_test_loop_scope = "session"`, marcador `slow: necesita PostgreSQL 18 real con el esquema de mailySoft-DB` y `addopts = "-m 'not slow'"`. Después ejecutar `uv lock` para generar `uv.lock`
- [X] T003 [P] Crear `Dockerfile` según research R13: `FROM python:3.14-slim`; `PYTHONDONTWRITEBYTECODE=1`, `PYTHONUNBUFFERED=1`, `UV_COMPILE_BYTECODE=1`, `UV_PYTHON_DOWNLOADS=never`; `pip install uv==0.13.1`; copiar `pyproject.toml` y `uv.lock` y `uv sync --frozen --no-dev`; copiar solo `src/`; `ARG`/`ENV` `APP_COMMIT_SHA` y `APP_BUILD_DATE` al final; `ENV PATH="/app/.venv/bin:$PATH"`; `EXPOSE 8000`; `CMD ["sh", "-c", "exec uvicorn src.main:create_app_from_environment --factory --host 0.0.0.0 --port ${PORT:-8000} --no-proxy-headers"]`
- [X] T004 [P] Crear `docker-compose.yml`: servicio `api` (build con args `APP_COMMIT_SHA`/`APP_BUILD_DATE`, `env_file: .env`, `ports: "8006:8000"`, red externa `mailysoft-db_default`, `restart: unless-stopped`) y servicio `db-test` (`image: postgres:18`, `profiles: ["test"]`, `POSTGRES_USER=postgres`, `POSTGRES_PASSWORD=postgres`, `POSTGRES_DB=maily_public_api_test`, `ports: "127.0.0.1:5436:5432"`, `tmpfs: /var/lib/postgresql`, healthcheck `pg_isready`); declarar `networks: mailysoft-db_default: external: true`. El Compose no levanta ninguna base para el servicio
- [X] T005 [P] Crear `.env.example` con el ejemplo de `specs/001-public-subscriptions-catalog/contracts/environment.md` (contraseñas de marcador, nunca reales) y `.dockerignore` que excluya `.env`, `.venv/`, `.git/`, `tests/`, `specs/`, `.specify/`, `.claude/`, `docs/` y `**/__pycache__/`
- [X] T006 [P] Crear `docs/database/read-only-role.sql` copiando **exactamente** el bloque SQL de la sección 2 de `specs/001-public-subscriptions-catalog/contracts/database-permissions.md` (rol `maily_public_api`, `CONNECTION LIMIT 12`, `default_transaction_read_only = on`, `statement_timeout = '5s'`, `idle_in_transaction_session_timeout = '10s'`, `CONNECT`, `USAGE` y los `GRANT SELECT` por columna de las cuatro tablas)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Configuración, errores, sesión de base de datos, aplicación y fixtures que todas las historias usan.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [X] T007 [P] Crear `src/messages.py` con `ErrorCode(StrEnum)`: `SERVICE_UNAVAILABLE = "service_unavailable"`, `RATE_LIMIT_EXCEEDED = "rate_limit_exceeded"`, `METHOD_NOT_ALLOWED = "method_not_allowed"`, `NOT_FOUND = "not_found"`, `INTERNAL_ERROR = "internal_error"`, y los mensajes literales de `contracts/error-catalog.md`: «El catálogo de suscripciones no está disponible por el momento. Inténtelo de nuevo más tarde.», «Se hicieron demasiadas solicitudes. Espere un momento e inténtelo de nuevo.», «Esta operación no está permitida: el servicio es de solo lectura.», «No existe el recurso solicitado.», «Ocurrió un error inesperado. Inténtelo de nuevo más tarde.»
- [X] T008 [P] Crear `src/dtos/errors.py` con `ErrorResponse(code: ErrorCode, message: str)`, descripciones en español (`"Formato uniforme de todos los errores."`) y sin campo `errors`
- [X] T009 Crear `src/exceptions.py`: `AppError(Exception)` con `status_code`, `code: ErrorCode`, `message: str` y `headers: dict[str, str]`; `ServiceUnavailableError` (503, `service_unavailable`); `RateLimitExceededError(retry_after_seconds: int)` (429, `rate_limit_exceeded`, cabecera `Retry-After` con el entero) (depende de T007)
- [X] T010 [P] Escribir `tests/unit/test_config.py`: valores por omisión (`CATALOG_CACHE_MAX_AGE_SECONDS=300`, `DATABASE_QUERY_TIMEOUT_SECONDS=3`, `DOCS_ENABLED=true`, `RATE_LIMIT_PER_MINUTE=60`, `TRUSTED_PROXY_HOPS=0`, `HEALTH_READY_TIMEOUT_SECONDS=2`); faltan `DATABASE_URL` y `CORS_ALLOWED_ORIGINS` → un solo error que nombra ambas; cada valor inválido de `contracts/environment.md` (fuera de rango, `*`, origen con ruta, lista vacía, esquema distinto de `postgresql+asyncpg://`, URL sin host) se rechaza nombrando la variable; ningún mensaje contiene el valor de `DATABASE_URL`; una variable vacía cuenta como no definida; `APP_COMMIT_SHA`/`APP_BUILD_DATE`/`APP_ENVIRONMENT` inválidos o vacíos → `unknown`, y `APP_BUILD_DATE` válido se normaliza a UTC con `Z`
- [X] T011 Crear `src/config.py` (pydantic-settings, `env_file=".env"`, `extra="ignore"`, `env_ignore_empty=True`): `Settings` con `database_url` (obligatoria; `postgresql+asyncpg://` con host), `cors_allowed_origins` (obligatoria; propiedad `cors_origins: list[str]`; cada origen `http(s)://host[:puerto]` sin ruta, consulta ni `*`; al menos uno), `catalog_cache_max_age_seconds: int` 0–86 400 = 300, `database_query_timeout_seconds: float` 1–30 = 3, `docs_enabled: bool = True`, `rate_limit_per_minute: int` 0–10 000 = 60, `trusted_proxy_hops: int` 0–5 = 0, `health_ready_timeout_seconds: float` >0 y ≤10 = 2, `app_commit_sha`, `app_build_date`, `app_environment` opcionales; `SERVICE_NAME = "maily-public-api"`; `BuildInfo` (`commit` hexadecimal 7–64, `build_date` ISO 8601 con zona → UTC `Z`, `environment` `[A-Za-z0-9._-]{1,50}`; inválido → `"unknown"`); `InvalidSettingsError` y `load_settings() -> Settings` que junta los errores de pydantic y los relanza con un mensaje que lista solo los nombres de las variables (nunca valores). Hacer pasar T010
- [X] T012 [P] Crear `src/models/base.py` con `class Base(DeclarativeBase)`; los modelos nunca crean tablas
- [X] T013 Crear `src/database/session.py` según research R4: `create_engine(settings) -> AsyncEngine` con `create_async_engine(settings.database_url, pool_pre_ping=True, pool_size=5, max_overflow=5, connect_args={"timeout": settings.database_query_timeout_seconds, "server_settings": {"application_name": "maily-public-api", "default_transaction_read_only": "on", "statement_timeout": str(int(settings.database_query_timeout_seconds * 1000))}})` y `.execution_options(isolation_level="REPEATABLE READ", postgresql_readonly=True)`; `create_session_factory(engine)` (`expire_on_commit=False`); dependencia `get_session(request)` que abre una `AsyncSession` de `request.app.state.session_factory` y la cierra al terminar. Crear el engine no abre conexiones
- [X] T014 Crear `src/repositories/errors.py` según research R5: `DatabaseUnavailableError(kind)` con `kind` en `{"timeout", "connection_error", "unexpected_error"}`; `is_unavailable(error: DBAPIError) -> bool` verdadero si `error.connection_invalidated` o si el SQLSTATE (`getattr(error.orig, "sqlstate", None) or getattr(error.orig, "pgcode", None)`) empieza por `08`, `53` o `57`; y `async def open_connection(session)` que llama a `session.connection()` y traduce cualquier excepción a `DatabaseUnavailableError("connection_error")`
- [X] T015 [P] Escribir `tests/unit/test_repository_errors.py`: SQLSTATE `08006`, `53300`, `57014` y conexión invalidada → no disponible; `42501`, `42P01` → disponible (se deja subir); `open_connection` traduce un `OSError` a `connection_error`
- [X] T016 Crear `src/error_handlers.py` según research R8 y `register_error_handlers(app)`: `AppError` → su estado, `{code, message}` y sus cabeceras; `StarletteHTTPException` 404 → `not_found`, 405 → `method_not_allowed` conservando `exc.headers` (`Allow`), cualquier otro código → 500 `internal_error`; `Exception` → 500 `internal_error` con `logger.exception` (sin cabeceras de la petición). Toda respuesta de error lleva `Cache-Control: no-store` y nunca `detail`
- [X] T017 Crear `src/main.py`: `create_app(settings: Settings) -> FastAPI` sin efectos secundarios (título `"MailySoft Public API"`, `version=VERSION`, descripción provisional en español, `docs_url="/docs"` y `openapi_url="/openapi.json"` solo si `settings.docs_enabled`, si no `None`; `redoc_url=None`; `swagger_ui_oauth2_redirect_url=None`); guarda `settings`, engine (`create_engine`) y `session_factory` en `app.state`; `lifespan` que hace `dispose()` del engine al apagar; `register_error_handlers(app)`. Fábrica `create_app_from_environment()`: `load_settings()`; ante `InvalidSettingsError` registra el mensaje (solo nombres) y termina con `SystemExit(1)`; si no, `create_app(settings)` (depende de T011, T013, T016)
- [X] T018 Crear `src/dependencies.py` con `get_settings(request) -> Settings` (desde `request.app.state.settings`) y la reexportación de `get_session`; los proveedores de Repositories y Services se agregan en cada historia
- [X] T019 [P] Crear `tests/helpers.py`: `make_settings(**overrides)` con valores válidos (`database_url="postgresql+asyncpg://test:test@127.0.0.1:1/unreachable_test"`, `cors_allowed_origins="https://frontend.example"`); `api_client(app, client_ip="127.0.0.1")` (contexto async con `httpx.AsyncClient(transport=httpx.ASGITransport(app=app, client=(client_ip, 50000)), base_url="http://testserver")`); `make_subscription(**fields)` que construye un `SimpleNamespace` con la forma del modelo `Subscription` (precios `Decimal`, `subscription_type`, `module_keys`); constantes `PUBLIC_SUBSCRIPTION_FIELDS` (los 14 campos de FR-008 sin `modules`) y `FORBIDDEN_FIELDS = {"status", "status_id", "self_service", "clinics_count", "created_at", "updated_at", "subscription_type_id"}`
- [X] T020 Crear `tests/conftest.py`: hook `pytest_collection_modifyitems` que marca `slow` toda prueba que use alguna fixture de `_NEEDS_REAL_DATABASE = {"admin_engine", "database_ready", "reader_settings", "reader_engine", "reader_session", "db_api"}`; fixtures `settings` (`make_settings()`) y `app` (`create_app(settings)`) para la corrida por defecto
- [X] T021 Crear `tests/integration/conftest.py` y `tests/integration/seed.py` (research R11), solo para pruebas `slow`: `TEST_DATABASE_URL` obligatoria y su base debe terminar en `_test` (si no, `pytest.fail` con mensaje claro); `MAILYSOFT_DB_DIR` (por omisión `../mailySoft-DB`; si falta, `pytest.fail`); fixture de sesión `database_ready` que, con una conexión asyncpg dedicada del administrador, hace `DROP SCHEMA public CASCADE; CREATE SCHEMA public;`, ejecuta `schema/current_schema.sql`, los catálogos `migrations/repeatable/R__40_cat_subscription_statuses.sql`, `R__40_cat_subscription_types.sql`, `R__40_cat_module_statuses.sql` y `R__40_cat_module_types.sql`, falla con un mensaje que cite FR-027 si no existen `subscription_modules` o `subscriptions.clinics_limit`, ejecuta `docs/database/read-only-role.sql` y asigna una contraseña aleatoria (`secrets.token_urlsafe`) al rol, y cierra la conexión; fixtures `admin_engine`, `reader_settings` (con `DATABASE_URL` del rol `maily_public_api`), `reader_engine`/`reader_session` (con `create_engine` de `src/database/session.py`) y `db_api` (cliente de `create_app(reader_settings)`); fixture autouse por prueba que hace `TRUNCATE subscription_modules, subscriptions, modules RESTART IDENTITY CASCADE` como administrador. `seed.py`: `insert_subscription(conn, **fields)` (columnas explícitas: `name`, `description`, `subscription_type_id`, `monthly_price`, `annual_price`, `trial_days`, `self_service`, `status_id`, `other_features`, los cinco límites y `created_at`; devuelve el `id`), `insert_subscription_module(conn, subscription_id, module_key)` e `insert_module(conn, key, name, sort_order, status_id, type_id)`
- [X] T022 [P] Escribir `tests/contract/test_error_format.py`: una ruta inexistente responde 404 con cuerpo exacto `{"code": "not_found", "message": "No existe el recurso solicitado."}`, `Cache-Control: no-store` y sin `detail`; una ruta de prueba agregada a una instancia propia de la aplicación que lanza `RuntimeError("secreto")` responde 500 `internal_error` con el mensaje genérico, sin el texto `secreto`

**Checkpoint**: `uv run pytest` en verde; la aplicación se construye sin variables ni base de datos.

---

## Phase 3: User Story 1 - Ver los planes que se pueden contratar sin iniciar sesión (Priority: P1) 🎯 MVP

**Goal**: `GET /api/v1/subscriptions` sin token devuelve solo las suscripciones Activas de autoservicio, en
orden `created_at, id`, con los campos públicos (sin `modules`, que llega en US2), caché pública y 503
sin detalles si la base no responde.

**Independent Test**: contrato con Repository sustituido (corrida por defecto) y, en `slow`, una base con
suscripciones en cada estatus y con/sin autoservicio: solo aparecen las Activas de autoservicio, en orden
y con los campos exactos.

### Tests for User Story 1 ⚠️

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [X] T023 [P] [US1] Escribir `tests/unit/test_subscription_catalog_service.py` con un Repository falso: llama a `list_by_publication(status_id=1, self_service=True)`; conserva el orden del Repository; mapea todos los campos; `Decimal("4500")` se serializa `"4500.00"`; `description=None` → `null`; con 501 suscripciones las devuelve todas y registra un solo aviso aunque se llame dos veces (`caplog`); `DatabaseUnavailableError` → `ServiceUnavailableError`; un Repository que tarda más que `query_timeout_seconds=0.05` → `ServiceUnavailableError`
- [X] T024 [P] [US1] Escribir `tests/contract/test_subscriptions_api.py` sustituyendo `get_subscription_repository` en `app.dependency_overrides`: 200 con las claves exactas de `PUBLIC_SUBSCRIPTION_FIELDS` y ninguna de `FORBIDDEN_FIELDS`; lista vacía → 200 `[]`; orden del Repository; precios con dos decimales; `Cache-Control: public, max-age=300` (y `max-age=120` con `catalog_cache_max_age_seconds=120`); `Vary` incluye `Origin` aun sin cabecera `Origin`; respuesta idéntica con `Authorization: Bearer x` y `Cookie: a=b`; `?page=2` se ignora; Repository que lanza `DatabaseUnavailableError` → 503 con cuerpo exacto de `service_unavailable`, `Cache-Control: no-store` y sin `127.0.0.1` ni `postgresql` en el cuerpo; Repository que lanza `RuntimeError` → 500 `internal_error`
- [X] T025 [P] [US1] Escribir `tests/integration/test_subscription_repository.py` (`slow`, conectado como el rol): sembrar suscripciones con `status_id` 1–4 × `self_service` verdadero/falso → solo vuelven las de `status_id = 1` y `self_service = true`; orden por `created_at` y, a igualdad, por `id`; `subscription_type` cargado con `id` y `name`; `module_keys` insertadas desordenadas (`scheduling`, `patients`, `clinical_records`) vuelven en el orden de la base; una suscripción sin módulos → `module_keys == []`
- [X] T026 [P] [US1] Escribir `tests/integration/test_catalog_api.py` (`slow`, `db_api`): `GET /api/v1/subscriptions` devuelve exactamente las suscripciones públicas sembradas, con los valores esperados y los precios como texto con dos decimales

### Implementation for User Story 1

- [X] T027 [P] [US1] Crear `src/models/subscription_type.py`: `SubscriptionType` (`subscription_types`) con `id: int` (PK, `Integer`) y `name: str` (`String(50)`, no nulo); nada más
- [X] T028 [P] [US1] Crear `src/models/subscription_module.py`: `SubscriptionModule` (`subscription_modules`) con `subscription_id: int` (`Integer`, PK, `ForeignKey("subscriptions.id")`) y `module_key: str` (`Text`, PK)
- [X] T029 [US1] Crear `src/models/subscription.py`: `Subscription` (`subscriptions`) con **solo** las 16 columnas concedidas de data-model.md §1: `id` (`Integer`, PK), `name` (`String(100)`), `description` (`String(500)`, nulo), `subscription_type_id` (`Integer`, `ForeignKey("subscription_types.id")`), `monthly_price` y `annual_price` (`Numeric(10, 2)` → `Decimal`), `trial_days` (`Integer`), `other_features` (`ARRAY(Text)`), `consulting_rooms_limit`, `doctors_limit`, `assistants_limit`, `new_patients_per_year_limit`, `clinics_limit` (`Integer`), `status_id` (`Integer`), `self_service` (`Boolean`), `created_at` (`DateTime(timezone=True)`); relaciones `subscription_type` (`lazy="raise"`) y `modules: list[SubscriptionModule]` (`lazy="raise"`, `order_by="SubscriptionModule.module_key"`); propiedad `module_keys`. Sin `updated_at` ni la columna `module_keys` (depende de T027, T028)
- [X] T030 [P] [US1] Crear `src/dtos/subscription.py`: `SubscriptionTypeRead` (`id: int` ≥ 1, `name: str`) y `PublicSubscriptionRead` (`from_attributes=True`) con los campos en este orden: `id` (≥ 1), `name`, `description: str | None`, `subscription_type`, `monthly_price: Decimal`, `annual_price: Decimal`, `trial_days` (0–3650), `module_keys: list[str]`, `other_features: list[str]`, `consulting_rooms_limit`, `doctors_limit`, `assistants_limit`, `new_patients_per_year_limit` (0–1 000 000), `clinics_limit` (1–100); descripciones y ejemplos en español como en el `SubscriptionRead` de maily-system-api; `field_serializer` de los dos precios que devuelve `format(value.quantize(Decimal("0.01")), "f")`
- [X] T031 [US1] Crear `src/repositories/subscription_repository.py`: `SubscriptionRepository(session)` con `list_by_publication(status_id: int, self_service: bool) -> list[Subscription]`: `open_connection`, luego `select(Subscription).where(Subscription.status_id == status_id, Subscription.self_service == self_service).order_by(Subscription.created_at, Subscription.id).options(joinedload(Subscription.subscription_type), selectinload(Subscription.modules))`; un `DBAPIError` con `is_unavailable` → `DatabaseUnavailableError("connection_error")`; cualquier otro error sube sin tocar (depende de T014, T029)
- [X] T032 [US1] Crear `src/services/subscription_catalog_service.py`: constantes `ACTIVE_STATUS_ID = 1`, `PUBLIC_SELF_SERVICE = True`, `CATALOG_MAX_EXPECTED = 500`; `SubscriptionCatalogService(subscriptions: SubscriptionRepository, query_timeout_seconds: float)` con `async list_catalog() -> list[PublicSubscriptionRead]` que envuelve la lectura en `asyncio.timeout(query_timeout_seconds)`, traduce `TimeoutError` y `DatabaseUnavailableError` a `ServiceUnavailableError`, registra una sola vez por proceso un `WARNING` si hay más de 500 y convierte cada modelo con `PublicSubscriptionRead.model_validate` (depende de T030, T031). Hacer pasar T023
- [X] T033 [P] [US1] Crear `src/routers/openapi_docs.py`: `error_response(description, **examples)` (modelo `ErrorResponse` y ejemplos) y las entradas `SERVICE_UNAVAILABLE` (503) e `INTERNAL_ERROR` (500) con los ejemplos de `contracts/error-catalog.md`
- [X] T034 [US1] Agregar a `src/dependencies.py` `get_subscription_repository(session)` y `get_subscription_catalog_service(repository, settings)` (usa `settings.database_query_timeout_seconds`)
- [X] T035 [US1] Crear `src/routers/subscriptions.py`: `APIRouter(prefix="/api/v1", tags=["subscriptions"])`; `GET /subscriptions` con `operation_id="list_subscriptions"`, `summary` y `description` en español, `response_model=list[PublicSubscriptionRead]`, respuestas 503 y 500 de `openapi_docs` y el ejemplo 200 de `contracts/subscriptions-catalog.md` (sin `modules` por ahora); pone en la respuesta `Cache-Control: public, max-age=<settings.catalog_cache_max_age_seconds>` y `Vary: Origin`. Incluir el router en `create_app` de `src/main.py`. Hacer pasar T024

**Checkpoint**: MVP: el catálogo público funciona y es comprobable por sí solo (sin nombres de módulos).

---

## Phase 4: User Story 2 - Ver los módulos de cada plan con su nombre legible (Priority: P2)

**Goal**: cada suscripción trae `modules` con `{key, name}` de sus módulos Activos de tipo Clínica,
ordenados por `(sort_order, key)`; las claves sin módulo se omiten de `modules` (siguen en `module_keys`)
con un aviso una vez por proceso.

**Independent Test**: con un catálogo de módulos con Activos, Bloqueados, Eliminados, de tipo Sistema y
una clave inexistente, `modules` contiene solo los Activos de tipo Clínica en su orden.

### Tests for User Story 2 ⚠️

- [X] T036 [P] [US2] Escribir `tests/unit/test_catalog_modules.py` con Repositories falsos: `list_by_keys` se llama una vez con todas las claves distintas, `status_id=1` y `type_id=2`; `modules` ordenados por `(sort_order, key)`; una clave sin módulo se omite de `modules`, se conserva en `module_keys` y registra un `WARNING` con `subscription_id` y `module_key` una sola vez aunque se llame dos veces; suscripción sin módulos → `modules == []`
- [X] T037 [P] [US2] Escribir `tests/contract/test_subscriptions_modules_api.py`: reproduce el segundo elemento del ejemplo de `contracts/subscriptions-catalog.md` (`legacy_reports` en `module_keys` y fuera de `modules`) y comprueba que `modules` es una lista de objetos con exactamente `key` y `name`
- [X] T038 [P] [US2] Escribir `tests/integration/test_module_repository.py` (`slow`, como el rol): devuelve el módulo Activo de tipo Clínica; no devuelve los Bloqueados (`status_id=2`), Eliminados (`status_id=3`) ni de tipo Sistema (`type_id=1`); con un módulo Eliminado y uno Activo con la misma clave devuelve solo el Activo; una clave inexistente no devuelve nada; con claves vacías devuelve `[]`

### Implementation for User Story 2

- [X] T039 [P] [US2] Crear `src/models/module.py`: `Module` (`modules`) con `key` (`String(50)`), `name` (`String(100)`), `sort_order` (`Integer`), `status_id` (`Integer`), `type_id` (`Integer`), sin `id`, y `__mapper_args__ = {"primary_key": [key]}` (research R6)
- [X] T040 [P] [US2] En `src/dtos/subscription.py`: agregar `ModuleRead` (`key: str` con patrón `^[a-z][a-z0-9_]*$`, `name: str`) y el campo `modules: list[ModuleRead]` en `PublicSubscriptionRead` inmediatamente después de `module_keys`, con descripción en español
- [X] T041 [US2] Crear `src/repositories/module_repository.py`: `ModuleRepository(session)` con `list_by_keys(keys: Collection[str], status_id: int, type_id: int) -> list[Module]` (`[]` sin consultar si no hay claves; `select(Module).where(Module.key.in_(keys), Module.status_id == status_id, Module.type_id == type_id)`; misma traducción de errores que `SubscriptionRepository`) (depende de T039)
- [X] T042 [US2] En `src/services/subscription_catalog_service.py`: recibir `ModuleRepository`; constantes `ACTIVE_MODULE_STATUS_ID = 1` y `CLINIC_MODULE_TYPE_ID = 2`; dentro del mismo `asyncio.timeout`, consultar los módulos de todas las claves y armar `modules` según data-model.md M1–M3; avisos de clave sin módulo una vez por proceso por `(subscription_id, module_key)`, en un conjunto acotado a 1 000 parejas (depende de T040, T041). Hacer pasar T036
- [X] T043 [US2] Agregar `get_module_repository(session)` en `src/dependencies.py` y pasarlo a `get_subscription_catalog_service`; actualizar el ejemplo 200 de `src/routers/subscriptions.py` al de `contracts/subscriptions-catalog.md` completo (con `modules`)
- [X] T044 [US2] Actualizar `tests/helpers.py` (`PUBLIC_SUBSCRIPTION_FIELDS` incluye `modules`; `make_subscription` acepta módulos) y los contratos de `tests/contract/test_subscriptions_api.py` para sustituir también `get_module_repository` con un Repository falso (catálogo vacío por omisión). Hacer pasar T037

**Checkpoint**: US1 y US2 funcionan; el catálogo trae nombres de módulos.

---

## Phase 5: User Story 3 - Un servicio público que no se puede abusar ni usar para escribir (Priority: P2)

**Goal**: solo GET (405 con `Allow: GET`), CORS por lista sin credenciales, límite por IP con 429 y
`Retry-After`, rol sin permisos de escritura y 503 ante una base lenta.

**Independent Test**: métodos de escritura → 405; origen no permitido sin permiso CORS; límite superado
→ 429; con las credenciales del servicio toda escritura es rechazada por la base.

### Tests for User Story 3 ⚠️

- [X] T045 [P] [US3] Escribir `tests/unit/test_rate_limit.py` con reloj falso: con 60 por minuto, 60 peticiones pasan y la 61.ª se rechaza con `retry_after` = 1; tras 1 s pasa una más; `0` nunca rechaza; IP distintas son independientes; las cubetas llenas se purgan cuando el registro supera el umbral
- [X] T046 [P] [US3] Escribir `tests/unit/test_client_ip.py` (`contracts/http-policies.md`): `hops=0` → IP de la conexión; `hops=1` con `X-Forwarded-For: 203.0.113.9, 198.51.100.7` → `198.51.100.7`; `hops=2` → `203.0.113.9`; varias cabeceras `X-Forwarded-For` se unen en orden; menos direcciones que `hops` o una entrada que no es IP → IP de la conexión; IPv6 válida
- [X] T047 [P] [US3] Escribir `tests/contract/test_http_policies.py`: POST, PUT, PATCH, DELETE y HEAD a `/api/v1/subscriptions` → 405, `Allow: GET`, `method_not_allowed`, `Cache-Control: no-store`; `Origin: https://frontend.example` → `Access-Control-Allow-Origin` igual y sin `Access-Control-Allow-Credentials`; `Origin: https://otro.example` → sin `Access-Control-Allow-Origin`; verificación previa con `Access-Control-Request-Method: DELETE` no lo permite; con `rate_limit_per_minute=3`, la 4.ª petición → 429 `rate_limit_exceeded`, `Retry-After` entero ≥ 1 y `no-store`, mientras otra IP (cliente ASGI distinto) recibe 200; con `trusted_proxy_hops=1` dos `X-Forwarded-For` distintos cuentan como IP distintas; con `rate_limit_per_minute=0` nunca hay 429
- [X] T048 [P] [US3] Escribir `tests/contract/test_get_only_routes.py` (constitución, Principio V): recorre `app.routes` (documentación activada) y falla si alguna ruta, salvo `/docs`, `/openapi.json`, `/health/live`, `/health/ready` e `/info`, admite un método distinto de `GET`; falla si `app.openapi()["paths"]` contiene una operación que no sea `get` o si existe `components.securitySchemes`
- [X] T049 [P] [US3] Escribir `tests/integration/test_read_only_role.py` (`slow`, SC-004), con una conexión asyncpg como `maily_public_api`: `BEGIN READ WRITE` + `INSERT`, `UPDATE` y `DELETE` sobre `subscriptions` → `InsufficientPrivilegeError`; `SELECT updated_at FROM subscriptions` y `SELECT 1 FROM subscription_statuses` → `InsufficientPrivilegeError`; `SHOW default_transaction_read_only` = `on`; como administrador, `pg_roles` del rol sin superusuario, sin `CREATEDB`/`CREATEROLE`/`REPLICATION`/`BYPASSRLS` y `rolconnlimit = 12`, sin filas en `pg_auth_members` y exactamente 25 filas `SELECT` en `information_schema.column_privileges`
- [X] T050 [P] [US3] Escribir `tests/integration/test_database_failures.py` (`slow`): con `database_query_timeout_seconds=1`, mientras el administrador mantiene `LOCK TABLE subscriptions IN ACCESS EXCLUSIVE MODE` en una transacción abierta, el catálogo responde 503 `service_unavailable` en ≤ 2 s y vuelve a 200 al liberar el bloqueo; con `REVOKE SELECT (clinics_limit) ON subscriptions FROM maily_public_api` el catálogo responde 500 `internal_error` con el mensaje genérico (restaurar el permiso al terminar)

### Implementation for User Story 3

- [X] T051 [US3] Crear `src/rate_limit.py` según research R1 y R2: `TokenBucketLimiter(per_minute: int, clock=time.monotonic, purge_threshold=10_000)` con `check(key: str) -> int | None` (`None` si pasa; si no, segundos enteros ≥ 1 hasta la siguiente ficha) y purga de cubetas llenas al superar el umbral; `client_ip(request, trusted_hops: int) -> str`; dependencia `enforce_rate_limit(request)` que usa `request.app.state.rate_limiter` y `settings.trusted_proxy_hops` y lanza `RateLimitExceededError`. Hacer pasar T045 y T046
- [X] T052 [US3] En `src/main.py`: crear `app.state.rate_limiter = TokenBucketLimiter(settings.rate_limit_per_minute)`; incluir el router de suscripciones con `dependencies=[Depends(enforce_rate_limit)]`; agregar `CORSMiddleware(allow_origins=settings.cors_origins, allow_methods=["GET"], allow_headers=[], allow_credentials=False)` (depende de T051)
- [X] T053 [US3] En `src/routers/openapi_docs.py` y `src/routers/subscriptions.py`: documentar las respuestas 429 (con la cabecera `Retry-After`) y 405 (con `Allow`) con los ejemplos de `contracts/error-catalog.md`. Hacer pasar T047 y T048

**Checkpoint**: el servicio solo lee, limita peticiones y respeta CORS; US1–US3 funcionan.

---

## Phase 6: User Story 4 - Monitorear el servicio y consultar su documentación (Priority: P3)

**Goal**: `/health/live`, `/health/ready` e `/info` según el contrato de salud v1, y documentación OpenAPI
en español desactivable.

**Independent Test**: las tres rutas responden según `contracts/health-v1.md` con la base disponible y
caída; `/docs` y `/openapi.json` responden 404 con `DOCS_ENABLED=false`.

### Tests for User Story 4 ⚠️

- [X] T054 [P] [US4] Escribir `tests/unit/test_health_service.py` con un Repository falso: `ready()` correcto → `status ok`, `latency_ms` ≥ 0, `error None`; `DatabaseUnavailableError("connection_error")` → `unavailable`/`connection_error`; un `ping` más lento que `ready_timeout_seconds=0.05` → `timeout` con `latency_ms` ≥ 50; cualquier otra excepción → `unexpected_error`; `info()` con `service="maily-public-api"`, `version=VERSION` y `unknown` sin variables
- [X] T055 [P] [US4] Escribir `tests/contract/test_health_api.py`: `/health/live` 200 `{"status": "ok"}`; `/health/ready` 200 y 503 con los cuerpos exactos de `contracts/health-v1.md` (Repository sustituido); `/info` con las cinco claves; las tres con `Cache-Control: no-store`; con `rate_limit_per_minute=1`, después de agotar el límite en el catálogo, cinco peticiones a cada ruta de salud responden 200
- [X] T056 [P] [US4] Escribir `tests/contract/test_openapi.py`: `info.title == "MailySoft Public API"` e `info.version == VERSION == "1.0.0"`; descripción en español; `operationId` `list_subscriptions` con etiqueta `subscriptions`, ejemplo 200 y respuestas 405/429/500/503 con `ErrorResponse`; sin `securitySchemes`; `/docs` 200 HTML y `/redoc` 404; con `docs_enabled=False`, `/docs` y `/openapi.json` → 404 `not_found`
- [X] T057 [P] [US4] Escribir `tests/integration/test_health_ready_db.py` (`slow`): `/health/ready` 200 con el rol de solo lectura; con `database_url` hacia un puerto cerrado → 503 `connection_error` dentro de `health_ready_timeout_seconds`

### Implementation for User Story 4

- [X] T058 [P] [US4] Crear `src/dtos/health.py`: `LiveResponse(status: Literal["ok"])`, `CheckResult(name: Literal["database"], status: Literal["ok", "error"], latency_ms: int ≥ 0, error: Literal["timeout", "connection_error", "unexpected_error"] | None)`, `ReadyResponse(status: Literal["ok", "unavailable"], checks: list[CheckResult])` e `InfoResponse(service, version, commit, build_date, environment)`, con descripciones en español
- [X] T059 [P] [US4] Crear `src/repositories/database_health_repository.py`: `DatabaseHealthRepository(session).ping()` en dos fases (`open_connection`; `SELECT 1`, donde un `DBAPIError` con conexión invalidada → `connection_error` y cualquier otro error → `unexpected_error`); el límite de tiempo es del llamador
- [X] T060 [US4] Crear `src/services/health_service.py`: `HealthService(repository, ready_timeout_seconds, build_info)` con `ready() -> ReadyResponse` (`time.perf_counter`, `asyncio.timeout`, `latency_ms` entero también al fallar; nunca lanza) e `info() -> InfoResponse` (depende de T058, T059). Hacer pasar T054
- [X] T061 [US4] Crear `src/routers/health.py`: `APIRouter(tags=["Salud"])` sin prefijo y sin límite de peticiones, con `GET /health/live`, `GET /health/ready` (200 o 503 según `status`) y `GET /info`, todas con `Cache-Control: no-store` y respuestas documentadas en español; agregar `get_database_health_repository` y `get_health_service` en `src/dependencies.py` e incluir el router en `src/main.py` (depende de T060). Hacer pasar T055
- [X] T062 [US4] En `src/main.py`: descripción final del OpenAPI en español (qué publica el servicio, sin token, solo GET, formato de errores, caché y límite por IP, salud v1) y `openapi_tags` para `subscriptions` y `Salud`. Hacer pasar T056

**Checkpoint**: las cuatro historias funcionan; `uv run pytest` en verde.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: documentación, comprobaciones transversales y puertas de calidad.

- [X] T063 [P] Escribir `tests/unit/test_layers.py` (Principio I y IX): con `ast`, ningún módulo de `src/repositories/` importa `src.services` ni `src.routers`; ninguno de `src/services/` importa `src.routers`; `src/models/` no importa `src.dtos`, `src.services`, `src.repositories` ni `src.routers`; ningún módulo de `src/` importa `httpx` ni `alembic`
- [X] T064 [P] Escribir `README.md` en español: propósito del servicio, cómo correr pruebas (`uv run pytest` y `uv run pytest -m ""` con `db-test`), cómo levantarlo en local (puerto 8006, red de mailySoft-DB), variables de entorno (enlace a `contracts/environment.md`) y dependencias con mailySoft-DB (FR-027 y `docs/database/read-only-role.sql`)
- [X] T065 Construir la imagen (`docker build -t maily-public-api .`) y comprobar que `docker run --rm maily-public-api python -c "import httpx"` y `... "import pytest"` fallan, y que `docker run --rm maily-public-api` sin variables termina con un error que nombra `DATABASE_URL` y `CORS_ALLOWED_ORIGINS` sin mostrar valores
- [ ] T066 Puerta antes de `main` (Principio V; **bloqueada por FR-027**): `docker compose --profile test up -d db-test` y `uv run pytest -m ""` en verde; registrar el resultado. No forma parte de `/speckit-implement`
- [ ] T067 Ejecutar los escenarios 1–14 y la sección 6 de `specs/001-public-subscriptions-catalog/quickstart.md` (requiere mailySoft-DB con FR-027 y el rol); el escenario de la sección 5 (SC-005), en el ambiente compartido de desarrollo

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: sin dependencias.
- **Foundational (Phase 2)**: depende de Setup; bloquea todas las historias.
- **US1 (Phase 3)**: depende de Foundational. Es el MVP.
- **US2 (Phase 4)**: depende de US1 (extiende `PublicSubscriptionRead`, el Service y el Router del catálogo).
- **US3 (Phase 5)**: depende de Foundational y del router de US1 (al que aplica el límite y del que prueba los métodos); es independiente de US2.
- **US4 (Phase 6)**: depende solo de Foundational; puede hacerse en paralelo con US1–US3.
- **Polish (Phase 7)**: depende de las historias que se entreguen; T066 y T067 además de FR-027 (mailySoft-DB).

### User Story Dependencies

- **US1 (P1)**: tras Foundational; sin dependencias de otras historias.
- **US2 (P2)**: tras US1.
- **US3 (P2)**: tras US1 (router del catálogo); no depende de US2.
- **US4 (P3)**: tras Foundational; independiente de US1–US3 (la prueba de «salud sin límite», T055, usa el catálogo y el limitador, así que conviene correrla después de US3).

### Within Each User Story

- Las pruebas se escriben primero y deben fallar.
- Modelos → DTOs → Repositories → Services → Routers → registro en `src/main.py`.
- Las pruebas `slow` se escriben, pero no se ejecutan en `/speckit-implement`.

### Parallel Opportunities

- Setup: T003, T004, T005 y T006 en paralelo tras T001–T002.
- Foundational: T007, T008, T010, T012, T015, T019 y T022 en paralelo (archivos distintos).
- US1: T023–T026 en paralelo; luego T027, T028, T030 y T033 en paralelo.
- US2: T036–T038 en paralelo; T039 y T040 en paralelo.
- US3: T045–T050 en paralelo.
- US4: T054–T057 en paralelo; T058 y T059 en paralelo. US4 completa puede avanzar en paralelo con US1–US3.
- Polish: T063 y T064 en paralelo.

---

## Parallel Example: User Story 1

```bash
# Pruebas de US1 en paralelo:
Task: "Pruebas unitarias del Service en tests/unit/test_subscription_catalog_service.py"
Task: "Contrato del catálogo en tests/contract/test_subscriptions_api.py"
Task: "Repository contra PostgreSQL en tests/integration/test_subscription_repository.py"
Task: "Punta a punta en tests/integration/test_catalog_api.py"

# Modelos y DTOs de US1 en paralelo:
Task: "SubscriptionType en src/models/subscription_type.py"
Task: "SubscriptionModule en src/models/subscription_module.py"
Task: "DTOs en src/dtos/subscription.py"
Task: "Respuestas de error documentadas en src/routers/openapi_docs.py"
```

## Parallel Example: User Story 3

```bash
Task: "Limitador en tests/unit/test_rate_limit.py"
Task: "IP del cliente en tests/unit/test_client_ip.py"
Task: "Políticas HTTP en tests/contract/test_http_policies.py"
Task: "Rutas solo GET en tests/contract/test_get_only_routes.py"
Task: "Permisos del rol en tests/integration/test_read_only_role.py"
Task: "Fallas de la base en tests/integration/test_database_failures.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Phase 1: Setup.
2. Phase 2: Foundational.
3. Phase 3: US1 → `uv run pytest` en verde → el catálogo público ya sirve a la página (con claves de módulo).
4. **STOP and VALIDATE** con las pruebas de contrato; la validación contra la base real espera a FR-027.

### Incremental Delivery

1. Setup + Foundational.
2. US1 (MVP) → US2 (nombres de módulos) → US3 (protección) → US4 (salud y documentación).
3. Antes de exponer el servicio al público en un ambiente compartido, US3 y US4 deben estar completas
   (límite por IP, CORS y monitoreo).

### Notas

- [P] = archivos distintos y sin dependencias pendientes.
- Hacer commit por tarea o grupo lógico.
- Ninguna tarea crea migraciones, ejecuta DDL en ambientes compartidos ni agrega dependencias fuera de la
  tabla de la constitución.
