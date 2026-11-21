# Report Sprint 7 – 21/11/2026: dashboard, sicurezza, backup

## Dashboard: i numeri dello studio
Nella pagina iniziale dell'area professionisti, sotto "Agenda di oggi", c'è la sezione **I numeri dello studio**.

- **Filtri:**
  - periodo: questa settimana, questo mese (predefinito), mese scorso, ultimi 3 mesi, quest'anno;
  - professionista: solo per titolare e segreteria.
- **Riquadri:**
  - **Appuntamenti** (quanti svolti e quanti da svolgere);
  - **Occupazione**: ore prenotate sulle ore di orario, tenendo conto di ferie, chiusure e festività;
  - **Clienti nuovi**: clienti il cui primo appuntamento non disdetto nello studio cade nel periodo;
  - **Incassato**: prezzo degli appuntamenti svolti, più il previsto da quelli ancora da svolgere;
  - **Disdette**: percentuale, divisa tra disdette del cliente e dello studio;
  - **Assenze**: percentuale sugli appuntamenti chiusi (svolti + assenti);
  - **Prenotati online**: quanti sono arrivati dalla pagina di prenotazione.
- **Andamento:** un grafico a barre, per giorno, oppure per mese oltre i 62 giorni. Passando sopra una barra, o selezionandola con il tasto Tab, si leggono svolti, disdetti e assenti.
- **Tabelle:** prestazioni (appuntamenti e incassato) e professionisti (appuntamenti, assenze, occupazione).
- **Permessi:** il professionista vede solo i numeri della propria agenda; chiedendo quelli di un altro riceve un errore. Titolare e segreteria vedono tutto lo studio.
- **Regole:**
  - gli appuntamenti si contano per data di inizio, nel fuso della sede principale;
  - il periodo massimo è di un anno;
  - "Per iniziare" sparisce quando i passi sono tutti fatti.

La pagina **Notifiche** (email fallite e nuovo invio), prevista dal piano per questo sprint, è già arrivata con lo Sprint 5.

## Backup cifrati e prova di ripristino
- `backend/ops/backup-db.sh`, da lanciare con il cron di cPanel ogni notte:
  - il dump è coerente (`--single-transaction`), compresso e cifrato AES-256 (PBKDF2, 200.000 iterazioni);
  - dopo il salvataggio il file viene **decifrato e controllato** fino alla riga finale "Dump completed": solo allora prende il nome definitivo, con la sua somma SHA-256;
  - conserva 14 giorni; credenziali e chiave stanno in file con permessi 600 fuori da `public_html`, altrimenti lo script si rifiuta di partire.
- `backend/ops/restore-db.sh`, per la prova di ripristino:
  - verifica la somma SHA-256, decifra e carica il backup in un database a scelta;
  - stampa la versione dello schema e il numero di righe delle tabelle principali;
  - non scrive sul database di produzione senza `--forza`.
- I due script arrivano sul server con il deploy, in `agenda-api/ops/`. Le istruzioni per cPanel sono in `07-deploy-netsons.md`, punto 7.

## Controllo di sicurezza (checklist)
Verificato in produzione il 21/11/2026, salvo dove indicato.

| Area | Stato |
|---|---|
| HTTPS e intestazioni | HSTS 1 anno; `X-Frame-Options: DENY`; `nosniff`; Referrer-Policy; Permissions-Policy; CSP `frame-ancestors 'none'` sul sito e `default-src 'none'` sulle API |
| File riservati | `.env`, `.git`, `.htaccess`, `package.json` rispondono 403; documentazione delle API (`/docs`, `openapi.json`) spenta: 404; pagina di anteprima dei componenti: 404 |
| Registrazione | Chiusa (`SIGNUP_OPEN=false`): il server rifiuta con "registrazione chiusa". Il link "Registrati" è stato tolto |
| Password | scrypt (32 MiB per hash); blocco dopo i tentativi falliti, per email e per IP |
| Sessioni | Cookie `__Host-`, HttpOnly, Secure, SameSite. Scadenze: professionisti 1 ora di inattività, clienti 5 minuti, piattaforma 30 minuti (massimo 12 ore) con codice a 6 cifre |
| Richieste da altri siti | Controllo dell'intestazione Origin su tutte le richieste che modificano dati (escluso il solo cron, che ha la sua chiave) |
| Limiti anti-abuso | Su login, email di verifica e di recupero password, link dell'area clienti, prenotazioni online e prima configurazione della piattaforma |
| Isolamento tra studi | Filtro automatico per studio su ogni query; test dedicati in ogni modulo |
| Dipendenze | `pip-audit` (backend) e `pnpm audit --prod` (frontend): nessuna vulnerabilità nota |
| Indicizzazione | Le pagine private (area professionisti, area clienti, link con token, login) chiedono ai motori di ricerca di non indicizzarle |
| Segnalazioni | `/.well-known/security.txt` con il contatto `info@corenexus.it` (scade il 21/11/2027) |
| IP reale | **Da verificare una volta:** in phpMyAdmin, tabella `audit_log`, colonna dell'IP. Devono comparire IP veri, non `127.0.0.1`; altrimenti i limiti per IP varrebbero per tutti insieme |
| Password del database | **Da fare (CoreNexus):** cambiarle tutte e due e aggiornare le variabili della Python App |

## Test
- **Backend:** 223 test (8 nuovi):
  - dashboard: conteggi, valore, occupazione, clienti nuovi, periodo vuoto, raggruppamento per mese, validazione, ruoli, filtro, isolamento, prenotazioni online;
  - backup: file cifrato senza SQL leggibile, ripristino con le stesse righe, rifiuto del database di produzione, file alterato, chiave sbagliata, permessi, chiave corta, credenziali errate senza file parziali, conservazione dei giorni.
- **Controprova:** 4 protezioni disattivate a turno (permessi del professionista, clienti nuovi solo da appuntamenti non disdetti, primo appuntamento nel periodo, blocco del ripristino in produzione): ognuna rilevata dai test.
- **E2E nel browser:** nuovo `frontend/e2e/flusso-dashboard.cjs` (sezione vuota, riquadri dopo tre appuntamenti, dettagli dell'andamento, cambio di periodo, telefono senza scorrimento orizzontale). Ripassati tutti gli altri 7 flussi.
- **Percorso completo** registrazione → prima prenotazione → promemoria → conferma: lo coprono insieme `flusso-accesso`, `flusso-prenotazione` e `flusso-notifiche`.

## Da fare (CoreNexus)
1. Backup: chiave, file `.cnf`, cron (punto 7 di `07-deploy-netsons.md`), poi la prima prova di ripristino.
2. Controllare l'IP reale nel registro (vedi tabella).
3. Cambiare le due password del database.
4. Informativa privacy e condizioni (P4) prima di aprire a clienti veri.
