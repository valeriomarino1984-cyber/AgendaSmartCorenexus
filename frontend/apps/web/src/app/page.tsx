import type { CSSProperties, ReactNode } from "react";
import {
  BellRing, CalendarClock, CalendarRange, Clock3, Globe, Lock, ShieldCheck, Sparkles, Stethoscope, Users, UserCog, Video,
} from "lucide-react";
import { Logo } from "@/components/Logo";
import { Motion } from "@/components/Motion";
import { Splash } from "@/components/Splash";
import { LaptopMock, PhoneMock } from "@/components/landing/Mocks";
import { DragAgendaMock, SlotsMock, VideoCallMock } from "@/components/landing/Showcase";
import { IconTile, btnPrimary, linkCls } from "@/components/ui";

const v = (name: string, value: string) => ({ [name]: value }) as CSSProperties;

type Status = "live" | "soon";

const FEATURES: { icon: ReactNode; tile: string; title: string; text: string; status: Status }[] = [
  {
    icon: <CalendarRange />,
    tile: "bg-accent",
    title: "Agenda giorno, settimana, mese",
    text: "I colori delle prestazioni, l'ora attuale, i professionisti a colpo d'occhio. Sposti un appuntamento trascinandolo.",
    status: "live",
  },
  {
    icon: <Video />,
    tile: "bg-sys-indigo",
    title: "Visite online",
    text: "Per le prestazioni online il link della videochiamata si crea da solo, diverso per ogni appuntamento.",
    status: "live",
  },
  {
    icon: <CalendarClock />,
    tile: "bg-sys-green",
    title: "Mai due clienti nello stesso orario",
    text: "Durata, tempo di preparazione, ferie e festività: gli orari liberi sono calcolati e le sovrapposizioni rifiutate.",
    status: "live",
  },
  {
    icon: <Users />,
    tile: "bg-sys-teal",
    title: "Clienti e consensi",
    text: "Anagrafica, ricerca per nome o telefono, avviso sui doppioni e storico dei consensi a email, WhatsApp e promozioni.",
    status: "live",
  },
  {
    icon: <Stethoscope />,
    tile: "bg-sys-orange",
    title: "Pronta per la tua professione",
    text: "Fisioterapisti, osteopati, nutrizionisti e psicologi trovano già le prestazioni tipiche, da modificare come vogliono.",
    status: "live",
  },
  {
    icon: <UserCog />,
    tile: "bg-ink-3",
    title: "Team e ruoli",
    text: "Titolare, professionisti e segreteria: ognuno vede e gestisce ciò che gli spetta, con il registro delle attività.",
    status: "live",
  },
  {
    icon: <Globe />,
    tile: "bg-accent",
    title: "Prenotazione online",
    text: "Una pagina dello studio con prestazioni e orari liberi: il cliente prenota da solo, anche dal telefono.",
    status: "soon",
  },
  {
    icon: <BellRing />,
    tile: "bg-wa",
    title: "Conferme e promemoria",
    text: "Email e WhatsApp con le API ufficiali di Meta, con il link della visita online e i pulsanti Conferma, Sposta, Disdici.",
    status: "soon",
  },
];

const PROFESSIONS = ["Fisioterapisti", "Nutrizionisti", "Psicologi", "Osteopati", "Psicoterapeuti", "Biologi nutrizionisti", "Massoterapisti", "Centri multidisciplinari", "Studi professionali", "Personal trainer"];

const PROFILES = [
  { name: "Fisioterapista", color: "#30b0c7", services: [["Valutazione fisioterapica", "60′"], ["Seduta di fisioterapia", "45′"], ["Terapia manuale", "30′"]] },
  { name: "Osteopata", color: "#5856d6", services: [["Prima visita osteopatica", "60′"], ["Trattamento osteopatico", "45′"]] },
  { name: "Nutrizionista", color: "#34c759", services: [["Prima visita", "60′"], ["Controllo", "30′"], ["Controllo online", "30′", "online"]] },
  { name: "Psicologa", color: "#ff9500", services: [["Primo colloquio", "60′"], ["Colloquio", "50′"], ["Colloquio online", "50′", "online"]] },
];

