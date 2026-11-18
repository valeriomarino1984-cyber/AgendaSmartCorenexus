"use client";

import { ChevronRight, Clock3, Stethoscope, UserCog, UserRound } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";
import { Field, IconTile, Notice, PageHeader, Panel, btnPrimary, inputCls, selectCls } from "@/components/ui";
import { LocationPanel } from "@/components/studio/LocationPanel";
import { useAction } from "@/components/auth/useAction";
import { api } from "@/lib/api";
import { useMe } from "@/lib/me";

interface Studio {
  name: string;
  slug: string;
  business_type: string;
  neutral_messaging: boolean;
  contact_email: string | null;
  contact_phone: string | null;
  address: string | null;
  cancellation_min_hours: number;
  email_confirmations: boolean;
  reminder_hours: number;
}
interface BusinessType { code: string; label: string }

export function StudioSettings() {
  const { me, refresh } = useMe();
  const canEdit = me.role === "owner";
  const [studio, setStudio] = useState<Studio | null>(null);
  const [types, setTypes] = useState<BusinessType[]>([]);
  const [saved, setSaved] = useState(false);
  const { pending, error, run } = useAction();

  useEffect(() => {
    api<Studio>("/tenants/current").then(setStudio, () => null);
    api<BusinessType[]>("/meta/business-types").then(setTypes, () => null);
  }, []);

  if (!studio) return <PageHeader title="Impostazioni" />;

  const set = <K extends keyof Studio>(key: K, value: Studio[K]) => {
    setSaved(false);
    setStudio({ ...studio, [key]: value });
  };

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!studio) return;
    const updated = await run(() =>
      api<Studio>("/tenants/current", {
        method: "PUT",
        body: {
          name: studio.name,
          business_type: studio.business_type,
          neutral_messaging: studio.neutral_messaging,
          contact_email: studio.contact_email || null,
          contact_phone: studio.contact_phone || null,
          address: studio.address || null,
          cancellation_min_hours: Number(studio.cancellation_min_hours),
          email_confirmations: studio.email_confirmations,
          reminder_hours: Number(studio.reminder_hours),
        },
      }),
    );
    if (updated) {
      setStudio(updated);
      setSaved(true);
      await refresh();
    }
  }

  return (
    <>
      <PageHeader meta={me.tenant.name} title="Impostazioni" />
      <form onSubmit={onSubmit} className="space-y-8">
        <fieldset disabled={!canEdit} className="space-y-8">
          {!canEdit && <Notice state={{ ok: true, message: "Solo il titolare può modificare i dati dello studio." }} />}
          <Panel title="Studio">
            <div className="grid gap-4 sm:grid-cols-2">
              <Field label="Nome dello studio">
                <input className={inputCls} required maxLength={120} value={studio.name} onChange={(e) => set("name", e.target.value)} />
              </Field>
              <Field label="Attività">
                <select className={selectCls} value={studio.business_type} onChange={(e) => set("business_type", e.target.value)}>
                  {types.map((t) => (
                    <option key={t.code} value={t.code}>{t.label}</option>
                  ))}
                </select>
              </Field>
              <Field label="Email di contatto">
                <input className={inputCls} type="email" value={studio.contact_email ?? ""} onChange={(e) => set("contact_email", e.target.value)} />
              </Field>
              <Field label="Telefono">
                <input className={inputCls} type="tel" value={studio.contact_phone ?? ""} onChange={(e) => set("contact_phone", e.target.value)} />
              </Field>
              <div className="sm:col-span-2">
                <Field label="Indirizzo">
                  <input className={inputCls} maxLength={200} value={studio.address ?? ""} onChange={(e) => set("address", e.target.value)} />
                </Field>
              </div>
            </div>
          </Panel>
          <Panel title="Appuntamenti e messaggi">
            <div className="space-y-5">
              <Field label="Preavviso minimo per disdire o spostare" hint="Entro questo limite il cliente vedrà i contatti dello studio invece del pulsante Disdici.">
                <select className={selectCls} value={studio.cancellation_min_hours}
                  onChange={(e) => set("cancellation_min_hours", Number(e.target.value))}>
                  {[0, 2, 6, 12, 24, 48, 72].map((h) => (
                    <option key={h} value={h}>{h === 0 ? "Nessun limite" : `${h} ore prima`}</option>
                  ))}
                </select>
              </Field>
              <label className="flex items-start gap-3">
                <input type="checkbox" className="mt-1 h-4 w-4 accent-[var(--color-accent)]" checked={studio.neutral_messaging}
                  onChange={(e) => set("neutral_messaging", e.target.checked)} />
                <span>
                  <span className="block t-body">Messaggi discreti</span>
                  <span className="block t-footnote text-ink-3">
                    Promemoria con testo neutro, senza il tipo di prestazione. Consigliato per le professioni sanitarie.
                  </span>
                </span>
              </label>
            </div>
          </Panel>
          <Panel title="Notifiche ai clienti" meta="Email">
            <div className="space-y-5">
              <label className="flex items-start gap-3">
                <input type="checkbox" className="mt-1 h-4 w-4 accent-[var(--color-accent)]" checked={studio.email_confirmations}
                  onChange={(e) => set("email_confirmations", e.target.checked)} />
                <span>
                  <span className="block t-body">Conferme e avvisi</span>
                  <span className="block t-footnote text-ink-3">
                    Email al cliente quando un appuntamento viene fissato, spostato o annullato, con il link della visita online.
                  </span>
                </span>
              </label>
              <Field label="Promemoria" hint="Email di promemoria prima dell'appuntamento.">
                <select className={selectCls} value={studio.reminder_hours}
                  onChange={(e) => set("reminder_hours", Number(e.target.value))}>
                  {[0, 2, 6, 12, 24, 48, 72].map((h) => (
                    <option key={h} value={h}>{h === 0 ? "Nessun promemoria" : `${h} ore prima`}</option>
                  ))}
                </select>
              </Field>
              <p className="t-footnote text-ink-3">
                Le email partono solo ai clienti con indirizzo email e consenso ai promemoria via email. L&apos;esito di ogni invio è nella pagina Notifiche.
              </p>
            </div>
          </Panel>
        </fieldset>
        {canEdit && (
          <div className="flex flex-wrap items-center gap-3">
            <button className={`${btnPrimary} cta`} disabled={pending}>{pending ? "Salvataggio…" : "Salva"}</button>
            {saved && <Notice state={{ ok: true, message: "Impostazioni salvate" }} />}
            {error && <Notice state={{ error: error.message }} />}
          </div>
        )}
      </form>
      <LocationPanel canEdit={canEdit} />
      <StudioLinks owner={canEdit} />
    </>
  );
}

