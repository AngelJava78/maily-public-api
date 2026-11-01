# Feature Specification: Catálogo público de suscripciones

**Feature Branch**: `001-public-subscriptions-catalog`

**Created**: 2026-11-01

**Status**: Draft

**Input**: User description: "Catálogo público de suscripciones. La página pública «Suscripciones» del
Frontend de Maily se ve sin iniciar sesión y muestra los planes que se pueden contratar. La operación que
hoy los lista en maily-system-api (`GET /api/v1/subscriptions`, operation_id `list_subscriptions`) no le
sirve al Frontend por tres razones: exige un token con el permiso `subscriptions:read`, devuelve también las
suscripciones Inactivas y Bloqueadas, y trae datos internos. Esta API publica una copia de solo lectura de
esa operación, sin autenticación." (La descripción completa —datos, campos, respuestas, protección, usuario
de base de datos, criterios de éxito y alcance— se recoge en los requisitos de abajo.)

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Ver los planes que se pueden contratar sin iniciar sesión (Priority: P1)

Una persona que visita la página pública «Suscripciones» del Frontend de Maily, sin cuenta ni sesión, ve
los planes que puede contratar por su cuenta: nombre, descripción, a quién va dirigido (tipo), precios
mensual y anual, días de prueba, límites (consultorios, doctores, asistentes, pacientes nuevos al año y
clínicas) y otras funcionalidades. El Frontend obtiene esa lista de este servicio sin enviar ningún token.
Solo aparecen los planes Activos de autoservicio; nunca uno Inactivo, Bloqueado, Eliminado o que no sea
de autoservicio, y nunca un dato interno (estatus, autoservicio, número de clínicas o fechas).

**Why this priority**: Es la razón de ser del servicio: sin esta lista la página pública no puede mostrar
los planes, y la operación de maily-system-api no sirve porque exige token y expone datos internos.

**Independent Test**: Con una base de datos de prueba que contenga suscripciones en cada estatus, con y
sin autoservicio, una consulta sin credenciales al catálogo devuelve exactamente las Activas de
autoservicio, en el orden fijado y solo con los campos públicos.

**Acceptance Scenarios**:

1. **Given** tres suscripciones Activas de autoservicio y otras Inactiva, Bloqueada, Eliminada y Activa
   sin autoservicio, **When** se consulta el catálogo sin token, **Then** la respuesta es 200 y contiene
   solo las tres Activas de autoservicio.
2. **Given** dos suscripciones públicas creadas en momentos distintos y dos creadas en el mismo instante,
   **When** se consulta el catálogo, **Then** aparecen de la más antigua a la más reciente y, a igualdad
   de fecha de creación, por identificador ascendente.
3. **Given** una suscripción pública, **When** se consulta el catálogo, **Then** cada elemento trae
   exactamente los campos de FR-008 y ninguno de los excluidos (FR-010).
4. **Given** una suscripción con precio mensual guardado como 4500, **When** se consulta el catálogo,
   **Then** el precio aparece como el texto `"4500.00"`.
5. **Given** que no hay ninguna suscripción pública, **When** se consulta el catálogo, **Then** la
   respuesta es 200 con una lista vacía.
6. **Given** una petición que incluye una cabecera `Authorization` o cookies, **When** se consulta el
   catálogo, **Then** la respuesta es la misma que sin ellas.
7. **Given** una suscripción Activa de autoservicio que en maily-system-api se cambia a Inactiva,
   **When** se consulta el catálogo después de que venza el tiempo de caché, **Then** ya no aparece.

---

### User Story 2 - Ver los módulos de cada plan con su nombre legible (Priority: P2)

En cada plan, la página muestra los módulos incluidos con su nombre en español (p. ej. «Pacientes»,
«Agenda»), no con su clave técnica, y en el orden en que el catálogo de módulos los presenta. El Frontend
no tiene que consultar la API de usuarios (que exige sesión) para traducir las claves.

**Why this priority**: Sin nombres legibles el visitante no entiende qué incluye cada plan; pero la lista
de planes (Historia 1) ya aporta valor por sí sola con las claves.

