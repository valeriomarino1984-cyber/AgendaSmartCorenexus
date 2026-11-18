"use client";

import { CalendarClock, CheckCircle2, Circle, Settings, UserCog } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";
import { EmptyState, IconTile, PageHeader, Panel } from "@/components/ui";
import { api } from "@/lib/api";
import { useMe } from "@/lib/me";

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

  useEffect(() => {
    api<Studio>("/tenants/current").then(setStudio, () => null);
    if (owner) api<Member[]>("/tenants/current/users").then(setMembers, () => null);
  }, [owner]);

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
      <Panel title="Per iniziare" flush>
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
      </Panel>
      <Panel title="Agenda di oggi">
        <EmptyState
          icon={<CalendarClock />}
          title="L'agenda arriva con i prossimi aggiornamenti"
          text="Stiamo costruendo prestazioni, clienti e appuntamenti. Intanto puoi preparare lo studio e il team."
        />
      </Panel>
    </>
  );
}
