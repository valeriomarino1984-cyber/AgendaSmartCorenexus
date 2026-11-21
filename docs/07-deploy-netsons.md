# Installazione su Netsons (cPanel)

L'Agenda gira sullo stesso hosting di Presenze, come **due applicazioni** sul sottodominio `agenda.corenexus.it`:

| Applicazione | cPanel | Cartella | Indirizzo |
|---|---|---|---|
| Sito e area studio (Next.js) | *Setup Node.js App* | `agenda-web` | `https://agenda.corenexus.it` |
| API (FastAPI) | *Setup Python App* | `agenda-api` | `https://agenda.corenexus.it/api` |

Database: **MariaDB/MySQL** del cPanel, con **due utenti**: uno per le migrazioni (tutti i privilegi) e uno per l'applicazione (solo lettura e scrittura dei dati). L'API si rifiuta di partire se l'utente applicativo può modificare lo schema.

Nella guida `UTENTE` è il nome utente cPanel. cPanel antepone `UTENTE_` ai nomi di database e utenti.

---

## 1. Dominio e HTTPS
1. Il sottodominio `agenda.corenexus.it` esiste già.
2. *SSL/TLS Status* → seleziona `agenda.corenexus.it` → **Run AutoSSL**. Senza HTTPS l'accesso e i webhook WhatsApp non funzionano.

## 2. Database
1. *Manage My Databases* (o *MySQL Databases*) → **Crea database**: `agenda` → diventa `UTENTE_agenda`.
2. *phpMyAdmin* → database `UTENTE_agenda` → *Operazioni* → *Codifica caratteri*: **utf8mb4_unicode_ci** → *Esegui*.
   La prima migrazione controlla questo valore e si ferma se è diverso.
3. **Crea due utenti** con password lunghe (almeno 24 caratteri), preferibilmente **solo lettere e numeri**. Se contengono simboli, nelle variabili `DATABASE_URL`/`MIGRATIONS_DATABASE_URL` vanno codificati: `;`→`%3B`, `,`→`%2C`, `@`→`%40`, `?`→`%3F`, `(`→`%28`, `)`→`%29`, `]`→`%5D`, `$`→`%24`, `#`→`%23`, `/`→`%2F`, `:`→`%3A`, `%`→`%25`. La `@` prima di `localhost` resta com'è.
   - `agmigr` → `UTENTE_agmigr`: per le migrazioni.
   - `agapp` → `UTENTE_agapp`: per l'applicazione.
4. **Aggiungi gli utenti al database:**
   - `UTENTE_agmigr` → **TUTTI I PRIVILEGI**.
   - `UTENTE_agapp` → **solo** `SELECT`, `INSERT`, `UPDATE`, `DELETE`. Nessun altro privilegio: con `CREATE`, `ALTER`, `DROP` ecc. l'API non parte, ed è voluto.

## 3. API (Setup Python App)
1. *Setup Python App* → **Create Application**:
   - *Python version*: la più recente disponibile, minimo **3.11**.
   - *Application root*: `agenda-api`
   - *Application URL*: `agenda.corenexus.it` / `api`
   - *Application startup file*: `passenger_wsgi.py`
   - *Application Entry point*: `application`