**Independent Test**: Con un catálogo de módulos de prueba (con módulos Activos, Bloqueados, Eliminados y
de tipo Sistema) y una suscripción pública que incluye claves de cada caso y una clave inexistente, el
campo `modules` contiene solo los módulos Activos de tipo Clínica, con su clave y su nombre, ordenados por
su orden de presentación.

**Acceptance Scenarios**:

1. **Given** una suscripción pública con las claves `patients` y `scheduling`, ambas módulos Activos de
   tipo Clínica con orden de presentación 2 y 1, **When** se consulta el catálogo, **Then** `modules` es
   `[{"key": "scheduling", "name": …}, {"key": "patients", "name": …}]` y `module_keys` es
   `["patients", "scheduling"]` (alfabético, como en maily-system-api).
2. **Given** una suscripción pública que incluye una clave que no existe en el catálogo de módulos,
   **When** se consulta el catálogo, **Then** la suscripción aparece, la clave sigue en `module_keys`, no
   aparece en `modules` y queda un aviso en los registros del servicio.
3. **Given** una suscripción pública que incluye un módulo Bloqueado, uno Eliminado y uno de tipo
   Sistema, **When** se consulta el catálogo, **Then** ninguno de los tres aparece en `modules`.
4. **Given** una suscripción pública sin módulos registrados, **When** se consulta el catálogo, **Then**
   aparece con `module_keys` y `modules` vacíos.

---

### User Story 3 - Un servicio público que no se puede abusar ni usar para escribir (Priority: P2)

Quien opera MailySoft necesita que este servicio, abierto a cualquiera en internet, no pueda modificar
datos, no exponga detalles internos cuando falla, responda solo a los orígenes del Frontend desde el
navegador, limite las peticiones por IP y deje que el navegador y las cachés intermedias guarden la lista
unos minutos para no cargar la base de datos compartida.

**Why this priority**: Es la condición para abrir el servicio al público sin poner en riesgo la base de
datos que comparten todos los servicios de MailySoft. Se puede probar por separado de los datos.

**Independent Test**: Contra el servicio desplegado con una base de prueba: un POST, PUT, PATCH o DELETE
responde 405; con la base detenida, el catálogo responde 503 sin detalles; una petición desde un origen no
permitido no recibe permiso de CORS; superar el límite de peticiones responde 429; y un intento de
escritura con las credenciales del servicio es rechazado por la base de datos.

**Acceptance Scenarios**:

1. **Given** el servicio en marcha, **When** se envía POST, PUT, PATCH, DELETE o HEAD a
   `/api/v1/subscriptions`, **Then** la respuesta es 405 con `Allow: GET` y el formato de error común.
2. **Given** la base de datos detenida o sin responder, **When** se consulta el catálogo, **Then** la
   respuesta es 503 `service_unavailable` en no más del tiempo máximo de consulta más un segundo, sin
   nombres de host, cadenas de conexión ni mensajes del driver.
3. **Given** una consulta exitosa del catálogo, **When** se revisan sus cabeceras, **Then** trae
   `Cache-Control: public, max-age=<segundos configurados>`; y una respuesta de error trae
   `Cache-Control: no-store`.
4. **Given** una petición del navegador desde un origen de la lista configurada, **When** consulta el
   catálogo, **Then** la respuesta lo permite por CORS, sin permitir credenciales; desde un origen fuera
   de la lista, la respuesta no incluye ese permiso.
5. **Given** una IP que supera el límite de peticiones, **When** vuelve a consultar el catálogo, **Then**
   recibe 429 hasta que se renueva su ventana, mientras otras IP siguen recibiendo el catálogo.
6. **Given** las credenciales de base de datos del servicio, **When** se intenta insertar, modificar o
   borrar cualquier fila (incluso pidiendo explícitamente una transacción de lectura y escritura),
   **Then** la base de datos lo rechaza por falta de permisos.

---

### User Story 4 - Monitorear el servicio y consultar su documentación (Priority: P3)

