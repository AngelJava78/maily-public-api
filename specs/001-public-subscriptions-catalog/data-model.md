# Data Model: Catálogo público de suscripciones

Este servicio no tiene esquema propio (Principio VI): lee cuatro tablas de la base compartida de
MailySoft, cuyo esquema administra mailySoft-DB (`schema/current_schema.sql` de ese repositorio). Este
documento fija (1) qué columnas se leen y cómo se mapean en `src/models/`, (2) los DTOs del contrato y
(3) las reglas que los unen.

## 1. Esquema vigente que se lee

Estado requerido del esquema de mailySoft-DB (FR-027). Las marcas **(pendiente)** son lo que hoy, en V5,
todavía no existe y debe incorporarse a mailySoft-DB (introducido por maily-system-api, specs 007 y 008,
Alembic 0006 y 0007).

### `subscriptions`

| Columna | Tipo | Nulo | Uso en este servicio |
|---|---|---|---|
| `id` | `integer` (PK) | no | `id`; desempate del orden |
| `name` | `varchar(100)` | no | `name` |
| `description` | `varchar(500)` | sí | `description` |
| `subscription_type_id` | `integer` (FK → `subscription_types.id`) | no | carga de `subscription_type` |
| `monthly_price` | `numeric(10,2)` | no | `monthly_price` |
| `annual_price` | `numeric(10,2)` | no | `annual_price` |
| `trial_days` | `integer` | no | `trial_days` |
| `other_features` | `text[]` | no | `other_features` |
| `consulting_rooms_limit` | `integer` | no | `consulting_rooms_limit` |
| `doctors_limit` | `integer` | no | `doctors_limit` |
| `assistants_limit` | `integer` | no | `assistants_limit` |
| `new_patients_per_year_limit` | `integer` | no | `new_patients_per_year_limit` |
| `clinics_limit` **(pendiente)** | `integer` | no | `clinics_limit` |
| `status_id` | `integer` (FK → `subscription_statuses.id`) | no | solo filtro (= 1); no se publica |
| `self_service` | `boolean` | no | solo filtro (= `true`); no se publica |
| `created_at` | `timestamptz` | no | solo orden; no se publica |

No se leen: `updated_at`, `module_keys` (la columna `text[]` que reemplaza `subscription_modules`) ni
ninguna otra columna que se agregue.

### `subscription_types`

| Columna | Tipo | Nulo | Uso |
|---|---|---|---|
| `id` | `integer` (PK) | no | `subscription_type.id` |
| `name` | `varchar(50)` | no | `subscription_type.name` |

### `subscription_modules` **(pendiente)**

| Columna | Tipo | Nulo | Uso |
|---|---|---|---|
| `subscription_id` | `integer` (PK, FK → `subscriptions.id`) | no | relación con la suscripción |
| `module_key` | `text` (PK) | no | `module_keys` y búsqueda en `modules` |

### `modules`

| Columna | Tipo | Nulo | Uso |
|---|---|---|---|
| `key` | `varchar(50)` | no | `modules[].key`; búsqueda por clave |
| `name` | `varchar(100)` | no | `modules[].name` |
| `sort_order` | `integer` | no | orden de `modules` |
| `status_id` | `integer` (FK → `module_statuses.id`) | no | solo filtro (= 1 Activo) |
| `type_id` | `integer` (FK → `module_types.id`) | no | solo filtro (= 2 Clínica) |

No se lee `modules.id`. La clave es única entre los módulos no Eliminados (índice
`modules_key_not_deleted_key`, `WHERE status_id <> 3`); como solo se leen los Activos, cada clave
corresponde a lo más a un módulo.

Catálogos que se reconocen por identificador y **no** se leen: `subscription_statuses` (1 Activa,
2 Inactiva, 3 Bloqueada, 4 Eliminada), `module_statuses` (1 Activo, 2 Bloqueado, 3 Eliminado) y
`module_types` (1 Sistema, 2 Clínica).

## 2. Modelos ORM (`src/models/`)

Solo mapean las columnas de la sección 1, con sus nombres y tipos. Nunca se escriben.

| Modelo | Tabla | Clave primaria del mapper | Relaciones |
|---|---|---|---|
| `Subscription` | `subscriptions` | `id` | `subscription_type` (muchos a uno, `lazy="raise"`, cargada con `joinedload`); `modules: list[SubscriptionModule]` (`lazy="raise"`, cargada con `selectinload`, `order_by=SubscriptionModule.module_key`); propiedad `module_keys` = claves en ese orden |
| `SubscriptionType` | `subscription_types` | `id` | — |
| `SubscriptionModule` | `subscription_modules` | (`subscription_id`, `module_key`) | — |
| `Module` | `modules` | `key` (solo en el mapper; research R6) | — |

