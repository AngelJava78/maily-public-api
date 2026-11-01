# Research: Catálogo público de suscripciones

Fase 0 del plan. Cada decisión resuelve una incógnita del contexto técnico o una elección que la
especificación dejó al plan. Formato: decisión, justificación y alternativas descartadas.

## R1. Dónde vive el límite de peticiones por IP (FR-019)

- **Decisión**: en la aplicación, como una dependencia de FastAPI aplicada solo al router de `/api/v1`, con
  un algoritmo de cubeta de fichas (*token bucket*) en memoria por IP: capacidad = `RATE_LIMIT_PER_MINUTE`
  (60 por omisión) y recarga de `RATE_LIMIT_PER_MINUTE / 60` fichas por segundo. Sin ficha disponible:
  429 `rate_limit_exceeded` con `Retry-After` = segundos (redondeados hacia arriba) hasta la siguiente
  ficha. `RATE_LIMIT_PER_MINUTE=0` apaga el límite en la aplicación y solo se usa si la infraestructura lo
  aplica. Las entradas de IP inactivas (cubeta llena de nuevo) se purgan cuando el diccionario crece, para
  acotar la memoria. El reloj es inyectable (`time.monotonic` por omisión) para las pruebas unitarias.
- **Justificación**: el servicio se despliega en Railway (mailysoft-infrastructure, fase 1) con dominio
  público y sin gateway, WAF ni regla de límite configurable en la infraestructura actual; la única capa
  que hoy puede aplicarlo es la aplicación. La cubeta de fichas no permite la ráfaga doble en el borde de
  una ventana fija y ocupa memoria constante por IP. Vivir como dependencia del router deja fuera, por
  construcción, a las rutas de salud y a la documentación.
- **Alternativas descartadas**: (a) `slowapi`/`limits`: es una tecnología nueva fuera de la tabla de la
  constitución (requeriría enmienda) para una lógica de pocas líneas. (b) En la infraestructura: no existe
  hoy; si se agrega (p. ej. un CDN o un gateway delante de Railway), se pone `RATE_LIMIT_PER_MINUTE=0`
  sin cambiar código. (c) Ventana fija: más simple pero permite el doble del límite en el cambio de
  ventana.
- **Limitación aceptada**: el contador es por proceso. Con varias réplicas el límite efectivo es
  `réplicas × límite`; hoy Railway corre una réplica. Un almacén compartido (Redis) sería otra tecnología.

## R2. Cómo se obtiene la IP del cliente detrás de un proxy (FR-019, caso borde de `X-Forwarded-For`)

- **Decisión**: `TRUSTED_PROXY_HOPS` (0 por omisión, de 0 a 5) = número de proxies de confianza delante
  del servicio. Con 0 se usa la IP de la conexión TCP. Con N > 0 se toma la N-ésima dirección contando
  desde la **derecha** de `X-Forwarded-For` (la que escribió el proxy de confianza más externo); si la
  cabecera tiene menos de N direcciones o la dirección no es una IP válida, se usa la IP de la conexión.
  uvicorn se arranca con `--no-proxy-headers` para que no reescriba la IP de la conexión por su cuenta.
- **Justificación**: tomar la dirección de la izquierda de `X-Forwarded-For` permite que un cliente
  falsifique su IP y evada el límite. Contar saltos desde la derecha solo confía en lo que escribieron los
  proxies propios. En Railway las direcciones del proxy de borde no son fijas, así que una lista de redes
  de confianza no se puede mantener; un conteo de saltos sí. Las respuestas del personal de Railway sobre
  si su borde reemplaza o agrega a `X-Forwarded-For` se contradicen ([foro de Railway][r1], [r2], [r3]);
  con `TRUSTED_PROXY_HOPS=1` la dirección de la derecha es la del cliente en ambos casos. Por esa
  incertidumbre, el quickstart incluye un paso para verificar las cabeceras reales en el ambiente de
  desarrollo antes de fijar el valor.
- **Alternativas descartadas**: (a) `X-Real-IP`: hay reportes de que con el CDN de Railway contiene la IP
  del CDN y no la del cliente. (b) `ProxyHeadersMiddleware` de uvicorn con `forwarded_allow_ips="*"`: confía
  en la dirección de la izquierda, falsificable. (c) Lista de redes de confianza: inviable sin direcciones
  fijas del proxy.

[r1]: https://station.railway.com/questions/edge-proxy-x-forwarded-for-and-x-real-ip-c5a50049
[r2]: https://station.railway.com/questions/does-the-edge-strip-client-x-forwarded-f-613e5cb6
[r3]: https://station.railway.com/questions/edge-cdn-layer-leaking-its-own-ip-as-cli-1ce29b05

