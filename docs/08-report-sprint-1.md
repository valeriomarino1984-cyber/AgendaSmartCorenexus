# Report Sprint 1 – Accesso, studi e collaboratori

**Data:** 18/11/2026
**Contesto:** hosting Netsons cPanel con MariaDB (Decisione 3), perimetro solo agenda, canali WhatsApp + email con WhatsApp in stand-by (18/11/2026): per ora le comunicazioni sono **solo email**.

## Cosa può fare ora un utente

| Funzione | Dove |
|---|---|
| Registrare uno studio (nome, attività, titolare) con 14 giorni di prova | `/registrati` |
| Confermare l'email con un link (valido 48 ore) ed entrare direttamente | `/verifica-email` |
| Accedere e uscire; dopo 12 ore di inattività la sessione scade | `/accedi` |
| Reimpostare la password con un link (valido 1 ora); dopo il cambio tutte le sessioni vengono chiuse | `/password-dimenticata`, `/reimposta-password` |
| Vedere la dashboard con i primi passi e il periodo di prova | `/app` |
| Modificare i dati dello studio, il preavviso per le disdette e i messaggi discreti (solo titolare) | `/app/impostazioni` |
| Invitare collaboratori (professionista, segreteria, titolare), cambiare ruolo, disattivare l'accesso (solo titolare) | `/app/collaboratori` |
| Accettare un invito scegliendo la password | `/invito` |
| Lavorare con più studi con lo stesso account e passare dall'uno all'altro | menu laterale |

Le voci del menu non ancora realizzate (agenda, clienti, prestazioni…) restano visibili con "In arrivo" e non sono cliccabili.

## API (`/api/v1`)
- `auth`: `register`, `verify-email`, `verify-email/resend`, `login`, `logout`, `me`, `switch-tenant`, `password/forgot`, `password/reset`, `invitation`, `invitation/accept`
- `tenants/current`: `GET`/`PUT` (dati dello studio), `users` `GET`/`POST`, `users/{id}` `PATCH`
- `meta`: `config`, `business-types`

## Sicurezza

| Misura | Dettaglio |
|---|---|
| Password | scrypt (N=2^15, r=8, p=1), parametri salvati con l'hash e aggiornati al login; regole: almeno 10 caratteri, non contenere nome o email, non banale |
| Sessioni | cookie `HttpOnly`, `SameSite=Lax`, `Secure` e prefisso `__Host-` in produzione; nel database solo l'hash del token; scadenza per inattività (12 h) e assoluta (14 giorni) |
| CSRF | ogni richiesta che modifica dati deve avere `Origin` (o `Referer`) del nostro sito |
| Enumerazione account | registrazione, reinvio e password dimenticata rispondono allo stesso modo che l'email esista o no; login con lo stesso errore per email inesistente e password errata, con tempo di risposta uguale (hash fittizio) |
| Limiti di frequenza (su database) | 5 accessi falliti per email e 30 per IP in 15 minuti; 10 registrazioni/ora per IP; 3 email/ora per indirizzo e 20 per IP |
| Link via email | token casuali da 256 bit, salvati come hash, monouso e con scadenza; un nuovo link invalida il precedente |
| Ruoli | controllati dall'API su ogni rotta (titolare, professionista, segreteria); lo studio deve avere sempre almeno un titolare attivo |
| Isolamento tra studi | tutte le tabelle degli studi sono `TenantScoped`; la sola lettura tra più studi (elenco degli studi di un utente al login) avviene con una sessione di piattaforma esplicita, motivata e in sola lettura |
| Registro attività | registrazione, accessi riusciti e falliti, uscite, reimpostazioni, inviti, modifiche ai ruoli e allo studio, con IP |
| Email | in produzione solo SMTP (l'API non parte con altri invii); destinatari mai scritti nei log |

## Verifiche

- **Backend: 107 test** su MariaDB 10.11, tra cui:
  - il flusso completo di registrazione, verifica, accesso e uscita;
  - link scaduti e riusati;
  - blocco dopo i tentativi falliti;
  - CSRF;
  - attributi del cookie;
  - inviti di persone nuove ed esistenti;
  - limiti dei ruoli;
  - isolamento tra due studi;
  - ultimo titolare;
  - disattivazione con revoca delle sessioni;
  - registro attività.
- **Test end-to-end nel browser** (`frontend/e2e/flusso-accesso.cjs`) su backend e frontend reali: registrazione → email di conferma → dashboard → impostazioni → invito → uscita → accettazione invito → il professionista non vede "Collaboratori" e ha le impostazioni in sola lettura → password errata e corretta. Nessun errore JavaScript nel browser.
- Lint, typecheck (mypy strict, TypeScript) e build superati. Migrazione `0002` provata in avanti e indietro.

## Difetti trovati e corretti durante lo sprint
1. **Blocco dei tentativi di accesso inefficace.** Il tentativo fallito veniva registrato nella stessa transazione poi annullata dall'errore, quindi il blocco dopo 5 tentativi non scattava e il registro restava vuoto. Trovato dai test e corretto. Controprova: reintroducendo il difetto, 2 test falliscono.
2. **Accessibilità dei campi.** L'etichetta includeva il suggerimento, quindi i lettori di schermo annunciavano "Password Almeno 10 caratteri…". Ora etichetta e suggerimento sono collegati correttamente (`htmlFor` e `aria-describedby`). Trovato dal test nel browser.
3. **Validazione della navigazione istantanea di Next.js 16.** L'area riservata si mostra solo dopo la verifica della sessione nel browser e non è pre-renderizzabile: esclusa dalla validazione con `export const instant = false`, come indicato dalla documentazione.

## Da fare prima di mettere online questa versione
1. In cPanel → *Setup Python App* aggiungere le variabili **SMTP** (`EMAIL_BACKEND`, `SMTP_HOST`, `SMTP_PORT`, `SMTP_SECURITY`, `SMTP_USERNAME`, `SMTP_PASSWORD`, `EMAIL_FROM`), vedi `07-deploy-netsons.md`. **Senza, l'API non parte.**
2. Creare la casella email del mittente (es. `no-reply@corenexus.it`) se non esiste.
3. Per provare la registrazione: `SIGNUP_OPEN=true` e poi *Restart*.

## Problemi aperti
- **Testi legali:** la casella "Accetto le condizioni del servizio e l'informativa…" non rimanda ancora a documenti, che vanno preparati con il legale (punto P4). Finché mancano, la registrazione pubblica resta chiusa (`SIGNUP_OPEN=false`).
- **Test end-to-end non ancora in CI:** richiede backend, database e frontend insieme. Per ora si esegue a mano; da valutare in uno sprint successivo.
- **Cambio password da profilo e gestione delle sessioni aperte:** non inclusi (c'è "password dimenticata"). Da aggiungere con la pagina profilo.

## Prossimo passo: Sprint 2
Sedi (con la sede predefinita creata in automatico), professionisti, prestazioni (durata, prezzo, colore, tempo di preparazione) e clienti (anagrafica, ricerca, consensi WhatsApp/email e **consenso marketing separato** per il futuro modulo Campagne).
