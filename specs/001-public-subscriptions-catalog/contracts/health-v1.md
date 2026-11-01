# Contrato: salud v1 en maily-public-api (FR-020)

El contrato común es el de maily-system-api:
`specs/005-health-monitoring/contracts/health-contract-v1.md` (en ese repositorio). Este documento fija
solo lo propio de este servicio; cualquier cambio de rutas, campos o códigos se coordina con los demás
servicios y con el Backoffice, nunca aquí por separado.

Reglas comunes: rutas en la raíz, fuera de `/api/v1`, solo GET, sin token, sin límite de peticiones,
`Cache-Control: no-store`, campos en inglés, sin secretos, hosts, direcciones, cadenas de conexión,
mensajes de excepción ni trazas. Llevan las cabeceras CORS de la aplicación como cualquier ruta.

## `GET /health/live`

200 `{"status": "ok"}` sin consultar la base de datos.

## `GET /health/ready`

- Ejecuta `SELECT 1` con las credenciales de solo lectura, en dos fases (obtener la conexión; consultar),
  dentro de `asyncio.timeout(HEALTH_READY_TIMEOUT_SECONDS)` (2 s por omisión, siempre menor que los 3 s
  del agregador del Backoffice).
- 200 si responde; 503 si no. Mismo cuerpo:

  ```json
  {"status": "ok", "checks": [{"name": "database", "status": "ok", "latency_ms": 12, "error": null}]}
  {"status": "unavailable", "checks": [{"name": "database", "status": "error", "latency_ms": 2001, "error": "timeout"}]}
  ```

- `error`: `timeout` (se agotó el límite), `connection_error` (no se obtuvo la conexión o se perdió) o
  `unexpected_error` (otra falla de la consulta). Nunca `not_configured` (este servicio no arranca sin
  `DATABASE_URL`). Una falla inesperada responde 503, nunca 500.
- `latency_ms`: entero ≥ 0, también cuando falla.
- Solo comprueba la conexión: un permiso faltante sobre las tablas del catálogo no se detecta aquí (caso
  borde de la especificación).

## `GET /info`

```json
{"service": "maily-public-api", "version": "1.0.0", "commit": "<sha>", "build_date": "2026-11-01T18:00:00Z", "environment": "dev"}
```

- `version`: `src.VERSION`, igual a `pyproject.toml` y a `info.version` del OpenAPI.
- `commit`, `build_date`, `environment`: de `APP_COMMIT_SHA`, `APP_BUILD_DATE` (argumentos del build de la
  imagen) y `APP_ENVIRONMENT` (al desplegar); vacías o inválidas → `unknown`. Mismas reglas de formato que
  maily-system-api (commit hexadecimal de 7 a 64; fecha ISO 8601 con zona, normalizada a UTC con `Z`;
  ambiente `[A-Za-z0-9._-]{1,50}`).

## Registro en el Backoffice

Se da de alta en «Componentes monitoreados» como `kind` `service` con `live_path` `/health/live`,
`ready_path` `/health/ready` e `info_path` `/info`; su host debe estar en `HEALTH_ALLOWED_HOSTS` del
agregador. Con la base detenida aparece `degraded` (sigue vivo), no `down` (SC-009).
