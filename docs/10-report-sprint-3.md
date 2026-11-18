# Report Sprint 3 – Agenda, disponibilità e visite online

**Data:** 18/11/2026
**Contesto:** visite online con **Jitsi pubblico** (`meet.jit.si`), scelto dal titolare il 18/11/2026; comunicazioni ancora solo email (i messaggi arrivano con lo Sprint 5).

## Cosa può fare ora un utente

| Funzione | Dove | Chi |
|---|---|---|
| Impostare l'**orario settimanale** (più fasce al giorno, es. 9–13 e 15–19), con "copia il lunedì fino al venerdì" | `/app/disponibilita` | titolare e segreteria per tutti; il professionista per sé |
| Inserire **ferie**, **indisponibilità**, **chiusure dello studio** (solo titolare) e **aperture straordinarie** (anche nei festivi), a giornate intere o a ore | `/app/disponibilita` | come sopra |
| Festività nazionali italiane **chiuse in automatico** (Pasqua e Pasquetta calcolate; 4 ottobre dal 2026) | automatico | — |
| **Agenda giorno / settimana / mese**, con i colori delle prestazioni, la linea dell'ora attuale, le ore fuori orario in grigio, filtro per professionista | `/app/agenda` | tutti (il professionista vede solo la propria) |
| **Prenotare** toccando uno spazio libero o con "Nuovo appuntamento": cerca o crea il cliente al volo, scegli la prestazione e il professionista abilitato, e scegli tra gli **orari liberi proposti** | pannello laterale | tutti (il professionista solo per sé) |
| **Spostare un appuntamento trascinandolo** in un altro giorno o orario (a scatti di 15 minuti) | `/app/agenda` | come sopra |
| Prenotare **fuori orario** o in un festivo con conferma esplicita ("Prenota comunque") | pannello | come sopra |
| **Visite online**: link della videochiamata creato in automatico, diverso per ogni appuntamento, con "Apri videochiamata" e "Copia link" | dettaglio appuntamento, dashboard | — |
| Stati: da confermare, confermato, **disdetto dal cliente**, **cancellato dallo studio** (con motivo), **svolto**, **assente**; storico di ogni modifica | dettaglio appuntamento | come sopra |
| Dashboard con gli **appuntamenti di oggi** e il passo "Imposta i tuoi orari" | `/app` | tutti |

## Garanzie

- **Nessuna doppia prenotazione.** MariaDB non ha i vincoli di esclusione di PostgreSQL. Ogni prenotazione o spostamento:
  - blocca la riga del professionista (`SELECT … FOR UPDATE`);
  - cerca sovrapposizioni con una **lettura bloccante**, che vede sempre gli ultimi dati confermati.

  Due richieste contemporanee vengono messe in fila: la seconda riceve "Orario già occupato" (409). Il tempo di **preparazione** dopo la visita conta come occupato. Gli appuntamenti cancellati liberano l'orario; quelli svolti o assenti no.
- **Modifiche contemporanee.** Ogni modifica indica la versione letta. Se nel frattempo qualcun altro ha cambiato l'appuntamento, si riceve "modificato da qualcun altro: ricarica" (409) invece di sovrascrivere.
- **Ora legale.** Gli orari settimanali sono "ora della sede": 9:00 resta 9:00 prima e dopo il cambio dell'ora. Gli istanti si salvano in UTC e l'interfaccia mostra sempre il fuso della sede, non quello del computer.
- **Link video.** Il nome della stanza è casuale (`CN-` + 22 caratteri, circa 130 bit): non contiene né nome dello studio, né cliente, né prestazione. L'indirizzo base si cambia con `VIDEO_BASE_URL`, per passare a un servizio con server UE o a un Jitsi proprio senza modificare il codice.
- **Ruoli.**
  - Titolare e segreteria gestiscono l'agenda di tutti.
  - Il professionista vede e gestisce solo la propria agenda: un appuntamento di un collega risulta "non trovato".
  - Solo il titolare chiude lo studio.
- **Isolamento tra studi.** Appuntamenti, orari e orari liberi di un altro studio risultano "non trovati". Non si può prenotare un cliente, un professionista o una prestazione di un altro studio.