const TRUST = [
  { icon: <Lock />, title: "Ogni studio vede solo i propri dati", text: "Separazione controllata dal sistema su ogni richiesta e verificata dai test." },
  { icon: <ShieldCheck />, title: "Nessun dato clinico", text: "Solo dati amministrativi. Nel link della videochiamata non c'è nessun nome." },
  { icon: <Clock3 />, title: "Ora legale e festività", text: "Le 9:00 restano le 9:00 dopo il cambio dell'ora; le festività nazionali sono già chiuse." },
  { icon: <Sparkles />, title: "Server in Europa", text: "Applicazione e database su hosting italiano, accesso con password protette e sessioni sicure." },
];

const FAQ = [
  {
    q: "Come funzionano le visite online?",
    a: "Per ogni prestazione scegli se si svolge in studio, online o in entrambi i modi. Quando prenoti un appuntamento online il link della videochiamata (Jitsi) si crea da solo: lo apri dall'agenda o dalla dashboard e lo copi per il cliente. L'invio automatico nella conferma e nei promemoria arriverà con le notifiche.",
  },
  {
    q: "Due persone possono prenotare lo stesso orario?",
    a: "No. Anche se due prenotazioni arrivano nello stesso istante, solo la prima va a buon fine; l'altra riceve \"orario già occupato\". Il tempo di preparazione dopo la visita conta come occupato.",
  },
  {
    q: "Per quali professioni è pensata?",
    a: "Fisioterapisti, osteopati, nutrizionisti e psicologi hanno un profilo dedicato con le prestazioni tipiche già pronte; per le altre attività c'è un profilo generico da personalizzare.",
  },
  {
    q: "Quando arrivano i promemoria su WhatsApp?",
    a: "Sono in preparazione: conferme e promemoria partiranno via email e, per chi ha dato il consenso, su WhatsApp con le API ufficiali di Meta. Ogni studio userà il proprio numero.",
  },
  {
    q: "Chi della squadra può fare cosa?",
    a: "Il titolare gestisce tutto. La segreteria gestisce agenda e clienti di tutti. Ogni professionista vede e gestisce solo la propria agenda.",
  },
];

function StatusTag({ status }: { status: Status }) {
  return status === "live" ? (
    <span className="inline-flex items-center gap-1.5 rounded-full bg-go-soft px-2.5 py-0.5 t-caption font-semibold text-go">
      <span className="live-dot h-1.5 w-1.5 rounded-full bg-current" /> Disponibile
    </span>
  ) : (
    <span className="inline-flex items-center rounded-full bg-paper-2 px-2.5 py-0.5 t-caption font-semibold text-ink-3">In arrivo</span>
  );
}

function SectionTitle({ eyebrow, title, text, tone = "text-accent", center = false }: { eyebrow: string; title: string; text?: string; tone?: string; center?: boolean }) {
  return (
    <div className={center ? "text-center" : ""}>
      <p className={`t-headline ${tone}`}>{eyebrow}</p>
      <h2 className="mt-2 text-[34px] leading-tight font-bold tracking-tight sm:text-[48px]">{title}</h2>
      {text && <p className={`mt-4 text-[19px] leading-relaxed text-ink-2 ${center ? "mx-auto max-w-2xl" : "max-w-xl"}`}>{text}</p>}
    </div>
  );
}

function Checks({ items }: { items: string[] }) {
  return (
    <ul data-stagger className="mt-6 space-y-2.5 t-body text-ink-2">
      {items.map((t) => (
        <li key={t} className="flex items-start gap-2.5">
          <span className="pop mt-0.5 grid h-5 w-5 shrink-0 place-items-center rounded-full bg-go-fill text-[12px] text-white">✓</span>
          {t}
        </li>
      ))}
    </ul>
  );
}

