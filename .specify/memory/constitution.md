# MailySoft Public API Constitution

Servicio REST público de MailySoft, de **solo lectura** y **sin autenticación**, que publica el
catálogo de **suscripciones** (planes) para la página pública «Suscripciones» del Frontend de Maily.
No administra datos: lee la base de datos compartida de MailySoft, cuyo esquema administra
mailySoft-DB, con un usuario de solo lectura. No se comunica con el proveedor de identidad ni con
otras APIs. Toma como base la constitución de maily-system-api (v1.1.0), adaptada a un servicio
público.

## Core Principles

### I. Arquitectura en Capas Estricta

El código se organiza en las capas Routers → Services → Repositories → Database, apoyadas por
`src/models/` (modelos ORM) y `src/dtos/` (esquemas de API). Reglas no negociables:

- Todo el código fuente de la aplicación MUST residir en la carpeta `src/` en la raíz del
  repositorio, con una subcarpeta por capa: `src/routers/`, `src/services/`,
  `src/repositories/`, `src/database/`, `src/models/` y `src/dtos/`. Fuera de `src/` solo se
  permiten pruebas (`tests/`), configuración, Docker y documentación. No existen
  `src/integrations/` (Principio IX) ni `alembic/` (Principio VI).
- Los **Routers** MUST limitarse a recibir la petición HTTP, validar con DTOs, invocar Services
  y serializar la respuesta. Los Routers MUST NOT acceder a la base de datos, a sesiones de
  SQLAlchemy ni a Repositories directamente.
- Los **Services** MUST contener toda la lógica de negocio (qué suscripciones son públicas, el
  orden del catálogo, la composición de cada plan con los nombres de sus módulos) y coordinar uno
  o más Repositories.
- Los **Repositories** MUST encapsular todo el acceso a los datos: son la única capa que construye
  consultas y lee modelos ORM. MUST NOT contener reglas de negocio ni escribir datos. MUST aplicar
  en la consulta el criterio de publicación que fija el Service (o leer una vista que ya lo
  aplique) y MUST NOT cargar filas no públicas para descartarlas en memoria.
- La capa **Database** MUST centralizar la configuración del engine async, la fábrica de
  sesiones y su ciclo de vida (inyectado vía dependencias de FastAPI), incluidos el modo de solo
  lectura y el tiempo máximo de consulta (Principio VI).
- Las dependencias MUST fluir en un solo sentido (Router → Service → Repository → Database); una
  capa inferior MUST NOT importar una superior.

**Rationale**: El aislamiento de responsabilidades permite probar cada capa por separado,
sustituir la persistencia sin tocar la API y mantener la lógica de negocio en un único lugar.
Filtrar en la consulta hace que los datos no públicos nunca salgan de la base de datos.

### II. Separación entre Modelos ORM y DTOs

- `src/models/` MUST contener solo modelos SQLAlchemy 2.0 que mapean las tablas (o la vista) que
  se leen; MUST NOT concentrar reglas de negocio.
- `src/dtos/` MUST contener los esquemas Pydantic v2 de entrada y salida de la API, separados de
  los modelos de persistencia (p. ej. `PublicSubscriptionRead`, `ErrorResponse`).
- Los Routers MUST validar la entrada (parámetros de ruta y de consulta) y serializar la salida
  exclusivamente con DTOs; MUST NOT exponer entidades ORM en respuestas HTTP. La conversión
  ORM → DTO MUST hacerse de forma explícita (p. ej. `model_validate` con `from_attributes=True`).
- Los DTOs de salida MUST llevar solo datos públicos y solo los campos del contrato publicado.
  MUST NOT incluir estatus, fechas, conteos internos, datos personales ni ningún otro campo que el
  contrato no declare. Agregar un campo es un cambio del contrato que MUST declararse en la
  especificación de la feature.

**Rationale**: Desacoplar el contrato público del esquema de base de datos evita fugas de datos
y permite evolucionar la persistencia sin romper a los consumidores. En un servicio que cualquiera
puede consultar, cada campo de más es una fuga visible para todos.

### III. Asincronía de Extremo a Extremo

- Toda operación de I/O (base de datos, archivos, red) MUST ser asíncrona usando
  `async`/`await`.
