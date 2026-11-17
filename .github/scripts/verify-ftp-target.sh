#!/bin/sh
# Verifica che l'account FTP punti alla cartella giusta prima di caricare qualsiasi file (come in Presenze).
# Uso: verify-ftp-target.sh <file-marcatore> <descrizione-cartella>
# Richiede FTP_SERVER, FTP_USERNAME, FTP_PASSWORD nell'ambiente.
MARKER="$1"
WHAT="$2"
set +e
curl --silent --show-error --fail --ssl-reqd --max-time 60 \
  --user "$FTP_USERNAME:$FTP_PASSWORD" "ftp://$FTP_SERVER/$MARKER" --output /dev/null
code=$?
set -e
case "$code" in
  0) echo "Cartella di destinazione verificata ($WHAT)." ;;
  51|60)
    echo "Nomi presenti nel certificato del server FTP (usa uno di questi come FTP_SERVER):"
    timeout 20 openssl s_client -starttls ftp -connect "$FTP_SERVER:21" </dev/null 2>/dev/null \
      | openssl x509 -noout -subject -ext subjectAltName 2>/dev/null | sed -e 's/^/    /' \
      || echo "    (impossibile leggere il certificato)"
    echo "::error::Il certificato SSL non corrisponde a FTP_SERVER. Deploy annullato: nessun file toccato."
    exit 1 ;;
  67) echo "::error::Accesso FTP rifiutato ($WHAT): controlla utente e password. Nessun file toccato."; exit 1 ;;
  6|7|28) echo "::error::Server FTP non raggiungibile (codice $code). Nessun file toccato."; exit 1 ;;
  *) echo "::error::Nella cartella FTP manca il file $MARKER ($WHAT, codice $code). Nessun file toccato."; exit 1 ;;
esac
