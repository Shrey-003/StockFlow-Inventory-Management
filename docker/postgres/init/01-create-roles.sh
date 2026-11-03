
#!/usr/bin/env bash
set -Eeuo pipefail

: "${APP_DB_PASSWORD:?APP_DB_PASSWORD is required}"
: "${MIGRATOR_DB_PASSWORD:?MIGRATOR_DB_PASSWORD is required}"

psql \
    -v ON_ERROR_STOP=1 \
    -v app_password="$APP_DB_PASSWORD" \
    -v migrator_password="$MIGRATOR_DB_PASSWORD" \
    --username "$POSTGRES_USER" \
    --dbname "$POSTGRES_DB" <<'EOSQL'

-- Create the dedicated migration account.
CREATE ROLE stockflow_migrator
    LOGIN PASSWORD :'migrator_password';

-- Create the restricted application account.
CREATE ROLE stockflow_app
    LOGIN PASSWORD :'app_password';

-- Give database ownership to the migration account.
ALTER DATABASE stockflow OWNER TO stockflow_migrator;

GRANT CONNECT ON DATABASE stockflow TO stockflow_app;

\connect stockflow

-- Restrict schema ownership to the migration account.
ALTER SCHEMA public OWNER TO stockflow_migrator;

-- Application permissions.
GRANT USAGE ON SCHEMA public TO stockflow_app;

GRANT SELECT, INSERT, UPDATE, DELETE
ON ALL TABLES IN SCHEMA public
TO stockflow_app;

GRANT USAGE, SELECT
ON ALL SEQUENCES IN SCHEMA public
TO stockflow_app;

-- Ensure future migration-created tables get application permissions.
ALTER DEFAULT PRIVILEGES
FOR ROLE stockflow_migrator
IN SCHEMA public
GRANT SELECT, INSERT, UPDATE, DELETE
ON TABLES TO stockflow_app;

ALTER DEFAULT PRIVILEGES
FOR ROLE stockflow_migrator
IN SCHEMA public
GRANT USAGE, SELECT
ON SEQUENCES TO stockflow_app;

EOSQL
