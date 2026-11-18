"use client";

import { CalendarDays, LogOut, MapPin, Phone, Video } from "lucide-react";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { AuthShell } from "@/components/AuthShell";
import { Logo } from "@/components/Logo";
import { VersionFooter } from "@/components/VersionFooter";
import { AreaSwitch } from "@/components/auth/AreaSwitch";
import { useAction } from "@/components/auth/useAction";
import { EmptyState, Field, Notice, Tag, btnDanger, btnPrimary, btnSecondary, inputCls } from "@/components/ui";
import { STATUS_TONE, formatDay, formatTime, zoned } from "@/lib/agenda";
import { api, ApiError } from "@/lib/api";
import { formatPhone } from "@/lib/catalog";
import type { PortalAppointment, PortalOverview } from "@/lib/clientPortal";

/** Area clienti: senza sessione mostra l'accesso con link via email, altrimenti gli appuntamenti. */
export function ClientArea() {
  const [data, setData] = useState<PortalOverview | null | "login">(null);

  const load = useCallback(() => {
    api<PortalOverview>("/client-portal/me").then(setData, (e) => {
      if (e instanceof ApiError && e.status === 401) setData("login");
    });
  }, []);
  useEffect(load, [load]);

  if (data === null) return <div className="min-h-screen bg-paper" />;
  if (data === "login") return <ClientLogin />;
  return <Portal data={data} onChanged={load} onLogout={() => setData("login")} />;
}

function ClientLogin() {
  const [email, setEmail] = useState("");
  const [sent, setSent] = useState<string | null>(null);
  const { pending, error, run } = useAction();

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    const res = await run(() => api<{ message: string }>("/client-portal/link", { body: { email } }));
    if (res) setSent(res.message);
  }

  return (
    <AuthShell kicker="Area clienti" title="Login clienti" subtitle="I tuoi appuntamenti e le visite online, senza password.">
      <AreaSwitch current="clienti" />
      {sent ? (
        <div className="space-y-4">
          <Notice state={{ ok: true, message: "Controlla la tua email" }} />
          <p className="t-body text-ink-2">{sent}</p>
          <button type="button" className={`${btnSecondary} w-full`} onClick={() => setSent(null)}>Usa un altro indirizzo</button>
        </div>
      ) : (
        <form onSubmit={submit} className="space-y-4" noValidate>
          {error && <Notice state={{ error: error.message }} />}
          <Field label="Email" hint="Quella che hai dato allo studio. Ti mandiamo un link per entrare.">
            <input className={inputCls} type="email" autoComplete="email" required value={email} onChange={(e) => setEmail(e.target.value)} />
          </Field>
          <button className={`${btnPrimary} w-full`} disabled={pending || !email.includes("@")}>
            {pending ? "Invio…" : "Inviami il link"}
          </button>
        </form>
      )}
    </AuthShell>
  );
}

function Portal({ data, onChanged, onLogout }: { data: PortalOverview; onChanged: () => void; onLogout: () => void }) {
  async function logout() {
    await api("/client-portal/logout", { method: "POST" }).catch(() => null);
    onLogout();
  }

  return (
    <div className="min-h-screen bg-paper">
      <header className="glass sticky top-0 z-10 border-b border-ink/10">
        <div className="mx-auto flex h-12 max-w-3xl items-center justify-between px-4">
          <Logo />
          <button type="button" onClick={logout} className="inline-flex items-center gap-1.5 t-footnote text-link hover:underline">
            <LogOut className="h-4 w-4" /> Esci
          </button>
        </div>
      </header>
      <main className="mx-auto max-w-3xl space-y-8 px-4 py-8 sm:py-12">
        <div>
          <p className="t-subhead font-semibold text-ink-3">Area clienti · {data.email}</p>
          <h1 className="t-large-title">I tuoi appuntamenti</h1>
        </div>
        <section className="space-y-3">
          <h2 className="px-1 t-title3">Prossimi</h2>
          {data.upcoming.length === 0 && (
            <div className="rounded-[14px] bg-card shadow-card">
              <EmptyState icon={<CalendarDays />} title="Nessun appuntamento in programma" text="Quando lo studio prenota un appuntamento per te, lo trovi qui." />
            </div>
          )}
          {data.upcoming.map((a) => <AppointmentCard key={a.id} a={a} onChanged={onChanged} />)}
        </section>
        {data.past.length > 0 && (
          <section className="space-y-3">
            <h2 className="px-1 t-title3">Passati</h2>
            <ul className="overflow-hidden rounded-[14px] bg-card shadow-card">
              {data.past.map((a) => (
                <li key={a.id} className="flex items-center gap-3 border-t border-rule px-5 py-3 first:border-t-0">
                  <span className="min-w-0 flex-1">
                    <span className="block truncate t-body">{a.service} · {a.studio}</span>
                    <span className="block t-footnote text-ink-3 first-letter:uppercase">
                      {formatDay(zoned(a.start_at, a.timezone).day, { day: "numeric", month: "long", year: "numeric" })} · {formatTime(a.start_at, a.timezone)}
                    </span>
                  </span>
                  <Tag tone={STATUS_TONE[a.status]}>{a.status_label}</Tag>
                </li>
              ))}
            </ul>
          </section>
        )}
        <p className="px-1 t-footnote text-ink-3">
          Per spostare un appuntamento contatta lo studio. Sei un professionista? <Link href="/accedi" className="text-link hover:underline">Login professionisti</Link>
        </p>
        <VersionFooter className="px-0" />
      </main>
    </div>
  );
}

