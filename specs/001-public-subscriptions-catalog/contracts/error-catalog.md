# Contrato: catálogo de errores (FR-013, FR-014)

Todos los errores de este servicio tienen el mismo cuerpo que los de maily-system-api:

```json
{
  "code": "service_unavailable",
  "message": "El catálogo de suscripciones no está disponible por el momento. Inténtelo de nuevo más tarde."
}
```

- `code`: código estable en inglés; quien consume la API se basa en él, no en el texto.
- `message`: texto en español para personas, sin detalles técnicos.
- No hay `errors`: este servicio no recibe datos que validar.
- Ningún error incluye nombres de host, direcciones, cadenas de conexión, nombres de usuario de la base de
  datos, mensajes del driver ni trazas, ni usa el cuerpo `{"detail": …}` del framework.
- Toda respuesta de error lleva `Cache-Control: no-store`.

## Códigos

| Código | HTTP | Cuándo | Cabeceras extra |
|---|---|---|---|
| `service_unavailable` | 503 | La base de datos no da una conexión, la rechaza, la pierde o no termina dentro de `DATABASE_QUERY_TIMEOUT_SECONDS` (research R5) | — |
| `rate_limit_exceeded` | 429 | La IP del cliente no tiene fichas disponibles (research R1) | `Retry-After: <segundos>` |
| `method_not_allowed` | 405 | Método distinto de GET sobre una ruta existente | `Allow: GET` |
| `not_found` | 404 | Ruta inexistente; `/docs` y `/openapi.json` con la documentación apagada | — |
| `internal_error` | 500 | Cualquier otro fallo inesperado | — |

## Mensajes

| Código | Mensaje |
|---|---|
| `service_unavailable` | «El catálogo de suscripciones no está disponible por el momento. Inténtelo de nuevo más tarde.» |
| `rate_limit_exceeded` | «Se hicieron demasiadas solicitudes. Espere un momento e inténtelo de nuevo.» |
| `method_not_allowed` | «Esta operación no está permitida: el servicio es de solo lectura.» |
| `not_found` | «No existe el recurso solicitado.» |
| `internal_error` | «Ocurrió un error inesperado. Inténtelo de nuevo más tarde.» (el mismo texto que maily-system-api) |

## Códigos que este servicio nunca emite

`unauthenticated`, `token_expired`, `invalid_token`, `permission_denied`, `authorization_unavailable`
(401/403: no hay control de acceso) y `validation_error` (422: no hay entrada que validar).

Las rutas de salud no usan este formato para su 503: siguen el cuerpo `{status, checks}` del contrato de
salud v1 ([health-v1.md](health-v1.md)).