- El acceso a PostgreSQL MUST usar SQLAlchemy 2.0 en modo async con el driver `asyncpg`
  (`AsyncEngine`, `AsyncSession`).
- Las llamadas bloqueantes (p. ej. drivers síncronos) MUST NOT usarse en el camino de una
  petición.
- Cuando una librería solo ofrezca API síncrona, su uso MUST aislarse (p. ej.
  `run_in_threadpool`) y justificarse en el plan de la feature.

**Rationale**: Un único hilo de eventos bloqueado degrada a todas las peticiones concurrentes; en
un servicio público, expuesto a tráfico anónimo, la asincronía consistente es requisito de
disponibilidad.

### IV. Contratos de API Documentados con OpenAPI

- Cada endpoint MUST estar documentado en el esquema OpenAPI generado por FastAPI, con
  `response_model`, códigos de estado (incluidos los de error), `tags` (p. ej. `subscriptions`) y
  descripciones.
- **Solo lectura**: la API MUST exponer únicamente operaciones GET. MUST NOT existir ninguna
  operación que cree, cambie o borre datos (POST, PUT, PATCH, DELETE), ni siquiera oculta del
  esquema. Una petición con otro método a una ruta existente MUST responder 405 con el formato de
  error común.
- Las rutas de la API MUST llevar el prefijo `/api/v1`; las de salud y la documentación publicada
  quedan en la raíz (ver «Salud y Monitoreo»). Los cambios incompatibles en un contrato publicado
  MUST versionarse (p. ej. `/api/v2`) y declararse en la especificación de la feature.
- Los códigos de estado MUST ser coherentes: 200 al consultar, 404 si el recurso no existe o no es
  público, 405 ante un método no permitido, 422 ante parámetros inválidos, 429 al superar el límite
  de peticiones, 503 si la base de datos no responde o se agota el tiempo máximo de consulta, y
  500 solo ante un fallo inesperado. El servicio MUST NOT responder 401 ni 403 (Principio VIII).
- Todos los errores MUST usar el mismo cuerpo que maily-system-api: `{"code", "message"}`, con
  `code` estable en inglés y `message` en español, sin detalles técnicos; `errors` (lista de
  `{field, message}`) solo en `validation_error`. Esto incluye los 404 de rutas inexistentes, los
  405, los 429 que emita la aplicación y los 500: ninguno usa el cuerpo por defecto
  `{"detail": …}` de FastAPI.
- El **catálogo de suscripciones** MUST devolverse completo, sin paginar, igual que en
  maily-system-api: es un catálogo pequeño y acotado por diseño. La especificación MUST fijar el
  máximo esperado de elementos (no superior a 500) y un orden determinista. Si el catálogo supera
  ese máximo, el listado MUST pasar a paginarse, lo que es un cambio incompatible del contrato y
  se versiona.
- Cualquier otro listado MUST soportar paginación, salvo que su especificación declare la misma
  excepción con su máximo (no superior a 500) y su orden determinista.

**Rationale**: El contrato OpenAPI es la fuente de verdad para el Frontend y para las pruebas de
contrato. Exponer solo GET hace imposible, por construcción, que el servicio público altere datos;
el formato de error común permite que los consumidores de MailySoft traten igual a todos los
servicios.

### V. Pruebas Automatizadas con pytest

- Toda funcionalidad MUST tener pruebas automatizadas con `pytest` (y soporte async,
  p. ej. `pytest-asyncio`).
- Los Services MUST tener pruebas unitarias de sus reglas de negocio con los Repositories
  sustituidos por dobles de prueba.
- Cada endpoint MUST tener pruebas de integración/contrato contra la API (cliente HTTP async) que
  verifiquen códigos de estado, la forma de los DTOs (exactamente los campos del contrato, sin
  campos de más) y las cabeceras que exige esta constitución (`Cache-Control`, CORS).
- Las pruebas de Repositories MUST ejecutarse contra PostgreSQL 18 real (contenedor Docker), no
  contra un motor sustituto como SQLite, en una base desechable cuyo esquema MUST provenir de
  mailySoft-DB (sus migraciones o su `schema/current_schema.sql`), nunca de DDL escrito a mano en
  este repositorio; el plan fija cómo se aplica. Sus datos de prueba MUST incluir suscripciones no
  públicas (Inactiva, Bloqueada, Eliminada y sin autoservicio) para comprobar que nunca se
  devuelven. SHOULD conectarse con un usuario con los mismos permisos que el usuario de solo
  lectura del servicio, para que una consulta fuera de esos permisos falle en las pruebas y no en
  producción.
