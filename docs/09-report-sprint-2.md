# Report Sprint 2 – Anagrafiche e profili professionali

**Data:** 18/11/2026
**Contesto:** perimetro solo agenda; comunicazioni solo email (WhatsApp in stand-by); profili professionali decisi il 18/11/2026 (vedi `04-decisioni-aperte.md`).

## Cosa può fare ora un utente

| Funzione | Dove | Chi |
|---|---|---|
| Alla registrazione lo studio trova già la **sede principale**, la **scheda professionista del titolare** e le **prestazioni consigliate** del suo profilo | automatico | — |
| Vedere, aggiungere e modificare le prestazioni: durata, tempo di preparazione, prezzo indicativo, colore, **modalità (in studio, online, entrambe)**, chi le eroga, se sono prenotabili online; disattivarle e riattivarle | `/app/prestazioni` | modifica: titolare; lettura: tutti |
| Aggiungere le prestazioni consigliate che mancano (anche dopo aver cambiato categoria dello studio) | `/app/prestazioni` → *Prestazioni consigliate* | titolare |
| Gestire i professionisti: chi ha un account ha la scheda automatica; si possono aggiungere persone senza account; colore in agenda, specializzazione, prenotabilità online, attivo/inattivo | `/app/professionisti` | modifica: titolare; lettura: tutti |
| Gestire i clienti: anagrafica amministrativa, ricerca per nome, cognome, telefono o email, professionista di riferimento, canale preferito, note amministrative, archivio e ripristino | `/app/clienti` | tutto lo staff |
| Registrare i **consensi** del cliente (promemoria email, promemoria WhatsApp, **offerte e promozioni** separato) con data e storico | `/app/clienti` → scheda cliente | tutto lo staff |
| Avviso se si sta creando un cliente con lo stesso telefono o email di uno esistente, con *Crea comunque* | `/app/clienti` | tutto lo staff |
| Modificare nome e indirizzo della sede principale | `/app/impostazioni` | titolare |

Su telefono, Prestazioni, Professionisti e Collaboratori si aprono da *Impostazioni → Studio* (la barra in basso ha spazio per Oggi, Clienti, Impostazioni).

## Profili professionali (approvati il 18/11/2026)

| Categoria dello studio | Prestazioni create |
|---|---|
| Fisioterapista | Valutazione fisioterapica 60′, Seduta di fisioterapia 45′, Terapia manuale 30′ (10′ di preparazione) |
| Osteopata | Prima visita osteopatica 60′, Trattamento osteopatico 45′ (10′ di preparazione) |
| Nutrizionista, Biologo nutrizionista | Prima visita 60′, Controllo 30′, **Controllo online 30′** |
| Psicologo, Psicoterapeuta | Primo colloquio 60′, Colloquio 50′, **Colloquio online 50′** |
| Tutte le altre | Profilo generico: Primo incontro 60′, Appuntamento 30′ |

Sono un punto di partenza: lo studio le modifica liberamente. Ricaricare il profilo aggiunge solo quelle mancanti (confronto per nome), non duplica.

## Visite online
Le prestazioni hanno ora la **modalità** (`in_person`, `online`, `both`). Il **link della videochiamata** per ogni appuntamento arriva con l'agenda (Sprint 3); nei messaggi con lo Sprint 5. Nell'interfaccia è scritto così, senza far credere che il link esista già.

## API (`/api/v1`)
- `locations`: `GET`, `PATCH /{id}` (la sede principale non si può disattivare)
- `professionals`: `GET`, `POST`, `PATCH /{id}` (collegamento a un account solo se è membro dello studio e non ha già una scheda)
- `services`: `GET`, `POST`, `PATCH /{id}`; `GET /services/profile` (anteprima), `POST /services/profile` (aggiunge le mancanti)
- `clients`: `GET` (con `q`, `status`, `limit`, `offset`), `POST` (con `force=true` per confermare un possibile doppione), `GET /{id}` (con storico consensi), `PATCH /{id}`, `DELETE /{id}` (archivia), `POST /{id}/restore`

