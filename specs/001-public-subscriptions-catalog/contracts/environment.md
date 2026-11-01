# Contrato: variables de entorno (FR-023, FR-024)

Se validan al arrancar (en el `lifespan`). Si una obligatoria falta o cualquiera es inválida, el servicio
no arranca y el mensaje nombra **todas** las variables con problema, nunca sus valores. Una variable vacía
cuenta como no definida. La base de datos no disponible al arrancar no impide el arranque.

## Servicio

| Variable | Obligatoria | Por omisión | Validación | Secreta |
|---|---|---|---|---|
| `DATABASE_URL` | Sí | — | `postgresql+asyncpg://usuario:contraseña@host[:puerto]/base[?ssl=...]` con host | Sí |
| `CORS_ALLOWED_ORIGINS` | Sí | — | Orígenes separados por comas; cada uno `http://` o `https://` + host [+ `:puerto`], sin ruta, consulta ni `*`; al menos uno | No |
| `CATALOG_CACHE_MAX_AGE_SECONDS` | No | `300` | Entero de 0 a 86 400 | No |
| `DATABASE_QUERY_TIMEOUT_SECONDS` | No | `3` | Número de 1 a 30 | No |
| `DOCS_ENABLED` | No | `true` | `true` o `false` | No |
| `RATE_LIMIT_PER_MINUTE` | No | `60` | Entero de 0 a 10 000; `0` apaga el límite en la aplicación | No |
| `TRUSTED_PROXY_HOPS` | No | `0` | Entero de 0 a 5 | No |

## Contrato de salud v1 (mismos nombres que en los demás servicios)

| Variable | Obligatoria | Por omisión | Validación |
|---|---|---|---|
| `HEALTH_READY_TIMEOUT_SECONDS` | No | `2` | Número mayor que 0 y hasta 10 |
| `APP_COMMIT_SHA` | No | `unknown` | Hexadecimal de 7 a 64; inválido → `unknown` |
| `APP_BUILD_DATE` | No | `unknown` | ISO 8601 con zona; inválido → `unknown` |
| `APP_ENVIRONMENT` | No | `unknown` | `[A-Za-z0-9._-]{1,50}`; inválido → `unknown` |

`APP_COMMIT_SHA` y `APP_BUILD_DATE` llegan como argumentos del build de la imagen; `APP_ENVIRONMENT`, al
desplegar.

## Solo pruebas (nunca en la imagen ni en producción)

| Variable | Por omisión | Uso |
|---|---|---|
| `TEST_DATABASE_URL` | — | Usuario administrador de la base desechable; el nombre de la base MUST terminar en `_test`. Sin ella, las pruebas `slow` fallan con un mensaje claro |
| `MAILYSOFT_DB_DIR` | `../mailySoft-DB` | Copia local de mailySoft-DB de la que se leen `schema/current_schema.sql` y los catálogos repetibles |

## Plataforma

| Variable | Uso |
|---|---|
| `PORT` | Puerto en que escucha uvicorn dentro del contenedor (Railway lo inyecta; `8000` por omisión). En local, Docker Compose publica `8006:8000` |

## Ejemplo `.env` (local; `.env.example` sin secretos reales)

```dotenv
DATABASE_URL=postgresql+asyncpg://maily_public_api:cambiar-en-local@db-local:5432/postgres
CORS_ALLOWED_ORIGINS=http://localhost:4200
CATALOG_CACHE_MAX_AGE_SECONDS=300
DATABASE_QUERY_TIMEOUT_SECONDS=3
DOCS_ENABLED=true
RATE_LIMIT_PER_MINUTE=60
TRUSTED_PROXY_HOPS=0
TEST_DATABASE_URL=postgresql+asyncpg://postgres:postgres@127.0.0.1:5436/maily_public_api_test
```