## R3. Usuario de base de datos: tablas con permisos por columna o vista dedicada (FR-025/FR-026)

- **Decisión**: la opción de referencia de FR-025 (tablas, con `SELECT` solo sobre las columnas que se
  leen). La propuesta exacta para mailySoft-DB vive en
  [`docs/database/read-only-role.sql`](../../docs/database/read-only-role.sql) y se describe en
  [contracts/database-permissions.md](contracts/database-permissions.md). Las pruebas lentas aplican ese
  mismo archivo a la base desechable, así que lo que se propone y lo que se prueba no pueden divergir.
- **Justificación**: los permisos por columna dan el mismo privilegio mínimo que una vista sin que la regla
  de publicación (Activa y autoservicio) quede escrita en dos repositorios: vive en el Service de este
  servicio, que la aplica en la consulta (Principio I). No hay un objeto de mailySoft-DB atado a este
  servicio que haya que cambiar cada vez que cambie el contrato.
- **Alternativas descartadas**: vista `public_subscriptions_catalog` en mailySoft-DB. Ventaja real: el
  usuario ni siquiera vería las filas no públicas. Se descarta por duplicar la regla de publicación y
  obligar a una migración de mailySoft-DB por cada campo nuevo del contrato. Si mailySoft-DB la prefiere,
  solo cambian `src/models/` y el Repository (FR-026 lo permite).
- **Seguimiento**: cuando mailySoft-DB adopte el rol en sus migraciones, las pruebas lentas deben aplicar
  el archivo de mailySoft-DB en lugar de `docs/database/read-only-role.sql`, y este archivo se elimina.

## R4. Solo lectura, tiempo máximo y aislamiento de cada lectura (FR-015, FR-016)

- **Decisión**: el engine de `src/database/session.py` se crea con:
  - `connect_args={"timeout": DATABASE_QUERY_TIMEOUT_SECONDS, "server_settings": {"application_name":
    "maily-public-api", "default_transaction_read_only": "on", "statement_timeout": "<ms>"}}`.
  - `execution_options(isolation_level="REPEATABLE READ", postgresql_readonly=True)`: cada transacción
    se abre como `BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY`.
  - `pool_pre_ping=True`, `pool_size=5`, `max_overflow=5` (máximo 10 conexiones por réplica).
  Además, el Service envuelve cada lectura completa (obtener la conexión + consultas) en
  `asyncio.timeout(DATABASE_QUERY_TIMEOUT_SECONDS)`; ese es el límite que garantiza FR-015 de punta a punta.
- **Justificación**: tres capas independientes (permisos del usuario, transacción `READ ONLY` pedida por
  el servicio y `default_transaction_read_only` del rol) hacen que una escritura sea imposible aunque una
  falle. `statement_timeout` corta la consulta en el servidor y libera la base compartida;
  `asyncio.timeout` cubre lo que el servidor no ve (conexión que no se establece, espera de una conexión
  libre del pool). `REPEATABLE READ` hace que las tres consultas del catálogo (R6) vean la misma
  instantánea; en una transacción de solo lectura no produce fallos de serialización. El pool acotado
  impide que el tráfico público agote las conexiones de la base compartida (el rol tiene además un
  `CONNECTION LIMIT`, R3).
- **Alternativas descartadas**: solo `statement_timeout` (no cubre una conexión colgada); solo
  `asyncio.timeout` (deja la consulta corriendo en el servidor); `READ COMMITTED` (las consultas podrían
  ver estados distintos si maily-system-api escribe entre ellas).

## R5. Clasificación de las fallas de la base de datos (FR-013, FR-015, caso borde de permisos)

- **Decisión**: el Repository traduce las excepciones a `DatabaseUnavailableError` (→ 503
  `service_unavailable`) cuando: se agota `asyncio.timeout`; falla la obtención de la conexión (cualquier
  error, incluidos `OSError`, credenciales rechazadas o demasiadas conexiones); o la consulta falla con la
  conexión invalidada o con un SQLSTATE de las clases `08` (conexión), `53` (recursos insuficientes) o
  `57` (intervención del operador, incluido `57014` por `statement_timeout`). Cualquier otro error de la
  consulta (p. ej. `42501` por un permiso faltante) se deja subir y termina en 500 `internal_error`, con
  la traza en el registro y el mensaje genérico al cliente. Mismo criterio de dos fases que el
  `DatabaseHealthRepository` de maily-system-api.
