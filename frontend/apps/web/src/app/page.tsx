import { BellRing, CalendarCheck2, CalendarClock, Globe, ShieldCheck, Users } from "lucide-react";
import { Logo } from "@/components/Logo";
import { Motion } from "@/components/Motion";
import { Splash } from "@/components/Splash";
import { LaptopMock, PhoneMock } from "@/components/landing/Mocks";
import { IconTile, btnPrimary, linkCls } from "@/components/ui";

const FEATURES = [
  {
    icon: <Globe />,
    tile: "bg-accent",
    title: "Prenotazione online",
    text: "Una pagina dello studio con le prestazioni e gli orari liberi. Il cliente prenota da solo, anche dal telefono.",
  },
  {
    icon: <BellRing />,
    tile: "bg-wa",
    title: "Promemoria su WhatsApp",
    text: "Conferma di prenotazione e promemoria 48 e 24 ore prima, inviati in automatico con le API ufficiali di WhatsApp Business.",
  },
  {
    icon: <CalendarCheck2 />,
    tile: "bg-sys-green",
    title: "Conferma, sposta, disdici",
    text: "Il cliente risponde con un tocco. L'agenda si aggiorna da sola e i promemoria vecchi vengono annullati.",
  },
  {
    icon: <CalendarClock />,
    tile: "bg-sys-indigo",
    title: "Mai due clienti nello stesso orario",
    text: "Durata della prestazione, pause e tempi di preparazione: lo slot viene bloccato appena qualcuno prenota.",
  },
  {
    icon: <Users />,
    tile: "bg-sys-teal",
    title: "Clienti in ordine",
    text: "Anagrafica, storico appuntamenti, assenze e consensi alle comunicazioni in un unico posto.",
  },
  {
    icon: <ShieldCheck />,
    tile: "bg-sys-orange",
    title: "Messaggi discreti",
    text: "Nessun dato clinico nei messaggi e testi neutri per le professioni sanitarie. Ogni studio vede solo i propri dati.",
  },
];

const FAQ = [
  {
    q: "Serve un numero WhatsApp dedicato?",
    a: "Si collega il numero WhatsApp Business dello studio con la procedura ufficiale di Meta. Ogni studio usa il proprio numero: i clienti vedono il nome dello studio.",
  },
  {
    q: "Chi paga i messaggi WhatsApp?",
    a: "Meta addebita i messaggi direttamente allo studio, secondo il proprio listino. L'abbonamento include l'automazione di un numero di notifiche che dipende dal piano.",
  },
  {
    q: "E se il cliente non usa WhatsApp?",
    a: "Conferme e promemoria arrivano via email. I messaggi WhatsApp partono solo ai clienti che hanno dato il consenso.",
  },
  {
    q: "Per quali professioni è pensata?",
    a: "Fisioterapisti, nutrizionisti, psicologi, osteopati, estetisti, consulenti, studi e piccoli centri con più professionisti.",
  },
];

