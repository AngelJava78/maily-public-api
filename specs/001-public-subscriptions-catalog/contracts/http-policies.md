# Contrato: políticas HTTP (FR-002, FR-003, FR-017 a FR-019, FR-021, FR-022)

## Rutas publicadas

| Ruta | Métodos | Prefijo | Límite por IP | `Cache-Control` | Notas |
|---|---|---|---|---|---|
| `/api/v1/subscriptions` | GET | `/api/v1` | Sí | `public, max-age=<N>` en 200; `no-store` en error | [subscriptions-catalog.md](subscriptions-catalog.md) |
| `/health/live` | GET | raíz | No | `no-store` | [health-v1.md](health-v1.md) |
| `/health/ready` | GET | raíz | No | `no-store` | [health-v1.md](health-v1.md) |
| `/info` | GET | raíz | No | `no-store` | [health-v1.md](health-v1.md) |
| `/docs` | GET | raíz | No | — | Solo con `DOCS_ENABLED=true` |
| `/openapi.json` | GET | raíz | No | — | Solo con `DOCS_ENABLED=true` |

No existe ninguna otra ruta (en particular, ni `/redoc` ni `/docs/oauth2-redirect`). Cualquier otra ruta
responde 404 `not_found`.

## Métodos

- Solo GET. Cualquier otro método sobre una ruta de la tabla responde 405 `method_not_allowed` con
  `Allow: GET` (HEAD incluido).
- Una petición `OPTIONS` con `Origin` y `Access-Control-Request-Method` (verificación previa de CORS) la
  atiende la política de CORS y no llega a las rutas.
- Prueba obligatoria (constitución, Principio V): recorrer las rutas registradas de la aplicación y fallar
  si alguna, salvo `/docs`, `/openapi.json`, `/health/live`, `/health/ready` e `/info`, admite un método
  distinto de GET; y fallar si el OpenAPI contiene una operación que no sea `get`.

## Credenciales

- `Authorization` y `Cookie` se ignoran: la respuesta es idéntica con o sin ellas, y nunca se registran.
- El OpenAPI no declara `securitySchemes` ni `security`.

## CORS

| Ajuste | Valor |
|---|---|
| Orígenes permitidos | Exactamente los de `CORS_ALLOWED_ORIGINS` (obligatoria, ≥ 1, sin `*`) |
| Métodos | `GET` |
| Cabeceras de la petición permitidas | Ninguna adicional a las simples |
| Credenciales | No (`Access-Control-Allow-Credentials` nunca se envía) |

- Origen permitido: la respuesta lleva `Access-Control-Allow-Origin: <ese origen>`.
- Origen no permitido: la respuesta no lleva `Access-Control-Allow-Origin` (el navegador la bloquea; un
  cliente que no es navegador recibe el catálogo igual, porque es público).
- `Vary` siempre incluye `Origin` en la respuesta 200 del catálogo (research R9).

## Caché

- Catálogo 200: `Cache-Control: public, max-age=<CATALOG_CACHE_MAX_AGE_SECONDS>` (300 por omisión).
- Cualquier error (404, 405, 429, 500, 503): `Cache-Control: no-store`.
- Salud: `Cache-Control: no-store` siempre.

## Límite de peticiones por IP (research R1, R2)

- Alcance: solo las rutas de `/api/v1`.
- Algoritmo: cubeta de fichas por IP; capacidad `RATE_LIMIT_PER_MINUTE` (60 por omisión), recarga de
  `RATE_LIMIT_PER_MINUTE / 60` fichas por segundo. `0` apaga el límite (solo si la infraestructura lo
  aplica).
- Exceso: 429 `rate_limit_exceeded`, `Retry-After` = segundos enteros (≥ 1) hasta la siguiente ficha.
- IP del cliente:
  - `TRUSTED_PROXY_HOPS = 0`: IP de la conexión.
  - `TRUSTED_PROXY_HOPS = N > 0`: la N-ésima dirección desde la derecha de `X-Forwarded-For` (todas las
    cabeceras `X-Forwarded-For` unidas en orden). Si hay menos de N direcciones o no es una IP válida,
    la IP de la conexión.
  - Ejemplo con `N = 1` y `X-Forwarded-For: 203.0.113.9, 198.51.100.7`: la IP es `198.51.100.7` (la
    escribió el proxy de confianza); `203.0.113.9` pudo escribirla el cliente.
- Memoria: las IP cuya cubeta ya está llena de nuevo se purgan cuando el registro crece.
- Varias réplicas: el límite es por réplica.
