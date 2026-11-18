# CoreNexus Agenda – Fase 1: Analisi e architettura proposta

**Riferimento:** Specifica funzionale v1.0 (Novembre 2026)
**Stato:** APPROVATA con modifiche: **hosting Netsons cPanel con MariaDB/MySQL** (Decisione 3). Le parti su PostgreSQL, RLS, Redis e Celery sono sostituite come descritto al **§7**.

---

## 1. Sintesi dell'analisi

La specifica è solida e coerente nell'impostazione (multi-tenant, WhatsApp ufficiale, roadmap incrementale). Prima di scrivere codice ho individuato tre aree in cui una decisione sbagliata costerebbe molto in seguito:

1. **Modello WhatsApp (chi possiede il numero e chi paga Meta).** Condiziona il wallet, il listino dei pacchetti e i tempi di go-live. È il percorso critico del progetto (vedi §5.1).
2. **Isolamento tenant e prevenzione doppie prenotazioni.** Vanno risolti a livello di database fin dal primo giorno, non solo nel codice applicativo (vedi §3.3 e §3.4).
3. **Scheduling delle notifiche.** Le notifiche programmate a 24/48 ore non devono vivere solo nella coda Redis (vedi §3.5).

---

## 2. Architettura logica

```
                    ┌──────────────────────────────┐
  Professionisti ──►│  Next.js – App gestionale     │
  Segreteria        │  (dashboard, agenda, clienti) │──┐
                    └──────────────────────────────┘  │
                    ┌──────────────────────────────┐  │  HTTPS / REST /api/v1
  Clienti finali ──►│  Next.js – Portale pubblico   │──┤
                    │  prenota.…/{slug}, /a/{token} │  │
                    └──────────────────────────────┘  │
                    ┌──────────────────────────────┐  │
  Super Admin ─────►│  Next.js – Admin (Release 4)  │──┤
                    └──────────────────────────────┘  ▼
                                          ┌────────────────────────┐
                                          │   FastAPI (API core)    │
                                          │  moduli di dominio      │
                                          │  RBAC + tenant context  │
                                          └──────┬──────────┬──────┘
                                                 │          │ outbox
                                       ┌─────────▼──┐   ┌───▼──────────────┐
                                       │ PostgreSQL │◄──┤ Celery beat       │
                                       │ + RLS      │   │ (dispatcher 1/min)│
                                       └─────────▲──┘   └───┬──────────────┘
                                                 │          │ Redis (broker)
                                                 │   ┌──────▼──────────────┐
                                                 └───┤ Celery workers       │
                                                     │ • notifications      │
                                                     │ • whatsapp (rate-lim)│
                                                     │ • email              │
                                                     └──────┬──────────────┘
                                                            │
                         ┌──────────────────────────────────┼──────────────┐
                         ▼                                  ▼              ▼
                 Meta WhatsApp Cloud API          Provider email     Stripe (R4)
                         │ webhook firmati (X-Hub-Signature-256)
                         └──────────► FastAPI /webhooks/whatsapp ─► coda ─► worker
```

### Principi

- **Monolite modulare**, non microservizi. Un solo backend FastAPI con moduli separati e confini netti, più i worker Celery che condividono lo stesso codice di dominio. Per un MVP con 100 tenant obiettivo, i microservizi aggiungerebbero costi operativi senza benefici. Il "WhatsApp Service" e il "Motore notifiche" richiesti dalla specifica sono **moduli indipendenti con interfacce proprie** (porte/adapter): si possono estrarre in servizi separati in futuro senza riscrivere il dominio.
- **Provider sostituibili**: ogni integrazione esterna (WhatsApp, email, pagamenti, SMS) è dietro un'interfaccia (`MessagingProvider`, `EmailProvider`, `PaymentProvider`). Gli adapter concreti stanno in `integrations/`.
- **Database come fonte di verità** per agenda, notifiche e consumi. Redis è solo un trasporto: se si perde Redis non si perdono notifiche.
- **Tutto in UTC** nel database (`timestamptz`), con il fuso della sede (`locations.timezone`, default `Europe/Rome`) usato per disponibilità, rendering e testi dei messaggi. Il cambio dell'ora legale va coperto con test specifici.

