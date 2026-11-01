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