/** Su telefono la barra in basso ha poco spazio: le altre sezioni dello studio si raggiungono da qui. */
function StudioLinks({ owner }: { owner: boolean }) {
  const links = [
    { href: "/app/prestazioni", label: "Prestazioni", icon: <Stethoscope />, tile: "bg-sys-teal" },
    { href: "/app/disponibilita", label: "Disponibilità", icon: <Clock3 />, tile: "bg-sys-green" },
    { href: "/app/professionisti", label: "Professionisti", icon: <UserRound />, tile: "bg-sys-indigo" },
    ...(owner ? [{ href: "/app/collaboratori", label: "Collaboratori", icon: <UserCog />, tile: "bg-sys-orange" }] : []),
  ];
  return (
    <div className="lg:hidden">
      <Panel title="Studio" flush>
        <ul>
          {links.map((l) => (
            <li key={l.href} className="group/row">
              <Link href={l.href} className="flex min-h-[52px] items-center gap-3.5 pl-5 hover:bg-ink/[0.03]">
                <IconTile icon={l.icon} className={l.tile} />
                <span className="flex min-h-[52px] flex-1 items-center border-t border-rule pr-4 t-body group-first/row:border-t-0">
                  <span className="flex-1">{l.label}</span>
                  <ChevronRight className="h-[17px] w-[17px] text-ink-3/60" strokeWidth={2.4} />
                </span>
              </Link>
            </li>
          ))}
        </ul>
      </Panel>
    </div>
  );
}