- **Justificación**: el cliente solo necesita saber si reintentar; quien opera necesita distinguir «la base
  no está» (503, transitorio, el monitoreo ya lo ve en `/health/ready`) de «el servicio está mal
  configurado» (500 persistente que hay que corregir).
- **Alternativas descartadas**: todo como 503 (ocultaría un error de configuración como si fuera una caída);
  todo como 500 (contradice FR-013 para la base caída).

## R6. Consultas del catálogo y modelos ORM con permisos por columna (FR-004 a FR-012)

- **Decisión**: tres consultas en una transacción:
  1. `subscriptions` filtradas por `status_id` y `self_service` (criterio que fija el Service), ordenadas
     por `created_at, id`, con `joinedload` de `subscription_type` (`subscription_types.id, name`).
  2. `selectinload` de `Subscription.modules` (`subscription_modules`), ordenada por `module_key` en la
     base de datos, igual que la relación de maily-system-api.
  3. `modules` con `key IN (<todas las claves del paso 2>)`, `status_id = 1` y `type_id = 2` (criterio del
     Service).
  Los modelos mapean solo las columnas concedidas (data-model.md). `Module` no tiene permiso sobre `id`, así
  que su mapeo declara `key` como clave primaria del mapper (`__mapper_args__ = {"primary_key": [key]}`):
  es única entre los módulos no Eliminados (índice `modules_key_not_deleted_key`) y la consulta solo lee
  Activos.
- **Justificación**: ordenar `module_keys` en la base de datos con la misma expresión que maily-system-api
  garantiza el mismo orden bajo la misma intercalación (con `_` en las claves, ordenar en Python podría
  diferir), que es lo que pide FR-009/SC-005. El filtro se aplica en la consulta (Principio I) y las filas
  no públicas no se cargan. Tres consultas acotadas cumplen de sobra SC-006 con ≤ 500 suscripciones.
- **Alternativas descartadas**: una sola consulta con `json_agg` (mapeo manual, menos legible y sin modelos
  ORM); relación ORM `SubscriptionModule → Module` por `key` (no hay clave foránea y mezclaría el criterio
  de módulos publicables en el modelo); conceder `SELECT` sobre `modules.id` solo para el ORM (ampliaría
  los permisos sin necesidad).

## R7. Composición de `modules` y avisos (FR-011, FR-012, FR-007)

- **Decisión**: el Service arma, por suscripción, `modules` = módulos encontrados para sus claves,
  ordenados por `(sort_order, key)` en Python. Una clave sin módulo encontrado se omite y se registra un
  aviso `WARNING` con `subscription_id` y `module_key`, **una vez por proceso** por pareja (conjunto acotado
  a 1 000 parejas). Si el catálogo publicado supera 500 suscripciones, se registra un aviso una vez por
  proceso y se devuelven todas.
- **Justificación**: el aviso sirve para que alguien corrija el catálogo; repetirlo en cada petición (hasta
  60 por minuto por IP) solo llenaría los registros. El orden de `modules` no tiene equivalente en
  maily-system-api, así que no necesita la intercalación de la base.
- **Alternativas descartadas**: registrar en cada petición; fallar el catálogo entero; incluir la clave con
  `name: null` (obliga al Frontend a manejar un caso que la especificación decidió ocultar).

## R8. Formato de errores, 404, 405 y caché de errores (FR-003, FR-013, FR-014, FR-017)

- **Decisión**: `src/error_handlers.py` registra manejadores para `AppError` (errores propios),
  `StarletteHTTPException` (404 de rutas inexistentes y documentación apagada; 405 conservando la cabecera
  `Allow` que pone Starlette, que en una ruta `APIRoute` solo GET es `Allow: GET`) y `Exception` (500).
  Todos responden `{code, message}` con `Cache-Control: no-store`. `HEAD` no se agrega a las rutas
  `APIRoute`, así que responde 405. No se registra manejador de `RequestValidationError`: la operación no
  tiene parámetros y los de consulta se ignoran.
- **Justificación**: mismo cuerpo que maily-system-api; ningún error usa `{"detail": …}`.
- **Limitación aceptada**: el 500 lo produce el `ServerErrorMiddleware` de Starlette, que envuelve al de
  CORS; esa respuesta no lleva cabeceras CORS. El Frontend recibe un error de red en lugar del cuerpo, que
  igual no muestra detalles.

## R9. CORS, `Cache-Control` y `Vary` (FR-017, FR-018)

