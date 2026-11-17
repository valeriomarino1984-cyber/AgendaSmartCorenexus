# CoreNexus Agenda – Schema database proposto

**Stato:** BOZZA. Sarà implementato esclusivamente tramite migrazioni Alembic. Il DDL qui sotto è di riferimento progettuale, non da eseguire a mano.

Legenda: **[R1]** MVP · **[R2]** Automazione · **[R3]** Multi-studio · **[R4]** Commercializzazione · **(+)** tabella o colonna aggiunta rispetto alla specifica, con motivazione.

## Convenzioni

- PK `uuid` (`gen_random_uuid()`), mai ID sequenziali esposti.
- Ogni tabella tenant-specific ha `tenant_id uuid NOT NULL`, `UNIQUE (tenant_id, id)` per le FK composite, RLS `ENABLE` + `FORCE`.
- Timestamp `timestamptz` in UTC; `created_at`, `updated_at` ovunque.
- Stati come `text` + `CHECK`, anziché enum Postgres, per migrazioni più semplici.
- Soft delete (`deleted_at`) solo dove serve lo storico (clienti, prestazioni, professionisti); la cancellazione GDPR effettiva è una procedura separata di anonimizzazione.

## Estensioni

```sql
CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS citext;
CREATE EXTENSION IF NOT EXISTS btree_gist;
```

## Policy RLS (modello comune)

```sql
ALTER TABLE <t> ENABLE ROW LEVEL SECURITY;
ALTER TABLE <t> FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON <t>
  USING      (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
  WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);
```
Il ruolo applicativo `app_rw` non è proprietario delle tabelle e non ha `BYPASSRLS`. Se `app.tenant_id` non è impostato, la policy non restituisce nulla (fail-closed). Il `NULLIF` è necessario: dopo una `SET LOCAL` conclusa, sulla stessa connessione del pool la variabile vale `''` e il cast a uuid fallirebbe con un errore.

> **Verificato su PostgreSQL 16** (17/11/2026): lo schema si carica senza errori; il vincolo `no_overlap_professional` rifiuta un appuntamento che cade nel buffer di preparazione del precedente e accetta quello adiacente; la FK composita impedisce di collegare un cliente di un altro tenant; la RLS con ruolo non privilegiato mostra solo le righe del tenant attivo, 0 righe senza tenant, e rifiuta inserimenti con `tenant_id` altrui.

---

## Identità e tenant [R1]

```sql
CREATE TABLE tenants (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  name text NOT NULL,
  slug citext NOT NULL UNIQUE,                     -- prenota.../{slug}
  business_type text NOT NULL,                     -- FK logica a business_types
  status text NOT NULL DEFAULT 'trial'
    CHECK (status IN ('trial','active','past_due','suspended','cancelled')),
  trial_ends_at timestamptz,
  default_timezone text NOT NULL DEFAULT 'Europe/Rome',
  neutral_messaging boolean NOT NULL DEFAULT false,   -- (+) GDPR: testi neutri
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);  -- no RLS: accesso filtrato per id nel backend

-- (+) categorie professionali estendibili senza modifiche al codice (§1.1)
CREATE TABLE business_types (
  code text PRIMARY KEY, label text NOT NULL,
  default_services jsonb NOT NULL DEFAULT '[]',     -- preset prestazioni all'onboarding
  active boolean NOT NULL DEFAULT true
);

-- (+) impostazioni studio, politica cancellazione, branding portale
CREATE TABLE tenant_settings (
  tenant_id uuid PRIMARY KEY REFERENCES tenants(id),
  cancellation_min_hours int NOT NULL DEFAULT 24,   -- valore da Decisione 8
  reschedule_min_hours int NOT NULL DEFAULT 24,
  cancellation_policy_text text,
  booking_enabled boolean NOT NULL DEFAULT true,
  booking_min_notice_minutes int NOT NULL DEFAULT 120,
  booking_max_days_ahead int NOT NULL DEFAULT 60,
  slot_step_minutes int NOT NULL DEFAULT 15,
  logo_url text, brand_color text, contact_phone text, contact_email citext,
  privacy_policy_url text,
  reminders jsonb NOT NULL DEFAULT '{"h48":true,"h24":true}',
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE users (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  email citext NOT NULL UNIQUE,
  password_hash text,                               -- Argon2id; null se auth esterna
  auth_provider_id text,
  full_name text NOT NULL,
  status text NOT NULL DEFAULT 'active' CHECK (status IN ('pending','active','disabled')),
  email_verified_at timestamptz,
  is_platform_admin boolean NOT NULL DEFAULT false, -- Super Admin CoreNexus
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE tenant_users (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL REFERENCES tenants(id),
  user_id uuid NOT NULL REFERENCES users(id),
  role text NOT NULL CHECK (role IN ('owner','professional','secretary')),
  permissions jsonb NOT NULL DEFAULT '{}',          -- override granulari (R3)
  UNIQUE (tenant_id, user_id)
);

-- (+) refresh token ruotati, revocabili
CREATE TABLE auth_sessions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL REFERENCES users(id),
  refresh_token_hash bytea NOT NULL UNIQUE,
  expires_at timestamptz NOT NULL, revoked_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(), user_agent text, ip inet
);
```