- Las pruebas automatizadas MUST NOT conectarse a la base de datos compartida, ni a la local ni a
  la de ningún ambiente: solo a la base desechable.
- Una prueba MUST recorrer las rutas registradas de la aplicación y fallar si alguna admite un
  método distinto de GET; las únicas rutas excluidas de esa revisión son las de la documentación
  publicada (`/docs`, `/redoc`, `/openapi.json`) y las de salud (`/health/live`, `/health/ready`,
  `/info`). La misma prueba MUST comprobar que el esquema OpenAPI solo contiene operaciones `get`.
- **Dos niveles de ejecución** (como en maily-system-api): toda prueba que necesite, directa o
  transitivamente, una base de datos real MUST marcarse `slow` de forma automática (un hook de
  `pytest_collection_modifyitems`, no a mano en cada archivo) y MUST quedar excluida de la corrida
  por defecto (`pyproject.toml`, `addopts = "-m 'not slow'"`). La corrida por defecto MUST NOT
  necesitar PostgreSQL. El ciclo activo de desarrollo de una feature (`/speckit-implement`) MUST
  limitarse a esa corrida por defecto; MUST NOT ejecutar ahí las pruebas marcadas `slow`.
- La suite completa (`uv run pytest -m ""`, unitarias + lo marcado `slow`) MUST pasar antes de
  integrar cambios en `main`. Esa corrida es responsabilidad de un pipeline de CI/despliegue;
  mientras ese pipeline no exista, quien integre el cambio a `main` MUST ejecutarla manualmente
  como sustituto explícito de esa puerta: su ausencia no exime la obligación, la traslada a una
  persona.

**Rationale**: El catálogo público es lo primero que ve un posible cliente; publicar un plan que no
debía verse o un precio equivocado es un error visible para cualquiera. Separar lo que necesita
PostgreSQL real de lo que no permite que el ciclo de desarrollo corra en segundos sin perder la
garantía, que se conserva como puerta de calidad antes de integrar. La prueba de rutas hace
comprobable que el servicio sigue siendo de solo lectura.

### VI. Sin Esquema Propio: Lectura de la Base de Datos Compartida

- El servicio MUST NOT tener migraciones (ni Alembic ni otra herramienta) ni ejecutar DDL
  (`CREATE`, `ALTER`, `DROP`, `GRANT`, …) ni sentencias que modifiquen datos.
- El servicio se conecta a la base de datos compartida de MailySoft, cuyo esquema administra
  mailySoft-DB. Todo cambio de esquema que necesite este servicio (una columna, un índice, una
  vista, un permiso) MUST proponerse, integrarse y desplegarse en mailySoft-DB, nunca aquí.
- El servicio MUST conectarse con un usuario de base de datos propio y de solo lectura que solo
  pueda consultar lo que necesita: las tablas del catálogo de suscripciones y los nombres de los
  módulos (en el esquema vigente, `subscriptions` y `modules`) o una vista creada para eso. Ese
  usuario MUST NOT tener otros privilegios ni ser propietario de objetos. El usuario y sus
  permisos se crean y versionan en mailySoft-DB, no en este repositorio.
- Toda sesión MUST abrir transacciones de solo lectura (p. ej. `default_transaction_read_only` o
  `SET TRANSACTION READ ONLY`) y aplicar un tiempo máximo de consulta (p. ej. `statement_timeout`)
  configurable por variable de entorno, como defensa adicional a los permisos del usuario. Una
  consulta que agota ese tiempo MUST responder 503 con el formato de error común, no 500.
- Los modelos de `src/models/` MUST reflejar solo las columnas que se leen, con los nombres y
  tipos del esquema vigente de mailySoft-DB (`schema/current_schema.sql` de ese repositorio), y
  MUST mantenerse consistentes con él. Un cambio en mailySoft-DB que afecte esas columnas MUST
  reflejarse aquí mediante una feature que lo declare en su especificación y en su
  `data-model.md`, citando la migración de mailySoft-DB que lo introduce.