export default function Home() {
  return (
    <>
      <Splash />
      <header className="glass head-scroll sticky top-0 z-30 border-b border-ink/10">
        <div className="mx-auto flex h-12 max-w-5xl items-center justify-between px-4 sm:px-6">
          <Logo />
          <nav className="hidden gap-7 t-subhead text-ink-2 md:flex">
            {[["#funzioni", "Funzioni"], ["#agenda", "Agenda"], ["#visite-online", "Visite online"], ["#professioni", "Professioni"], ["#domande", "Domande"]].map(([href, label]) => (
              <a key={href} href={href} className="nav-u hover:text-ink">{label}</a>
            ))}
          </nav>
          <a href="/accedi" className="rounded-full bg-accent px-4 py-1.5 t-footnote font-semibold text-white transition hover:bg-accent-hover">
            Accedi
          </a>
        </div>
        <span className="scroll-bar" aria-hidden />
      </header>

      <main className="bg-canvas">
        <section className="relative overflow-hidden px-4 pt-16 text-center sm:pt-24">
          <div className="aurora" aria-hidden>
            <span />
            <span />
            <span />
          </div>
          <div className="relative z-10">
            <p className="hero-seq t-headline text-accent">
              Per{" "}
              <span className="word-cycle" aria-label="studi e liberi professionisti">
                {["fisioterapisti", "nutrizionisti", "psicologi", "osteopati", "studi e centri"].map((w, i) => (
                  <span key={w} aria-hidden style={v("--i", String(i))}>{w}</span>
                ))}
              </span>
            </p>
            <h1 className="hero-seq mt-2 text-[56px] leading-none font-bold tracking-[-0.04em] sm:text-[96px]" style={v("--hd", "0.08s")}>
              Agenda
            </h1>
            <p className="hero-seq mx-auto mt-4 max-w-2xl text-[24px] leading-tight font-semibold tracking-tight text-ink-3 sm:text-[34px]" style={v("--hd", "0.16s")}>
              Appuntamenti, clienti e visite online. Senza doppie prenotazioni.
            </p>
            <div className="hero-seq mt-8 flex flex-wrap items-center justify-center gap-6" style={v("--hd", "0.24s")}>
              <a href="#funzioni" className={`${btnPrimary} cta shine shine-auto h-12 px-7 t-body`}>
                Scopri come funziona <span className="cta-arrow">›</span>
              </a>
              <a href="#visite-online" className={`${linkCls} nudge-link t-body`}>
                Le visite online <span className="nudge">›</span>
              </a>
            </div>
            <div className="hero-mock relative mx-auto mt-14 max-w-5xl pb-16 sm:mt-20" style={v("--hd", "0.3s")}>
              <div className="scroll-fade-out">
                <LaptopMock />
              </div>
              <div className="float-soft absolute -right-2 bottom-6 hidden items-center gap-3 rounded-[16px] bg-card/90 p-3 pr-4 text-left shadow-[0_20px_50px_-20px_rgb(0_0_0/0.45)] backdrop-blur md:flex lg:-right-10">
                <IconTile icon={<Video />} className="bg-sys-indigo" />
                <span>
                  <span className="block t-subhead font-semibold">Visita online · 10:00</span>
                  <span className="block t-caption text-ink-3">Link della videochiamata creato</span>
                </span>
              </div>
            </div>
          </div>
        </section>

        <section aria-label="Professioni" className="border-y border-rule bg-paper py-5">
          <div className="marquee">
            <div>
              {[...PROFESSIONS, ...PROFESSIONS].map((p, i) => (
                <span key={i} aria-hidden={i >= PROFESSIONS.length} className="whitespace-nowrap rounded-full bg-card px-4 py-1.5 t-subhead text-ink-2 shadow-card">{p}</span>
              ))}
            </div>
          </div>
        </section>

        <section id="funzioni" className="bg-paper px-4 py-20 sm:py-28">
          <div className="mx-auto max-w-5xl">
            <SectionTitle center eyebrow="Funzioni" title="Meno telefonate. Meno buchi in agenda." text="Quello che puoi usare oggi e quello che arriva a breve, senza promesse a vuoto." />
            <div data-stagger className="mt-12 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
              {FEATURES.map((f) => (
                <article key={f.title} data-spot className={`spot lift tile-host flex flex-col rounded-[18px] bg-card p-6 shadow-card ${f.status === "soon" ? "opacity-80" : ""}`}>
                  <div className="flex items-start justify-between gap-2">
                    <span className="tile inline-block"><IconTile icon={f.icon} className={f.tile} /></span>
                    <StatusTag status={f.status} />
                  </div>
                  <h3 className="mt-4 t-headline">{f.title}</h3>
                  <p className="mt-2 t-subhead text-ink-2">{f.text}</p>
                </article>
              ))}
            </div>
          </div>
        </section>

        <section id="agenda" className="fade-top overflow-hidden bg-canvas px-4 py-20 sm:py-28" style={v("--fade-from", "var(--color-paper)")}>
          <div className="mx-auto grid max-w-5xl items-center gap-14 md:grid-cols-[1fr_1.15fr]">
            <div>
              <SectionTitle
                eyebrow="Agenda"
                title="Trascina. È spostato."
                text="Prendi un appuntamento e portalo in un altro giorno o orario: se è libero viene spostato, se c'è già qualcuno te lo dice subito. Fuori orario o in un giorno festivo chiede conferma."
              />
              <Checks items={["Viste giorno, settimana e mese, filtro per professionista", "Tocchi uno spazio libero e prenoti: l'orario è già compilato", "Storico di ogni modifica: chi ha spostato cosa e quando"]} />
            </div>
            <div className="scroll-fade">
              <DragAgendaMock />
            </div>
          </div>
          <div className="mx-auto mt-24 grid max-w-5xl items-center gap-14 md:grid-cols-[1fr_1fr]">
            <div data-reveal className="order-2 md:order-1">
              <SlotsMock />
            </div>
            <div className="order-1 md:order-2">
              <SectionTitle
                eyebrow="Orari liberi"
                tone="text-sys-green"
                title="Gli orari giusti, già pronti."
                text="Imposti una volta l'orario settimanale, le ferie e le chiusure. Quando prenoti vedi solo gli orari in cui la prestazione ci sta davvero, con il tempo di preparazione."
              />
              <Checks items={["Più fasce al giorno, per esempio 9–13 e 15–19", "Festività nazionali chiuse in automatico, aperture straordinarie quando vuoi", "Due prenotazioni nello stesso istante? Ne passa una sola"]} />
            </div>
          </div>
        </section>

        <section id="visite-online" className="relative overflow-hidden bg-[#0b0b0f] px-4 py-20 text-white sm:py-28">
          <div className="aurora aurora-fill opacity-70" aria-hidden>
            <span />
            <span />
            <span />
          </div>
          <div className="relative z-10 mx-auto grid max-w-5xl items-center gap-14 md:grid-cols-[1fr_1.1fr]">
            <div>
              <p className="t-headline text-[#64d2ff]">Visite online</p>
              <h2 className="mt-2 text-[34px] leading-tight font-bold tracking-tight sm:text-[48px]">La videochiamata è già nell&apos;appuntamento.</h2>
              <p className="mt-4 max-w-xl text-[19px] leading-relaxed text-white/70">
                Controlli, colloqui e consulenze a distanza: scegli una prestazione online e il link della stanza si crea da solo.
                Lo apri con un clic dall&apos;agenda o dalla dashboard.
              </p>
              <ul data-stagger className="mt-6 space-y-2.5 t-body text-white/80">
                {[
                  "Un link diverso per ogni appuntamento",
                  "Nel nome della stanza nessun dato dello studio o del cliente",
                  "Prestazioni in studio, online o in entrambi i modi",
                  "Videochiamata con Jitsi, senza installare nulla",
                ].map((t) => (
                  <li key={t} className="flex items-start gap-2.5">
                    <span className="pop mt-0.5 grid h-5 w-5 shrink-0 place-items-center rounded-full bg-[#30d158] text-[12px] text-black">✓</span>
                    {t}
                  </li>
                ))}
              </ul>
            </div>
            <div data-reveal>
              <VideoCallMock />
            </div>
          </div>
        </section>

        <section id="professioni" className="bg-paper px-4 py-20 sm:py-28">
          <div className="mx-auto max-w-5xl">
            <SectionTitle center eyebrow="Profili professionali" tone="text-sys-orange" title="Parti con le prestazioni già pronte." text="Alla registrazione scegli la tua attività: trovi le prestazioni tipiche con durata e modalità. Le cambi quando vuoi." />
            <div data-stagger className="mt-12 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
              {PROFILES.map((p) => (
                <article key={p.name} data-spot className="spot lift rounded-[18px] bg-card p-5 shadow-card">
                  <p className="flex items-center gap-2 t-headline">
                    <span className="h-3 w-3 rounded-full" style={{ background: p.color }} />
                    {p.name}
                  </p>
                  <ul className="mt-4 space-y-2">
                    {p.services.map(([name, dur, mode]) => (
                      <li key={name} className="svc-chip flex items-center justify-between gap-2 rounded-[8px] px-2.5 py-1.5 t-footnote font-semibold" style={v("--sc", p.color)}>
                        <span className="truncate">{name}</span>
                        <span className="flex shrink-0 items-center gap-1 opacity-80">
                          {mode && <Video className="h-3.5 w-3.5" />}
                          {dur}
                        </span>
                      </li>
                    ))}
                  </ul>
                </article>
              ))}
            </div>
            <p className="mt-6 text-center t-subhead text-ink-3">Altre attività? C&apos;è un profilo generico da personalizzare.</p>
          </div>
        </section>

        <section className="bg-canvas px-4 py-20 sm:py-28">
          <div className="mx-auto max-w-5xl">
            <SectionTitle center eyebrow="Fiducia" tone="text-sys-teal" title="Fatta per i dati delle persone." />
            <div data-stagger className="mt-12 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
              {TRUST.map((t) => (
                <div key={t.title} className="tile-host rounded-[18px] bg-paper p-5">
                  <span className="tile inline-block"><IconTile icon={t.icon} className="bg-sys-teal" /></span>
                  <h3 className="mt-3 t-headline">{t.title}</h3>
                  <p className="mt-1.5 t-subhead text-ink-2">{t.text}</p>
                </div>
              ))}
            </div>
          </div>
        </section>

        <section id="whatsapp" className="bg-paper px-4 py-20 sm:py-28">
          <div className="mx-auto grid max-w-5xl items-center gap-12 md:grid-cols-[1fr_auto]">
            <div>
              <p className="flex items-center gap-2 t-headline text-wa">
                Conferme e promemoria <StatusTag status="soon" />
              </p>
              <h2 className="mt-2 text-[34px] leading-tight font-bold tracking-tight sm:text-[48px]">Il promemoria arriverà dove il cliente lo legge.</h2>
              <p className="mt-4 max-w-xl text-[19px] leading-relaxed text-ink-2">
                Conferma alla prenotazione e promemoria prima dell&apos;appuntamento, via email e su WhatsApp, con il link della visita online e tre
                pulsanti: Conferma, Sposta, Disdici.
              </p>
              <Checks items={["API ufficiali di Meta, nessuna automazione non autorizzata", "Messaggi solo a chi ha dato il consenso, già registrato oggi nella scheda cliente", "Link sicuri e con scadenza, senza dati personali"]} />
            </div>
            <div data-reveal className="mx-auto">
              <PhoneMock />
            </div>
          </div>
        </section>

        <section id="domande" className="bg-canvas px-4 py-20 sm:py-28">
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

        <section className="relative overflow-hidden bg-paper px-4 py-24 text-center">
          <div className="aurora aurora-fill" aria-hidden>
            <span />
            <span />
            <span />
          </div>
          <div className="relative z-10">
            <h2 className="text-[34px] leading-tight font-bold tracking-tight sm:text-[48px]">La tua agenda, finalmente in ordine.</h2>
            <p className="mx-auto mt-3 max-w-xl text-[19px] text-ink-2">Accedi all&apos;area riservata del tuo studio.</p>
            <a href="/accedi" className={`${btnPrimary} cta shine shine-auto mt-8 h-12 px-8 t-body`} style={v("--sd", "1s")}>
              Accedi <span className="cta-arrow">›</span>
            </a>
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