Quien opera MailySoft registra el servicio en «Componentes monitoreados» del Backoffice y ve si está vivo,
si puede leer la base de datos y qué versión corre. Quien desarrolla el Frontend consulta la documentación
interactiva del contrato, con ejemplos en español; en producción esa documentación se puede apagar.

**Why this priority**: Necesario para operar el servicio, pero no bloquea que la página pública muestre
los planes.

**Independent Test**: Las tres rutas de salud responden según el contrato de salud v1 con la base
disponible y detenida; `/docs` y `/openapi.json` responden con la documentación activada y 404 con ella
desactivada.

**Acceptance Scenarios**:

1. **Given** la base de datos disponible, **When** se consulta `/health/ready`, **Then** la respuesta es
   200 con `status` `ok` y el chequeo `database` en `ok`; con la base detenida, 503 con `status`
   `unavailable` y el chequeo en `error` (`timeout` o `connection_error`), mientras `/health/live` sigue
   respondiendo 200.
2. **Given** el servicio en marcha, **When** se consulta `/info`, **Then** responde 200 con
   `service` `maily-public-api`, su versión y, si no se configuraron, `commit`, `build_date` y
   `environment` en `unknown`.
3. **Given** la documentación activada, **When** se abre `/docs` o se descarga `/openapi.json`, **Then**
   el contrato muestra la operación del catálogo con descripciones y ejemplos en español, sin esquemas de
   seguridad y solo con operaciones GET.
4. **Given** la documentación desactivada por configuración, **When** se consulta `/docs` o
   `/openapi.json`, **Then** la respuesta es 404 con el formato de error común.

---

### Edge Cases

- **Clave de módulo sin módulo en el catálogo** (o con un módulo Bloqueado, Eliminado o de tipo Sistema):
  la suscripción se publica igual; la clave queda en `module_keys` pero no en `modules`, y el servicio
  registra un aviso con el identificador de la suscripción y la clave (FR-012). Un módulo mal registrado no
  oculta el plan entero ni hace fallar el catálogo.
- **Claves repetidas en el catálogo de módulos**: el catálogo solo garantiza una clave única entre los
  módulos no Eliminados; como solo se usan los Activos, cada clave corresponde a lo más a un módulo.
- **Suscripción sin módulos**: se publica con `module_keys` y `modules` vacíos (la regla de que
  `patients` siempre se incluya la garantiza maily-system-api, no este servicio).
- **Suscripción sin descripción**: `description` es `null`.
- **Catálogo vacío**: 200 con `[]`, nunca 404.
- **Más de 500 suscripciones públicas**: se devuelven todas igualmente (nunca se recorta en silencio) y
  el servicio registra un aviso; superar el máximo obliga a publicar una versión paginada (FR-007).
- **Cambio de una suscripción en maily-system-api** (precio, estatus, autoservicio): se refleja en la
  siguiente consulta al servicio, pero el navegador y las cachés intermedias pueden mostrar la versión
  anterior durante el tiempo de caché configurado (5 minutos por omisión).
- **Base de datos lenta**: si la conexión o la consulta no terminan dentro del tiempo máximo de consulta,
  la respuesta es 503, nunca una espera indefinida ni un 500.
- **Base de datos disponible pero sin los permisos esperados** (p. ej. falta un permiso del usuario de
  solo lectura): la respuesta es 500 `internal_error` con el mensaje genérico, y el detalle técnico queda
  en los registros, sin secretos. `/health/ready` no lo detecta (solo comprueba la conexión).
- **Parámetros de consulta** (p. ej. `?page=2`): se ignoran; la respuesta es el catálogo completo.
- **Ruta inexistente** (p. ej. `/api/v1/subscriptions/1`, fuera del alcance): 404 `not_found` con el
  formato de error común.
- **Petición OPTIONS de verificación previa de CORS**: la atiende la política de CORS; un origen fuera de
  la lista no recibe permiso.
