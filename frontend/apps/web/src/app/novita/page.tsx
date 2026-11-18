import { ArrowUpRight, CalendarRange, Clock3, Timer, LockKeyhole, Sparkles, Stethoscope, UserCog, Users, Video } from "lucide-react";
import Link from "next/link";
import type { ReactNode } from "react";
import { Logo } from "@/components/Logo";
import { SiteFooter } from "@/components/SiteFooter";
import { IconTile, btnPrimary } from "@/components/ui";
import { APP_NAME } from "@/lib/brand";
import { CONTACT_PAGE } from "@/lib/contacts";

export const metadata = { title: `Novità di ${APP_NAME}`, description: `Gli ultimi aggiornamenti di ${APP_NAME}.` };

const releases: { label: string; items: { icon: ReactNode; tile: string; title: string; text: string }[] }[] = [
  {
    label: "18 novembre 2026 · versione 0.5",
    items: [
      { icon: <Timer />, tile: "bg-sys-orange", title: "Uscita automatica per sicurezza", text: "Nell'area clienti un timer in alto a destra chiude la sessione dopo 5 minuti senza attività, con un avviso 30 secondi prima per restare connessi. I professionisti escono dopo un'ora senza attività." },
    ],
  },
  {
    label: "18 novembre 2026 · versione 0.4",
    items: [
      { icon: <Users />, tile: "bg-sys-teal", title: "Area clienti", text: "I clienti entrano con un link via email, senza password: vedono i loro appuntamenti, aprono la visita online e possono disdire nei tempi stabiliti dallo studio." },
      { icon: <Sparkles />, tile: "bg-accent", title: "Nuova pagina di presentazione", text: "Funzioni con l'indicazione di cosa è già disponibile, visite online, profili per professione e contatti diretti, anche su WhatsApp." },
    ],
  },
  {
    label: "18 novembre 2026 · versione 0.3",
    items: [
      { icon: <CalendarRange />, tile: "bg-accent", title: "Agenda giorno, settimana e mese", text: "Prenoti toccando uno spazio libero e sposti gli appuntamenti trascinandoli. Due prenotazioni nello stesso istante? Ne passa una sola." },
      { icon: <Video />, tile: "bg-sys-indigo", title: "Visite online", text: "Per le prestazioni online il link della videochiamata si crea da solo, diverso per ogni appuntamento." },
      { icon: <Clock3 />, tile: "bg-sys-green", title: "Orari, ferie e festività", text: "Orario settimanale per professionista, ferie, chiusure e aperture straordinarie; festività nazionali già chiuse." },
    ],
  },
  {
    label: "18 novembre 2026 · versione 0.2",
    items: [
      { icon: <Stethoscope />, tile: "bg-sys-orange", title: "Prestazioni e profili professionali", text: "Fisioterapisti, osteopati, nutrizionisti e psicologi partono con le prestazioni tipiche già pronte." },
      { icon: <Users />, tile: "bg-sys-teal", title: "Clienti e consensi", text: "Anagrafica con ricerca, avviso sui doppioni e storico dei consensi a email, WhatsApp e promozioni." },
    ],
  },
  {
    label: "18 novembre 2026 · versione 0.1",
    items: [
      { icon: <LockKeyhole />, tile: "bg-[#1d1d1f]", title: "Accesso sicuro", text: "Registrazione dello studio con conferma via email, sessioni protette e registro delle attività." },
      { icon: <UserCog />, tile: "bg-ink-3", title: "Team e ruoli", text: "Titolare, professionisti e segreteria, ognuno con i propri permessi." },
    ],
  },
];

export default function Novita() {
  return (
    <>
      <header className="glass sticky top-0 z-30 border-b border-ink/10">
        <div className="mx-auto flex h-12 max-w-5xl items-center justify-between px-4 sm:px-6">
          <Logo />
          <Link href="/" className="t-footnote text-link hover:underline">Torna al sito</Link>
        </div>
      </header>
      <main className="bg-paper px-4 py-16 sm:py-24">
        <div className="mx-auto max-w-3xl">
          <p className="text-center t-headline text-accent">Novità</p>
          <h1 className="mt-2 text-center text-[40px] leading-tight font-bold tracking-tight sm:text-[56px]">Cosa c&apos;è di nuovo in {APP_NAME}.</h1>
          <div className="mt-14 space-y-12">
            {releases.map((r) => (
              <section key={r.label} className="animate-rise">
                <h2 className="px-1 t-subhead font-semibold text-ink-3">{r.label}</h2>
                <ul className="mt-3 overflow-hidden rounded-[18px] bg-card shadow-card">
                  {r.items.map((it) => (
                    <li key={it.title} className="flex gap-4 border-t border-rule px-5 py-4 first:border-t-0">
                      <IconTile icon={it.icon} className={it.tile} />
                      <div>
                        <p className="t-headline">{it.title}</p>
                        <p className="mt-1 t-subhead text-ink-2">{it.text}</p>
                      </div>
                    </li>
                  ))}
                </ul>
              </section>
            ))}
          </div>
          <div className="mt-14 text-center">
            <a href={CONTACT_PAGE} target="_blank" rel="noopener noreferrer" className={`${btnPrimary} cta h-12 px-7 t-body`}>
              Richiedi una prova gratuita <ArrowUpRight className="h-[18px] w-[18px]" />
            </a>
          </div>
        </div>
      </main>
      <SiteFooter />
    </>
  );
}
