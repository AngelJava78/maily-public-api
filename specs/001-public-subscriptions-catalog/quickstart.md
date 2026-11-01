# Quickstart: validar el catálogo público de suscripciones

Guía para comprobar de punta a punta que la feature cumple la especificación. Los detalles del contrato
están en [contracts/](contracts/) y los del modelo en [data-model.md](data-model.md).

## Requisitos previos

- Docker y Docker Compose; `uv` (la misma versión que la imagen, 0.13.1); PowerShell o Bash.
- Una copia local de mailySoft-DB junto a este repositorio (`../mailySoft-DB`) o su ruta en
  `MAILYSOFT_DB_DIR`.
- **Bloqueante (FR-027)**: mailySoft-DB con `subscription_modules` y `subscriptions.clinics_limit` en sus
  migraciones y en `schema/current_schema.sql`. Mientras no estén, solo la corrida por defecto de pruebas
  (paso 1) puede pasar.
- Un `.env` a partir de `.env.example` ([contracts/environment.md](contracts/environment.md)); ajustar
  `CORS_ALLOWED_ORIGINS` al origen local del Frontend.

## 1. Corrida por defecto (sin PostgreSQL)

```sh
uv sync
uv run pytest
```

Esperado: todo en verde sin ninguna base de datos. Cubre los Services, la configuración, el límite por
IP, el contrato de cada ruta (con Repositories sustituidos), las cabeceras, los errores, el OpenAPI y la
prueba de rutas solo GET. Es lo único que corre `/speckit-implement`.

## 2. Suite completa (puerta antes de `main`)

```sh
docker compose --profile test up -d db-test
uv run pytest -m ""
docker compose --profile test down
```

Esperado: todo en verde, incluidas las pruebas `slow`, que aplican `schema/current_schema.sql` y los
catálogos de mailySoft-DB a la base desechable, crean el rol con `docs/database/read-only-role.sql` y se
conectan como ese rol. Demuestran, entre otras cosas, SC-002 (ninguna suscripción no pública aparece) y
SC-004 (escrituras rechazadas aun con `BEGIN READ WRITE`). Mientras no haya CI, quien integra a `main` la
corre a mano (constitución, Principio V).

## 3. Levantar el servicio en local contra la base compartida

1. Levantar la base compartida local y desplegar el esquema desde mailySoft-DB (su README, «Agregar un
   cambio de estructura», paso 4).
2. **Provisional, hasta que mailySoft-DB tenga el rol**: crear el rol en la base local con el SQL de este
   repositorio y asignarle la contraseña del `.env`:

   ```sh
   docker compose -f ../mailySoft-DB/docker-compose.yml exec -T db-local \
     psql -U maily_local -d postgres < docs/database/read-only-role.sql
   docker compose -f ../mailySoft-DB/docker-compose.yml exec -T db-local \
     psql -U maily_local -d postgres -c "ALTER ROLE maily_public_api PASSWORD 'cambiar-en-local'"
   ```

3. Levantar el servicio: `docker compose up -d --build api` (se une a la red `mailysoft-db_default`).

## 4. Escenarios de validación

Con el servicio en `http://localhost:8006` y algunas suscripciones creadas con maily-system-api apuntando
a la misma base (Activas y no Activas, con y sin autoservicio):