- **Cabecera `X-Forwarded-For` falsificada**: solo se toma en cuenta si proviene de un proxy de confianza;
  si no, el límite se aplica a la IP de la conexión.
- **Servicio arrancado con la base detenida**: arranca igual; `/health/live` responde 200, `/health/ready`
  503 y el catálogo 503 hasta que la base vuelve.
- **Variable de entorno obligatoria ausente o inválida**: el servicio no arranca y dice cuál, sin mostrar
  su valor si es secreto.

## Requirements *(mandatory)*

### Functional Requirements

**Operación y acceso**

- **FR-001**: El servicio MUST ofrecer una única operación de negocio, `GET /api/v1/subscriptions`
  (identificador de operación `list_subscriptions`, etiqueta `subscriptions`), que devuelve el catálogo
  público de suscripciones como una lista JSON (el mismo formato de lista que la operación homónima de
  maily-system-api).
- **FR-002**: La operación MUST responder sin token ni ninguna otra credencial. Una cabecera
  `Authorization` o una cookie recibida MUST ignorarse: no cambia la respuesta y MUST NOT registrarse. El
  servicio MUST NOT comunicarse con el proveedor de identidad ni con ninguna otra API.
- **FR-003**: MUST NOT existir ninguna operación que cree, cambie o borre datos. Cualquier método distinto
  de GET (POST, PUT, PATCH, DELETE, HEAD…) sobre una ruta existente MUST responder 405
  `method_not_allowed` con la cabecera `Allow: GET`.

**Qué suscripciones se publican y en qué orden**

- **FR-004**: El catálogo MUST incluir solo las suscripciones con estatus Activa (identificador 1 del
  catálogo de estatus, reconocido por su identificador y no por su nombre) y con autoservicio activado.
- **FR-005**: Las suscripciones Inactivas, Bloqueadas, Eliminadas, con cualquier otro estatus o sin
  autoservicio MUST NOT aparecer en ninguna respuesta. El filtro MUST aplicarse al leer los datos: las
  filas no públicas no se cargan para descartarlas después.
- **FR-006**: El catálogo MUST ordenarse igual que en maily-system-api: por fecha de creación ascendente
  (la más antigua primero) y, a igualdad, por identificador ascendente.
- **FR-007**: El catálogo MUST devolverse completo, sin paginar. El catálogo público esperado no supera
  100 suscripciones y su máximo para devolverse completo es 500. Si hay más de 500, el servicio MUST
  devolverlas todas igualmente y registrar un aviso; superar el máximo exige publicar una versión
  paginada del contrato (cambio incompatible que se versiona). Sin suscripciones públicas, la respuesta
  MUST ser 200 con una lista vacía.

**Qué datos lleva cada suscripción**

- **FR-008**: Cada suscripción del catálogo MUST mostrar exactamente estos campos, con el mismo
  significado y formato que en el `SubscriptionRead` de maily-system-api:
  - `id`: identificador de la suscripción.
  - `name`: nombre.
  - `description`: descripción, o `null` si no tiene.
  - `subscription_type`: objeto con `id` y `name` del tipo de suscripción (hoy, 1 Individual y 2
    Empresarial).
  - `monthly_price` y `annual_price`: precios en pesos mexicanos sin IVA, como texto con exactamente dos
    decimales (p. ej. `"1299.00"`), sin pérdida de precisión.
  - `trial_days`: días de prueba (`0` = sin periodo de prueba).
  - `module_keys`: claves de todos los módulos que incluye la suscripción, en orden alfabético.
  - `modules`: ver FR-011.
  - `other_features`: otras funcionalidades que no son módulos, en el orden en que se guardaron.
  - `consulting_rooms_limit`, `doctors_limit`, `assistants_limit`, `new_patients_per_year_limit` y
    `clinics_limit`: los techos del plan.
- **FR-009**: Para los campos compartidos (todos los de FR-008 salvo `modules`), cada suscripción MUST
  tener los mismos valores, en el mismo formato, que la misma suscripción en la operación
  `list_subscriptions` de maily-system-api leyendo la misma base de datos.