## Struttura studio [R1, UI multi-sede R3]

```sql
CREATE TABLE locations (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL REFERENCES tenants(id),
  name text NOT NULL, address text,
  timezone text NOT NULL DEFAULT 'Europe/Rome',
  is_default boolean NOT NULL DEFAULT false,
  active boolean NOT NULL DEFAULT true,
  UNIQUE (tenant_id, id)
);

CREATE TABLE rooms (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL,
  location_id uuid NOT NULL,
  name text NOT NULL, active boolean NOT NULL DEFAULT true,
  UNIQUE (tenant_id, id),
  FOREIGN KEY (tenant_id, location_id) REFERENCES locations(tenant_id, id)
);

CREATE TABLE professionals (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL REFERENCES tenants(id),
  user_id uuid REFERENCES users(id),               -- null se senza accesso
  name text NOT NULL, specialization text,
  color text,
  status text NOT NULL DEFAULT 'active' CHECK (status IN ('active','inactive')),
  public_booking boolean NOT NULL DEFAULT true,
  deleted_at timestamptz,
  UNIQUE (tenant_id, id)
);

CREATE TABLE services (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL REFERENCES tenants(id),
  name text NOT NULL, description text,
  duration_minutes int NOT NULL CHECK (duration_minutes BETWEEN 5 AND 600),
  preparation_minutes int NOT NULL DEFAULT 0 CHECK (preparation_minutes >= 0),
  price numeric(10,2) CHECK (price >= 0),
  color text,
  public_visible boolean NOT NULL DEFAULT true,
  active boolean NOT NULL DEFAULT true,
  deleted_at timestamptz,
  UNIQUE (tenant_id, id)
);

-- (+) relazioni M:N previste in §3.4 ("professionisti abilitati", "sedi disponibili")
CREATE TABLE service_professionals (
  tenant_id uuid NOT NULL, service_id uuid NOT NULL, professional_id uuid NOT NULL,
  PRIMARY KEY (service_id, professional_id),
  FOREIGN KEY (tenant_id, service_id) REFERENCES services(tenant_id, id),
  FOREIGN KEY (tenant_id, professional_id) REFERENCES professionals(tenant_id, id)
);
CREATE TABLE service_locations (
  tenant_id uuid NOT NULL, service_id uuid NOT NULL, location_id uuid NOT NULL,
  PRIMARY KEY (service_id, location_id),
  FOREIGN KEY (tenant_id, service_id) REFERENCES services(tenant_id, id),
  FOREIGN KEY (tenant_id, location_id) REFERENCES locations(tenant_id, id)
);
```

## Disponibilità [R1]

```sql
CREATE TABLE availability (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL,
  professional_id uuid NOT NULL,
  location_id uuid NOT NULL,                        -- (+) orari diversi per sede
  weekday smallint NOT NULL CHECK (weekday BETWEEN 1 AND 7),  -- ISO, 1 = lunedì
  start_time time NOT NULL, end_time time NOT NULL CHECK (end_time > start_time),
  valid_from date, valid_to date,                   -- (+) orari stagionali
  active boolean NOT NULL DEFAULT true,
  FOREIGN KEY (tenant_id, professional_id) REFERENCES professionals(tenant_id, id),
  FOREIGN KEY (tenant_id, location_id) REFERENCES locations(tenant_id, id)
);

CREATE TABLE availability_exceptions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL,
  professional_id uuid,                             -- null = tutto lo studio (festività)
  location_id uuid,
  start_at timestamptz NOT NULL, end_at timestamptz NOT NULL CHECK (end_at > start_at),
  type text NOT NULL CHECK (type IN ('vacation','unavailable','holiday','extra_availability','booking_block')),
  reason text
);
CREATE INDEX ON availability_exceptions (tenant_id, professional_id, start_at, end_at);
```

