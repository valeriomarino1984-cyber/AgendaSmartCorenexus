# CoreNexus Agenda

SaaS multi-tenant per la gestione degli appuntamenti con notifiche automatiche tramite WhatsApp Business Platform (Cloud API ufficiale).

**Stato:** Sprint 0 (fondamenta) completato. Prossimo: Sprint 1, autenticazione e tenant. Report: [`docs/05-report-sprint-0.md`](docs/05-report-sprint-0.md).

## Struttura

```
backend/    FastAPI, SQLAlchemy async, Alembic (Python 3.12+)
frontend/   workspace pnpm; apps/web = Next.js (gestionale + portale pubblico)
infra/      ruoli database, Dockerfile
docs/       analisi, schema, piano, decisioni, report di sprint
```

## Documentazione
1. [`docs/01-analisi-e-architettura.md`](docs/01-analisi-e-architettura.md): architettura, ADR, criticità
2. [`docs/02-schema-database.md`](docs/02-schema-database.md): schema PostgreSQL di riferimento
3. [`docs/03-piano-di-sviluppo.md`](docs/03-piano-di-sviluppo.md): sprint e release
4. [`docs/04-decisioni-aperte.md`](docs/04-decisioni-aperte.md): registro decisioni
5. [`docs/05-report-sprint-0.md`](docs/05-report-sprint-0.md): report Sprint 0
6. [`docs/06-design-system.md`](docs/06-design-system.md): design system (condiviso con Presenze)

## Modello di sicurezza del database (da leggere prima di contribuire)

- **`corenexus_migrator`** è proprietario dello schema ed è usato **solo** da Alembic.
- **`corenexus_app`** è il ruolo con cui gira l'applicazione: non è proprietario, non ha `BYPASSRLS` e non può creare tabelle. Se l'API viene avviata con un ruolo diverso, si rifiuta di partire.
- Ogni tabella con colonna `tenant_id` deve chiamare `enable_tenant_rls_sql()` (`app/core/rls.py`) nella sua migrazione. Se manca, un test fa fallire la CI.
- Il codice accede ai dati tenant solo tramite `Database.tenant_session(tenant_id)`.

## Sviluppo locale

### Con Docker (PostgreSQL, Redis, migrazioni, API)

```bash
cp .env.example .env
```

Impostare le tre password nel file `.env`, poi:

```bash
docker compose up --build
```

L'API risponde su `http://localhost:8000/api/v1/health`, la documentazione OpenAPI su `http://localhost:8000/api/docs`.

### Senza Docker

Requisiti: PostgreSQL 16, Redis 7, Python 3.12+ con [uv](https://docs.astral.sh/uv/), Node 22 con pnpm.

1. Creare il database e i ruoli (come superuser PostgreSQL):

```bash
createdb corenexus
```

```bash
psql -d corenexus -v migrator_password=<pw> -v app_password=<pw> -v dbname=corenexus -f infra/db/roles.sql
```

2. Applicare le migrazioni e avviare l'API:

```bash
cd backend && uv sync
```

```bash
MIGRATIONS_DATABASE_URL=postgresql+asyncpg://corenexus_migrator:<pw>@localhost:5432/corenexus uv run alembic upgrade head
```

```bash
DATABASE_URL=postgresql+asyncpg://corenexus_app:<pw>@localhost:5432/corenexus uv run uvicorn app.main:create_app --factory --reload
```

3. Frontend:

```bash
cd frontend && pnpm install && pnpm dev
```

## Test

I test del backend usano **PostgreSQL e Redis reali**, non SQLite né mock, perché verificano RLS e vincoli del database. Serve un database dedicato ai test con i ruoli creati da `infra/db/roles.sql`. Le variabili sono in `backend/.env.test.example`.

```bash
cd backend && set -a && . ./.env.test && set +a && uv run pytest
```

Controlli di qualità (gli stessi della CI):

```bash
cd backend && uv run ruff check . && uv run ruff format --check . && uv run mypy app tests
```

```bash
cd frontend && pnpm lint && pnpm typecheck && pnpm build
```
