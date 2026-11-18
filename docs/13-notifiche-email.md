# Notifiche email ai clienti – 18/11/2026 (Sprint 5, canale email)

WhatsApp resta in attesa; le email partono già con il server di posta del cPanel (`agenda@corenexus.it`).

## Cosa riceve il cliente
| Quando | Email |
|---|---|
| Lo studio fissa un appuntamento | **Conferma**, oppure "Da confermare" se l'appuntamento è in attesa. Quando lo studio lo conferma arriva la conferma vera |
| Prima dell'appuntamento | **Promemoria** (24 ore prima, oppure l'anticipo scelto dallo studio) |
| L'appuntamento cambia orario o professionista | **Appuntamento spostato** con il nuovo orario; il vecchio promemoria si annulla e se ne programma uno nuovo |
| Lo studio o il cliente lo annulla | **Appuntamento annullato**; i promemoria in coda si annullano |

Svolto o assente: i promemoria in coda si annullano.

Cosa c'è nel testo:
- data e ora nel fuso della sede, professionista e indirizzo della sede;
- per le visite online, il pulsante **"Entra nella videochiamata"**;
- il link all'**area clienti** (vedere e disdire) e il preavviso per disdire;
- i contatti dello studio.

Con i **messaggi discreti** (professioni sanitarie) il testo dice "Appuntamento", non il nome della prestazione.

Mittente e risposte:
- il mittente si chiama "*Nome studio* via Agenda", con indirizzo `agenda@corenexus.it`;
- se lo studio ha un'email di contatto, le risposte vanno direttamente allo studio (Reply-To).

## Regole
L'email parte solo se il cliente:
- ha un indirizzo email;
- ha il **consenso ai promemoria via email**;
- non ha scelto "Nessun messaggio";
- non è archiviato.

Il controllo si ripete al momento dell'invio. Se qualcosa manca, la notifica è "Non inviata" con il motivo, e dalla pagina Notifiche si può **riprovare** (per esempio dopo aver aggiunto l'email).

Errori del server di posta: fino a 3 tentativi (dopo 10 e 20 minuti), poi "Non riuscita".

Lo studio regola tutto in **Impostazioni → Notifiche ai clienti**: conferme e avvisi sì/no, promemoria nessuno / 2, 6, 12, 24, 48 o 72 ore prima.

## Pagina Notifiche
**Notifiche** nel menu: inviate, in programma, non inviate e non riuscite, con il filtro "Da controllare". Nella scheda di ogni appuntamento c'è la sezione **"Email al cliente"**. Il professionista vede solo le notifiche dei propri appuntamenti.

## Come partono i promemoria: cron di cPanel (da fare una volta)
Conferme e avvisi partono subito. I promemoria partono all'ora prevista: con il sito in uso al massimo ogni 5 minuti, e **con il cron di cPanel anche di notte e nei giorni senza accessi** (consigliato).

1. **Setup Python App → variabili.** Aggiungi `CRON_SECRET` con almeno 32 caratteri casuali, generati con un gestore di password, poi premi *Restart*.
2. **cPanel → Cron Jobs → Aggiungi nuovo cron job:**
   - impostazione comune: **"Una volta ogni cinque minuti"** (`*/5 * * * *`);
   - comando (sostituisci `LA_CHIAVE` con lo stesso valore di `CRON_SECRET`):

     ```
     curl -fsS -X POST -H "X-Cron-Key: LA_CHIAVE" https://agenda.corenexus.it/api/v1/webhooks/cron/notifiche > /dev/null
     ```

Senza `CRON_SECRET` l'indirizzo del cron risponde "non trovato"; con una chiave sbagliata risponde 403.

## Sicurezza e affidabilità
- **Coda nel database:** le notifiche nascono nella stessa transazione della modifica dell'appuntamento, quindi niente notifiche perse né notifiche di modifiche annullate.
- **Nessun doppio invio:** più processi insieme non inviano due volte la stessa email (`SELECT … FOR UPDATE SKIP LOCKED`). Un invio interrotto a metà diventa "Non riuscita" invece di essere ripetuto.
- **Log:** i destinatari non compaiono mai nei log; il registro conserva solo tipo, esito e motivo.

## Verifiche
- **Backend:** 203 test, di cui 12 nuovi:
  - conferma con mittente e risposta allo studio;
  - testo discreto e link della videochiamata;
  - consenso mancante, poi nuovo tentativo;
  - "Nessun messaggio";
  - spostamento, annullamento dallo studio e dall'area clienti;
  - cron con e senza chiave;
  - impostazioni spente;
  - errori del server di posta e 3 tentativi;
  - **4 processi in parallelo, una sola email**;
  - isolamento tra studi;
  - professionista.
- **Controprova:** 7 protezioni disattivate a turno, ognuna rilevata dai test.
- **E2E nel browser:** `frontend/e2e/flusso-notifiche.cjs`.
