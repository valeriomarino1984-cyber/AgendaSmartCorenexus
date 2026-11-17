#!/bin/sh
# Pacchetto per cPanel "Setup Python App" (Passenger): codice, migrazioni, passenger_wsgi.py e
# requirements.txt a versioni fisse esportate da uv.lock ("Run Pip Install" le installa).
set -e
cd "$(dirname "$0")/.."
OUT=dist/cpanel-api
rm -rf "$OUT" dist/agenda-api-cpanel.zip
mkdir -p "$OUT/tmp"
cp -r app migrations "$OUT/"
cp alembic.ini passenger_wsgi.py install_deps.py "$OUT/"
find "$OUT" -name "__pycache__" -type d -prune -exec rm -rf {} +
uv export --frozen --no-dev --no-hashes --no-emit-project --no-header -q -o "$OUT/requirements.txt"
(cd "$OUT" && zip -qr ../agenda-api-cpanel.zip .)
echo "Pacchetto pronto: backend/dist/agenda-api-cpanel.zip"