- **FR-010**: Ninguna respuesta MUST incluir `status`, `self_service`, `clinics_count`, `created_at`,
  `updated_at` ni ningún otro campo que no esté en FR-008. El número de clínicas no se publica, ni
  calculado ni estimado: lo aporta otra API y este servicio no se comunica con otras APIs.
- **FR-011**: `modules` MUST ser una lista de objetos `{key, name}`, uno por cada clave de `module_keys`
  que corresponda a un módulo **Activo** de tipo **Clínica** del catálogo de módulos, con su clave y su
  nombre legible tal como están en ese catálogo, ordenados por el orden de presentación del módulo
  (`sort_order` ascendente) y, a igualdad, por clave ascendente.
- **FR-012**: Una clave de `module_keys` que no corresponda a un módulo Activo de tipo Clínica (porque no
  existe en el catálogo, está Bloqueado o Eliminado, o es de tipo Sistema) MUST permanecer en
  `module_keys`, MUST omitirse de `modules` y MUST NOT impedir que la suscripción se publique. El servicio
  MUST registrar un aviso con el identificador de la suscripción y la clave, para que se corrija el
  catálogo.

**Respuestas, errores y cabeceras**

- **FR-013**: Todos los errores MUST usar el formato de maily-system-api: `{"code": …, "message": …}`, con
  `code` estable en inglés y `message` en español sin detalles técnicos. Los códigos de este servicio son:

  | Código | HTTP | Cuándo | Mensaje |
  |---|---|---|---|
  | `service_unavailable` | 503 | La base de datos no responde, rechaza la conexión o no termina dentro del tiempo máximo de consulta | «El catálogo de suscripciones no está disponible por el momento. Inténtelo de nuevo más tarde.» |
  | `rate_limit_exceeded` | 429 | La IP superó el límite de peticiones (FR-019) | «Se hicieron demasiadas solicitudes. Espere un momento e inténtelo de nuevo.» |
  | `method_not_allowed` | 405 | Método distinto de GET sobre una ruta existente (FR-003) | «Esta operación no está permitida: el servicio es de solo lectura.» |
  | `not_found` | 404 | Ruta inexistente, o documentación desactivada (FR-022) | «No existe el recurso solicitado.» |
  | `internal_error` | 500 | Cualquier fallo inesperado | «Ocurrió un error inesperado. Inténtelo de nuevo más tarde.» |

- **FR-014**: Ningún error MUST mostrar nombres de host, direcciones, cadenas de conexión, nombres de
  usuario de la base de datos, mensajes del driver, trazas ni el cuerpo por defecto `{"detail": …}` del
  framework. Lo mismo aplica a los registros en cuanto a secretos.
- **FR-015**: Ninguna petición al catálogo MUST esperar a la base de datos más del tiempo máximo de
  consulta configurado (FR-023): si la conexión o la consulta no terminan en ese tiempo, la respuesta MUST
  ser 503 `service_unavailable`.
- **FR-016**: Toda lectura de la base de datos MUST hacerse en transacciones de solo lectura.
- **FR-017**: Las respuestas exitosas del catálogo MUST llevar `Cache-Control: public, max-age=<N>`, con
  `N` el tiempo de caché configurado (FR-023). Las respuestas de error MUST llevar
  `Cache-Control: no-store`.
- **FR-018**: CORS MUST permitir solo los orígenes de la lista configurada (FR-023), nunca `*`, solo el
  método GET y sin credenciales ni cookies. Las respuestas MUST indicar que varían según el origen
  (`Vary: Origin`), para que una caché intermedia no entregue el permiso de un origen a otro.
- **FR-019**: MUST existir un límite de peticiones por IP de cliente sobre las rutas de `/api/v1`: por
  omisión, 60 peticiones por minuto por IP, configurable. El plan decide si se aplica en la
  infraestructura o en la aplicación y lo justifica. Si se aplica en la aplicación: el exceso MUST
  responder 429 `rate_limit_exceeded` con la cabecera `Retry-After`, y la IP MUST tomarse de las cabeceras
  de reenvío solo en la medida en que las escriben los proxies de confianza configurados (nunca de lo que
  pudo escribir el cliente). Las rutas de salud MUST NOT
  quedar sujetas a un límite que haga que el monitoreo reciba 429.