---

## 3. Decisioni architetturali proposte (ADR sintetici)

### 3.1 Stack

Confermo lo stack della specifica, con queste precisazioni:

| Area | Scelta proposta | Motivazione |
|---|---|---|
| Backend | Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2 (async), Alembic | Allineato alla specifica; Alembic copre la regola "nessuna modifica senza migrazioni" |
| Worker | Celery 5 + Redis 7 | Richiesto dalla specifica; vedi §3.5 sull'uso corretto. Introdotto nello Sprint 5 |
| DB | PostgreSQL 16 con estensioni `btree_gist`, `citext`, `pgcrypto` | Vincoli di esclusione anti-overlap, email case-insensitive |
| Frontend | Next.js (App Router), TypeScript, Tailwind CSS, TanStack Query, React Hook Form + Zod | Validazione condivisa lato client; il server resta l'unica fonte di verità |
| Calendario UI | FullCalendar (licenza standard MIT) – da valutare contro la versione Premium per la vista "per risorsa/stanza" | La vista per stanza/professionista affiancati richiede `resource-timeline`, che è **Premium a pagamento** |
| API client | Generato dall'OpenAPI di FastAPI (`openapi-typescript`) | Contratto unico, niente tipi duplicati a mano |
| Test | pytest, pytest-asyncio, testcontainers (Postgres reale), Playwright per E2E | I test su isolamento e concorrenza devono girare su Postgres vero, non su SQLite |
| Osservabilità | Log JSON strutturati (structlog) con `request_id`/`tenant_id`, Sentry (EU), metriche Prometheus | Criteri MVP 17–18 |

### 3.2 Autenticazione

**Proposta:** autenticazione gestita dal backend FastAPI (password con Argon2id, access token JWT a breve scadenza di 15 min + refresh token ruotato in cookie `HttpOnly; Secure; SameSite=Lax`), senza Supabase Auth.

Motivazione: con Supabase Auth + FastAPI che accede al DB con un ruolo di servizio, la RLS di Supabase viene **bypassata** e si finisce per mantenere due modelli di sicurezza. Se si sceglie Supabase, lo si può usare solo come Postgres gestito (in regione UE) senza perdere nulla. Questa scelta resta da confermare (Decisione 2–3).

### 3.3 Isolamento multi-tenant (difesa in profondità)

Tre livelli, tutti obbligatori:

1. **Applicativo:** ogni richiesta autenticata risolve un `TenantContext` (tenant + ruolo + permessi) da un'unica dipendenza FastAPI. I repository ricevono sempre il contesto; non esistono query "senza tenant".
2. **Database – RLS:** l'applicazione si connette con un ruolo **non proprietario e senza `BYPASSRLS`**. All'inizio di ogni transazione esegue `SET LOCAL app.tenant_id = '<uuid>'`. Ogni tabella tenant-specific ha `ENABLE` + `FORCE ROW LEVEL SECURITY` e una policy `tenant_id = current_tenant_id()`: la funzione, definita nella migrazione `0001_baseline`, legge `app.tenant_id` con `NULLIF`. Se il codice dimentica un filtro, il DB restituisce zero righe invece di dati altrui.
3. **Integrità referenziale per tenant:** chiavi esterne composite `(tenant_id, id)`, così un appuntamento del tenant A non può puntare a un cliente del tenant B nemmeno per errore.

Contesti speciali:
- **Portale pubblico:** lo slug viene risolto lato server in `tenant_id`, poi si applica lo stesso contesto.
- **Webhook WhatsApp:** il `phone_number_id` del payload viene risolto in tenant tramite una tabella di lookup senza RLS e in sola lettura.
- **Super Admin:** ruolo DB separato, endpoint separati, ogni accesso ai dati di un tenant scritto in `audit_logs` con motivazione.

