import { CalendarCheck2, CalendarX2, Clock3, MessageCircle, UserRoundX } from "lucide-react";
import { notFound } from "next/navigation";
import { STUDIO_NAV } from "@/components/AppNav";
import { AppShell } from "@/components/AppShell";
import {
  AddRow, Disclosure, Field, Monogram, Notice, PageHeader, Panel, ServiceChip, StatStrip, StatusTag, Tag,
  btnDanger, btnPrimary, btnSecondary, btnTinted, inputCls, type AppointmentStatus,
} from "@/components/ui";
import { SegmentedDemo } from "./SegmentedDemo";

/*
 * Catalogo dei componenti del design system, SOLO in sviluppo (in produzione risponde 404).
 * I dati qui sotto sono di esempio e servono esclusivamente a vedere i componenti.
 */

export const metadata = { title: "Anteprima componenti", robots: { index: false } };

const SAMPLE: { time: string; name: string; service: string; color: string; status: AppointmentStatus }[] = [
  { time: "09:00", name: "Giulia Ferri", service: "Prima visita", color: "#0071e3", status: "confirmed" },
  { time: "10:00", name: "Marco Conti", service: "Controllo", color: "#30b0c7", status: "pending" },
  { time: "11:00", name: "Sara Galli", service: "Seduta", color: "#5856d6", status: "cancelled_by_client" },
  { time: "12:00", name: "Luca Moretti", service: "Consulenza", color: "#ff9500", status: "no_show" },
  { time: "15:00", name: "Elena Rinaldi", service: "Controllo", color: "#30b0c7", status: "completed" },
];

export default function Anteprima() {
  if (process.env.NODE_ENV === "production") notFound();
  return (
    <AppShell
      items={STUDIO_NAV}
      studioName="Studio di esempio"
      roleLabel="Owner"
      userName="Anna Esempio"
      banner={
        <div role="status" className="rounded-[14px] bg-warn-soft px-5 py-3.5 t-subhead text-ink-2">
          <strong className="text-ink">Anteprima dei componenti.</strong> Pagina visibile solo in sviluppo, con dati di esempio.
        </div>
      }
    >
      <PageHeader meta="martedì 17 novembre" title="Oggi" actions={<button className={btnPrimary}>Nuovo appuntamento</button>} />
      <StatStrip
        items={[
          { label: "Confermati", value: 6, icon: <CalendarCheck2 />, tone: "go" },
          { label: "Da confermare", value: 2, icon: <Clock3 />, tone: "warn", emphasize: true },
          { label: "Disdetti", value: 1, icon: <CalendarX2 />, tone: "stamp" },
          { label: "WhatsApp inviati", value: 14, unit: "/ 100", icon: <MessageCircle />, tone: "accent", note: "Quota del mese" },
        ]}
      />
      <div className="grid gap-8 lg:grid-cols-[1fr_320px]">
        <Panel title="Appuntamenti" meta="5 oggi" flush actions={<SegmentedDemo />}>
          <ul>
            {SAMPLE.map((a) => (
              <Disclosure
                key={a.time}
                leading={<span className="num w-12 shrink-0 t-subhead font-semibold text-ink-2">{a.time}</span>}
                title={a.name}
                subtitle={a.service}
                muted={a.status.startsWith("cancelled")}
                trailing={<StatusTag status={a.status} />}
              >
                <div className="flex flex-wrap gap-2">
                  <button className={btnTinted}>Sposta</button>
                  <button className={btnSecondary}>Segna come svolto</button>
                  <button className={btnDanger}>Cancella</button>
                </div>
              </Disclosure>
            ))}
          </ul>
          <AddRow label="Aggiungi appuntamento">
            <div className="grid gap-4 sm:grid-cols-2">
              <Field label="Cliente">
                <input className={inputCls} placeholder="Cerca per nome o telefono" />
              </Field>
              <Field label="Data e ora" hint="Solo gli orari liberi del professionista">
                <input className={inputCls} type="datetime-local" />
              </Field>
            </div>
          </AddRow>
        </Panel>
        <div className="space-y-8">
          <Panel title="Blocchi in agenda">
            <div className="space-y-2">
              {SAMPLE.slice(0, 3).map((a) => (
                <ServiceChip key={a.time} color={a.color} time={a.time} title={a.service} subtitle={a.name} />
              ))}
            </div>
          </Panel>
          <Panel title="Etichette">
            <div className="flex flex-wrap gap-2">
              <Tag tone="wa">WhatsApp</Tag>
              <Tag tone="accent">Email</Tag>
              <Tag tone="neutral">Manuale</Tag>
              <Tag tone="go">Consegnato</Tag>
              <Tag tone="warn">In coda</Tag>
              <Tag tone="stamp">Non consegnato</Tag>
            </div>
          </Panel>
          <Panel title="Messaggi">
            <div className="space-y-3">
              <Notice state={{ ok: true, message: "Appuntamento confermato", detail: "promemoria annullati" }} />
              <Notice state={{ error: "Lo slot non è più disponibile: scegli un altro orario." }} />
              <p className="flex items-center gap-2 t-subhead text-ink-3">
                <Monogram name="Giulia Ferri" /> <UserRoundX className="h-4 w-4" /> Monogramma e icone
              </p>
            </div>
          </Panel>
        </div>
      </div>
    </AppShell>
  );
}
