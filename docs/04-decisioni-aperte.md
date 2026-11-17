# CoreNexus Agenda – Registro decisioni (§23 della specifica)

Come previsto dalla specifica, **queste decisioni non sono state prese dall'agente**. Per ognuna sono indicati cosa blocca, le opzioni e una raccomandazione motivata. Lo stato passa ad "APPROVATA" solo dopo conferma esplicita del proprietario del prodotto.

| # | Decisione | Blocca | Opzioni | Raccomandazione | Stato |
|---|---|---|---|---|---|
| 1 | Nome commerciale | Branding, dominio, template WhatsApp (il nome compare nei messaggi) | — | Decidere prima dello Sprint 6 (i template approvati contengono testo fisso) | APERTA |
| 2 | Stack definitivo | Sprint 0 | a) Specifica: Next.js + FastAPI + Celery/Redis + PostgreSQL · b) Varianti | **(a)**, con auth gestita dal backend (no Supabase Auth): vedi Analisi §3.2 | **APPROVATA** (17/11/2026): stack della specifica, auth gestita dal backend FastAPI, niente Supabase Auth |
| 3 | Hosting e database | Sprint 0 | a) Cloud gestito UE (es. AWS eu-south-1 Milano / GCP europe-west8) · b) Provider europei (Hetzner, Scaleway, OVH) + Postgres gestito · c) Supabase solo come Postgres gestito in regione UE | Postgres **gestito** con backup PITR e regione UE; scelta del provider in base al budget | **PARZIALE** (17/11/2026): dominio applicativo `agenda.corenexus.it` approvato. **Provider cloud ancora da scegliere**: blocca solo il deploy (`infra/deploy`), non lo sviluppo |
| 4 | Onboarding WhatsApp | Sprint 6, App Review | a) Embedded Signup (richiede Tech Provider) · b) Collegamento manuale assistito (solo fase pilota) · c) Tramite BSP | **(a)** a regime; **(b)** per i primi tenant pilota mentre è in corso l'approvazione Meta | **APPROVATA** (17/11/2026) |
| 5 | Numeri dei professionisti | Modello dati WhatsApp, prezzi | a) 1 numero per tenant · b) 1 numero per professionista · c) Numero unico CoreNexus per tutti | **(a)** per l'MVP. (c) è sconsigliata: il cliente finale vedrebbe CoreNexus e non lo studio, e la qualità del numero sarebbe condivisa tra tutti i tenant | **APPROVATA** (17/11/2026): 1 numero per studio |
| 6 | Provider pagamenti | R2/R4 | Stripe / altri | Stripe (Billing + Checkout), come da specifica | APERTA |
| 7 | **Contabilizzazione messaggi** | Wallet, listino §10.3, piani | a) Il tenant paga Meta direttamente, CoreNexus conta i messaggi solo come limite di piano · b) CoreNexus rivende i messaggi (richiede Solution Partner o BSP con linea di credito) · c) Ibrido | **Decisione critica.** Con (a) i pacchetti €/messaggi del §10.3 non sono coerenti (doppio costo per lo studio). Con (b) il listino ha senso ma aumentano requisiti e rischio di credito. Serve una scelta commerciale prima di R2 | **APPROVATA** (17/11/2026): **(a)**, per ora gli studi pagano Meta direttamente. Vedi conseguenze sotto |
| 8 | Politica di cancellazione | Sprint 4 | Preavviso minimo, motivazione obbligatoria o no, gestione oltre il limite (bloccare o consentire con avviso) | Default configurabile per tenant: 24 h di preavviso; oltre il limite il link mostra i contatti dello studio invece del pulsante Disdici | APERTA |
| 9 | Perimetro MVP | Pianificazione | — | Quello indicato in `03-piano-di-sviluppo.md` (incluso l'**email come fallback** obbligatorio) | APERTA |
| 10 | Conservazione dati | Job di pulizia, informative | Durata storico appuntamenti, log notifiche, webhook grezzi, audit, clienti inattivi | Proposta da validare con il legale: webhook grezzi 30 gg · log notifiche 24 mesi · audit 24 mesi · clienti inattivi: anonimizzazione dopo N anni definiti dal tenant | APERTA |

## Decisioni aggiuntive emerse dall'analisi

| # | Decisione | Note |
|---|---|---|
| 11 | Messaggi "neutri" per categorie sensibili (psicologi ecc.) attivi di default? | Raccomandato: attivi di default per le categorie sanitarie |
| 12 | Componente calendario per la vista per risorse (FullCalendar Premium a pagamento o sviluppo su misura) | Serve entro R3 |
| 13 | Allineamento del listino alla roadmap (lista d'attesa e Google Calendar sono nel piano PRO ma arrivano in R2) | Prima del lancio commerciale |
| 14 | Prenotazione pubblica: l'appuntamento nasce `pending` o `confirmed`? È prevista l'approvazione manuale dello studio? | Proposta: `confirmed` alla prenotazione, conferma di presenza tramite il promemoria a 24 h |

## Conseguenze delle decisioni approvate

### Decisione 3 – dominio `agenda.corenexus.it`
- App gestionale: `https://agenda.corenexus.it`
- Portale pubblico: proposta `https://agenda.corenexus.it/prenota/{slug}` (stesso dominio, un solo certificato e una sola configurazione cookie). In alternativa `prenota.corenexus.it` come da specifica: entrambe le soluzioni sono possibili perché l'URL base è configurabile (`PUBLIC_BOOKING_BASE_URL`).
- Link di gestione appuntamento: `https://agenda.corenexus.it/a/{token}`
- Webhook Meta: `https://agenda.corenexus.it/api/v1/webhooks/whatsapp`

### Decisione 7 – gli studi pagano Meta direttamente
- Durante l'Embedded Signup lo studio aggiunge il proprio metodo di pagamento alla sua WABA. CoreNexus non anticipa costi Meta e non ha rischio di credito.
- `whatsapp_usage` resta: registra categoria e costo per messaggio (dal campo `pricing` dei webhook) **a scopo informativo**, per mostrare allo studio una stima della sua bolletta Meta e per le metriche del Super Admin.
- Le "notifiche WhatsApp incluse" dei piani (100/500/1.500/4.000) diventano una **quota di utilizzo del servizio di automazione** CoreNexus, applicata dal worker. Non sono crediti Meta.
- **Da rivedere commercialmente:** i pacchetti aggiuntivi del §10.3 (es. 250 messaggi a 7,90 €), venduti con questo modello, sarebbero un ampliamento della quota di automazione e lo studio pagherebbe comunque Meta a parte. Va deciso se mantenerli (con una comunicazione chiara) o eliminarli. Il wallet di R2/R4 si riduce quindi a un contatore di quota con soglie dell'80% e di esaurimento.
- Il modello resta reversibile: passare in futuro a Solution Partner richiede di aggiungere il ledger dei costi, non di riprogettare.