Tipos Python: `Decimal` para `numeric` (nunca `float`), `datetime` con zona para `created_at`,
`list[str]` para `text[]`.

Constantes de negocio (en el Service, no en los modelos ni en los Repositories): `ACTIVE_STATUS_ID = 1`,
`PUBLIC_SELF_SERVICE = True`, `ACTIVE_MODULE_STATUS_ID = 1`, `CLINIC_MODULE_TYPE_ID = 2`,
`CATALOG_MAX_EXPECTED = 500`.

## 3. DTOs del contrato (`src/dtos/`)

### `PublicSubscriptionRead`

| Campo | Tipo JSON | Origen | Regla |
|---|---|---|---|
| `id` | entero ≥ 1 | `subscriptions.id` | — |
| `name` | texto | `subscriptions.name` | — |
| `description` | texto o `null` | `subscriptions.description` | `null` si no tiene |
| `subscription_type` | `SubscriptionTypeRead` | `subscription_types` | — |
| `monthly_price` | texto | `subscriptions.monthly_price` | Exactamente dos decimales (`"4500.00"`), como `_two_decimals` de maily-system-api |
| `annual_price` | texto | `subscriptions.annual_price` | Igual que `monthly_price` |
| `trial_days` | entero 0–3650 | `subscriptions.trial_days` | — |
| `module_keys` | lista de texto | `subscription_modules.module_key` | Todas las claves, en el orden de la base (`ORDER BY module_key`), como maily-system-api |
| `modules` | lista de `ModuleRead` | `modules` | Ver regla M1 |
| `other_features` | lista de texto | `subscriptions.other_features` | Orden guardado |
| `consulting_rooms_limit` | entero 0–1 000 000 | columna homónima | — |
| `doctors_limit` | entero 0–1 000 000 | columna homónima | — |
| `assistants_limit` | entero 0–1 000 000 | columna homónima | — |
| `new_patients_per_year_limit` | entero 0–1 000 000 | columna homónima | — |
| `clinics_limit` | entero 1–100 | columna homónima | — |

No tiene ningún otro campo (FR-010). En el OpenAPI, los campos llevan descripción y ejemplo en español.

### `SubscriptionTypeRead`

`{id: entero ≥ 1, name: texto}`; mismo significado que en maily-system-api.

### `ModuleRead`

`{key: texto, name: texto}`; `key` con el patrón `^[a-z][a-z0-9_]*$`.

### `ErrorResponse`

`{code: texto, message: texto}` (sin `errors`: este servicio no tiene validaciones de entrada). Códigos en
[contracts/error-catalog.md](contracts/error-catalog.md).

### DTOs de salud

`LiveResponse {status: "ok"}`, `ReadyResponse {status: "ok" | "unavailable", checks: [CheckResult]}`,
`CheckResult {name: "database", status: "ok" | "error", latency_ms: entero ≥ 0, error: null | "timeout" |
"connection_error" | "unexpected_error"}` e `InfoResponse {service, version, commit, build_date,
environment}`. Ver [contracts/health-v1.md](contracts/health-v1.md).

## 4. Reglas que unen datos y contrato

- **P1 — Publicación** (FR-004, FR-005): solo filas con `status_id = 1` y `self_service = true`; el filtro
  va en la consulta.
- **P2 — Orden** (FR-006): `ORDER BY created_at ASC, id ASC`.
- **P3 — Tamaño** (FR-007): se devuelven todas; si son más de 500, aviso una vez por proceso.
- **M1 — Módulos publicados** (FR-011): para cada clave de `module_keys`, el módulo con esa `key`,
  `status_id = 1` y `type_id = 2`; la lista se ordena por `(sort_order, key)`.
- **M2 — Clave sin módulo** (FR-012): la clave queda en `module_keys`, no entra en `modules` y se registra
  un aviso con `subscription_id` y `module_key`, una vez por proceso por pareja.
- **M3 — Sin módulos**: `module_keys = []` y `modules = []`.
- **E1 — Errores de lectura** (FR-013, FR-015): base no disponible o tiempo agotado → 503
  `service_unavailable`; otro error → 500 `internal_error` (research R5).

## 5. Estados y transiciones

Este servicio no cambia estados. Las transiciones de estatus y de autoservicio las hace maily-system-api;
aquí solo determinan si una suscripción aparece (P1). Una suscripción que entra o sale del catálogo lo hace
en la siguiente lectura, más el tiempo de caché del cliente (SC-008).
