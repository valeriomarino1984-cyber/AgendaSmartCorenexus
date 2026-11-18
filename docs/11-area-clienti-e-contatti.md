# Area clienti, contatti e versione – 18/11/2026

## Due accessi separati
- **Login professionisti** (`/accedi`): titolari, professionisti e segreteria, con email e password.
- **Login clienti** (`/area-clienti`): i clienti degli studi, **senza password**. Inseriscono l'email data allo studio e ricevono un link monouso valido 15 minuti.
- In cima a entrambe le pagine c'è la scelta **Professionisti | Clienti**.
- Le due sessioni usano **cookie diversi**: un cliente non apre l'area dello studio (`/app` lo rimanda al Login professionisti) e un account dello studio non apre l'area clienti.

## Cosa vede il cliente
- **Prossimi appuntamenti** di tutti gli studi in cui è registrato con quell'email: data, orario, prestazione, professionista, studio, indirizzo o telefono dello studio, stato.
- **Visite online:** pulsante "Entra nella videochiamata", solo per gli appuntamenti futuri ancora attivi.
- **Disdetta** con conferma, se mancano almeno le ore di preavviso impostate dallo studio (*Impostazioni → Preavviso minimo*). Altrimenti l'area invita a contattare lo studio. In agenda l'appuntamento risulta "Disdetto dal cliente", e lo storico lo attribuisce al cliente.
- **Appuntamenti passati:** gli ultimi 10.

## Sicurezza
- **Nessuna enumerazione:** la risposta alla richiesta del link è sempre la stessa, che l'email sia di un cliente o no.
- **Limiti:**
  - 3 link all'ora per indirizzo;
  - 20 richieste all'ora per IP.
- **Link e sessioni:**
  - link monouso con scadenza, nel database solo l'hash;
  - sessione di 14 giorni al massimo, che si chiude dopo 3 giorni di inattività.
- **Clienti archiviati e studi sospesi:** non ricevono link.
- **Lettura tra studi:** avviene con una sessione di piattaforma motivata e in sola lettura. La disdetta si scrive con la sessione dello studio dell'appuntamento.
- **Test:** 7 test di integrazione:
  - sessioni separate;
  - link monouso e scaduto;
  - preavviso;
  - appuntamenti di più studi;
  - nessun accesso agli appuntamenti di altri clienti;
  - cliente archiviato;
  - limiti.

  Controprova: 5 protezioni disattivate a turno, ognuna rilevata dai test.
- **E2E nel browser:** `frontend/e2e/flusso-area-clienti.cjs`.

## Home
- Sezione **Contatti** come presenze.corenexus.it:
  - "Richiedi una prova gratuita";
  - telefono, email, WhatsApp;
  - riquadro "Scrivici direttamente su WhatsApp" con QR (generato al momento della build) e pulsante.
- **Piè di pagina** come Presenze:
  - copyright e collegamenti (Novità, Contatti, Area professionisti, Area clienti);
  - riga con **versione e data** ("Agenda 0.4 · aggiornata al 18/11/2026 · Sviluppato da CoreNexus Technology Solutions"), anche nelle pagine di accesso e nell'area riservata.
- **Pagina `/novita`** con le versioni 0.1–0.4.
- **A ogni rilascio** aggiornare `APP_VERSION` e `APP_UPDATED` in `frontend/apps/web/src/lib/brand.ts` e la pagina Novità.
