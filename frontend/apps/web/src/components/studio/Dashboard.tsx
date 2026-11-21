"use client";

import { CalendarClock, CheckCircle2, Circle, Clock3, Settings, UserCog, Video } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";
import { EmptyState, IconTile, PageHeader, Panel, Tag, linkCls } from "@/components/ui";
import { api } from "@/lib/api";
import { STATUS_TONE, addDays, formatTime, toInstant, today as todayIn, type Appointment, type WeeklyRule } from "@/lib/agenda";
import type { Location, Professional } from "@/lib/catalog";
import { useMe } from "@/lib/me";
import { StudioNumbers } from "./StudioNumbers";

interface Studio { contact_email: string | null; contact_phone: string | null; address: string | null }
interface Member { status: string }

function today() {
  return new Intl.DateTimeFormat("it-IT", { weekday: "long", day: "numeric", month: "long" }).format(new Date());
}

export function Dashboard() {
  const { me } = useMe();
  const owner = me.role === "owner";
  const [studio, setStudio] = useState<Studio | null>(null);
  const [members, setMembers] = useState<Member[] | null>(null);
  const [hasHours, setHasHours] = useState<boolean | null>(null);
  const [agenda, setAgenda] = useState<{ tz: string; items: Appointment[] } | null>(null);

  useEffect(() => {
    api<Studio>("/tenants/current").then(setStudio, () => null);
    if (owner) api<Member[]>("/tenants/current/users").then(setMembers, () => null);
    api<Professional[]>("/professionals").then(async (profs) => {
      const mine = profs.find((p) => p.user_id === me.user.id);
      if (mine) setHasHours((await api<WeeklyRule[]>(`/professionals/${mine.id}/availability`)).length > 0);
    }, () => null);
    api<Location[]>("/locations").then(async (locs) => {
      const tz = locs.find((l) => l.is_default)?.timezone ?? "Europe/Rome";
      const day = todayIn(tz);
      const q = new URLSearchParams({ from: toInstant(day, 0, tz), to: toInstant(addDays(day, 1), 0, tz) });
      setAgenda({ tz, items: await api<Appointment[]>(`/appointments?${q}`) });
    }, () => null);
  }, [owner, me.user.id]);

  const steps = [
    {
      done: Boolean(studio?.contact_email || studio?.contact_phone),
      title: "Completa i dati dello studio",
      text: "Contatti e indirizzo compariranno nella pagina di prenotazione.",
      href: "/app/impostazioni",
      icon: <Settings />,
      tile: "bg-ink-3",
      show: true,
    },
    {
      done: Boolean(hasHours),
      title: "Imposta i tuoi orari",
      text: "Giorni e fasce in cui ricevi: servono per proporre gli orari liberi.",
      href: "/app/disponibilita",
      icon: <Clock3 />,
      tile: "bg-sys-teal",
      show: hasHours !== null,
    },
    {
      done: (members?.length ?? 0) > 1,
      title: "Invita i collaboratori",
      text: "Professionisti e segreteria accedono con il proprio account.",
      href: "/app/collaboratori",
      icon: <UserCog />,
      tile: "bg-sys-indigo",
      show: owner,
    },
  ].filter((s) => s.show);

  return (
    <>
      <PageHeader meta={today()} title={`Ciao, ${me.user.full_name.split(" ")[0]}`} />
      {steps.some((st) => !st.done) && <Panel title="Per iniziare" flush>
        <ul>
          {steps.map((s) => (
            <li key={s.href} className="border-t border-rule first:border-t-0">
              <Link href={s.href} className="flex items-center gap-3.5 px-5 py-4 transition-colors hover:bg-ink/[0.03]">
                <IconTile icon={s.icon} className={s.tile} />
                <span className="min-w-0 flex-1">
                  <span className="block t-body">{s.title}</span>
                  <span className="block t-footnote text-ink-3">{s.text}</span>
                </span>
                {s.done ? (
                  <CheckCircle2 className="h-5 w-5 text-go" aria-label="Fatto" />
                ) : (
                  <Circle className="h-5 w-5 text-rule-strong" aria-label="Da fare" />
                )}
              </Link>
            </li>
          ))}
        </ul>
      </Panel>}
      <Panel
        title="Agenda di oggi"
        meta={agenda ? `${agenda.items.length} ${agenda.items.length === 1 ? "appuntamento" : "appuntamenti"}` : undefined}
        actions={<Link href="/app/agenda" className={linkCls}>Apri l&apos;agenda</Link>}
        flush
      >
        {agenda && agenda.items.length === 0 && (
          <EmptyState icon={<CalendarClock />} title="Nessun appuntamento oggi" text="Gli appuntamenti si prenotano dall'agenda." />
        )}
        <ul>
          {agenda?.items.map((a) => (
            <li key={a.id} className="flex min-h-[56px] items-center gap-3.5 border-t border-rule px-5 py-2.5 first:border-t-0">
              <span className="num w-12 shrink-0 t-subhead font-semibold">{formatTime(a.start_at, agenda.tz)}</span>
              <span aria-hidden className="h-8 w-1 shrink-0 rounded-full" style={{ background: a.color }} />
              <span className="min-w-0 flex-1">
                <span className="block truncate t-body">{a.client_name}</span>
                <span className="block truncate t-footnote text-ink-3">{a.service_name} · {a.professional_name}</span>
              </span>
              {a.is_online && a.video_url && (
                <a href={a.video_url} target="_blank" rel="noopener noreferrer" aria-label="Apri videochiamata" className="grid h-8 w-8 place-items-center rounded-full bg-accent/12 text-accent">
                  <Video className="h-4 w-4" />
                </a>
              )}
              <span className="hidden sm:block"><Tag tone={STATUS_TONE[a.status]}>{a.status_label}</Tag></span>
            </li>
          ))}
        </ul>
      </Panel>
      {agenda && <StudioNumbers tz={agenda.tz} canFilter={me.role !== "professional"} />}
    </>
  );
}