- El estatus de una suscripción MUST reconocerse por su identificador (Activa = 1 en
  `subscription_statuses`), no por su nombre, como en maily-system-api.
- Los importes (precios) MUST transportarse con tipos decimales exactos (`NUMERIC` en la base de
  datos y `Decimal` en Python); MUST NOT usarse `float`. La forma de serializarlos en JSON la fija
  la especificación, en coherencia con maily-system-api.

**Rationale**: Un único dueño del esquema evita que dos repositorios lo modifiquen y diverjan. El
privilegio mínimo y las transacciones de solo lectura limitan el daño si el servicio público se
ve comprometido, y el tiempo máximo de consulta impide que tráfico anónimo degrade la base de datos
que comparten los demás servicios.

### VII. Idioma: Código en Inglés, Textos para Personas en Español

- Todos los identificadores del código (clases, funciones, métodos, variables, constantes y
  módulos) MUST estar en inglés.
- Los nombres de campos y parámetros de la API y los códigos de error MUST estar en inglés
  (p. ej. `monthly_price`, `modules`, `service_unavailable`).
- Los mensajes dirigidos a personas (los errores que devuelve la API), la documentación publicada
  de la API (descripciones y ejemplos de OpenAPI) y los documentos del proyecto (especificaciones,
  planes y guías) MUST estar en español.
- Los comentarios y docstrings del código SHOULD escribirse en inglés; toda excepción MUST
  justificarse en la revisión.

**Rationale**: Los consumidores técnicos de la API dependen de nombres y códigos estables y en un
único idioma, mientras que las personas que usan las aplicaciones necesitan mensajes que entiendan.
Separar ambos evita mezclarlos y hace comprobable cada regla.

### VIII. Acceso Público y Superficie Mínima

- Ninguna operación exige token ni otra credencial, y el esquema OpenAPI MUST NOT declarar
  esquemas de seguridad. El servicio MUST NOT aceptar, validar ni reenviar tokens: una cabecera
  `Authorization` o una cookie recibida se ignora, no cambia la respuesta y MUST NOT registrarse.
  El servicio MUST NOT comunicarse con Auth0 ni con otras APIs de MailySoft (Principio IX).
- El servicio MUST NOT tener credenciales de otros servicios: su único secreto es la conexión de
  solo lectura a la base de datos (Principio VI).
- Solo se publican datos pensados para ser públicos: las suscripciones **Activas** de
  **autoservicio** (`self_service = true`) y los nombres de sus módulos. Una suscripción Inactiva,
  Bloqueada, Eliminada o sin autoservicio MUST NOT aparecer en ninguna respuesta y, si se consulta
  de forma individual, se comporta como inexistente (404). Qué campos de cada suscripción se
  publican lo fija la especificación dentro de este límite (Principio II).
- CORS MUST restringirse a los orígenes del Frontend, tomados de una variable de entorno (p. ej.
  `CORS_ALLOWED_ORIGINS`) como lista explícita; MUST NOT permitir `*`, MUST permitir solo el
  método GET y MUST NOT permitir credenciales ni cookies.
- Las respuestas exitosas del catálogo MUST llevar una cabecera `Cache-Control` pública con un
  tiempo de caché configurable por variable de entorno (p. ej. `public, max-age=<segundos>`). Las
  respuestas de error MUST llevar `Cache-Control: no-store`, para que un error transitorio no
  quede guardado en cachés intermedias. Las rutas de salud siguen su propio contrato (`no-store`).
- MUST existir un límite de peticiones por IP de cliente, en la infraestructura (p. ej. el gateway
  o el balanceador) o en la aplicación; el plan de la feature que lo introduzca MUST justificar
  dónde y fijar el límite. Si vive en la aplicación, la IP MUST tomarse de cabeceras de reenvío
  (`X-Forwarded-For` y similares) solo cuando provengan de proxies de confianza, y el exceso MUST
  responder 429 con el formato de error común (SHOULD incluir `Retry-After`). Las rutas de salud
  MUST NOT quedar sujetas a un límite que haga que el monitoreo del Backoffice o las sondas de la
  plataforma reciban 429.