2. **Variabili d'ambiente** (*Add Variable*):

   | Nome | Valore |
   |---|---|
   | `ENVIRONMENT` | `production` |
   | `DATABASE_URL` | `mysql+pymysql://UTENTE_agapp:PASSWORD@localhost:3306/UTENTE_agenda` |
   | `MIGRATIONS_DATABASE_URL` | `mysql+pymysql://UTENTE_agmigr:PASSWORD@localhost:3306/UTENTE_agenda` |
   | `AUTO_MIGRATE` | `1` |
   | `APP_BASE_URL` | `https://agenda.corenexus.it` |
   | `PUBLIC_BOOKING_BASE_URL` | `https://agenda.corenexus.it/prenota` |
   | `CORS_ORIGINS` | `["https://agenda.corenexus.it"]` |
   | `LOG_JSON` | `true` |
   | `EMAIL_BACKEND` | `smtp` (obbligatorio: senza l'API non parte) |
   | `SMTP_HOST` | es. `mail.corenexus.it` (cPanel → *Account email* → *Configura client*) |
   | `SMTP_PORT` | `465` |
   | `SMTP_SECURITY` | `ssl` (oppure `starttls` con porta `587`) |
   | `SMTP_USERNAME` | es. `no-reply@corenexus.it` |
   | `SMTP_PASSWORD` | password di quella casella |
   | `EMAIL_FROM` | `CoreNexus Agenda <no-reply@corenexus.it>` (stesso indirizzo di `SMTP_USERNAME`) |
   | `SIGNUP_OPEN` | `false` (default). `true` solo per prove o dopo la pubblicazione di condizioni e informativa privacy |
   | `VIDEO_BASE_URL` | facoltativa: `https://meet.jit.si` (default). Indirizzo base delle stanze per le visite online; si cambia per passare a un servizio con server UE o a un Jitsi proprio |
   | `SESSION_IDLE_HOURS` | facoltativa: `1` (default). Ore senza attività dopo cui i professionisti escono; l'area clienti esce dopo 5 minuti |
   | `PLATFORM_SECRET_KEY` | **segreta**, almeno 32 caratteri casuali. Accende l'area piattaforma (`/piattaforma`) e serve a ricavare i codici a 6 cifre. Non va mai cambiata dopo l'attivazione (i codici delle app smetterebbero di funzionare) né scritta in chat |
   | `PLATFORM_BOOTSTRAP_EMAIL` | email di chi fa la prima configurazione dell'area piattaforma. Usata solo finché non esiste nessun account |
   | `CRON_SECRET` | **segreta**, almeno 32 caratteri casuali. Chiave del cron di cPanel che fa partire i promemoria (vedi `13-notifiche-email.md`) |
   | `SENTRY_DSN` | facoltativo, progetto Sentry in regione UE |

   Con `AUTO_MIGRATE=1` le migrazioni partono all'avvio dell'app con l'utente `agmigr`. Subito dopo, l'indirizzo con quelle credenziali viene tolto dalla memoria del processo: il resto dell'applicazione usa solo `agapp`.
3. **File:** *File Manager* → cartella `agenda-api` → elimina i file di esempio creati da cPanel (non la cartella `tmp`) → *Upload* di `agenda-api-cpanel.zip` → *Extract* → elimina lo zip.
   Il pacchetto si crea con `backend/scripts/build-cpanel-api.sh` oppure si scarica dagli artifact del workflow.
4. **Dipendenze:** *Setup Python App* → matita sull'app → *Execute python script*: `install_deps.py` → **Run Script**. Alla fine tutte le righe devono essere `OK`.
   Su Netsons il pulsante *Run Pip Install* può terminare senza installare nulla (verificato il 17/11/2026), per questo si usa lo script incluso nel pacchetto.
   Poi **Restart**.
5. **Verifica:** `https://agenda.corenexus.it/api/v1/health/ready` deve rispondere `{"status":"ok"}`.

## 4. Sito (Setup Node.js App)
1. *Setup Node.js App* → **Create Application**:
   - *Node.js version*: **22.x** (la stessa di Presenze)
   - *Application mode*: `Production`
   - *Application root*: `agenda-web`
   - *Application URL*: `agenda.corenexus.it`
   - *Application startup file*: `server.js`
2. **File:** cartella `agenda-web` → elimina l'eventuale `app.js` di esempio → *Upload* di `agenda-web-cpanel.zip` → *Extract* → elimina lo zip. Per vedere la cartella `.next`: *Settings* → *Show Hidden Files*.
   Il pacchetto si crea con `frontend/scripts/build-cpanel-web.sh`.
3. **Run NPM Install** → **Restart**.
4. **Verifica:** `https://agenda.corenexus.it` mostra la home. `https://agenda.corenexus.it/api/v1/health` deve ancora rispondere dall'API: le due app convivono.

> **Se `/api` viene servito dal sito invece che dall'API** (pagina "non trovata" di Next.js invece del JSON), Passenger su questo server non supporta un'app dentro l'altra. Soluzione: un sottodominio dedicato all'API (es. `api-agenda.corenexus.it`) e un inoltro configurato nel sito. Avvisami e preparo la modifica.

## 5. Aggiornamenti automatici (GitHub Actions)
Il workflow `.github/workflows/deploy-cpanel.yml` parte dopo ogni CI riuscita su `main`:
1. Costruisce i due pacchetti.
2. Verifica le cartelle di destinazione.
3. Carica via FTPS solo i file cambiati e riavvia le app (`tmp/restart.txt`).
4. Controlla che sito e API rispondano.

Configurazione, una volta sola:
1. *Account FTP* → crea **due account dedicati**: `agenda-api@corenexus.it` con directory `agenda-api` e `agenda-web@corenexus.it` con directory `agenda-web`.
   Controlla nella colonna *Directory* che siano `/home/UTENTE/agenda-api` e `/home/UTENTE/agenda-web`, **non** `public_html` né la cartella di Presenze.
2. *File Manager* → crea un **file vuoto** `.agenda-api-deploy-target` in `agenda-api` e `.agenda-web-deploy-target` in `agenda-web`. Senza questi file il deploy si ferma senza toccare nulla.
3. GitHub → repository → *Settings* → *Secrets and variables* → *Actions* → *New repository secret*:
   `FTP_SERVER` (lo stesso di Presenze), `FTP_API_USERNAME`, `FTP_API_PASSWORD`, `FTP_WEB_USERNAME`, `FTP_WEB_PASSWORD`.
4. GitHub → *Actions* → *Deploy cPanel* → **Run workflow** per il primo rilascio.

Se cambiano le dipendenze il workflow lo segnala con un avviso: in cPanel esegui `install_deps.py` con *Execute python script* (API) oppure *Run NPM Install* (sito), poi *Restart*.

## 6. Se non parte
- **Log:** file `stderr.log` nelle cartelle `agenda-api` e `agenda-web`.
- *"l'utente applicativo ha privilegi sullo schema"*: `UTENTE_agapp` ha privilegi in più. Lasciagli solo SELECT, INSERT, UPDATE, DELETE.
- *"Il database usa il set di caratteri …"*: ripeti il punto 2.2 (utf8mb4).
- *"l'URL del database deve iniziare con mysql+pymysql://"*: controlla `DATABASE_URL` e `MIGRATIONS_DATABASE_URL`.
- *Access denied*: password errata (simboli non codificati?), oppure utente non aggiunto al database.
- *ModuleNotFoundError*: dipendenze non installate, esegui `install_deps.py` (punto 3.4).
- *"schema del database alla versione …"*: le migrazioni non sono state applicate. Verifica `AUTO_MIGRATE=1` e `MIGRATIONS_DATABASE_URL`, poi *Restart*.
- Nel log può comparire `auto_migrate_skipped`: è normale quando Passenger ricarica l'app dopo che le migrazioni sono già state applicate.

## 7. Backup cifrati del database (da fare una volta)
Ogni notte uno script salva il database **cifrato** (AES-256), controlla che il file si apra e sia completo, e tiene gli ultimi 14 giorni. Gli script arrivano con il deploy in `agenda-api/ops/`.

1. **Chiave di cifratura.** Genera con il password manager una frase casuale di **almeno 32 caratteri**. Salvala nel password manager: **senza questa chiave i backup non si possono aprire**.
2. *File Manager* → cartella home (`/home/UTENTE`, **non** `public_html`) → *+ File*:
   - `.agenda-backup.key`: incolla la chiave, salva.
   - `.agenda-backup.cnf`, con l'utente delle migrazioni (ha i permessi di lettura completi):
     ```
     [client]
     user=UTENTE_agmigr
     password=la-password-dell-utente
     host=localhost
     database=UTENTE_agenda
     ```
   - Su entrambi: tasto destro → *Change Permissions* → **600** (solo lettura e scrittura del proprietario). Lo script si rifiuta di partire con permessi più larghi.
3. *Cron Jobs* → *Add New Cron Job*, ogni notte alle 3:17:
   ```
   17 3 * * * bash $HOME/agenda-api/ops/backup-db.sh >> $HOME/agenda-backup.log 2>&1
   ```
4. Il mattino dopo, in `agenda-backup.log` deve esserci `Backup verificato: …`. I file sono in `/home/UTENTE/agenda-backup/` (`agenda-AAAAMMGG-HHMMSS.sql.gz.enc` e la sua somma `.sha256`).
5. **Copia fuori dal server**, almeno una volta a settimana: scarica l'ultimo `.enc` dal *File Manager* e conservalo altrove (è cifrato, si può tenere anche su un disco o un cloud personale).

### Prova di ripristino (una volta, poi ogni 3 mesi)
1. *Database MySQL* → crea un database vuoto `UTENTE_agprova` e aggiungici `UTENTE_agmigr` con *Tutti i privilegi*.
2. *Terminale* di cPanel:
   ```
   bash ~/agenda-api/ops/restore-db.sh ~/agenda-backup/<ultimo-file>.sql.gz.enc UTENTE_agprova
   ```
3. Deve stampare la versione dello schema e il numero di righe di studi, utenti, clienti e appuntamenti: confrontali con il sito.
4. Svuota o elimina `UTENTE_agprova` dopo la prova.

Lo script **non** scrive sul database di produzione, a meno di aggiungere `--forza`: serve solo per un vero ripristino d'emergenza, a sito fermo (*Stop App* su `agenda-api`).

I backup completi di cPanel (database e cartelle) restano attivi come seconda copia.

## Email (dallo Sprint 1)
Le email di conferma, password dimenticata e inviti partono via SMTP. La casella più semplice è un account email del cPanel (es. `no-reply@corenexus.it`, *Account email* → *Crea*); i parametri sono in *Configura client email*. Per una buona consegna verifica in cPanel → *Email Deliverability* che SPF e DKIM del dominio siano a posto.

## Registrazione degli studi
Con `SIGNUP_OPEN=false` (default) la pagina `/registrati` mostra "registrazione chiusa". Per le prove interne impostala a `true`, crea lo studio e poi riportala a `false` (*Restart* dopo ogni modifica). Va aperta al pubblico solo quando saranno pubblicate condizioni del servizio e informativa privacy (punto P4 del piano: revisione legale).