## Clienti e consensi [R1]

```sql
CREATE TABLE clients (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL REFERENCES tenants(id),
  first_name text NOT NULL, last_name text NOT NULL,
  phone_e164 text,                                  -- normalizzato E.164
  email citext,
  birth_date date,
  reference_professional_id uuid,
  admin_notes text,                                 -- cifrato a livello applicativo
  preferred_channel text CHECK (preferred_channel IN ('whatsapp','email','none')),
  whatsapp_consent boolean NOT NULL DEFAULT false,
  whatsapp_consent_at timestamptz,
  email_consent boolean NOT NULL DEFAULT false,
  status text NOT NULL DEFAULT 'active' CHECK (status IN ('active','inactive','anonymized')),
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  deleted_at timestamptz,
  UNIQUE (tenant_id, id),
  FOREIGN KEY (tenant_id, reference_professional_id) REFERENCES professionals(tenant_id, id)
);
CREATE INDEX ON clients (tenant_id, last_name, first_name);
CREATE INDEX ON clients (tenant_id, phone_e164);
CREATE INDEX ON clients (tenant_id, email);
-- ricerca parziale: indice trigram (pg_trgm) se necessario, da misurare

-- (+) storico consensi e revoche (prova del consenso, GDPR art. 7)
CREATE TABLE client_consent_events (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL, client_id uuid NOT NULL,
  channel text NOT NULL CHECK (channel IN ('whatsapp','email','privacy')),
  action text NOT NULL CHECK (action IN ('granted','revoked')),
  source text NOT NULL,              -- 'public_booking','staff','whatsapp_stop',…
  policy_version text,
  ip inet, created_at timestamptz NOT NULL DEFAULT now(),
  FOREIGN KEY (tenant_id, client_id) REFERENCES clients(tenant_id, id)
);
```

## Appuntamenti [R1]