- Los secretos (la cadena de conexión, la contraseña, el nombre de host o la dirección de la base
  de datos) MUST NOT aparecer en respuestas, mensajes de error ni registros. Los errores de la base
  de datos MUST traducirse al formato de error común sin filtrar el mensaje del driver.

**Rationale**: El catálogo está pensado para cualquier visitante, así que no hay identidad que
verificar; no recibir ni reenviar tokens elimina toda una clase de fugas. Como cualquiera puede
llamarlo, la seguridad descansa en exponer lo mínimo: solo GET, solo datos públicos, solo los
orígenes del Frontend, un límite de peticiones y un único secreto de solo lectura.

### IX. Sin Integraciones con Otros APIs

- El servicio MUST NOT llamar a otras APIs (de MailySoft o de terceros) ni al proveedor de
  identidad: no existe `src/integrations/` ni un cliente HTTP entre las dependencias del servicio
  (httpx solo como cliente de pruebas).
- Lo que no está en la base de datos compartida MUST NOT publicarse ni estimarse. En particular, el
  número de clínicas de un plan (que en maily-system-api aporta el API de clínicas) no forma parte
  de este catálogo.
- Agregar una integración MUST requerir una enmienda de esta constitución, porque reintroduce
  `src/integrations/`, un cliente HTTP en el servicio y el manejo de las fallas de esa dependencia.

**Rationale**: La base de datos compartida es la única dependencia del servicio; cada API adicional
sería un punto más de falla y de exposición para una página pública cuya única función es mostrar
los planes.

## Stack Tecnológico y Restricciones

| Ámbito                              | Tecnología obligatoria                                              |
|-------------------------------------|---------------------------------------------------------------------|
| Lenguaje                            | Python 3.14 o superior                                              |
| Framework web                       | FastAPI                                                             |
| Servidor de aplicación              | uvicorn (ASGI)                                                      |
| Base de datos                       | PostgreSQL 18 (la base compartida; su esquema lo administra mailySoft-DB) |
| ORM                                 | SQLAlchemy 2.0 (async) con asyncpg                                  |
| Migraciones                         | Ninguna en este repositorio (las administra mailySoft-DB)           |
| Validación, DTOs y configuración    | Pydantic v2 (con pydantic-settings)                                 |
| Pruebas                             | pytest (con pytest-asyncio); httpx solo como cliente de pruebas     |
| Documentación de APIs               | OpenAPI (generado por FastAPI)                                      |
| Comunicación con otras APIs         | Ninguna (Principio IX)                                              |
| Identidad y autorización            | Ninguna: servicio público (Principio VIII)                          |
| Gestión de dependencias             | uv (con `uv.lock`)                                                  |
| Contenerización                     | Docker y Docker Compose                                             |
| Metodología                         | GitHub Spec Kit                                                     |
| IDE de referencia                   | Visual Studio Code                                                  |

Restricciones adicionales:

- La versión de PostgreSQL MUST ser la misma que usa la base compartida de mailySoft-DB; si
  mailySoft-DB cambia de versión, esta tabla se enmienda.
- El servicio MUST ejecutarse en un contenedor Docker. En local MUST poder levantarse con Docker
  Compose conectado a la base compartida local de mailySoft-DB; el Compose de este repositorio MUST
  NOT levantar una base de datos propia para el servicio ni aplicar el esquema. El puerto local
  SHOULD ser 8006.
- Las pruebas usan una base desechable con el esquema de mailySoft-DB (Principio V), nunca la base
  compartida local.
- La configuración MUST provenir de variables de entorno validadas al arrancar con
  pydantic-settings: como mínimo, la cadena de conexión de solo lectura, los orígenes de CORS, el
  tiempo de caché del catálogo y el tiempo máximo de consulta, además de las variables del contrato
  de salud v1 (ver «Salud y Monitoreo»). Los secretos MUST NOT versionarse.
- Si falta una variable obligatoria o su valor no es válido, el servicio MUST NOT arrancar y MUST
  indicar cuál, sin mostrar secretos.
- Las dependencias de desarrollo y pruebas (pytest, httpx) MUST NOT formar parte de la imagen de
  la aplicación.
- Sustituir o añadir una tecnología fuera de esta tabla MUST requerir una enmienda de esta
  constitución.

## Salud y Monitoreo