function AppointmentCard({ a, onChanged }: { a: PortalAppointment; onChanged: () => void }) {
  const [confirming, setConfirming] = useState(false);
  const { pending, error, run } = useAction();
  const start = zoned(a.start_at, a.timezone);
  const active = a.status === "pending" || a.status === "confirmed";

  async function cancel() {
    const ok = await run(() => api(`/client-portal/appointments/${a.id}/cancel`, { method: "POST" }).then(() => true));
    if (ok) onChanged();
  }

  return (
    <article className="animate-rise rounded-[16px] bg-card p-5 shadow-card">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="t-subhead font-semibold text-accent first-letter:uppercase">{formatDay(start.day)}</p>
          <p className="num text-[28px] leading-tight font-bold tracking-tight">
            {formatTime(a.start_at, a.timezone)}<span className="text-ink-3">–{formatTime(a.end_at, a.timezone)}</span>
          </p>
          <p className="mt-1 t-body">{a.service} · {a.professional}</p>
          <p className="t-subhead text-ink-3">{a.studio}</p>
        </div>
        <Tag tone={STATUS_TONE[a.status]}>{a.status_label}</Tag>
      </div>
      <div className="mt-4 space-y-2">
        {a.is_online && a.video_url && (
          <a href={a.video_url} target="_blank" rel="noopener noreferrer" className={`${btnPrimary} w-full sm:w-auto`}>
            <Video className="h-4 w-4" /> Entra nella videochiamata
          </a>
        )}
        {a.is_online && active && <p className="t-footnote text-ink-3">Visita online: apri il link all&apos;orario dell&apos;appuntamento.</p>}
        {a.address && (
          <p className="flex items-center gap-1.5 t-subhead text-ink-2"><MapPin className="h-4 w-4 shrink-0 text-ink-3" /> {a.address}</p>
        )}
        {a.studio_phone && (
          <a href={`tel:${a.studio_phone}`} className="flex items-center gap-1.5 t-subhead text-link hover:underline">
            <Phone className="h-4 w-4 shrink-0" /> {formatPhone(a.studio_phone) ?? a.studio_phone}
          </a>
        )}
      </div>
      {error && <div className="mt-3"><Notice state={{ error: error.message }} /></div>}
      {active && (
        <div className="mt-4 border-t border-rule pt-4">
          {a.can_cancel ? (
            confirming ? (
              <div className="flex flex-wrap items-center gap-2">
                <span className="t-subhead">Vuoi davvero disdire?</span>
                <button type="button" className={btnDanger} disabled={pending} onClick={cancel}>Sì, disdici</button>
                <button type="button" className={btnSecondary} onClick={() => setConfirming(false)}>No</button>
              </div>
            ) : (
              <button type="button" className={btnSecondary} onClick={() => setConfirming(true)}>Disdici l&apos;appuntamento</button>
            )
          ) : (
            <p className="t-footnote text-ink-3">
              {a.cancellation_min_hours > 0
                ? `Mancano meno di ${a.cancellation_min_hours} ore: per disdire contatta lo studio.`
                : "Per disdire contatta lo studio."}
            </p>
          )}
        </div>
      )}
    </article>
  );
}