**Salud y documentación**

- **FR-020**: El servicio MUST cumplir el contrato de salud v1 de los servicios de MailySoft (el mismo que
  maily-system-api, `specs/005-health-monitoring/contracts/health-contract-v1.md` de ese repositorio), en
  la raíz, fuera de `/api/v1`, sin token y con `Cache-Control: no-store`:
  - `GET /health/live`: 200 `{"status": "ok"}` sin consultar la base de datos.
  - `GET /health/ready`: comprueba la conexión a la base de datos con una consulta trivial, con las
    credenciales de solo lectura, dentro de `HEALTH_READY_TIMEOUT_SECONDS` (2 s por omisión); 200 o 503
    con el cuerpo `{status, checks}` del contrato (`error`: `timeout`, `connection_error` o
    `unexpected_error`, nunca un 500).
  - `GET /info`: 200 con `service` = `maily-public-api`, `version` (la del servicio, igual a la del
    contrato OpenAPI), y `commit`, `build_date` y `environment` tomados de `APP_COMMIT_SHA`,
    `APP_BUILD_DATE` y `APP_ENVIRONMENT`, o `unknown` si no se configuraron.
- **FR-021**: La documentación MUST publicarse en `/docs` (interactiva) y `/openapi.json` (contrato), con
  descripciones y ejemplos en español, sin esquemas de seguridad y solo con operaciones GET. No se publica
  ninguna otra vista de documentación (p. ej. `/redoc`).
- **FR-022**: La documentación MUST poder desactivarse por configuración (FR-023); desactivada, `/docs` y
  `/openapi.json` MUST responder 404 `not_found`.

**Configuración**

- **FR-023**: El servicio MUST tomar su configuración de variables de entorno, validadas al arrancar:

  | Dato | Obligatoria | Por omisión | Regla |
  |---|---|---|---|
  | Cadena de conexión con el usuario de solo lectura | Sí | — | Secreta; nunca se muestra |
  | Orígenes de CORS del Frontend | Sí | — | Lista de orígenes `http(s)://host[:puerto]`, sin `*` |
  | Tiempo de caché del catálogo | No | 300 s | Entero de 0 a 86 400 |
  | Tiempo máximo de consulta | No | 3 s | De 1 a 30 s |
  | Documentación activada | No | Sí | Verdadero o falso; en producción se desactiva |
  | Límite de peticiones por IP (si vive en la aplicación) | No | 60 por minuto | Entero ≥ 0; `0` lo apaga en la aplicación, solo si la infraestructura lo aplica |
  | Número de proxies de confianza delante del servicio | No | 0 (se usa la IP de la conexión) | Entero de 0 a 5 |
  | `HEALTH_READY_TIMEOUT_SECONDS`, `APP_COMMIT_SHA`, `APP_BUILD_DATE`, `APP_ENVIRONMENT` | No | Las del contrato de salud v1 | Las del contrato de salud v1 |

  Los nombres de las variables de los primeros siete datos los fija el plan; los del contrato de salud son
  los mismos que en los demás servicios.
- **FR-024**: Si falta una variable obligatoria o una tiene un valor inválido, el servicio MUST NOT
  arrancar y MUST indicar cuál, sin mostrar su valor si es secreto. La base de datos no disponible al
  arrancar no impide el arranque (FR-020).

### Permisos del usuario de base de datos (dependencia en mailySoft-DB)

Este servicio no crea el usuario ni sus permisos ni tiene migraciones: se crean y versionan en
mailySoft-DB. Lo que sigue es lo que ese repositorio debe proveer y lo único que este servicio necesita.