| # | Paso | Resultado esperado | Criterio |
|---|---|---|---|
| 1 | `curl -i http://localhost:8006/api/v1/subscriptions` (sin token) | 200; solo Activas de autoservicio, orden por creación e `id`; `Cache-Control: public, max-age=300`; `Vary` con `Origin` | SC-001, SC-002 |
| 2 | Revisar cada elemento | Solo los campos de [subscriptions-catalog.md](contracts/subscriptions-catalog.md); precios como `"499.00"`; nada de `status`, `self_service`, `clinics_count` ni fechas | SC-003 |
| 3 | Repetir 1 con `-H "Authorization: Bearer x" -H "Cookie: a=b"` | Respuesta idéntica | FR-002 |
| 4 | `curl -i -X POST …/api/v1/subscriptions` (y PUT, PATCH, DELETE, `-I` para HEAD) | 405 `method_not_allowed`, `Allow: GET`, `Cache-Control: no-store` | FR-003 |
| 5 | `curl -i -H "Origin: <origen permitido>" …` y luego con `Origin: https://otro.example` | Con el permitido, `Access-Control-Allow-Origin: <origen>` y sin `Allow-Credentials`; con el otro, sin `Access-Control-Allow-Origin` | FR-018 |
| 6 | 61 peticiones seguidas desde la misma IP | La 61.ª responde 429 `rate_limit_exceeded` con `Retry-After`; `/health/live` sigue en 200 | FR-019 |
| 7 | Detener la base compartida (`docker compose -f ../mailySoft-DB/docker-compose.yml stop db-local`) y consultar el catálogo | 503 `service_unavailable` en ≤ 4 s, sin host ni mensajes del driver; `/health/live` 200; `/health/ready` 503 con `error` `connection_error` o `timeout` | SC-007, FR-020 |
| 8 | Volver a levantar la base | El catálogo y `/health/ready` vuelven a 200 sin reiniciar el servicio | FR-020 |
| 9 | `curl http://localhost:8006/info` | `service` `maily-public-api`, `version` `1.0.0`; sin argumentos de build, `commit` y `build_date` en `unknown` | FR-020 |
| 10 | Abrir `http://localhost:8006/docs` | Documentación en español, solo GET, sin candado de seguridad; `/redoc` da 404 | FR-021 |
| 11 | Reiniciar con `DOCS_ENABLED=false` | `/docs` y `/openapi.json` dan 404 `not_found` | FR-022 |
| 12 | Quitar `CORS_ALLOWED_ORIGINS` del `.env` y reiniciar | El servicio no arranca; el registro nombra `CORS_ALLOWED_ORIGINS`, sin mostrar valores | FR-024 |
| 13 | Ejecutar como `maily_public_api` el bloque de verificación de [database-permissions.md](contracts/database-permissions.md) §3 | Cada escritura falla con 42501 | SC-004 |
| 14 | Agregar a una suscripción pública una clave inexistente en `modules` | Sigue en el catálogo; la clave en `module_keys`, no en `modules`; un aviso en el registro (una sola vez) | FR-012 |

## 5. Coincidencia con maily-system-api (SC-005)

Solo en un ambiente donde ambos servicios leen la misma base (p. ej. desarrollo compartido). Con un token
válido de maily-system-api con `subscriptions:read`:

```powershell
$system = Invoke-RestMethod "$env:SYSTEM_API/api/v1/subscriptions" -Headers @{ Authorization = "Bearer $env:TOKEN" }
$public = Invoke-RestMethod "$env:PUBLIC_API/api/v1/subscriptions"
$excluded = 'status','self_service','clinics_count','created_at','updated_at'
$expected = @($system | Where-Object { $_.status.id -eq 1 -and $_.self_service } |
    Select-Object -Property * -ExcludeProperty $excluded)
$actual = @($public | Select-Object -Property * -ExcludeProperty 'modules')
(ConvertTo-Json $expected -Depth 5) -eq (ConvertTo-Json $actual -Depth 5)   # True
```

## 6. Antes de fijar `TRUSTED_PROXY_HOPS` en Railway (research R2)

En el ambiente de desarrollo, con `RATE_LIMIT_PER_MINUTE` alto, desplegar una vez con un registro
temporal de `X-Forwarded-For` y la IP de la conexión (o usar un servicio de eco de cabeceras detrás del
mismo borde) y hacer peticiones enviando `X-Forwarded-For: 203.0.113.9`. Si la dirección de la derecha es
siempre la IP pública real de quien prueba, usar `TRUSTED_PROXY_HOPS=1`. Si aparece la IP de un CDN, usar
el número de saltos que la deja fuera. Quitar el registro temporal después.