### 3.4 Prevenzione doppie prenotazioni

Il controllo nel codice ("lo slot è libero?") non basta con richieste concorrenti. Proposta:

- **Vincolo di esclusione PostgreSQL** su `appointments`:
  `EXCLUDE USING gist (professional_id WITH =, occupied WITH &&) WHERE (status IN ('pending','confirmed'))`
  dove `occupied = tstzrange(start_at, buffer_end_at)` (colonna generata; `buffer_end_at` = fine + tempo di preparazione). Lo stesso per `room_id` quando valorizzato.
- Il backend intercetta la violazione (`23P01 exclusion_violation`) e risponde `409 Conflict – slot non più disponibile`.
- Il calcolo delle disponibilità resta in codice (orari, eccezioni, festività, durata, buffer), ma la garanzia finale è il vincolo del DB.
- Le richieste di prenotazione pubbliche accettano un header `Idempotency-Key` per evitare doppie creazioni da doppio click o retry di rete.

Lo stesso meccanismo copre la lista d'attesa (Release 2): "il primo che accetta" è chi riesce a inserire la riga.

### 3.5 Motore notifiche: outbox su DB + dispatcher

**Da evitare:** programmare il promemoria a 48 ore come task Celery con `eta`/`countdown`. Con il broker Redis, i task con ETA oltre il `visibility_timeout` vengono riconsegnati (invii duplicati) e l'annullamento di un task già in coda non è affidabile.

**Proposta:**
1. Alla creazione/modifica di un appuntamento, **nella stessa transazione** si scrivono le righe `notification_jobs` (`status='scheduled'`, `scheduled_at`, `idempotency_key`).
2. Un task periodico (Celery beat, ogni minuto) seleziona i job scaduti con `SELECT … FOR UPDATE SKIP LOCKED`, li passa a `pending` e li accoda.
3. Il worker, **prima di inviare, ricontrolla** stato appuntamento, consenso del cliente, crediti e stato della connessione WhatsApp. Se qualcosa non va: `cancelled` o `failed` con motivo.
4. Spostamento/cancellazione: una sola `UPDATE notification_jobs SET status='cancelled' WHERE appointment_id=… AND status IN ('scheduled','pending')` nella stessa transazione della modifica.
5. `idempotency_key = hash(appointment_id, event_type, start_at)`: indice univoco. Dopo uno spostamento la chiave cambia, quindi il nuovo promemoria è legittimo e il vecchio non può essere reinviato.
6. Retry con backoff esponenziale solo sugli errori **transitori** (5xx, rate limit 130429/131056, timeout). Gli errori permanenti (template non approvato, numero non WhatsApp, token revocato) vanno subito in `failed` e sono visibili in dashboard. Dopo N tentativi: dead letter (`status='failed'`, `dead_lettered=true`) e reinvio manuale da UI.
7. Webhook di stato (`sent/delivered/read/failed`): salvati grezzi in `webhook_events` con deduplica su `(provider_message_id, status)`, poi elaborati in modo asincrono. Lo stato non può "tornare indietro" (`read` non diventa `delivered` se i webhook arrivano fuori ordine).

### 3.6 Link sicuri di gestione appuntamento

- Token casuale da 256 bit (`secrets.token_urlsafe(32)`), **salvato solo come hash SHA-256** in `appointment_access_tokens`.
- Ogni token ha uno scope (`view`, `confirm`, `reschedule`, `cancel`) e una scadenza (default: fine appuntamento + 24 h), è revocabile e viene ruotato dopo uno spostamento.
- URL: `https://prenota.<dominio>/a/<token>`: nessun dato personale, nessun ID sequenziale.
- Rate limiting per IP sulle rotte pubbliche e nessuna differenza osservabile tra "token inesistente" e "token scaduto".
- Il token va nel suffisso dinamico dei pulsanti URL dei template WhatsApp.

