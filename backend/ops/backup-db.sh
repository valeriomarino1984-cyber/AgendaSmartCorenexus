#!/usr/bin/env bash
# Backup cifrato del database di Agenda, con verifica. Pensato per il cron di cPanel:
#   bash ~/agenda-api/ops/backup-db.sh
#
# File e variabili (tutti con valori predefiniti nella home dell'account):
#   BACKUP_CNF              credenziali: gruppo [client] con user/password/host e gruppo
#                           [agenda] con database=… (default ~/.agenda-backup.cnf, permessi 600).
#                           Il nome del database sta in [agenda] perché il mysqldump di MySQL 8
#                           rifiuta l'opzione database in [client].
#   BACKUP_PASSPHRASE_FILE  chiave di cifratura (default ~/.agenda-backup.key, permessi 600).
#                           Conservane una copia FUORI dal server: senza, i backup non si aprono.
#   BACKUP_DIR              cartella dei backup (default ~/agenda-backup, fuori da public_html)
#   BACKUP_KEEP_DAYS        giorni di conservazione (default 14)
#
# Ogni backup: mysqldump in transazione → gzip → AES-256 (openssl, PBKDF2) → verifica che il file
# si decifri e contenga il dump completo → somma SHA-256. Solo allora prende il nome finale.
set -euo pipefail
umask 077

CNF=${BACKUP_CNF:-$HOME/.agenda-backup.cnf}
KEY=${BACKUP_PASSPHRASE_FILE:-$HOME/.agenda-backup.key}
DIR=${BACKUP_DIR:-$HOME/agenda-backup}
KEEP=${BACKUP_KEEP_DAYS:-14}

fail() { echo "ERRORE backup: $*" >&2; exit 1; }
[ -r "$CNF" ] || fail "manca il file delle credenziali $CNF"
[ -r "$KEY" ] || fail "manca la chiave di cifratura $KEY"
[ "$(wc -c < "$KEY")" -ge 32 ] || fail "la chiave in $KEY è troppo corta (minimo 32 caratteri)"
for f in "$CNF" "$KEY"; do
  case "$(stat -c %a "$f")" in 600|400) ;; *) fail "$f deve avere permessi 600 (chmod 600 $f)";; esac
done
DB=$(sed -n 's/^[[:space:]]*database[[:space:]]*=[[:space:]]*//p' "$CNF" | head -n1)
[ -n "$DB" ] || fail "in $CNF manca la riga database=… (nel gruppo [agenda])"

DUMP=$(command -v mariadb-dump || command -v mysqldump || true)
[ -n "$DUMP" ] || fail "mysqldump non trovato"
EXTRA=()
# Il mysqldump di MySQL 8 su MariaDB fallisce sulle statistiche delle colonne.
if "$DUMP" --help 2>/dev/null | grep -q -- '--column-statistics'; then EXTRA+=(--column-statistics=0); fi

ENC=(-aes-256-cbc -pbkdf2 -iter 200000 -md sha256)
mkdir -p "$DIR"
stamp=$(date +%Y%m%d-%H%M%S)
out="$DIR/agenda-$stamp.sql.gz.enc"
tmp="$out.part"
trap 'rm -f "$tmp"' EXIT

"$DUMP" --defaults-extra-file="$CNF" --single-transaction --quick --no-tablespaces \
  --hex-blob --default-character-set=utf8mb4 --routines --triggers "${EXTRA[@]}" "$DB" \
  | gzip -9 | openssl enc "${ENC[@]}" -salt -pass "file:$KEY" -out "$tmp"

# Verifica: si decifra, si decomprime e termina con la riga che mysqldump scrive solo a fine dump.
last=$(openssl enc -d "${ENC[@]}" -pass "file:$KEY" -in "$tmp" | gunzip -c | tail -n 1)
case "$last" in *"Dump completed"*) ;; *) fail "verifica non riuscita: il dump è incompleto";; esac

mv "$tmp" "$out"
(cd "$DIR" && sha256sum "$(basename "$out")" > "$(basename "$out").sha256")
find "$DIR" -maxdepth 1 -name 'agenda-*.sql.gz.enc*' -mtime +"$KEEP" -delete
echo "Backup verificato: $out ($(du -h "$out" | cut -f1))"
