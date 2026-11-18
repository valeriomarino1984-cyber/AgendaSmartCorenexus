# Area piattaforma CoreNexus – 18/11/2026 (Sprint 2-bis)

Pannello riservato al team CoreNexus: `https://agenda.corenexus.it/piattaforma`.

## Attivazione (una volta, da cPanel → Setup Python App → variabili)
1. `PLATFORM_SECRET_KEY`: almeno 32 caratteri casuali, generati con un gestore di password. Non va scritta in chat e non va più cambiata, altrimenti i codici delle app smettono di funzionare.
2. `PLATFORM_BOOTSTRAP_EMAIL`: la tua email.
3. *Restart* dell'app Python.
4. Apri `/piattaforma` → "Prima configurazione" → inserisci l'email → apri il link ricevuto. Scegli la password, inquadra il QR con l'app di autenticazione (Google Authenticator, Microsoft Authenticator…) e inserisci il codice.

Da quel momento la prima configurazione non è più disponibile: le altre persone del team si invitano da *Team*.

## Accesso
- Email e password, poi il **codice a 6 cifre** dell'app, a ogni accesso.
- Un codice vale una sola volta.
- **Limiti:**
  - 5 password sbagliate in 15 minuti per email;
  - 5 codici sbagliati per tentativo, poi il tentativo si chiude.
- **Sessione:** cookie proprio (`SameSite=Strict`), diverso da quelli di studi e clienti. Si chiude dopo 30 minuti senza attività, al massimo dopo 12 ore.
- **Codici:** il segreto non è nel database. Si ricava dalla chiave del server e da un sale per persona, quindi una copia del database da sola non basta.
- **Senza `PLATFORM_SECRET_KEY`** l'area è spenta (503).

## Cosa si fa dal pannello
- **Studi:**
  - elenco con ricerca, stato, giorni di prova rimasti, titolare, conteggi (professionisti, clienti, appuntamenti futuri);
  - **nuovo studio** con invito al titolare: email con la pagina `/invito` già esistente; se l'email ha già un account, lo studio si aggiunge al suo profilo;
  - giorni di prova o attivo subito;
  - attiva, prova +14/+30 giorni, sospendi (lo staff dello studio non entra più) e riattiva;
  - cambio di profilo professionale e "Aggiungi prestazioni consigliate";
  - nuovo invio dell'invito al titolare.
- **Moduli:** sezione "In arrivo" (il modulo Campagne non esiste ancora).
- **Team:** invito, disattivazione (chiude subito le sessioni) e riattivazione. Non si può disattivare il proprio account.
- **Registro:** ultime 100 azioni con persona, studio e IP.

## Privacy
Dal pannello si vedono dati amministrativi e **conteggi**, mai nomi di clienti o appuntamenti. Le letture tra più studi usano la sessione di piattaforma motivata e in sola lettura. Le modifiche usano la sessione dello studio interessato, oppure la tabella globale degli studi.

## Verifiche
- **Codici a 6 cifre:** test con i valori ufficiali della RFC 6238.
- **11 test di integrazione:**
  - area spenta senza chiave;
  - prima configurazione solo per l'email prevista e una sola volta;
  - password più codice obbligatori;
  - codice non riutilizzabile;
  - tentativi limitati;
  - 30 minuti di inattività;
  - aree separate;
  - creazione, sospensione, prova e profilo di uno studio;
  - titolare già esistente;
  - team;
  - account disattivato con sessione aperta;
  - chiave corta rifiutata in produzione.
- **Controprova:** 6 protezioni disattivate a turno, ognuna rilevata dai test. All'inizio una non lo era (controllo dello stato nella sessione aperta), quindi ho aggiunto il test.
- **E2E nel browser:** `frontend/e2e/flusso-piattaforma.cjs`. Copre prima configurazione con QR, codice calcolato come un'app, nuovo studio, sospensione, registro, uscita e nuovo accesso con codice errato e poi corretto.