## API (`/api/v1`)
- `professionals/{id}/availability`: `GET`, `PUT` (sostituisce l'orario settimanale)
- `availability-exceptions`: `GET ?from&to`, `POST`, `DELETE /{id}`
- `slots`: `GET ?professional_id&service_id&from&to` (orari liberi, passo 15 minuti, più le festività del periodo)
- `appointments`:
  - `GET ?from&to[&professional_id&client_id&include_cancelled]`;
  - `POST` (con `force` per confermare fuori orario);
  - `GET /{id}` (con storico);
  - `PATCH /{id}` (con `version`);
  - `POST /{id}/status` (con `version`).

## Database (migrazione `0004_agenda`)
Tabelle `availability`, `availability_exceptions`, `appointments` (codice leggibile, versione, link video, fine della preparazione) e `appointment_events`. Le chiavi esterne sono composite `(tenant_id, id)`. I vincoli coprono orari, stati, origine, tipi di eccezione e link obbligatorio per le visite online. Gli eventi hanno l'ora con i microsecondi, per restare in ordine anche quando sono nello stesso secondo.

## Verifiche
- **Backend: 168 test** su MariaDB 10.11 (erano 142). Tra questi:
  - **test di concorrenza**: 8 prenotazioni contemporanee sullo stesso orario danno esattamente 1 successo e 7 risposte 409; due spostamenti contemporanei nello stesso orario danno 1 successo e 1 risposta 409;
  - **ora legale** (29/03 e 25/10/2026) e ora inesistente;
  - Pasqua per diversi anni;
  - festività e aperture straordinarie;
  - preparazione;
  - versioni;
  - stati;
  - ruoli;
  - isolamento tra studi.
- **Controprova dei test (mutation testing):** ho disattivato a turno 10 protezioni: blocco del professionista, lettura bloccante, controllo di versione, ruoli, filtro del professionista, cancellati che non occupano, preparazione, fuori orario, prestazione abilitata, festività. Ogni volta almeno un test fallisce.
  - All'inizio il test HTTP di concorrenza **non rilevava** la mancanza della lettura bloccante: dipendeva dai tempi.
  - Ho aggiunto un test deterministico che riproduce il caso (la transazione legge, un'altra prenota, poi arriva il controllo), e ora il difetto viene rilevato.
- **Test end-to-end nel browser** (`frontend/e2e/flusso-agenda.cjs`), nessun errore JavaScript:
  - orario lun–ven 9–13;
  - clic sulla griglia per una prenotazione precompilata, con cliente creato dal pannello e orari liberi proposti;
  - visita online con link Jitsi;
  - **trascinamento** da lunedì 10:00 a martedì 11:00;
  - fuori orario con conferma;
  - sovrapposizione rifiutata;
  - vista mese;
  - disdetta con motivo;
  - vista telefono.

  Ripassati anche i test degli Sprint 1 e 2.
- Migrazione `0004` provata in avanti e indietro, `alembic check` senza differenze. Lint, mypy strict, TypeScript e build superati.

## Difetti trovati e corretti durante lo sprint
1. **Storico in disordine:** `DATETIME` di MySQL non conserva le frazioni di secondo, quindi eventi nello stesso secondo uscivano in ordine casuale. Trovato dai test e corretto con un'ora a microsecondi.
2. **L'agenda tornava a "oggi" da sola** se si cambiava settimana prima che la sede fosse caricata. Trovato dal test nel browser e corretto.
3. **Visite brevi illeggibili** nella settimana (nome tagliato): ora ora e cliente stanno su una riga.

## Problemi aperti
- **Jitsi pubblico:** da valutare nell'uso reale la privacy (soprattutto per gli psicologi) e se il professionista deve accedere con un account per aprire la stanza. Il passaggio a un servizio UE richiede solo `VIDEO_BASE_URL`.
- **Messaggi al cliente** (conferma, promemoria con il link della visita online): arrivano con lo Sprint 5.
- **Feste patronali:** sono locali, quindi non incluse. Lo studio le inserisce come chiusura.
- **Più sedi e stanze:** l'agenda usa la sede principale (multi-sede in Release 3).
- **Appuntamenti ricorrenti:** previsti in Release 2.
- **Spostamento da tastiera:** il trascinamento è con mouse o dito; da tastiera si sposta dal dettaglio con "Sposta o modifica".

## Prossimo passo
Sprint 4: pagina di prenotazione online per i clienti (`/prenota/{studio}`), che usa lo stesso calcolo degli orari liberi. In alternativa, lo Sprint 2-bis (area piattaforma CoreNexus).
