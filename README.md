# maily-public-api

API pública de MailySoft, **de solo lectura y sin autenticación**. Publica el catálogo de suscripciones
(planes) que muestra la página pública «Suscripciones» del Frontend de Maily: solo las suscripciones
Activas de autoservicio, con sus precios, módulos y límites, y nunca datos internos.

Principios no negociables: [.specify/memory/constitution.md](.specify/memory/constitution.md).
Especificación de la primera feature: [specs/001-public-subscriptions-catalog/](specs/001-public-subscriptions-catalog/).

## Qué expone

| Ruta | Para qué |
|---|---|
| `GET /api/v1/subscriptions` | Catálogo público completo, sin paginar ([contrato](specs/001-public-subscriptions-catalog/contracts/subscriptions-catalog.md)) |
| `GET /health/live`, `GET /health/ready`, `GET /info` | Contrato de salud v1 de MailySoft ([contrato](specs/001-public-subscriptions-catalog/contracts/health-v1.md)) |
| `GET /docs`, `GET /openapi.json` | Documentación en español; se apaga con `DOCS_ENABLED=false` |

Solo existen operaciones GET. Ninguna exige token. El catálogo lleva `Cache-Control: public` y cada IP
tiene un límite de peticiones por minuto
([políticas HTTP](specs/001-public-subscriptions-catalog/contracts/http-policies.md)).

## Dependencias con mailySoft-DB

Este servicio no tiene esquema propio ni migraciones: lee la base de datos compartida de MailySoft, cuyo
esquema administra **mailySoft-DB**. Necesita de ese repositorio:

1. Las tablas `subscription_modules` y la columna `subscriptions.clinics_limit` (FR-027 de la
   especificación).
2. El usuario de base de datos de solo lectura `maily_public_api`, con los permisos exactos de
   [docs/database/read-only-role.sql](docs/database/read-only-role.sql)
   ([detalle y verificación](specs/001-public-subscriptions-catalog/contracts/database-permissions.md)).
   Ese archivo es la propuesta para mailySoft-DB; las pruebas lo aplican a su base desechable.

## Configuración

Copia [.env.example](.env.example) a `.env`. Obligatorias: `DATABASE_URL` (el usuario de solo lectura;
es el único secreto) y `CORS_ALLOWED_ORIGINS` (los orígenes del Frontend). El resto tiene valores por
omisión: [contracts/environment.md](specs/001-public-subscriptions-catalog/contracts/environment.md).
Si falta una variable obligatoria o una es inválida, el servicio no arranca y dice cuál, sin mostrar
valores.

## Pruebas

```sh
uv sync
uv run pytest                                   # corrida por defecto: sin PostgreSQL
```

La suite completa (puerta antes de integrar a `main`) también corre las pruebas `slow`, contra un
PostgreSQL 18 desechable con el esquema de mailySoft-DB (se lee de `../mailySoft-DB` o de
`MAILYSOFT_DB_DIR`) y conectadas como el usuario de solo lectura:

```sh
docker compose --profile test up -d db-test
uv run pytest -m ""
docker compose --profile test down
```

## Ejecutar en local

1. Levanta la base compartida local con el Compose de mailySoft-DB y despliega su esquema (ver su
   README).
2. Mientras mailySoft-DB no tenga el usuario de solo lectura, créalo en tu base local con
   `docs/database/read-only-role.sql` y asígnale la contraseña de tu `.env`
   ([quickstart](specs/001-public-subscriptions-catalog/quickstart.md), paso 3).
3. `docker compose up -d --build api` → `http://localhost:8006/api/v1/subscriptions` y
   `http://localhost:8006/docs`.

Sin Docker, igual que maily-system-api:

```sh
uv run uvicorn src.main:app --port 8006
```

Lee el `.env`. Como corre fuera de la red de Docker, `DATABASE_URL` apunta al puerto que la base publica
en tu máquina (`127.0.0.1:5434` con el Compose de mailySoft-DB), no a `db-local:5432`. Si Windows
bloquea el ejecutable `uvicorn.exe` del entorno virtual (Control de aplicaciones), usa
`uv run python -m uvicorn src.main:app --port 8006`.

## Stack

Python 3.14, FastAPI, uvicorn, SQLAlchemy 2.0 async con asyncpg, Pydantic v2 con pydantic-settings,
pytest con pytest-asyncio, uv, Docker y Docker Compose. Metodología: GitHub Spec Kit.
