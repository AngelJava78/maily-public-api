# Contrato: usuario de base de datos de solo lectura (FR-025, FR-027)

Contrato **consumido**: lo provee mailySoft-DB, no este repositorio. Este servicio nunca crea roles ni
ejecuta DDL. Se elige la opción de referencia por tablas con permisos por columna (research R3).

## 1. Requisito previo de esquema (FR-027)

Antes de crear el rol, el esquema vigente de mailySoft-DB MUST tener:

- `subscriptions.clinics_limit integer NOT NULL` (maily-system-api, Alembic 0006).
- `subscription_modules (subscription_id integer FK → subscriptions.id, module_key text, PK (subscription_id, module_key))`
  (maily-system-api, Alembic 0007).

Hoy (mailySoft-DB V5) faltan ambos. Sin ellos los `GRANT` de abajo fallan.

## 2. Definición propuesta

Durante la implementación este SQL se guarda tal cual en `docs/database/read-only-role.sql`; las pruebas
lentas lo aplican a la base desechable (research R11) y mailySoft-DB lo adopta como migración. Es
idempotente. No contiene contraseña: se asigna por ambiente, fuera de cualquier repositorio.

```sql
-- Usuario de solo lectura de maily-public-api (catálogo público de suscripciones).
-- Propuesta para mailySoft-DB. maily-public-api no lo ejecuta en ningún ambiente compartido.
-- La contraseña se asigna por ambiente, fuera del repositorio:
--   ALTER ROLE maily_public_api PASSWORD '<secreto>';

DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'maily_public_api') THEN
        CREATE ROLE maily_public_api
            LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS
            CONNECTION LIMIT 12;
    END IF;
END
$$;

-- Topes por omisión del rol; el servicio fija además su propio statement_timeout (3 s) por sesión.
ALTER ROLE maily_public_api SET default_transaction_read_only = on;
ALTER ROLE maily_public_api SET statement_timeout = '5s';
ALTER ROLE maily_public_api SET idle_in_transaction_session_timeout = '10s';

DO $$
BEGIN
    EXECUTE format('GRANT CONNECT ON DATABASE %I TO maily_public_api', current_database());
END
$$;

GRANT USAGE ON SCHEMA public TO maily_public_api;

GRANT SELECT (
    id, name, description, subscription_type_id, monthly_price, annual_price, trial_days,
    other_features, consulting_rooms_limit, doctors_limit, assistants_limit,
    new_patients_per_year_limit, clinics_limit, status_id, self_service, created_at
) ON public.subscriptions TO maily_public_api;

GRANT SELECT (id, name) ON public.subscription_types TO maily_public_api;

GRANT SELECT (subscription_id, module_key) ON public.subscription_modules TO maily_public_api;

GRANT SELECT (key, name, sort_order, status_id, type_id) ON public.modules TO maily_public_api;
```

Notas para mailySoft-DB:

- `CONNECTION LIMIT 12` = pool del servicio (5 + 5 de desborde, research R4) + 2 de margen para
  operación, por réplica. Si aumentan las réplicas, se ajusta.
- El rol no es miembro de ningún otro rol ni dueño de ningún objeto.
- `PUBLIC` conserva por omisión `CONNECT` y `TEMPORARY` sobre la base y `EXECUTE` sobre funciones; en
  PostgreSQL 18 ya no tiene `CREATE` sobre `public`. Las transacciones de solo lectura impiden crear
  tablas temporales. Retirar privilegios a `PUBLIC` afecta a todos los roles y queda fuera de esta
  feature.
- Si el esquema agrega columnas a estas tablas, el rol **no** las puede leer hasta que se concedan: es lo
  esperado (privilegio mínimo).

## 3. Verificación (quien opera, con un usuario administrador)

```sql
-- Atributos y topes del rol (rolconnlimit = 12; rolconfig con los tres ajustes).
SELECT rolname, rolsuper, rolcreatedb, rolcreaterole, rolreplication, rolbypassrls,
       rolconnlimit, rolconfig
FROM pg_catalog.pg_roles WHERE rolname = 'maily_public_api';

-- Sin membresías (0 filas).
SELECT roleid::regrole FROM pg_catalog.pg_auth_members
WHERE member = 'maily_public_api'::regrole;

-- Exactamente las 25 columnas concedidas, todas SELECT.
SELECT table_name, column_name, privilege_type
FROM information_schema.column_privileges
WHERE grantee = 'maily_public_api'
ORDER BY table_name, column_name;

-- Ningún privilegio de escritura en ninguna tabla (0 filas).
SELECT table_name, privilege_type
FROM information_schema.table_privileges
WHERE grantee = 'maily_public_api' AND privilege_type <> 'SELECT';
```

Y, conectado **como** `maily_public_api` (SC-004):

```sql
BEGIN READ WRITE;
INSERT INTO public.subscriptions (name) VALUES ('x');           -- ERROR 42501 permission denied
ROLLBACK;
BEGIN READ WRITE;
UPDATE public.subscriptions SET name = name WHERE false;        -- ERROR 42501 permission denied
ROLLBACK;
BEGIN READ WRITE;
DELETE FROM public.subscriptions WHERE false;                   -- ERROR 42501 permission denied
ROLLBACK;
SELECT updated_at FROM public.subscriptions LIMIT 1;            -- ERROR 42501 (columna no concedida)
SELECT 1 FROM public.users LIMIT 1;                             -- ERROR 42501 (tabla no concedida)
```

## 4. Cadena de conexión del servicio

`DATABASE_URL=postgresql+asyncpg://maily_public_api:<secreto>@<host>:<puerto>/<base>` (más `?ssl=require`
en Azure). Es el único secreto del servicio.