- **Decisión**: `CORSMiddleware` con `allow_origins` = lista de `CORS_ALLOWED_ORIGINS` (obligatoria, sin
  `*`, cada origen `http(s)://host[:puerto]` sin ruta), `allow_methods=["GET"]`, `allow_credentials=False`,
  `allow_headers=[]`. El Router del catálogo pone en la respuesta 200
  `Cache-Control: public, max-age=<CATALOG_CACHE_MAX_AGE_SECONDS>` y `Vary: Origin` siempre (también sin
  cabecera `Origin`); las rutas de salud ponen `Cache-Control: no-store`.
- **Justificación**: `CORSMiddleware` solo agrega `Vary: Origin` cuando la petición trae `Origin`; una
  caché intermedia podría guardar la respuesta sin permiso CORS y entregarla al navegador. Ponerlo siempre
  en el Router lo evita. Las pruebas comprueban que `Origin` esté entre los valores de `Vary` (el
  middleware puede repetirlo).
- **Alternativas descartadas**: `allow_origin_regex` (más difícil de auditar); `Cache-Control` en un
  middleware global (pondría caché pública a respuestas que no deben tenerla).

## R10. Configuración (FR-023, FR-024)

- **Decisión**: `src/config.py` con pydantic-settings, `.env` opcional y `env_ignore_empty=True`:

  | Variable | Por omisión | Validación |
  |---|---|---|
  | `DATABASE_URL` | obligatoria | Esquema `postgresql+asyncpg://` con host |
  | `CORS_ALLOWED_ORIGINS` | obligatoria | Lista separada por comas, ≥ 1 origen, sin `*`, sin ruta |
  | `CATALOG_CACHE_MAX_AGE_SECONDS` | 300 | Entero de 0 a 86 400 |
  | `DATABASE_QUERY_TIMEOUT_SECONDS` | 3 | Número de 1 a 30 |
  | `DOCS_ENABLED` | `true` | Booleano |
  | `RATE_LIMIT_PER_MINUTE` | 60 | Entero de 0 a 10 000 |
  | `TRUSTED_PROXY_HOPS` | 0 | Entero de 0 a 5 |
  | `HEALTH_READY_TIMEOUT_SECONDS` | 2 | Número > 0 y ≤ 10 |
  | `APP_COMMIT_SHA`, `APP_BUILD_DATE`, `APP_ENVIRONMENT` | vacías → `unknown` | Las del contrato v1 |

  `create_app(settings)` recibe la configuración ya validada y no tiene efectos secundarios (no lee
  variables ni abre conexiones), así que las pruebas la construyen con la configuración que quieran. El
  punto de entrada es la fábrica `src.main:create_app_from_environment` (uvicorn `--factory`): carga toda
  la configuración, junta todos los errores y, si hay alguno, detiene el arranque con un mensaje que nombra
  las variables, nunca sus valores; si no, llama a `create_app(settings)`. Así la documentación
  (`DOCS_ENABLED`) y los orígenes de CORS se conocen al construir la aplicación. En local también
  funciona `uvicorn src.main:app`, como en maily-system-api: `app` llama a la fábrica la primera vez que
  se pide (`__getattr__` del módulo), así que importar `src.main` sigue sin leer variables.
- **Justificación**: los nombres siguen las convenciones de maily-system-api (`DATABASE_URL`,
  `CORS_ALLOWED_ORIGINS`, `HEALTH_READY_TIMEOUT_SECONDS`, `APP_*`). La base no disponible no impide
  arrancar (el engine se crea en el primer uso).
- **Alternativas descartadas**: un `CORS_ALLOWED_ORIGINS` vacío que deje sin CORS (en maily-system-api es
  válido; aquí el único consumidor es el Frontend en navegador, así que vacío es un error de configuración).

## R11. Base de datos de las pruebas con el esquema de mailySoft-DB (Principio V)

- **Decisión**: las pruebas lentas usan `TEST_DATABASE_URL` (usuario administrador de una base desechable
  PostgreSQL 18 cuyo nombre MUST terminar en `_test`; el servicio `db-test` del Compose, perfil `test`,
  puerto `127.0.0.1:5436`). Por sesión de pruebas: recrean el esquema `public`, aplican
  `schema/current_schema.sql` de mailySoft-DB y los catálogos repetibles que necesitan
  (`R__40_cat_subscription_statuses.sql`, `R__40_cat_subscription_types.sql`,
  `R__40_cat_module_statuses.sql`, `R__40_cat_module_types.sql`), crean el rol de solo lectura con
  `docs/database/read-only-role.sql` (contraseña aleatoria por sesión) y se conectan **como ese rol**
  para probar los Repositories y la API de punta a punta. Los datos de prueba se insertan con el
  administrador. La ruta a mailySoft-DB sale de `MAILYSOFT_DB_DIR` (por omisión, `../mailySoft-DB`); si no
  existe, las pruebas fallan con un mensaje que lo explica.