### 3.7 Pulsanti WhatsApp

Proposta per il template "Promemoria 24 h":
- **CONFERMA** → pulsante *quick reply* con payload `confirm:<job_ref>`. Arriva come webhook e conferma senza uscire da WhatsApp. Effetto collaterale utile: apre la finestra di assistenza di 24 h, quindi il messaggio di ringraziamento successivo può essere un messaggio di servizio.
- **SPOSTA** e **DISDICI** → pulsanti URL con suffisso dinamico (token firmato) verso il portale.
- WhatsApp Flows: rimandati a dopo l'MVP (Release 2+), come indicato nella specifica.

Il payload del quick reply non contiene dati personali e viene validato lato server (job esistente, tenant coerente con il `phone_number_id`, numero mittente uguale a quello del cliente).

---

## 4. Struttura delle directory

```
corenexus-agenda/
├── README.md
├── docs/                         # specifica, ADR, schema, piano, report di fase
├── docker-compose.yml            # postgres, redis, api, worker, beat, web (solo sviluppo)
├── .env.example                  # solo nomi delle variabili, nessun valore reale
├── backend/
│   ├── pyproject.toml
│   ├── alembic.ini
│   ├── migrations/               # Alembic: unica via per modificare lo schema
│   ├── app/
│   │   ├── main.py               # app FastAPI, router v1, middleware
│   │   ├── core/
│   │   │   ├── config.py         # pydantic-settings, tutti i segreti da env
│   │   │   ├── db.py             # engine, sessione, SET LOCAL app.tenant_id
│   │   │   ├── security.py       # hashing, JWT, cifratura token (envelope/KMS)
│   │   │   ├── tenancy.py        # TenantContext, dipendenze FastAPI
│   │   │   ├── rbac.py           # ruoli, permessi, guard
│   │   │   ├── logging.py        # structlog JSON, request_id
│   │   │   ├── errors.py         # eccezioni di dominio → risposte HTTP
│   │   │   └── ratelimit.py
│   │   ├── modules/              # un package per contesto di dominio
│   │   │   ├── auth/             #   ogni modulo: models, schemas, repository,
│   │   │   ├── tenants/          #   service, router, tests locali se utili
│   │   │   ├── users/
│   │   │   ├── professionals/
│   │   │   ├── locations/        # sedi e stanze (schema da R1, UI da R3)
│   │   │   ├── services/         # catalogo prestazioni
│   │   │   ├── clients/          # anagrafica + consensi
│   │   │   ├── availability/     # orari, eccezioni, festività, motore slot
│   │   │   ├── appointments/     # agenda, stati, eventi, anti-overlap
│   │   │   ├── public_booking/   # portale per slug
│   │   │   ├── self_service/     # link token: conferma/sposta/disdici
│   │   │   ├── notifications/    # job, template, dispatcher, stati
│   │   │   ├── whatsapp/         # account tenant, template, webhook, usage
│   │   │   ├── email/
│   │   │   ├── usage/            # contatori e consumi (wallet in R2/R4)
│   │   │   ├── dashboard/
│   │   │   ├── audit/
│   │   │   ├── billing/          # R4
│   │   │   └── admin/            # R4, Super Admin
│   │   ├── integrations/         # adapter verso l'esterno, dietro interfacce
│   │   │   ├── whatsapp_cloud/   # client Graph API, firma webhook, mappatura errori
│   │   │   ├── email_provider/
│   │   │   └── stripe/           # R4
│   │   └── workers/
│   │       ├── celery_app.py
│   │       ├── beat_schedule.py
│   │       └── tasks/            # dispatch, send_whatsapp, send_email, process_webhook
│   └── tests/
│       ├── unit/
│       ├── integration/          # Postgres reale via testcontainers
│       ├── security/             # isolamento tenant, RBAC, token pubblici
│       └── concurrency/          # doppia prenotazione, lista d'attesa
├── frontend/
│   ├── package.json              # workspace pnpm
│   ├── apps/
│   │   ├── web/                  # gestionale + portale pubblico (route group separati)
│   │   │   └── app/
│   │   │       ├── (auth)/
│   │   │       ├── (dashboard)/  # dashboard, agenda, clienti, prestazioni, …
│   │   │       ├── prenota/[slug]/
│   │   │       └── a/[token]/    # gestione appuntamento da link
│   │   └── admin/                # Super Admin, deploy separato (R4)
│   ├── packages/
│   │   ├── api-client/           # generato da OpenAPI
│   │   ├── ui/                   # componenti condivisi (Tailwind)
│   │   └── i18n/                 # testi IT; struttura pronta per altre lingue
│   └── e2e/                      # Playwright
└── infra/
    ├── docker/                   # Dockerfile api, worker, web
    └── deploy/                   # IaC/manifest secondo l'hosting scelto
```

