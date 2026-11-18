# CoreNexus Agenda – Design system

L'interfaccia riprende il design system di **Presenze** (repository `PresenzeSmartCorenexus`), così che i prodotti CoreNexus abbiano lo stesso aspetto: stile ispirato alle Human Interface Guidelines di Apple, tema chiaro e scuro automatici, animazioni che si spengono con "riduci movimento".

## Dove si trova

| File | Contenuto |
|---|---|
| `frontend/apps/web/src/app/globals.css` | Colori, ombre, scala tipografica, materiali traslucidi, animazioni |
| `src/components/ui.tsx` | Pulsanti, campi, `Panel`, `PageHeader`, `StatStrip`, `Tag`, `StatusTag`, `ServiceChip`, `Disclosure`, `AddRow`, `Notice`, `EmptyState`, `Monogram`, `IconTile` |
| `src/components/AppNav.tsx` | Menu dello studio (specifica §15), barra laterale e barra in basso per telefono |
| `src/components/AppShell.tsx` | Struttura dell'area riservata |
| `src/components/Logo.tsx` | Logo: squircle blu della famiglia CoreNexus con calendario e spunta |
| `src/components/Splash.tsx`, `Motion.tsx` | Apertura animata della home, comparse allo scorrimento |
| `src/components/Segmented.tsx` | Controllo segmentato (giorno/settimana/mese) |
| `src/app/anteprima/` | **Catalogo dei componenti**, visibile solo in sviluppo (`/anteprima`; in produzione risponde 404) |

## Cosa è uguale a Presenze
- Tutti i colori (`canvas`, `paper`, `card`, `ink`, `accent` …) e la loro versione scura.
- La scala tipografica (`t-large-title` … `t-caption`) e i numeri arrotondati (`num`).
- Pulsanti a pillola, schede con angoli da 14 px, liste in stile Impostazioni di iPhone, monogrammi.
- Barra laterale traslucida (`vibrant`), barre in vetro (`glass`), barra delle schede sul telefono.
- Effetti della home: logo d'apertura, titolo in sequenza, comparsa allo scorrimento, schede che si sollevano (`lift`), alone che segue il puntatore (`spot`), riflesso sui pulsanti (`shine`), barra di lettura, FAQ che si aprono morbide.

## Cosa è specifico dell'Agenda
- **Logo:** stesso squircle blu, con un calendario. All'apertura della home la spunta si disegna da sola.
- **Stati degli appuntamenti** (`StatusTag`): da confermare (arancio), confermato (verde), disdetto/cancellato (rosso), assente (nero), svolto (grigio). Le etichette sono le stesse in tutta l'app.
- **Colore della prestazione** (`ServiceChip`, classe `svc-chip`): ogni prestazione ha il suo colore (campo `services.color`), leggibile in entrambi i temi.
- **Verde WhatsApp** (`wa`, `wa-soft`): usato solo per ciò che rappresenta quel canale.
- **Voci di menu future:** lista d'attesa, report (R2) e abbonamento (R4) compaiono grigie con "In arrivo" e non sono cliccabili.
- **Home:** illustrazioni del portatile con l'agenda e del telefono con il promemoria WhatsApp (i messaggi arrivano uno dopo l'altro). **Sono illustrazioni, non dati reali.** La home dichiara che il prodotto è "In arrivo".

## Regole
1. Usare sempre i colori del tema (`bg-card`, `text-ink-3`, …), mai esadecimali sparsi: così il tema scuro funziona da solo. Fanno eccezione le illustrazioni della home.
2. Ogni nuova animazione va spenta in `@media (prefers-reduced-motion: reduce)`.
3. Font: Inter tramite `next/font`, scaricato in fase di build e servito dal nostro dominio, quindi nessuna richiesta a Google dal browser. Sui dispositivi Apple si usa il carattere di sistema (SF Pro).
4. Testi solo in italiano. Le etichette ricorrenti (stati, ruoli) stanno in un solo punto.

## Verifica
Lint, typecheck e build superati. Screenshot controllati a 1440 px e su iPhone 13, in tema chiaro e scuro: nessun errore in console e nessuno scorrimento orizzontale. `/anteprima` risponde 200 in sviluppo e 404 in produzione.