- **FR-025**: El servicio MUST conectarse con un usuario de base de datos propio (no compartido con otro
  servicio) que:
  - Puede iniciar sesión, pero no es superusuario, no puede crear bases de datos ni roles, no puede
    replicar, no evita la seguridad por filas y no es miembro de ningún otro rol.
  - No es dueño de ningún objeto.
  - Tiene **solo** estos privilegios (opción de referencia, sobre tablas):

    | Objeto | Privilegio |
    |---|---|
    | La base de datos compartida | `CONNECT` |
    | Esquema `public` | `USAGE` |
    | `subscriptions` | `SELECT` sobre las columnas `id`, `name`, `description`, `subscription_type_id`, `monthly_price`, `annual_price`, `trial_days`, `other_features`, `consulting_rooms_limit`, `doctors_limit`, `assistants_limit`, `new_patients_per_year_limit`, `clinics_limit`, `status_id`, `self_service`, `created_at` |
    | `subscription_types` | `SELECT` sobre `id`, `name` |
    | `subscription_modules` | `SELECT` sobre `subscription_id`, `module_key` |
    | `modules` | `SELECT` sobre `key`, `name`, `sort_order`, `status_id`, `type_id` |

  - Ningún otro privilegio: ni `INSERT`, `UPDATE`, `DELETE`, `TRUNCATE`, `REFERENCES` o `TRIGGER` sobre
    ninguna tabla, ni uso de secuencias, ni `CREATE` sobre el esquema o la base de datos, ni lectura de
    otras tablas (usuarios, clínicas, pacientes, expedientes…).
  - Tiene por omisión transacciones de solo lectura (`default_transaction_read_only = on`) y un tiempo
    máximo de consulta (`statement_timeout`) que sirva de tope aunque el servicio no fije el suyo; SHOULD
    tener además un límite de conexiones acorde al tamaño máximo del pool del servicio, para que el tráfico
    público no agote las conexiones de la base compartida.
- **FR-026**: Como alternativa a la opción de referencia, mailySoft-DB MAY crear una vista dedicada a este
  catálogo que exponga solo las suscripciones públicas y solo los datos de FR-008 (más lo necesario para
  ordenar); entonces el usuario MUST tener `SELECT` solo sobre esa vista, además de `CONNECT` y `USAGE`.
  El plan, de acuerdo con mailySoft-DB, elige una de las dos opciones.
- **FR-027**: El esquema vigente de mailySoft-DB MUST contener, antes de integrar esta feature, la tabla
  `subscription_modules` y la columna `subscriptions.clinics_limit`. Hoy (mailySoft-DB en V5) el esquema
  todavía guarda los módulos en `subscriptions.module_keys` y no tiene `clinics_limit`; ambos cambios los
  introdujo maily-system-api en sus specs 007 y 008 (Alembic 0006 y 0007) y deben incorporarse primero a
  mailySoft-DB.

### Key Entities *(include if feature involves data)*

- **Suscripción pública**: un plan Activo de autoservicio, tal como lo ve el visitante: identificador,
  nombre, descripción, tipo, precios mensual y anual, días de prueba, claves de módulos, módulos con nombre,
  otras funcionalidades y cinco límites. La administra maily-system-api; este servicio solo la lee.
- **Tipo de suscripción**: a quién va dirigido el plan (hoy Individual o Empresarial), con identificador y
  nombre. Catálogo editado a mano en la base compartida.
- **Módulo incluido**: un módulo de la aplicación para clínicas que forma parte del plan, con su clave y su
  nombre legible. La relación plan-módulo la guarda maily-system-api; el catálogo de módulos (nombre,
  orden de presentación, estatus y tipo) lo administra el servicio de usuarios.
- **Error**: cuerpo uniforme con código en inglés y mensaje en español.
- **Usuario de base de datos de solo lectura**: la única credencial del servicio; definido en
  mailySoft-DB con los privilegios mínimos de FR-025 o FR-026.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: El 100 % de las consultas al catálogo hechas sin ninguna credencial reciben la lista de
  planes; ninguna recibe un error de autenticación o de permisos.