---

## 5. Criticità individuate

### 5.1 WhatsApp – percorso critico (ALTA)

1. **Embedded Signup richiede che CoreNexus sia un Tech Provider Meta.** Servono una Meta App, la verifica aziendale di CoreNexus su Meta Business Manager, l'App Review per i permessi `whatsapp_business_management` e `whatsapp_business_messaging` e la configurazione di Embedded Signup. Ci vogliono **settimane** e i tempi non dipendono da noi: va avviato **subito**, in parallelo allo sviluppo.
2. **Chi paga Meta condiziona il wallet.** Come Tech Provider, di norma ogni tenant possiede la propria WABA e **inserisce il proprio metodo di pagamento su Meta**: Meta fattura direttamente lo studio. In questo caso rivendere "pacchetti di messaggi" (§10.3) sarebbe un doppio addebito. Per rivendere i messaggi CoreNexus deve diventare **Solution Partner** (con linea di credito condivisa) oppure appoggiarsi a un BSP. **Questa è la decisione più importante del progetto** (Decisione 5 e 7). Alternativa possibile: i crediti CoreNexus misurano un "diritto d'uso del servizio di automazione" e Meta fattura a parte. Va però chiarito commercialmente.
3. **Listino Meta per messaggio.** Dal luglio 2025 Meta fattura per singolo messaggio template consegnato, con prezzo che dipende da categoria e Paese. I template *utility* inviati dentro una finestra di assistenza aperta sono gratuiti. Il dato di costo reale arriva dal webhook (`pricing`) e va salvato per singolo messaggio (`whatsapp_usage.actual_cost`), come la specifica già prevede. Il listino va verificato sulla documentazione Meta in vigore al momento dell'implementazione.
4. **Il numero dello studio.** Un numero già attivo sull'app WhatsApp Business può essere collegato alla Cloud API in modalità *coexistence*, tramite Embedded Signup, con alcune limitazioni. In alternativa serve un numero nuovo dedicato. Va deciso come proporlo ai clienti (Decisione 4–5) e la disponibilità per l'Italia va verificata.
5. **Template per WABA.** I template appartengono alla WABA del tenant: a ogni onboarding vanno creati via API e attendere l'approvazione. L'evento "Prenotazione creata" va classificato come *utility*. Il rischio è che Meta riclassifichi come *marketing* template con testo promozionale: i testi vanno tenuti strettamente transazionali.
6. **Limiti di invio e qualità.** I nuovi numeri partono con limiti bassi sui messaggi avviati dall'azienda (nell'ordine di 250 destinatari/24 h) e un rating di qualità basso può bloccarli. Il worker deve rispettare i limiti e la dashboard deve mostrare lo stato di qualità.
7. **Fallback obbligatorio.** Se il tenant non ha ancora completato l'onboarding WhatsApp, o il cliente non ha dato il consenso, le notifiche devono andare via **email**. Per questo l'email fa parte dell'MVP.

