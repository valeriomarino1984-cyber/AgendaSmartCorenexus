#!/usr/bin/env bash
# Ripristino di un backup cifrato in un database a scelta, con riepilogo per la prova di
# ripristino. Uso:
#   bash ~/agenda-api/ops/restore-db.sh <file.sql.gz.enc> <database_di_destinazione> [--forza]
#
# Usa le stesse credenziali e la stessa chiave del backup (BACKUP_CNF, BACKUP_PASSPHRASE_FILE).
# Per sicurezza rifiuta di scrivere sul database di produzione (quello del file .cnf) se non
# si aggiunge --forza: la prova di ripristino si fa su un database vuoto a parte.
set -euo pipefail
umask 077

CNF=${BACKUP_CNF:-$HOME/.agenda-backup.cnf}
KEY=${BACKUP_PASSPHRASE_FILE:-$HOME/.agenda-backup.key}
fail() { echo "ERRORE ripristino: $*" >&2; exit 1; }

[ $# -ge 2 ] || fail "uso: restore-db.sh <file.sql.gz.enc> <database> [--forza]"
FILE=$1; TARGET=$2; FORCE=${3:-}
[ -r "$FILE" ] || fail "file non trovato: $FILE"
[ -r "$CNF" ] || fail "manca il file delle credenziali $CNF"
[ -r "$KEY" ] || fail "manca la chiave di cifratura $KEY"
case "$TARGET" in *[!A-Za-z0-9_]*|"") fail "nome di database non valido: $TARGET";; esac
LIVE=$(sed -n 's/^[[:space:]]*database[[:space:]]*=[[:space:]]*//p' "$CNF" | head -n1)
if [ "$TARGET" = "$LIVE" ] && [ "$FORCE" != "--forza" ]; then
  fail "$TARGET è il database di produzione: per sovrascriverlo aggiungi --forza"
fi

if [ -r "$FILE.sha256" ]; then
  (cd "$(dirname "$FILE")" && sha256sum -c --quiet "$(basename "$FILE").sha256") \
    || fail "la somma SHA-256 non corrisponde: il file è danneggiato"
fi

CLIENT=$(command -v mariadb || command -v mysql || true)
[ -n "$CLIENT" ] || fail "client mysql non trovato"
ENC=(-aes-256-cbc -pbkdf2 -iter 200000 -md sha256)

openssl enc -d "${ENC[@]}" -pass "file:$KEY" -in "$FILE" | gunzip -c \
  | "$CLIENT" --defaults-extra-file="$CNF" --default-character-set=utf8mb4 "$TARGET"

echo "Ripristinato $FILE in $TARGET."
q() { "$CLIENT" --defaults-extra-file="$CNF" -N -B "$TARGET" -e "$1"; }
echo "Versione dello schema: $(q 'SELECT version_num FROM alembic_version')"
echo "Righe per tabella:"
for t in tenants users clients professionals services appointments notification_jobs; do
  printf '  %-20s %s\n' "$t" "$(q "SELECT COUNT(*) FROM \`$t\`")"
done
