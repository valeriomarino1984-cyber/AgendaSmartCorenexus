# Report Sprint 0 – Fondamenta

**Data:** 17/11/2026
**Decisioni applicate:** 2 (stack approvato, auth gestita dal backend), 3 (dominio `agenda.corenexus.it`), 4–5 (un numero WhatsApp per studio), 7 (gli studi pagano Meta direttamente). Vedi `04-decisioni-aperte.md`.

## Completato e verificato

| Area | Cosa | Verifica |
|---|---|---|
| Monorepo | `backend/` (uv), `frontend/` (pnpm workspace, Next.js 16.4 + Tailwind 4), `infra/`, `docs/` | — |
| Configurazione | `pydantic-settings`, segreti solo da env (`SecretStr`, mai nei `repr`/log); in staging e produzione obbligatori https, niente CORS `*` e log JSON | 11 test unitari |
| Ruoli DB | `infra/db/roles.sql`: `corenexus_migrator` (proprietario, non superuser) e `corenexus_app` (no owner, no BYPASSRLS) | Eseguito su PostgreSQL 16 |
| Migrazioni | Alembic async; `0001_baseline`: estensioni, funzione `current_tenant_id()`, privilegi di default per il ruolo app | Test up → down → up; test "una sola head" |
| Infrastruttura RLS | `enable_tenant_rls_sql()` (con rifiuto di identificatori non validi), `Database.tenant_session()` con `SET LOCAL`, controllo che rileva le tabelle con `tenant_id` senza RLS | 10 test di sicurezza (vedi sotto) + 6 unitari |
| Fail-closed all'avvio | L'API non parte se connessa come superuser, con BYPASSRLS o con un ruolo diverso da quello atteso | Test + prova reale con uvicorn |
| Logging | structlog JSON con `request_id` (propagato o generato, con validazione del formato); log di accesso con **template della rotta**, mai valori dei parametri né query string (i token dei link non finiscono nei log) | 5 test di integrazione |
| Errori | Formato unico `{"error": {code, message, request_id}}`; errori 422 senza eco dei valori inviati; errori 500 senza dettagli interni | 3 test |
| Health | `GET /api/v1/health` (liveness), `GET /api/v1/health/ready` (DB + Redis) | Test + prova con curl |
| Sentry | Inizializzato solo se `SENTRY_DSN` è valorizzato, `send_default_pii=False` | — |
| OpenAPI | `/api/docs` fuori dalla produzione, disabilitato in produzione | 2 test |
| Frontend | Layout in italiano, build statica (dal branch `design-system`: font Inter via `next/font`, servito dal nostro dominio) | `pnpm lint`, `pnpm typecheck`, `pnpm build` superati |
| CI | `.github/workflows/ci.yml`: backend (ruff, format, mypy strict, pytest con Postgres e Redis reali) e frontend (lint, typecheck, build) | YAML validato; **non ancora eseguita su GitHub** |

**Risultato:** 40 test superati, ruff e mypy (strict) puliti.

### Test di sicurezza sull'isolamento tenant
- Il tenant A vede solo le proprie righe, e lo stesso vale per B.
- Il contesto tenant non sopravvive tra transazioni sulla **stessa connessione del pool**.
- Non si possono inserire righe con il `tenant_id` di un altro tenant, né spostare righe verso un altro tenant.
- Il ruolo applicativo non è superuser, non ha BYPASSRLS e non può creare tabelle.
- La guardia di schema segnala le tabelle con `tenant_id` senza RLS forzata e senza policy, e oggi lo schema è conforme.

**Controllo di efficacia:** ho reintrodotto di proposito in `current_tenant_id()` il difetto individuato in Fase 1 (cast senza `NULLIF`) e la suite è fallita come atteso. Ripristinato il codice, la suite torna verde.

## Difetti trovati e corretti durante lo sprint
1. **Log con path parziale:** con FastAPI 0.163 i router inclusi espongono il path relativo (`/health` invece di `/api/v1/health`). Il template ora si ricostruisce sostituendo i valori dei parametri con il loro nome. Se un valore non è individuabile (es. parametri `:path` con `/`), il fallback non registra comunque il valore. Il test originale non copriva il caso perché usava una rotta montata direttamente sull'app: aggiunti test con router incluso e con parametro `:path`.

## Non verificato / scelte rimandate
- **docker-compose e Dockerfile non sono stati eseguiti:** Docker non è disponibile in questo ambiente. Lo stesso flusso (ruoli → migrazioni → API) è stato verificato senza container. Va provato al primo avvio su una macchina con Docker.
- **CI non eseguita su GitHub:** il progetto non è ancora in un repository.
- **Celery rimandato allo Sprint 5** (motore notifiche), quando servirà davvero (regola 9: niente dipendenze non necessarie). Redis è già presente.
- **Provider cloud (Decisione 3)** ancora da scegliere: blocca solo `infra/deploy`.

## Problemi aperti
- Il progetto esiste solo in questo ambiente temporaneo: va spostato su un repository Git (GitHub) per non perderlo e per attivare la CI.
- Avviare subito la traccia parallela Meta (P1–P3 in `03-piano-di-sviluppo.md`): verifica aziendale e richiesta Tech Provider.
- Decisione 8 (politica di cancellazione) necessaria entro lo Sprint 4.

## Prossimo passo: Sprint 1
Autenticazione (registrazione con verifica email, login, refresh token ruotati in cookie HttpOnly, logout, `/auth/me`), tabelle `tenants`, `tenant_settings`, `users`, `tenant_users`, `auth_sessions`, `audit_logs`, RBAC owner/professional/secretary, rate limiting sul login, suite di isolamento A/B estesa agli endpoint.
Nota: per la verifica email in Sprint 1 serve un provider email transazionale (UE). Fino alla scelta userò un adapter SMTP generico configurabile, provato in sviluppo con un server SMTP locale.
