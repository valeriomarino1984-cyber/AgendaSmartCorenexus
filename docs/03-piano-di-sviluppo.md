# CoreNexus Agenda – Piano di sviluppo

**Stato:** PROPOSTA. Le stime sono indicative, per un team di 1–2 sviluppatori full-stack affiancati da un agente AI. Ogni modulo è "completato" solo con test verdi e documentazione (regola inderogabile 7).

## Traccia parallela (da avviare subito, non è sviluppo)

| # | Attività | Responsabile | Perché ora |
|---|---|---|---|
| P1 | Verifica aziendale CoreNexus su Meta Business Manager | CoreNexus | Prerequisito di tutto il percorso WhatsApp |
| P2 | Meta App + richiesta stato **Tech Provider** (o accordo con BSP / percorso Solution Partner, vedi Decisione 5/7) | CoreNexus | Tempi decisi da Meta, nell'ordine di settimane. **Percorso critico** dal 18/11/2026: WhatsApp è l'unico canale di messaggistica dell'MVP oltre all'email |
| P3 | App Review permessi `whatsapp_business_management`, `whatsapp_business_messaging` | CoreNexus + sviluppo (video demo) | Serve un flusso funzionante in staging: va pianificata per la fine dello Sprint 4 |
| P4 | Consulenza legale: DPA, informative, DPIA per categorie sanitarie, trasferimenti verso Meta | Legale | Va chiusa prima del primo cliente reale |
| P5 | Scelta hosting UE e provider email UE | CoreNexus | Decisione 3, blocca lo Sprint 0 |
| P6 | Dominio `prenota.<dominio>` e dominio email con SPF/DKIM/DMARC | CoreNexus | La deliverability email richiede tempo di "riscaldamento" |

> **Aggiornamento 17/11/2026:** hosting Netsons cPanel con MariaDB (Decisione 3). Lo Sprint 0 è stato adattato (vedi `07-deploy-netsons.md`). Negli sprint seguenti: rate limit su DB (Sprint 1), lock `FOR UPDATE` contro le doppie prenotazioni (Sprint 3), cron di cPanel al posto di Celery (Sprint 5).

## Release 1 – MVP (≈ 12–14 settimane)

| Sprint | Contenuto | Criteri MVP coperti | Test chiave |
|---|---|---|---|
| **0** (1 sett.) ✅ completato 17/11/2026, vedi `05-report-sprint-0.md` | Monorepo, docker-compose, CI (lint, type-check, test), config da env, logging strutturato, Sentry, Alembic, ruolo DB non privilegiato e infrastruttura RLS | 17 (parziale) | La CI fallisce se una tabella con `tenant_id` non ha la RLS (test di meta-schema) |
| **1** (2 sett.) | Auth (registrazione, verifica email, login, refresh, logout, me), tenant + impostazioni, utenti e ruoli owner/professional/secretary, audit log | 1, 2, 15 | Suite isolamento A/B su ogni endpoint; matrice RBAC |
| **2** (2 sett.) | Sedi (default), professionisti, prestazioni (M:N), clienti con consensi e ricerca, preset per categoria professionale | 3, 4 | Validazione e normalizzazione E.164; isolamento |
| **3** (2 sett.) | Disponibilità + eccezioni + festività, **motore slot**, appuntamenti (CRUD, stati, eventi, vincolo anti-overlap, optimistic locking), UI agenda giorno/settimana/mese con drag & drop | 5 | **Test concorrenza**: N richieste parallele sullo stesso slot → esattamente 1 successo e N−1 risposte 409; test DST |
| **4** (2 sett.) | Portale pubblico `/prenota/{slug}` (branding, prestazioni, slot, dati, privacy, consenso WA separato), idempotenza, rate limit, captcha opzionale; link sicuri `/a/{token}` (vedi, conferma, sposta, disdici con politica configurabile) | 6, 7, 10, 11 | E2E Playwright mobile; token scaduto/revocato/scope errato; prenotazione concorrente da portale |
| **5** (2 sett.) | Motore notifiche (outbox, dispatcher `SKIP LOCKED`, retry/backoff, dead letter, reinvio manuale), canale **email** completo con template IT, invalidazione su modifica/cancellazione | 12, 13, 18 | Modifica prima del promemoria → vecchio job `cancelled`, nuovo job creato; nessun invio per appuntamenti cancellati; idempotenza sotto retry |
| **6** (2 sett.) | **WhatsApp**: onboarding (Embedded Signup se approvato, altrimenti collegamento guidato manuale di WABA/numero in staging), creazione template via API, invio template con pulsanti, webhook firmati (verifica `X-Hub-Signature-256`), stati, quick reply CONFERMA, STOP → revoca consenso, registrazione consumi e costi | 8, 9, 14 | Tutti i "Test WhatsApp" della specifica §19, con mock HTTP (respx) + **prova manuale su numero di test Meta reale** in staging |
| **7** (1–2 sett.) | Dashboard (KPI §3.1 con filtri), pagina Notifiche (fallite e reinvio), hardening sicurezza (Fase 3), backup cifrati e prova di ripristino, documentazione installazione e deploy, report di fase | 16, 17, 18 | E2E del percorso completo "registrazione → prima prenotazione → promemoria → conferma"; checklist sicurezza |

**Fuori dall'MVP (scelta esplicita):** lista d'attesa, ricorrenze, Google Calendar, Stripe, Super Admin completo. **Fuori perimetro del prodotto** (decisione 18/11/2026): pagamenti dei clienti finali, pacchetti di sedute, wallet, fatturazione, scheda clinica. Canali dell'MVP: **WhatsApp + email**. Per l'MVP basta un'interfaccia admin minima interna, protetta e tracciata, per sospendere un tenant e vedere errori e consumi.

## Release 2 – Automazione
Ricorrenze materializzate → lista d'attesa (offerte con scadenza; assegnazione garantita dal lock in transazione) → Google Calendar (solo scrittura in R2, sincronizzazione bidirezionale da valutare) → report. ~~Pagamenti e pacchetti sedute~~: fuori perimetro (18/11/2026).

## Modulo "Campagne" (dopo l'MVP, da validare)
Offerte promozionali dello studio via WhatsApp (template Marketing), con consenso marketing separato e revoca in un clic. Dettagli e vincoli in `04-decisioni-aperte.md` → *Posizionamento e perimetro*.

## Release 3 – Multi-studio
UI multi-sede e stanze, vista per risorsa (da decidere il componente/licenza), ruolo segreteria con agende autorizzate, permessi granulari, dashboard studio.

## Release 4 – Commercializzazione
Stripe Billing (trial, checkout, upgrade/downgrade con proration, annuale, insoluti → `past_due` → sospensione), limiti di piano applicati dal backend, wallet e acquisto pacchetti, pannello Super Admin separato (MRR/ARR/churn/ARPU, consumi e costi Meta), referral, white-label.

## Definition of Done (per ogni modulo)
1. Migrazione Alembic reversibile.
2. Endpoint documentati in OpenAPI con esempi.
3. Test unitari e di integrazione su Postgres reale; test di isolamento tenant per ogni nuovo endpoint.
4. Errori delle API esterne gestiti, loggati e visibili all'utente quando serve.
5. Nessun segreto nel codice; nuove variabili aggiunte a `.env.example`.
6. Report del modulo: cosa è fatto, cosa resta aperto.
