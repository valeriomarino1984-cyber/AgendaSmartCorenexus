# Prenotazione online – 21/11/2026 (Sprint 4)

Ogni studio ha una pagina pubblica, per esempio `https://agenda.corenexus.it/prenota/<nome-studio>`. È **spenta** finché lo studio non la attiva da **Prenotazioni online**.

## Il cliente
1. Sceglie la **prestazione**: durata, prezzo indicativo, in studio o online.
2. Sceglie il **professionista**, oppure "Qualsiasi professionista".
3. Sceglie il **giorno**, su una settimana con il numero di orari liberi per giorno, e l'**ora**, divisa in mattina, pomeriggio e sera. Se la prestazione si può fare nei due modi, sceglie se in studio o online.
4. Inserisce i **dati**: nome, cognome, email, cellulare, note pratiche facoltative. Poi i consensi:
   - trattamento dei dati per l'appuntamento (obbligatorio);
   - promemoria via email (facoltativo);
   - offerte e novità (facoltativo).
5. **Conferma:** "Prenotazione confermata", oppure "Richiesta inviata" con la conferma manuale. Contiene un riepilogo e il link all'area clienti, e arriva l'email.

## Lo studio
- Pagina **Prenotazioni online**:
  - attiva o spenta;
  - link da copiare e QR da stampare;
  - prenotabile fino a 7–180 giorni;
  - preavviso minimo (nessuno fino a 48 ore);
  - **conferma manuale** (gli appuntamenti arrivano "Da confermare").
- **Cosa compare sulla pagina:** solo le prestazioni attive segnate "Prenotabile online", con almeno un professionista attivo e "Prenotabile online".
- **In agenda:** l'appuntamento arriva con origine "prenotazione online". Lo storico lo attribuisce al cliente.

## Regole e garanzie
- **Orari:** sono quelli dell'agenda (orario settimanale, ferie, chiusure, festività, appuntamenti, preparazione), più il preavviso e il limite di giorni dello studio. Si può prenotare **solo un orario proposto**: niente orari fuori turno o non allineati.
- **Nessuna doppia prenotazione:** stesso blocco del professionista dell'agenda. Il secondo cliente riceve "Questo orario non è più disponibile" e la pagina ricarica gli orari.
- **Doppio clic o invio ripetuto:** stessa prenotazione, nessun doppione (chiave unica per prenotazione).
- **Qualsiasi professionista:** si assegna chi è libero a quell'ora.
- **Cliente riconosciuto dall'email:** nessuna scheda doppia. Il telefono si aggiunge se mancava. I consensi si possono solo aggiungere da qui, mai togliere, e ognuno lascia un evento con origine "public_booking".
- **Email:**
  - la **conferma** e gli avvisi di una prenotazione fatta dal cliente partono sempre, perché li ha chiesti lui;
  - i **promemoria** partono solo con il consenso.
- **Anti-abuso:**
  - campo nascosto anti-spam;
  - limite di 10 prenotazioni all'ora per IP;
  - limite di 5 al giorno per la stessa email nello stesso studio.
- **Studio sospeso o pagina spenta:** "Pagina non disponibile".

## Da completare (fuori dal codice)
- **Informativa privacy dello studio:** la casella del consenso spiega l'uso dei dati in una riga, ma manca il collegamento a un'informativa completa. Va preparata con il legale (punto P4) e poi aggiunta alla pagina.
- **Captcha:** non attivo. Con i limiti attuali non serve; si valuta se arriveranno prenotazioni automatiche.

## Verifiche
- **Backend:** 215 test, di cui 12 nuovi:
  - pagina accesa e spenta;
  - prestazioni e professionisti nascosti;
  - orari con preavviso e limite di giorni;
  - prenotazione con cliente, conferma e storico;
  - cliente riconosciuto e consensi;
  - solo orari proposti;
  - stesso orario e doppio invio;
  - qualsiasi professionista;
  - conferma manuale;
  - anti-spam e limiti;
  - studio sospeso;
  - isolamento tra studi.
- **Controprova:** 8 protezioni disattivate a turno, ognuna rilevata dai test.
- **E2E nel browser:** `frontend/e2e/flusso-prenotazione.cjs` copre:
  - lo studio attiva la pagina;
  - il cliente prenota da telefono;
  - email di conferma;
  - appuntamento in agenda;
  - l'orario non è più proposto agli altri;
  - pagina spenta.

  Ripassati i flussi di agenda, notifiche e area clienti.