- El servicio MUST cumplir el contrato de salud v1 de los servicios de MailySoft, igual que
  maily-system-api (documentado en su `specs/005-health-monitoring/contracts/health-contract-v1.md`),
  para que pueda registrarse en «Componentes monitoreados» del Backoffice.
- Las rutas de salud MUST estar en la raíz, fuera de `/api/v1`, ser GET, no exigir token y
  responder con `Cache-Control: no-store`:
  - `GET /health/live`: 200 `{"status": "ok"}` mientras el proceso atienda HTTP, sin consultar
    ninguna dependencia.
  - `GET /health/ready`: comprueba la conexión a la base de datos con una consulta trivial
    (`SELECT 1`) dentro de `HEALTH_READY_TIMEOUT_SECONDS`; 200 si responde y 503 si no, con el
    cuerpo `{status, checks}` del contrato. Una falla inesperada MUST responder 503 con
    `unexpected_error`, nunca 500.
  - `GET /info`: 200 con `service` (`maily-public-api`), `version`, `commit`, `build_date` y
    `environment`, tomados de la versión del servicio y de `APP_COMMIT_SHA`, `APP_BUILD_DATE` y
    `APP_ENVIRONMENT`; sin ellas, `unknown`.
- Los nombres de las variables del contrato (`HEALTH_READY_TIMEOUT_SECONDS`, `APP_COMMIT_SHA`,
  `APP_BUILD_DATE`, `APP_ENVIRONMENT`) MUST ser los mismos que en los demás servicios.
- Las respuestas de salud MUST NOT incluir secretos, nombres de host, direcciones, cadenas de
  conexión, mensajes de excepción ni trazas.
- Este servicio MUST NOT cambiar el contrato v1 por su cuenta: un cambio se coordina con los demás
  servicios que lo implementan y con el Backoffice.

## Flujo de Desarrollo y Puertas de Calidad

- Toda feature MUST seguir el flujo de Spec Kit: `/speckit-specify` → `/speckit-clarify`
  (cuando haya ambigüedad) → `/speckit-plan` → `/speckit-tasks` → `/speckit-implement`.
- El plan de cada feature MUST incluir una verificación explícita ("Constitution Check") contra
  los principios I–IX y la sección «Salud y Monitoreo»; cualquier desviación MUST quedar
  justificada en la sección de complejidad del plan.
- Estructura del repositorio obligatoria (ver Principio I): código de la aplicación en `src/`
  (`src/routers/`, `src/services/`, `src/repositories/`, `src/database/`, `src/models/`,
  `src/dtos/`) y pruebas en `tests/`.
- Si una feature necesita un cambio en la base de datos (una columna, una vista o un permiso del
  usuario de solo lectura), su especificación MUST declararlo como dependencia de mailySoft-DB, y
  ese cambio MUST integrarse y desplegarse allí antes de integrar la feature en `main`.
- Cada cambio integrado en `main` MUST cumplir: suite de pytest **completa** en verde (incluidas
  las pruebas marcadas `slow`, Principio V), esquema OpenAPI generado sin errores y solo con
  operaciones `get`, prueba de rutas solo GET en verde, modelos consistentes con el esquema vigente
  de mailySoft-DB y revisión de cumplimiento de capas.

## Governance

- Esta constitución prevalece sobre cualquier otra práctica o guía del proyecto. En caso de
  conflicto, rige este documento.
- **Enmiendas**: se proponen mediante `/speckit-constitution`, deben documentar el motivo y el
  impacto (Sync Impact Report), ser revisadas y aprobadas por el responsable del proyecto, e
  incluir un plan de migración cuando afecten código existente.
- **Versionado** (semántico):
  - MAJOR: eliminación o redefinición incompatible de principios o reglas de gobierno.
  - MINOR: nuevo principio o sección, o ampliación material de una guía existente.
  - PATCH: aclaraciones, redacción o correcciones sin cambio semántico.
- **Cumplimiento**: toda revisión de código y todo plan MUST verificar el cumplimiento de esta
  constitución; la complejidad adicional MUST justificarse. La referencia del esquema de datos es
  `schema/current_schema.sql` de mailySoft-DB.

**Version**: 1.0.0 | **Ratified**: 2026-11-01 | **Last Amended**: 2026-11-01