### 5.2 GDPR e dati sanitari (ALTA)

- Per psicologi, psicoterapeuti, fisioterapisti e simili, **il solo fatto di avere un appuntamento** può essere un dato relativo alla salute (art. 9 GDPR), anche senza alcuna cartella clinica. Ne seguono queste misure:
  - nome mittente e testi WhatsApp/email configurabili in forma **neutra** (es. "Studio R." invece di "Studio di Psicoterapia Rossi"). Va aggiunto un flag `neutral_messaging` a livello tenant;
  - il campo `notes` degli appuntamenti va dichiarato in UI come "nota amministrativa" e, con il flag attivo, **non deve mai finire nei messaggi**;
  - è opportuno cifrare a livello applicativo almeno le note.
- **Trasferimento extra-SEE:** Meta tratta i messaggi come responsabile/sub-responsabile. Vanno valutati con il legale la base giuridica, l'eventuale DPIA e l'opzione di *local storage* UE della Cloud API, se disponibile.
- CoreNexus è **responsabile del trattamento** per conto degli studi: serve un DPA standard da far accettare in fase di registrazione, insieme all'elenco dei sub-responsabili (hosting, email, Meta, Stripe, Sentry).
- I consensi WhatsApp ed email vanno storicizzati (`client_consent_events`: chi, quando, come, testo informativa), non salvati solo come booleano. La revoca (anche con "STOP" in chat) blocca subito le notifiche future.

### 5.3 Incoerenze o punti della specifica da chiarire (MEDIA)

| # | Punto | Osservazione | Proposta |
|---|---|---|---|
| a | Crediti WhatsApp in R2/R4, ma criterio MVP 14 "consumi registrati" | Non c'è conflitto, ma va reso esplicito | MVP: registrare consumi e costi per messaggio e mostrare il contatore. Wallet e acquisto pacchetti in R2/R4 |
| b | Limite "100 notifiche" del piano Start in MVP | Senza billing (R4) non c'è un piano da applicare | MVP: limiti configurabili per tenant a mano dal DB/admin, applicati dal worker |
| c | Multi-sede/stanze in R3, ma le tabelle `locations`/`rooms` sono già nello schema | Corretto prevederle subito | Ogni tenant nasce con una sede di default; UI multi-sede in R3 |
| d | "Appuntamenti mancati" (no-show) in dashboard | Manca lo stato nel modello | Aggiungere lo stato `no_show` all'appuntamento |
| e | Lista d'attesa e Google Calendar nel piano PRO | Sono funzioni R2: i piani commerciali non saranno vendibili per intero prima di R2 | Allineare il listino alla roadmap al lancio |
| f | Evento 4 "Conferma" | Se arriva via quick reply è un messaggio di servizio (gratuito, dentro la finestra 24 h); se arriva da link web serve un template | Gestire entrambi i casi |
| g | "Data di nascita" in anagrafica | Non serve per gli appuntamenti: è un dato da minimizzare | Facoltativo e nascondibile da impostazioni |
| h | Trial 14 giorni in R4, ma "registrazione autonoma" in MVP | Durante l'MVP i tenant sono di fatto in trial perpetuo | Stato `trial` con scadenza configurabile già dall'MVP, senza pagamento |

### 5.4 Tecniche (MEDIA)

- **Vista calendario per risorse:** la vista "per professionista/stanza" affiancata richiede FullCalendar Premium (licenza commerciale) o un componente sviluppato su misura. Serve una decisione di budget prima di R3.
- **Fusi orari e ora legale:** i promemoria "48 h prima" si calcolano in UTC, i testi usano l'ora locale della sede. Servono test sui giorni di cambio ora.
- **Ricorrenze (R2):** gli appuntamenti ricorrenti vanno materializzati come singole righe, non calcolati al volo, così il vincolo anti-overlap e le notifiche funzionano senza casi speciali.
- **Cifratura token WhatsApp:** cifratura envelope con chiave master in un KMS/secret manager dell'hosting, mai nel DB né nel repository.
- **Ambienti:** servono almeno `dev`, `staging` (con un numero WhatsApp di test Meta reale) e `prod`. Per i test automatici serve un adapter WhatsApp fittizio **attivabile solo in ambiente test**: la configurazione di produzione lo rifiuta all'avvio (regola inderogabile 1).