- **Justificación**: el esquema sale de los artefactos de mailySoft-DB, nunca de DDL escrito aquí
  (Principio VI). `current_schema.sql` es un `pg_dump --schema-only --no-owner --no-privileges` sin
  metacomandos de psql, ejecutable como script con asyncpg en una conexión dedicada (fija
  `search_path` a vacío, por eso no se reutiliza). Conectarse como el rol real detecta en las pruebas una
  consulta fuera de sus permisos.
- **Alternativas descartadas**: Flyway en Docker desde las pruebas (más lento y mete Docker dentro de
  pytest); copiar el esquema a este repositorio (se desactualiza); SQLite (prohibido).
- **Dependencia bloqueante**: hoy `current_schema.sql` (mailySoft-DB V5) no tiene `subscription_modules` ni
  `subscriptions.clinics_limit` (FR-027). Hasta que mailySoft-DB los incorpore, las pruebas lentas no
  pueden pasar; las de la corrida por defecto (sin base) sí.

## R12. Pruebas por nivel (Principio V)

- **Decisión**:
  - **Corrida por defecto (sin PostgreSQL)**: unitarias de los Services con Repositories falsos; de la
    configuración; del limitador (reloj falso) y de la resolución de IP; y **de contrato de cada endpoint**
    con httpx `ASGITransport` contra la aplicación real con `dependency_overrides` que sustituyen los
    Repositories por dobles (incluido uno que lanza `DatabaseUnavailableError`). Cubren códigos, forma
    exacta de los DTOs, campos excluidos, cabeceras (`Cache-Control`, `Vary`, CORS, `Allow`,
    `Retry-After`), 404/405/429/503/500, salud, OpenAPI y la prueba de rutas solo GET.
  - **`slow` (PostgreSQL 18 real, marcadas por el hook de `pytest_collection_modifyitems`)**: Repositories
    conectados como el rol de solo lectura (filtro con suscripciones en cada estatus y sin autoservicio,
    orden, módulos Activos/Bloqueados/Eliminados/Sistema/inexistentes); permisos del rol (SC-004: `INSERT`,
    `UPDATE`, `DELETE` rechazados aun con `BEGIN READ WRITE`; lectura de una tabla no concedida
    rechazada); `statement_timeout` → 503; y un recorrido de punta a punta de la API con la base real.
- **Justificación**: el ciclo de `/speckit-implement` corre en segundos y cubre el contrato completo; la
  garantía sobre la base real queda como puerta antes de `main`.

## R13. Ejecución local y contenedor (Stack y Restricciones)

- **Decisión**: `Dockerfile` igual al de maily-system-api (`python:3.14-slim`, `uv==0.13.1`,
  `uv sync --frozen --no-dev`, argumentos `APP_COMMIT_SHA`/`APP_BUILD_DATE`) sin Alembic, con
  `CMD ["sh", "-c", "exec uvicorn src.main:create_app_from_environment --factory --host 0.0.0.0 --port ${PORT:-8000} --no-proxy-headers"]`
  (Railway inyecta `PORT`). `docker-compose.yml`: servicio `api` (puerto `8006:8000`) unido a la red
  externa `mailysoft-db_default` del Compose de mailySoft-DB, con `DATABASE_URL` hacia `db-local:5432`
  desde `.env`; servicio `db-test` (`postgres:18`, perfil `test`, `127.0.0.1:5436`, datos en `tmpfs`).
- **Justificación**: el servicio usa la base compartida local (no una propia); la base de pruebas es
  desechable y aislada. Las dependencias de desarrollo (pytest, httpx) no entran en la imagen.
- **Pendiente operativo**: hasta que mailySoft-DB cree el rol, en local se crea a mano aplicando
  `docs/database/read-only-role.sql` sobre `db-local` (quickstart). Es un paso de quien desarrolla, no del
  servicio, que nunca ejecuta DDL.

## R14. Versiones y dependencias

- **Decisión**: las mismas restricciones que maily-system-api: `fastapi>=0.143`, `uvicorn>=0.30`,
  `sqlalchemy[asyncio]>=2.0,<2.1`, `asyncpg>=0.30`, `pydantic-settings>=2.6`; desarrollo:
  `pytest>=8.3`, `pytest-asyncio>=1.0`, `httpx>=0.28`. Sin Alembic ni httpx en las dependencias del
  servicio. Versión inicial del servicio `1.0.0` en `src/__init__.py` (`VERSION`), `pyproject.toml` y
  OpenAPI.
- **Justificación**: mismo stack probado en maily-system-api (constitución, «Stack Tecnológico»).
