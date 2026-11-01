# Contrato: `GET /api/v1/subscriptions` (catálogo público)

Requisitos: FR-001 a FR-019. Modelo: [data-model.md](../data-model.md). Errores:
[error-catalog.md](error-catalog.md). Cabeceras y límites: [http-policies.md](http-policies.md).

## Operación

| Atributo | Valor |
|---|---|
| Método y ruta | `GET /api/v1/subscriptions` |
| `operationId` | `list_subscriptions` |
| Etiqueta | `subscriptions` |
| Seguridad | Ninguna (el OpenAPI no declara `securitySchemes`) |
| Parámetros | Ninguno. Los parámetros de consulta se ignoran; `Authorization` y cookies se ignoran |
| Cuerpo de la petición | Ninguno |

## Respuesta 200

`Content-Type: application/json`. Cuerpo: lista JSON de `PublicSubscriptionRead` (puede ser `[]`), en el
orden `created_at ASC, id ASC`.

Cabeceras: `Cache-Control: public, max-age=<CATALOG_CACHE_MAX_AGE_SECONDS>` y `Vary` con `Origin`; las de
CORS si el origen está permitido.

Ejemplo:

```json
[
  {
    "id": 1,
    "name": "Consultorio",
    "description": "Para un médico que empieza a digitalizar su consultorio.",
    "subscription_type": {"id": 1, "name": "Individual"},
    "monthly_price": "499.00",
    "annual_price": "4990.00",
    "trial_days": 14,
    "module_keys": ["patients", "scheduling"],
    "modules": [
      {"key": "patients", "name": "Pacientes"},
      {"key": "scheduling", "name": "Agenda"}
    ],
    "other_features": ["Soporte por correo"],
    "consulting_rooms_limit": 1,
    "doctors_limit": 1,
    "assistants_limit": 1,
    "new_patients_per_year_limit": 500,
    "clinics_limit": 1
  },
  {
    "id": 3,
    "name": "Profesional",
    "description": null,
    "subscription_type": {"id": 2, "name": "Empresarial"},
    "monthly_price": "1299.00",
    "annual_price": "12990.00",
    "trial_days": 0,
    "module_keys": ["clinical_records", "legacy_reports", "patients", "scheduling"],
    "modules": [
      {"key": "patients", "name": "Pacientes"},
      {"key": "scheduling", "name": "Agenda"},
      {"key": "clinical_records", "name": "Expediente clínico"}
    ],
    "other_features": [],
    "consulting_rooms_limit": 5,
    "doctors_limit": 10,
    "assistants_limit": 10,
    "new_patients_per_year_limit": 5000,
    "clinics_limit": 5
  }
]
```

En el segundo elemento, `legacy_reports` no corresponde a un módulo Activo de tipo Clínica: sigue en
`module_keys` y no aparece en `modules` (FR-012).

## Esquema `PublicSubscriptionRead`

Todos los campos son obligatorios en la respuesta (presentes siempre; solo `description` admite `null`).
No hay propiedades adicionales.

| Campo | Tipo | Notas |
|---|---|---|
| `id` | integer, ≥ 1 | |
| `name` | string | |
| `description` | string \| null | |
| `subscription_type` | object `{id: integer ≥ 1, name: string}` | |
| `monthly_price` | string, patrón `^\d+\.\d{2}$` | Pesos mexicanos sin IVA |
| `annual_price` | string, patrón `^\d+\.\d{2}$` | Pesos mexicanos sin IVA |
| `trial_days` | integer, 0–3650 | `0` = sin prueba |
| `module_keys` | array de string | Orden de la base (`ORDER BY module_key`) |
| `modules` | array de `{key: string, name: string}` | Orden `(sort_order, key)` |
| `other_features` | array de string | Orden guardado |
| `consulting_rooms_limit` | integer, 0–1 000 000 | |
| `doctors_limit` | integer, 0–1 000 000 | |
| `assistants_limit` | integer, 0–1 000 000 | |
| `new_patients_per_year_limit` | integer, 0–1 000 000 | |
| `clinics_limit` | integer, 1–100 | |

**Campos prohibidos** (una prueba de contrato falla si aparece cualquiera): `status`, `status_id`,
`self_service`, `clinics_count`, `created_at`, `updated_at`, `subscription_type_id`.

## Equivalencia con maily-system-api (FR-009, SC-005)

Para la misma base de datos: tomar la respuesta de `list_subscriptions` de maily-system-api, quedarse con
los elementos cuyo `status.id == 1` y `self_service == true`, en el mismo orden, y quitar `status`,
`self_service`, `clinics_count`, `created_at` y `updated_at`. El resultado MUST ser igual al catálogo de
este servicio sin el campo `modules`.

## Respuestas de error

| HTTP | `code` | Cuándo |
|---|---|---|
| 405 | `method_not_allowed` | POST, PUT, PATCH, DELETE, HEAD u otro método; con `Allow: GET` |
| 429 | `rate_limit_exceeded` | Límite por IP superado; con `Retry-After` |
| 503 | `service_unavailable` | Base no disponible o tiempo máximo agotado |
| 500 | `internal_error` | Fallo inesperado (p. ej. un permiso faltante del usuario de base de datos) |

Todas con `Cache-Control: no-store`.