---

## 6. Dipendenze principali

**Backend:** fastapi, uvicorn, pydantic, pydantic-settings, sqlalchemy[asyncio], asyncpg, alembic, celery, redis, httpx, argon2-cffi, pyjwt, cryptography, structlog, sentry-sdk, phonenumbers (normalizzazione E.164, indispensabile per WhatsApp), python-dateutil/zoneinfo (stdlib), prometheus-client.
**Test backend:** pytest, pytest-asyncio, testcontainers, respx (mock HTTP verso Meta nei test), factory-boy, freezegun/time-machine.
**Frontend:** next, react, typescript, tailwindcss, @tanstack/react-query, react-hook-form, zod, @fullcalendar/*, date-fns + date-fns-tz, openapi-typescript.
**Test frontend:** vitest, @testing-library/react, playwright.
**Esterni:** Meta WhatsApp Cloud API (Graph API, versione fissata in config), provider email transazionale UE, Stripe (R4).

Nessuna dipendenza è stata ancora installata: le versioni esatte verranno fissate nei lockfile all'avvio della Fase 2.

---

## 7. Adattamento a Netsons cPanel (Decisione 3, 17/11/2026)

L'hosting scelto non offre PostgreSQL, Redis né processi sempre attivi. Le scelte dei §3.3–3.5 cambiano così:

| Area | Progetto originale | Su Netsons cPanel | Verifica |
|---|---|---|---|
| Database | PostgreSQL 16 | MariaDB/MySQL del cPanel, InnoDB, utf8mb4 | Migrazione baseline che controlla charset e motore |
| Isolamento tra studi | RLS + ruolo senza BYPASSRLS | `app/core/tenancy.py`: filtro ORM automatico su SELECT/UPDATE/DELETE (anche conteggi, sottoquery, EXISTS), controllo delle scritture prima del flush, rifiuto senza contesto tenant, rifiuto delle query Core su tabelle degli studi | 17 test di sicurezza; controprova con filtro disattivato: 7 falliscono |
| Seconda barriera nel DB | RLS | Chiavi esterne composite `(tenant_id, id)` + utente applicativo con soli SELECT/INSERT/UPDATE/DELETE (l'API non parte altrimenti) | Test FK cross-tenant, test privilegi, guardia di schema in CI |
| Doppie prenotazioni | Vincolo di esclusione GiST | Lock `SELECT … FOR UPDATE` sul professionista (e sulla stanza) nella transazione di prenotazione, poi controllo di sovrapposizione | Test di concorrenza nello Sprint 3 |
| Code e scheduler | Celery + Redis + beat | Outbox `notification_jobs` nel DB + cron di cPanel che chiama `/api/v1/internal/cron` con chiave segreta | Sprint 5 |
| Rate limiting | Redis | Tabella nel database | Sprint 1 |
| Avvio | uvicorn | Passenger (WSGI) → a2wsgi → FastAPI; migrazioni all'avvio con lock `GET_LOCK` | Test end-to-end del percorso Passenger; simulazione di deploy su database vuoto |

**Rischio accettato:** l'isolamento poggia sul codice applicativo più le chiavi composite, non su una policy del database. Per compensare:
1. ogni nuovo endpoint deve avere il test A/B di isolamento (Definition of Done);
2. il SQL testuale sulle tabelle degli studi è vietato;
3. la guardia di schema fa fallire la CI se una tabella con `tenant_id` non è mappata come `TenantScoped` o non ha la chiave `(tenant_id, id)`.