- **SC-002**: Con un conjunto de prueba que tenga suscripciones en cada estatus, con y sin autoservicio,
  0 suscripciones Inactivas, Bloqueadas, Eliminadas o sin autoservicio aparecen en el catálogo.
- **SC-003**: En el 100 % de las respuestas del catálogo, cada suscripción tiene exactamente los campos
  publicados y ninguno de los excluidos (estatus, autoservicio, número de clínicas, fechas).
- **SC-004**: El 100 % de los intentos de insertar, modificar o borrar datos con las credenciales del
  servicio son rechazados por la base de datos por falta de permisos, aunque se pida una transacción de
  escritura.
- **SC-005**: Leyendo la misma base de datos, el catálogo coincide con el de maily-system-api filtrado por
  Activa y autoservicio: las mismas suscripciones, en el mismo orden y con los mismos valores en el 100 %
  de los campos compartidos.
- **SC-006**: En condiciones normales (base de datos disponible, hasta 500 suscripciones públicas), el
  95 % de las consultas al catálogo responden en menos de 1 segundo.
- **SC-007**: Con la base de datos detenida o sin responder, el 100 % de las consultas al catálogo
  reciben la respuesta de no disponible en no más del tiempo máximo de consulta más 1 segundo (4 segundos
  con la configuración por omisión), sin ningún detalle interno.
- **SC-008**: Un cambio de una suscripción hecho en maily-system-api (alta, baja, cambio de estatus, de
  autoservicio o de precio) se ve en la página pública a más tardar cuando vence el tiempo de caché
  configurado (5 minutos por omisión).
- **SC-009**: Registrado en «Componentes monitoreados» del Backoffice, el servicio aparece «arriba» con la
  base disponible y «degradado» (no «caído») con la base detenida, sin redesplegar nada.

## Assumptions

- **Origen de los datos**: las suscripciones, sus tipos y sus módulos los escribe maily-system-api en la
  base compartida de MailySoft; el catálogo de módulos lo administra el servicio de usuarios en esa misma
  base. Este servicio no escribe nada y no valida reglas que garantizan otros servicios (p. ej. que
  `patients` siempre esté incluido).
- **Coincidencia con maily-system-api (SC-005)**: solo se puede verificar cuando ambos servicios leen la
  misma base (p. ej. el ambiente compartido de desarrollo). En local, maily-system-api usa hoy su propia
  base de PostgreSQL 17 y no la base compartida de mailySoft-DB (PostgreSQL 18).
- **Formato de los precios**: el mismo que en maily-system-api (texto con dos decimales) para que el
  Frontend los trate igual en ambos servicios.
- **Módulos Bloqueados**: un módulo Bloqueado no se anuncia en `modules`, porque una clínica que contrate
  el plan no podría usarlo; su clave sigue en `module_keys`, igual que en maily-system-api.
- **Tiempo de caché por omisión**: 5 minutos, a cambio de que un cambio de un plan tarde hasta ese tiempo
  en verse en la página pública.
- **Límite por omisión de 60 peticiones por minuto por IP**: la página pública hace una consulta por visita
  y el navegador la guarda en caché, así que el límite solo afecta a clientes abusivos.
- **Tiempo máximo de consulta por omisión de 3 segundos**: el catálogo es pequeño y una consulta normal
  tarda milisegundos; 3 s deja margen sin dejar peticiones colgadas.
- **Documentación activada por omisión**: el contrato es público y no revela nada sensible; en producción
  se desactiva por configuración si se decide no exponerla.
- **Dependencias fuera de este repositorio**: (1) mailySoft-DB incorpora `subscription_modules` y
  `subscriptions.clinics_limit` (FR-027); (2) mailySoft-DB crea el usuario de solo lectura con los
  permisos de FR-025 o FR-026; (3) el Frontend configura la dirección de este servicio y sus orígenes se
  dan de alta en la lista de CORS; (4) el servicio se registra en «Componentes monitoreados» del
  Backoffice.
- **Fuera del alcance**: consultar una suscripción por su identificador, otros catálogos, la página del
  Frontend y la creación del usuario de base de datos (va en mailySoft-DB).