## Database (migrazione `0003_catalog`)
Tabelle `locations`, `professionals`, `services`, `service_professionals`, `clients`, `client_consent_events`: tutte legate allo studio, con chiavi esterne composite `(tenant_id, id)` (un record non può puntare a quello di un altro studio nemmeno a livello di database) e vincoli di validità (durate, prezzo, modalità, stati, canali).

La migrazione **aggiorna anche gli studi già esistenti** (compreso quello di prova in produzione): crea la sede principale e la scheda professionista per titolari e professionisti attivi. Le prestazioni consigliate non vengono create in automatico per gli studi esistenti: il titolare le aggiunge con un clic da *Prestazioni consigliate*.

## Sicurezza e privacy
- **Isolamento tra studi** su ogni nuova risorsa: un id di un altro studio risulta "non trovato" (404) in lettura, modifica, archiviazione e ripristino; non si può indicare un professionista o un account di un altro studio (né come erogatore di una prestazione, né come riferimento di un cliente).
- **Consensi**: ogni cambiamento crea un evento (canale, dato/revocato, origine `staff`, chi l'ha fatto, quando) – prova del consenso (art. 7 GDPR). Un "no" alla creazione non genera eventi; un salvataggio senza cambiamenti nemmeno. Il consenso **marketing è separato** dai promemoria.
- **Minimizzazione**: il registro attività contiene solo *quali* campi sono cambiati, mai i dati del cliente; nessun dato clinico (le note sono dichiaratamente amministrative).
- **Telefoni** normalizzati in formato internazionale E.164 (senza prefisso si assume +39), necessario per WhatsApp e per riconoscere i doppioni.

## Verifiche
- **Backend: 142 test** su MariaDB 10.11 (erano 107): CRUD delle quattro anagrafiche, ruoli (segreteria e professionista non modificano catalogo, professionisti e sede; tutti gestiscono i clienti), isolamento tra due studi per ogni risorsa e azione, consensi e storico, doppioni, ricerca (anche con caratteri speciali come `%`), validazioni, profili per categoria e cambio di categoria, schede automatiche per inviti e cambi di ruolo, **aggiornamento degli studi esistenti con la migrazione**.
- **Controprova dei test (mutation testing):** disattivando a turno 7 controlli del codice (riferimento a professionista di altro studio, account di altro studio, consensi, idempotenza del profilo, ricerca per telefono…) almeno un test fallisce ogni volta. Uno dei 7 inizialmente non veniva rilevato (evento di revoca creato per un "no" iniziale): aggiunto il test.
- **Test end-to-end nel browser** (`frontend/e2e/flusso-anagrafiche.cjs`): registrazione da fisioterapista → 3 prestazioni del profilo → nuova prestazione online con prezzo "35,50 €" → professionista senza account → sede → cliente con telefono normalizzato → avviso doppione e *Crea comunque* → ricerca → consenso WhatsApp e storico → archivio → vista telefono. Nessun errore JavaScript. Anche il test dello Sprint 1 passa ancora.
- Migrazione `0003` provata in avanti, indietro e di nuovo avanti; `alembic check` senza differenze; provata anche sul database di prova con studi già esistenti.
- Lint, typecheck (mypy strict, TypeScript) e build superati.

## Problemi aperti
- **Cifratura applicativa delle note amministrative:** prevista nello schema (`02-schema-database.md`) ma rinviata: le note sono amministrative e il database non è esposto. Da rivalutare prima dell'apertura pubblica, insieme al legale (P4).
- **Più sedi:** il modello le supporta, l'interfaccia mostra solo la principale (multi-sede in Release 3).
- **Professionista e clienti:** per ora il professionista vede tutti i clienti dello studio. La restrizione "solo i propri clienti" va decisa con l'agenda (Sprint 3), quando esiste il legame cliente–appuntamento.
- **Eliminazione definitiva del cliente (diritto all'oblio):** per ora solo archivio; la cancellazione con anonimizzazione degli appuntamenti arriverà con l'agenda.
- **Importazione clienti da file (CSV/Excel):** utile per chi arriva da un altro gestionale, da pianificare.

## Prossimo passo
Sprint 2-bis: area piattaforma CoreNexus (`/piattaforma`) – oppure Sprint 3 (agenda e link delle visite online), secondo la priorità che preferisci.
