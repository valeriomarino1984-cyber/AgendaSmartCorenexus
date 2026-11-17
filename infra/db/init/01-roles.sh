#!/usr/bin/env bash
# Eseguito dall'immagine ufficiale postgres alla prima inizializzazione (docker-compose).
set -euo pipefail
: "${MIGRATOR_DB_PASSWORD:?MIGRATOR_DB_PASSWORD obbligatoria}"
: "${APP_DB_PASSWORD:?APP_DB_PASSWORD obbligatoria}"
psql --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
  -v migrator_password="$MIGRATOR_DB_PASSWORD" \
  -v app_password="$APP_DB_PASSWORD" \
  -v dbname="$POSTGRES_DB" \
  -f /docker-entrypoint-initdb.d/roles.sql.inc