export default function Home() {
  return (
    <>
      <Splash />
      <header className="glass head-scroll sticky top-0 z-30 border-b border-ink/10">
        <div className="mx-auto flex h-12 max-w-5xl items-center justify-between px-4 sm:px-6">
          <Logo />
          <nav className="hidden gap-8 t-subhead text-ink-2 sm:flex">
            <a href="#funzioni" className="nav-u hover:text-ink">
              Funzioni
            </a>
            <a href="#whatsapp" className="nav-u hover:text-ink">
              WhatsApp
            </a>
            <a href="#domande" className="nav-u hover:text-ink">
              Domande
            </a>
          </nav>
          <span className="rounded-full bg-accent/12 px-3 py-1 t-footnote font-semibold text-accent">In arrivo</span>
        </div>
        <span className="scroll-bar" aria-hidden />
      </header>

      <main className="bg-canvas">
        <section className="overflow-hidden px-4 pt-16 text-center sm:pt-24">
          <p className="hero-seq t-headline text-accent">Per studi e liberi professionisti</p>
          <h1 className="hero-seq mt-2 text-[56px] leading-none font-bold tracking-[-0.04em] sm:text-[96px]" style={{ "--hd": "0.08s" } as React.CSSProperties}>
            Agenda
          </h1>
          <p className="hero-seq mx-auto mt-4 max-w-2xl text-[24px] leading-tight font-semibold tracking-tight text-ink-3 sm:text-[34px]" style={{ "--hd": "0.16s" } as React.CSSProperties}>
            Gli appuntamenti si confermano da soli.
          </p>
          <div className="hero-seq mt-8 flex flex-wrap items-center justify-center gap-6" style={{ "--hd": "0.24s" } as React.CSSProperties}>
            <a href="#funzioni" className={`${btnPrimary} cta shine shine-auto h-12 px-7 t-body`}>
              Scopri come funziona <span className="cta-arrow">›</span>
            </a>
            <a href="#whatsapp" className={`${linkCls} nudge-link t-body`}>
              Guarda il promemoria <span className="nudge">›</span>
            </a>
          </div>
          <div className="hero-mock relative mx-auto mt-14 max-w-5xl pb-16 sm:mt-20" style={{ "--hd": "0.3s" } as React.CSSProperties}>
            <LaptopMock />
            <div className="float-soft absolute -right-2 -bottom-2 hidden md:block lg:-right-10">
              <PhoneMock />
            </div>
          </div>
        </section>

        <section id="funzioni" className="bg-paper px-4 py-20 sm:py-28">
          <div className="mx-auto max-w-5xl">
            <p className="text-center t-headline text-accent">Funzioni</p>
            <h2 className="mt-2 text-center text-[34px] leading-tight font-bold tracking-tight sm:text-[48px]">Meno telefonate. Meno buchi in agenda.</h2>
            <div data-stagger className="mt-12 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {FEATURES.map((f) => (
                <article key={f.title} data-spot className="spot lift tile-host rounded-[18px] bg-card p-6 shadow-card">
                  <span className="tile inline-block">
                    <IconTile icon={f.icon} className={f.tile} />
                  </span>
                  <h3 className="mt-4 t-title3">{f.title}</h3>
                  <p className="mt-2 t-subhead text-ink-2">{f.text}</p>
                </article>
              ))}
            </div>
          </div>
        </section>

        <section id="whatsapp" className="bg-canvas px-4 py-20 sm:py-28">
          <div className="mx-auto grid max-w-5xl items-center gap-12 md:grid-cols-[1fr_auto]">
            <div>
              <p className="t-headline text-wa">WhatsApp Business</p>
              <h2 className="mt-2 text-[34px] leading-tight font-bold tracking-tight sm:text-[48px]">Il promemoria arriva dove il cliente lo legge.</h2>
              <p className="mt-4 max-w-xl text-[19px] leading-relaxed text-ink-2">
                Il giorno prima il cliente riceve il promemoria con tre pulsanti. Se conferma, l&apos;appuntamento diventa verde in agenda.
                Se sposta o disdice, lo slot torna libero e la nuova disponibilità è subito prenotabile.
              </p>
              <ul data-stagger className="mt-6 space-y-2 t-body text-ink-2">
                {["API ufficiali di Meta, nessuna automazione non autorizzata", "Link sicuri e con scadenza, senza dati personali", "Consenso ai messaggi raccolto e registrato"].map((t) => (
                  <li key={t} className="flex items-center gap-2">
                    <span className="pop grid h-5 w-5 place-items-center rounded-full bg-go-fill text-[12px] text-white">✓</span>
                    {t}
                  </li>
                ))}
              </ul>
            </div>
            <div data-reveal className="mx-auto">
              <PhoneMock />
            </div>
          </div>
        </section>

        <section id="domande" className="bg-paper px-4 py-20 sm:py-28">
          <div className="mx-auto max-w-3xl">
            <h2 className="text-center text-[34px] leading-tight font-bold tracking-tight sm:text-[48px]">Domande frequenti</h2>
            <div data-stagger className="mt-10 overflow-hidden rounded-[18px] bg-card shadow-card">
              {FAQ.map((f) => (
                <details key={f.q} className="faq group border-t border-rule first:border-t-0">
                  <summary className="flex cursor-pointer list-none items-center justify-between gap-4 px-6 py-5 t-headline [&::-webkit-details-marker]:hidden">
                    {f.q}
                    <span className="text-[22px] font-normal text-accent transition-transform duration-300 group-open:rotate-45">+</span>
                  </summary>
                  <p className="px-6 pb-5 t-body text-ink-2">{f.a}</p>
                </details>
              ))}
            </div>
          </div>
        </section>

        <footer className="border-t border-rule bg-paper px-4 py-8 text-center t-footnote text-ink-3">
          CoreNexus Agenda · in sviluppo
        </footer>
        <Motion />
      </main>
    </>
  );
}