```sql
CREATE TABLE appointments (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL,
  public_code text NOT NULL,                         -- (+) identificativo leggibile non sequenziale
  client_id uuid NOT NULL,
  professional_id uuid NOT NULL,
  service_id uuid NOT NULL,
  location_id uuid NOT NULL,
  room_id uuid,
  start_at timestamptz NOT NULL,
  end_at timestamptz NOT NULL CHECK (end_at > start_at),
  preparation_minutes int NOT NULL DEFAULT 0,        -- copiato dalla prestazione al momento della prenotazione
  buffer_end_at timestamptz NOT NULL CHECK (buffer_end_at >= end_at),  -- end_at + preparazione, calcolato dal backend
  -- nota: timestamptz + interval è STABLE e non è ammesso in una colonna generata,
  -- per questo il buffer è materializzato in buffer_end_at
  occupied tstzrange GENERATED ALWAYS AS (tstzrange(start_at, buffer_end_at, '[)')) STORED,
  status text NOT NULL DEFAULT 'pending'
    CHECK (status IN ('pending','confirmed','cancelled_by_client','cancelled_by_staff','completed','no_show')),
  source text NOT NULL CHECK (source IN ('staff','public_booking','waitlist','recurring')),
  price numeric(10,2),
  notes text,                                        -- solo amministrative, mai nei messaggi
  cancellation_reason text,
  recurrence_id uuid,                                -- R2
  version int NOT NULL DEFAULT 1,                    -- (+) optimistic locking per drag & drop
  created_by uuid REFERENCES users(id),
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (tenant_id, id),
  UNIQUE (tenant_id, public_code),
  FOREIGN KEY (tenant_id, client_id)       REFERENCES clients(tenant_id, id),
  FOREIGN KEY (tenant_id, professional_id) REFERENCES professionals(tenant_id, id),
  FOREIGN KEY (tenant_id, service_id)      REFERENCES services(tenant_id, id),
  FOREIGN KEY (tenant_id, location_id)     REFERENCES locations(tenant_id, id),
  FOREIGN KEY (tenant_id, room_id)         REFERENCES rooms(tenant_id, id),

  -- GARANZIA ANTI DOPPIA PRENOTAZIONE
  CONSTRAINT no_overlap_professional EXCLUDE USING gist
    (professional_id WITH =, occupied WITH &&)
    WHERE (status IN ('pending','confirmed')),
  CONSTRAINT no_overlap_room EXCLUDE USING gist
    (room_id WITH =, occupied WITH &&)
    WHERE (status IN ('pending','confirmed') AND room_id IS NOT NULL)
);
CREATE INDEX ON appointments (tenant_id, professional_id, start_at);
CREATE INDEX ON appointments (tenant_id, client_id, start_at DESC);
CREATE INDEX ON appointments (tenant_id, status, start_at);

CREATE TABLE appointment_events (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL, appointment_id uuid NOT NULL,
  event_type text NOT NULL,   -- created, confirmed, rescheduled, cancelled, no_show, …
  actor_type text NOT NULL CHECK (actor_type IN ('staff','client','system')),
  actor_user_id uuid,
  previous_value jsonb, new_value jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  FOREIGN KEY (tenant_id, appointment_id) REFERENCES appointments(tenant_id, id)
);

-- (+) link sicuri di gestione (§5.4 specifica)
CREATE TABLE appointment_access_tokens (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL, appointment_id uuid NOT NULL,
  token_hash bytea NOT NULL UNIQUE,                  -- SHA-256, il token in chiaro non si salva
  scopes text[] NOT NULL,                            -- {view,confirm,reschedule,cancel}
  expires_at timestamptz NOT NULL,
  revoked_at timestamptz, last_used_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  FOREIGN KEY (tenant_id, appointment_id) REFERENCES appointments(tenant_id, id)
);

-- (+) idempotenza richieste pubbliche (doppio click, retry)
CREATE TABLE idempotency_keys (
  tenant_id uuid NOT NULL, key text NOT NULL,
  request_hash bytea NOT NULL, response jsonb, created_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (tenant_id, key)
);
```

## Notifiche [R1]

```sql
CREATE TABLE notification_templates (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL,
  channel text NOT NULL CHECK (channel IN ('whatsapp','email')),
  event_type text NOT NULL CHECK (event_type IN
    ('booking_created','reminder_48h','reminder_24h','confirmed','rescheduled','cancelled','cancelled_by_staff')),
  language text NOT NULL DEFAULT 'it',
  provider_template_name text,                       -- nome template Meta
  provider_template_id text,
  provider_status text,                              -- APPROVED / PENDING / REJECTED / PAUSED
  category text,                                     -- UTILITY / MARKETING
  body text,                                         -- per email; per WA è copia informativa
  variables jsonb NOT NULL DEFAULT '[]',
  active boolean NOT NULL DEFAULT true,
  UNIQUE (tenant_id, channel, event_type, language)
);

CREATE TABLE notification_jobs (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL,
  appointment_id uuid NOT NULL,
  event_type text NOT NULL,
  channel text NOT NULL CHECK (channel IN ('whatsapp','email')),
  scheduled_at timestamptz NOT NULL,
  status text NOT NULL DEFAULT 'scheduled' CHECK (status IN
    ('scheduled','pending','processing','sent','delivered','read','failed','cancelled')),
  idempotency_key text NOT NULL UNIQUE,
  attempts int NOT NULL DEFAULT 0,
  next_attempt_at timestamptz,
  dead_lettered boolean NOT NULL DEFAULT false,
  cancel_reason text, last_error_code text, last_error_message text,
  created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now(),
  FOREIGN KEY (tenant_id, appointment_id) REFERENCES appointments(tenant_id, id)
);
-- dispatcher: SELECT … WHERE status='scheduled' AND scheduled_at <= now() FOR UPDATE SKIP LOCKED
CREATE INDEX notification_jobs_due ON notification_jobs (scheduled_at) WHERE status = 'scheduled';
CREATE INDEX ON notification_jobs (tenant_id, appointment_id);

CREATE TABLE notification_logs (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL,
  notification_job_id uuid NOT NULL REFERENCES notification_jobs(id),
  attempt int NOT NULL,
  provider_message_id text,                          -- wamid.*
  status text NOT NULL,
  error_code text, error_detail text,
  sent_at timestamptz, delivered_at timestamptz, read_at timestamptz, failed_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX ON notification_logs (provider_message_id) WHERE provider_message_id IS NOT NULL;
```

