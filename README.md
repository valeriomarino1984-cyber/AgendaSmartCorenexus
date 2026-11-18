# CoreNexus Agenda

SaaS multi-tenant per la gestione degli appuntamenti con notifiche automatiche tramite WhatsApp Business Platform (Cloud API ufficiale).

**Stato:** Sprint 1 completato (accesso, studi, ruoli, collaboratori). Prossimo: Sprint 2, sedi, professionisti, prestazioni e clienti. Report: [`docs/08-report-sprint-1.md`](docs/08-report-sprint-1.md).

## Struttura

```
backend/    FastAPI, SQLAlchemy, Alembic, MariaDB/MySQL (Python 3.11+)
frontend/   workspace pnpm; apps/web = Next.js (gestionale + portale pubblico)
infra/      script database per sviluppo e CI
docs/       analisi, schema, piano, decisioni, report di sprint
```

## Documentazione
1. [`docs/01-analisi-e-architettura.md`](docs/01-analisi-e-architettura.md): architettura, ADR, criticità
2. [`docs/02-schema-database.md`](docs/02-schema-database.md): schema PostgreSQL di riferimento
3. [`docs/03-piano-di-sviluppo.md`](docs/03-piano-di-sviluppo.md): sprint e release
4. [`docs/04-decisioni-aperte.md`](docs/04-decisioni-aperte.md): registro decisioni
5. [`docs/05-report-sprint-0.md`](docs/05-report-sprint-0.md): report Sprint 0
6. [`docs/06-design-system.md`](docs/06-design-system.md): design system (condiviso con Presenze)
7. [`docs/07-deploy-netsons.md`](docs/07-deploy-netsons.md): **installazione su Netsons cPanel** e deploy automatico
8. [`docs/08-report-sprint-1.md`](docs/08-report-sprint-1.md): report Sprint 1

## Modello di sicurezza del database (da leggere prima di contribuire)

Il database è MariaDB/MySQL (hosting Netsons), che non ha la Row Level Security. L'isolamento tra studi è garantito così:
- I modelli degli studi ereditano `TenantScoped` (`app/core/models.py`): **ogni** query ORM viene filtrata automaticamente per studio e le scritture verso un altro studio sono rifiutate (`app/core/tenancy.py`).
- Si accede ai dati solo tramite `Database.tenant_session(tenant_id)`. Senza contesto, l'accesso è rifiutato.
- **Vietato** il SQL testuale (`text()`) e l'uso di `Modello.__table__` sulle tabelle degli studi.
- Ogni tabella degli studi ha `UNIQUE (tenant_id, id)` e chiavi esterne composite verso le altre tabelle: un test fa fallire la CI se manca.
- Due utenti del database: `agmigr` (migrazioni) e `agapp` (applicazione, solo SELECT/INSERT/UPDATE/DELETE). L'API non parte con un utente che può modificare lo schema.

## Sviluppo locale

Requisiti: MariaDB 10.6+ (o MySQL 8), Python 3.11+ con [uv](https://docs.astral.sh/uv/), Node 22 con pnpm.

1. Database e utenti di sviluppo (come root di MariaDB):

```bash
mariadb -uroot < infra/db/mariadb-users.sql
```

2. Migrazioni e avvio dell'API (in sviluppo le migrazioni si lanciano a mano; `AUTO_MIGRATE` vale solo per l'avvio su cPanel tramite `passenger_wsgi.py`):

```bash
cd backend && uv sync
```

```bash
MIGRATIONS_DATABASE_URL=mysql+pymysql://agenda_migr:migr_dev@127.0.0.1:3306/agenda_test uv run alembic upgrade head
```

```bash
SIGNUP_OPEN=true EMAIL_BACKEND=file DATABASE_URL=mysql+pymysql://agenda_app:app_dev@127.0.0.1:3306/agenda_test uv run uvicorn app.main:create_app --factory --reload
```

Con `EMAIL_BACKEND=file` le email (conferma, password, inviti) vengono salvate in `backend/var/mail` invece di essere inviate.

3. Frontend:

```bash
cd frontend && pnpm install && pnpm dev
```

In sviluppo `/api` viene inoltrato dal frontend al backend su `http://localhost:8000` (variabile `AGENDA_API_DEV_URL` per cambiarlo).

## Test

I test del backend usano **MariaDB reale**: verificano isolamento tra studi, chiavi composite e privilegi del database. Le variabili sono in `backend/.env.test.example`.

```bash
cd backend && set -a && . ./.env.test && set +a && uv run pytest
```

Controlli di qualità (gli stessi della CI):

```bash
cd backend && uv run ruff check . && uv run ruff format --check . && uv run mypy app tests passenger_wsgi.py
```

```bash
cd frontend && pnpm lint && pnpm typecheck && pnpm build
```

## Test end-to-end (browser)

Il flusso completo di accesso (registrazione, conferma email, impostazioni, invito, ruoli, uscita) si prova con `frontend/e2e/flusso-accesso.cjs`, quello delle anagrafiche (prestazioni, professionisti, sede, clienti e consensi) con `frontend/e2e/flusso-anagrafiche.cjs`, quello dell'agenda (orari, prenotazione, visita online, trascinamento, disdetta) con `frontend/e2e/flusso-agenda.cjs`: le istruzioni sono in testa ai file. Le email vengono scritte su file (`EMAIL_BACKEND=file`) e lette dal test.

## Deploy

Su Netsons cPanel, automatico dopo ogni CI riuscita su `main`: vedi [`docs/07-deploy-netsons.md`](docs/07-deploy-netsons.md).