## WhatsApp [R1]

```sql
CREATE TABLE whatsapp_accounts (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL UNIQUE REFERENCES tenants(id),  -- MVP: 1 numero per tenant (Decisione 5)
  business_account_id text NOT NULL,
  phone_number_id text NOT NULL UNIQUE,
  display_phone_number text,
  signup_config_id text,                             -- identificativo configurazione Embedded Signup
  encrypted_access_token bytea NOT NULL,             -- cifratura envelope, chiave in KMS
  token_key_id text NOT NULL,
  token_expires_at timestamptz,
  connection_status text NOT NULL CHECK (connection_status IN ('pending','connected','error','disconnected')),
  verification_status text,
  quality_rating text,                               -- GREEN / YELLOW / RED
  messaging_limit_tier text,
  created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now()
);

-- (+) webhook grezzi: deduplica e rielaborazione
CREATE TABLE webhook_events (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  provider text NOT NULL,                            -- 'whatsapp','stripe'
  dedupe_key text NOT NULL UNIQUE,                   -- es. wamid + status
  tenant_id uuid,
  payload jsonb NOT NULL,                            -- conservazione limitata (Decisione 10)
  received_at timestamptz NOT NULL DEFAULT now(),
  processed_at timestamptz, processing_error text
);  -- accesso solo da worker con ruolo dedicato

-- (+) messaggi in entrata (risposte, richieste di assistenza, STOP)
CREATE TABLE inbound_messages (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL, client_id uuid,
  provider_message_id text NOT NULL UNIQUE,
  from_phone_e164 text NOT NULL,
  message_type text NOT NULL,                        -- text, button, interactive
  button_payload text, text_body text,
  handled_as text,                                   -- confirm, opt_out, support, ignored
  received_at timestamptz NOT NULL
);

CREATE TABLE whatsapp_usage (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL,
  notification_log_id uuid REFERENCES notification_logs(id),
  provider_message_id text NOT NULL UNIQUE,
  category text NOT NULL,                            -- utility / marketing / service / authentication
  billable boolean,
  quantity int NOT NULL DEFAULT 1,
  estimated_cost numeric(10,5), actual_cost numeric(10,5), currency text DEFAULT 'EUR',
  pricing_model text,
  created_at timestamptz NOT NULL DEFAULT now()
);

-- (+) listino costi Meta aggiornabile (§10.3: prezzo non costante)
CREATE TABLE provider_rate_cards (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  provider text NOT NULL, country text NOT NULL, category text NOT NULL,
  unit_cost numeric(10,5) NOT NULL, currency text NOT NULL,
  valid_from timestamptz NOT NULL, valid_to timestamptz
);
```

## Audit [R1]

```sql
CREATE TABLE audit_logs (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  tenant_id uuid, user_id uuid,
  actor_type text NOT NULL,                          -- staff, client_token, system, platform_admin
  action text NOT NULL, resource text NOT NULL, resource_id uuid,
  metadata jsonb, ip inet,
  timestamp timestamptz NOT NULL DEFAULT now()
);  -- append-only: il ruolo applicativo ha solo INSERT/SELECT
```

## Release successive (sintesi)

| Tabella | Release | Note |
|---|---|---|
| `waitlist`, `waitlist_offers` (+) | R2 | Offerte con scadenza; l'assegnazione dello slot è garantita dal vincolo anti-overlap |
| `appointment_recurrences` (+) | R2 | Regola RRULE; gli appuntamenti sono materializzati come righe |
| `payments`, `service_packages`, `client_packages`, `package_usages` (+) | R2 | Registrazione pagamenti, crediti sedute, scadenze |
| `credit_wallets`, `credit_transactions` | R2/R4 | **Ledger append-only**: il saldo è derivato, `credit_wallets` è una cache aggiornata in transazione |
| `subscription_plans`, `subscriptions`, `plan_limits` | R4 | Limiti in `jsonb` modificabili dal Super Admin senza codice |
| `calendar_connections` (+) | R2 | Google Calendar, token cifrati |
