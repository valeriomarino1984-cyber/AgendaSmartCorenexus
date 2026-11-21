"use client";

import { CalendarCheck2, ChevronLeft, ChevronRight, Clock, MapPin, Phone, Video } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";
import { Logo } from "@/components/Logo";
import { Segmented } from "@/components/Segmented";
import { VersionFooter } from "@/components/VersionFooter";
import { useAction } from "@/components/auth/useAction";
import { Field, Notice, btnPrimary, btnSecondary, inputCls } from "@/components/ui";
import { addDays, formatDay, formatTime, today as todayIn, zoned, type Day } from "@/lib/agenda";
import { api, ApiError } from "@/lib/api";
import { MODE_LABELS, formatPhone, formatPrice, type ServiceMode } from "@/lib/catalog";

interface PublicService {
  id: string;
  name: string;
  description: string | null;
  duration_minutes: number;
  mode: ServiceMode;
  price: string | null;
  color: string;
  professional_ids: string[];
}
interface PublicStudio {
  name: string;
  slug: string;
  timezone: string;
  address: string | null;
  phone: string | null;
  email: string | null;
  cancellation_min_hours: number;
  days_ahead: number;
  requires_confirmation: boolean;
  services: PublicService[];
  professionals: { id: string; name: string; specialization: string | null; color: string }[];
}
interface Slot { start_at: string; time: string; professional_ids: string[] }
interface Result {
  code: string;
  status: string;
  start_at: string;
  end_at: string;
  timezone: string;
  studio: string;
  service: string;
  professional: string;
  is_online: boolean;
  address: string | null;
}

const WEEK = 7;

function newKey(): string {
  const bytes = new Uint8Array(18);
  crypto.getRandomValues(bytes);
  return Array.from(bytes, (b) => b.toString(16).padStart(2, "0")).join("");
}

/** Prenotazione online in quattro passi: prestazione, professionista, giorno e ora, dati. */
export function BookingFlow() {
  const { slug } = useParams<{ slug: string }>();
  const [studio, setStudio] = useState<PublicStudio | null | "missing">(null);
  const [serviceId, setServiceId] = useState<string | null>(null);
  const [profId, setProfId] = useState<string>("");
  const [online, setOnline] = useState(false);
  const [weekStart, setWeekStart] = useState<Day | null>(null);
  // Orari legati alla ricerca che li ha prodotti: cambiando settimana o prestazione si mostra "…".
  const [found, setFound] = useState<{ key: string; days: Record<Day, Slot[]> } | null>(null);
  const [day, setDay] = useState<Day | null>(null);
  const [slot, setSlot] = useState<Slot | null>(null);
  const [result, setResult] = useState<Result | null>(null);

  useEffect(() => {
    api<PublicStudio>(`/public/studios/${slug}`).then(
      (s) => {
        setStudio(s);
        setWeekStart(todayIn(s.timezone));
      },
      () => setStudio("missing"),
    );
  }, [slug]);

  const service = studio && studio !== "missing" ? studio.services.find((s) => s.id === serviceId) ?? null : null;
  const profs = useMemo(
    () => (studio && studio !== "missing" && service ? studio.professionals.filter((p) => service.professional_ids.includes(p.id)) : []),
    [studio, service],
  );

  const slotKey = service && weekStart ? `${service.id}|${weekStart}|${profId}` : "";
  const slots = found && found.key === slotKey ? found.days : null;
  const [reload, setReload] = useState(0);
  const loadSlots = useCallback(() => setReload((n) => n + 1), []);
  useEffect(() => {
    if (!service || !weekStart || !studio || studio === "missing") return;
    const q = new URLSearchParams({ service_id: service.id, from: weekStart, to: addDays(weekStart, WEEK - 1) });
    if (profId) q.set("professional_id", profId);
    const key = `${service.id}|${weekStart}|${profId}`;
    let alive = true;
    api<{ days: Record<Day, Slot[]> }>(`/public/studios/${slug}/slots?${q}`).then(
      (r) => alive && setFound({ key, days: r.days }),
      () => alive && setFound({ key, days: {} }),
    );
    return () => {
      alive = false;
    };
  }, [service, weekStart, profId, slug, studio, reload]);

  if (studio === null) return <div className="min-h-screen bg-paper" />;
  if (studio === "missing")
    return (
      <PublicShell>
        <div className="mx-auto max-w-md rounded-[18px] bg-card p-8 text-center shadow-card">
          <p className="t-title3">Pagina non disponibile</p>
          <p className="mt-2 t-subhead text-ink-3">Lo studio non ha attivato la prenotazione online oppure l&apos;indirizzo non è corretto.</p>
        </div>
      </PublicShell>
    );

  const tz = studio.timezone;
  const days = weekStart ? Array.from({ length: WEEK }, (_, i) => addDays(weekStart, i)) : [];
  const first = todayIn(tz);
  const last = addDays(first, studio.days_ahead);

  if (result)
    return (
      <PublicShell studio={studio}>
        <Done result={result} studio={studio} onAgain={() => { setResult(null); setSlot(null); setDay(null); setServiceId(null); }} />
      </PublicShell>
    );

  return (
    <PublicShell studio={studio}>
      <div className="mx-auto max-w-3xl space-y-8">
        <Step n={1} title="Scegli la prestazione">
          {studio.services.length === 0 && <p className="t-subhead text-ink-3">Al momento non ci sono prestazioni prenotabili online.</p>}
          <div className="grid gap-3 sm:grid-cols-2">
            {studio.services.map((s) => (
              <button
                key={s.id}
                type="button"
                onClick={() => { setServiceId(s.id); setProfId(""); setSlot(null); setDay(null); setOnline(s.mode === "online"); }}
                aria-pressed={serviceId === s.id}
                className={`lift rounded-[16px] border-2 bg-card p-4 text-left shadow-card transition ${serviceId === s.id ? "border-accent" : "border-transparent"}`}
              >
                <span className="flex items-center gap-2 t-headline">
                  <span aria-hidden className="h-2.5 w-2.5 rounded-full" style={{ background: s.color }} />
                  {s.name}
                </span>
                <span className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 t-footnote text-ink-3">
                  <span className="inline-flex items-center gap-1"><Clock className="h-3.5 w-3.5" /> {s.duration_minutes} min</span>
                  {s.mode !== "in_person" && <span className="inline-flex items-center gap-1 text-accent"><Video className="h-3.5 w-3.5" /> {MODE_LABELS[s.mode]}</span>}
                  {s.price && <span>{formatPrice(s.price)}</span>}
                </span>
                {s.description && <span className="mt-2 block t-footnote text-ink-2">{s.description}</span>}
              </button>
            ))}
          </div>
        </Step>

        {service && (
          <Step n={2} title="Con chi">
            <div className="flex flex-wrap gap-2">
              {profs.length > 1 && (
                <Chip active={profId === ""} onClick={() => { setProfId(""); setSlot(null); }}>Qualsiasi professionista</Chip>
              )}
              {profs.map((p) => (
                <Chip key={p.id} active={profId === p.id || profs.length === 1} onClick={() => { setProfId(p.id); setSlot(null); }}>
                  {p.name}{p.specialization ? ` · ${p.specialization}` : ""}
                </Chip>
              ))}
            </div>
            {service.mode === "both" && (
              <div className="mt-4 max-w-xs">
                <Segmented label="Modalità" options={[["studio", "In studio"], ["online", "Online"]] as const} value={online ? "online" : "studio"} onChange={(v) => setOnline(v === "online")} />
              </div>
            )}
          </Step>
        )}

        {service && weekStart && (
          <Step n={3} title="Scegli giorno e ora">
            <div className="flex items-center justify-between">
              <button type="button" aria-label="Settimana precedente" disabled={weekStart <= first} onClick={() => { setWeekStart(addDays(weekStart, -WEEK) < first ? first : addDays(weekStart, -WEEK)); setDay(null); setSlot(null); }} className="grid h-9 w-9 place-items-center rounded-full hover:bg-ink/[0.06] disabled:opacity-30">
                <ChevronLeft className="h-5 w-5" />
              </button>
              <p className="t-subhead font-semibold first-letter:uppercase">{formatDay(weekStart, { month: "long", year: "numeric" })}</p>
              <button type="button" aria-label="Settimana successiva" disabled={addDays(weekStart, WEEK) > last} onClick={() => { setWeekStart(addDays(weekStart, WEEK)); setDay(null); setSlot(null); }} className="grid h-9 w-9 place-items-center rounded-full hover:bg-ink/[0.06] disabled:opacity-30">
                <ChevronRight className="h-5 w-5" />
              </button>
            </div>
            <div className="mt-3 grid grid-cols-7 gap-1.5">
              {days.map((d) => {
                const n = slots?.[d]?.length ?? 0;
                return (
                  <button
                    key={d}
                    type="button"
                    disabled={!n}
                    onClick={() => { setDay(d); setSlot(null); }}
                    aria-pressed={day === d}
                    className={`rounded-[12px] py-2 text-center transition disabled:opacity-35 ${day === d ? "bg-accent text-white" : "bg-card shadow-card hover:bg-paper"}`}
                  >
                    <span className="block t-caption font-semibold opacity-80">{formatDay(d, { weekday: "short" })}</span>
                    <span className="num block t-title3">{Number(d.slice(8))}</span>
                    <span className={`block t-caption ${day === d ? "opacity-90" : "text-ink-3"}`}>{slots === null ? "…" : n ? `${n} liberi` : "—"}</span>
                  </button>
                );
              })}
            </div>
            {slots && Object.keys(slots).length === 0 && <p className="mt-3 t-subhead text-ink-3">Nessun orario libero in questa settimana: prova quella successiva.</p>}
            {day && slots?.[day] && (
              <div className="mt-4">
                <p className="mb-2 t-subhead first-letter:uppercase">{formatDay(day)}</p>
                <div className="space-y-4">
                  {([["Mattina", 0, 13], ["Pomeriggio", 13, 18], ["Sera", 18, 24]] as const).map(([label, from, to]) => {
                    const group = slots[day]!.filter((s) => Number(s.time.slice(0, 2)) >= from && Number(s.time.slice(0, 2)) < to);
                    if (!group.length) return null;
                    return (
                      <div key={label}>
                        <p className="mb-1.5 t-caption font-semibold text-ink-3 uppercase">{label}</p>
                        <div className="flex flex-wrap gap-2">
                          {group.map((s) => (
                            <button
                              key={s.start_at}
                              type="button"
                              onClick={() => setSlot(s)}
                              aria-pressed={slot?.start_at === s.start_at}
                              className={`num rounded-full px-4 py-2 t-subhead font-semibold transition ${slot?.start_at === s.start_at ? "bg-accent text-white" : "bg-card shadow-card hover:bg-paper"}`}
                            >
                              {s.time}
                            </button>
                          ))}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}
          </Step>
        )}

        {service && slot && (
          <Step n={4} title="I tuoi dati">
            <DetailsForm
              studio={studio}
              service={service}
              slot={slot}
              professionalId={profId || null}
              online={service.mode === "online" || (service.mode === "both" && online)}
              onDone={setResult}
              onTaken={() => { setSlot(null); loadSlots(); }}
            />
          </Step>
        )}
      </div>
      <p className="mt-10 text-center t-footnote text-ink-3">
        Hai già prenotato? <Link href="/area-clienti" className="text-link hover:underline">Area clienti</Link> per vedere o disdire i tuoi appuntamenti.
      </p>
    </PublicShell>
  );
}

function DetailsForm({
  studio, service, slot, professionalId, online, onDone, onTaken,
}: {
  studio: PublicStudio;
  service: PublicService;
  slot: Slot;
  professionalId: string | null;
  online: boolean;
  onDone: (r: Result) => void;
  onTaken: () => void;
}) {
  const [f, setF] = useState({ first_name: "", last_name: "", email: "", phone: "", notes: "", privacy_accepted: false, email_consent: false, marketing_consent: false, website: "" });
  const [key] = useState(newKey);
  const { pending, error, run } = useAction();
  const [taken, setTaken] = useState<string | null>(null);
  const set = (patch: Partial<typeof f>) => setF((prev) => ({ ...prev, ...patch }));
  const ready = f.first_name.trim() && f.last_name.trim() && f.email.includes("@") && f.phone.trim().length >= 6 && f.privacy_accepted;

  return (
    <form
      className="space-y-4"
      noValidate
      onSubmit={async (e) => {
        e.preventDefault();
        setTaken(null);
        const r = await run(() =>
          api<Result>(`/public/studios/${studio.slug}/bookings`, {
            body: { ...f, notes: f.notes || null, service_id: service.id, professional_id: professionalId, start_at: slot.start_at, is_online: online, booking_key: key },
          }).catch((err: unknown) => {
            if (err instanceof ApiError && err.status === 409) {
              setTaken(err.message);
              onTaken();
              return null;
            }
            throw err;
          }),
        );
        if (r) onDone(r);
      }}
    >
      <div className="rounded-[14px] bg-accent/10 px-4 py-3 t-subhead">
        <b>{service.name}</b> · <span className="first-letter:uppercase">{formatDay(zoned(slot.start_at, studio.timezone).day)}</span> alle <b className="num">{slot.time}</b>
        {online && <span className="ml-1 inline-flex items-center gap-1 text-accent"><Video className="h-3.5 w-3.5" /> online</span>}
      </div>
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="Nome"><input className={inputCls} autoComplete="given-name" value={f.first_name} onChange={(e) => set({ first_name: e.target.value })} /></Field>
        <Field label="Cognome"><input className={inputCls} autoComplete="family-name" value={f.last_name} onChange={(e) => set({ last_name: e.target.value })} /></Field>
        <Field label="Email" hint="Qui riceverai la conferma."><input className={inputCls} type="email" autoComplete="email" value={f.email} onChange={(e) => set({ email: e.target.value })} /></Field>
        <Field label="Cellulare"><input className={inputCls} type="tel" autoComplete="tel" value={f.phone} onChange={(e) => set({ phone: e.target.value })} /></Field>
        <div className="sm:col-span-2">
          <Field label="Note per lo studio (facoltative)" hint="Solo informazioni pratiche, non dati di salute.">
            <textarea className={`${inputCls} h-auto min-h-16 py-2.5`} maxLength={500} value={f.notes} onChange={(e) => set({ notes: e.target.value })} />
          </Field>
        </div>
      </div>
      {/* Campo nascosto anti-spam: le persone non lo vedono e non lo compilano. */}
      <div aria-hidden className="absolute -left-[9999px] h-0 w-0 overflow-hidden">
        <label>Sito web<input tabIndex={-1} autoComplete="off" value={f.website} onChange={(e) => set({ website: e.target.value })} /></label>
      </div>
      <div className="space-y-3 rounded-[14px] bg-paper-2/60 p-4">
        <label className="flex items-start gap-3">
          <input type="checkbox" className="mt-1 h-4 w-4 accent-[var(--color-accent)]" checked={f.privacy_accepted} onChange={(e) => set({ privacy_accepted: e.target.checked })} />
          <span className="t-subhead">Acconsento al trattamento dei miei dati da parte di <b>{studio.name}</b> per gestire questo appuntamento. <span className="text-ink-3">(obbligatorio)</span></span>
        </label>
        <label className="flex items-start gap-3">
          <input type="checkbox" className="mt-1 h-4 w-4 accent-[var(--color-accent)]" checked={f.email_consent} onChange={(e) => set({ email_consent: e.target.checked })} />
          <span className="t-subhead">Voglio ricevere i promemoria degli appuntamenti via email.</span>
        </label>
        <label className="flex items-start gap-3">
          <input type="checkbox" className="mt-1 h-4 w-4 accent-[var(--color-accent)]" checked={f.marketing_consent} onChange={(e) => set({ marketing_consent: e.target.checked })} />
          <span className="t-subhead">Voglio ricevere offerte e novità dallo studio. <span className="text-ink-3">(facoltativo)</span></span>
        </label>
      </div>
      {taken && <Notice state={{ error: taken }} />}
      {error && !taken && <Notice state={{ error: error.message }} />}
      <button className={`${btnPrimary} cta w-full`} disabled={pending || !ready}>
        {pending ? "Prenotazione…" : studio.requires_confirmation ? "Invia la richiesta" : "Prenota"}
      </button>
    </form>
  );
}

function Done({ result, studio, onAgain }: { result: Result; studio: PublicStudio; onAgain: () => void }) {
  const pending = result.status === "pending";
  const d = zoned(result.start_at, result.timezone);
  return (
    <div className="mx-auto max-w-lg animate-rise rounded-[22px] bg-card p-8 text-center shadow-card">
      <span className="mx-auto grid h-16 w-16 place-items-center rounded-full bg-go-soft text-go"><CalendarCheck2 className="h-8 w-8" /></span>
      <h1 className="mt-4 text-[28px] font-semibold tracking-tight">{pending ? "Richiesta inviata" : "Prenotazione confermata"}</h1>
      <p className="mt-2 t-body text-ink-2">
        {result.service} con {result.professional}
        <br />
        <span className="first-letter:uppercase">{formatDay(d.day)}</span> alle <b className="num">{formatTime(result.start_at, result.timezone)}</b>
      </p>
      {result.is_online ? (
        <p className="mt-3 inline-flex items-center gap-1.5 t-subhead text-accent"><Video className="h-4 w-4" /> Visita online: il link è nell&apos;email</p>
      ) : (
        result.address && <p className="mt-3 inline-flex items-center gap-1.5 t-subhead text-ink-2"><MapPin className="h-4 w-4" /> {result.address}</p>
      )}
      <p className="mt-4 t-subhead text-ink-3">
        {pending ? "Lo studio confermerà l'orario: ti scriviamo via email." : "Ti abbiamo inviato un'email di conferma."} Codice {result.code}.
      </p>
      <div className="mt-6 flex flex-wrap justify-center gap-2">
        <Link href="/area-clienti" className={btnPrimary}>I miei appuntamenti</Link>
        <button type="button" className={btnSecondary} onClick={onAgain}>Prenota un altro appuntamento</button>
      </div>
      {studio.cancellation_min_hours > 0 && (
        <p className="mt-4 t-footnote text-ink-3">Puoi disdire dall&apos;area clienti fino a {studio.cancellation_min_hours} ore prima.</p>
      )}
    </div>
  );
}

function Step({ n, title, children }: { n: number; title: string; children: React.ReactNode }) {
  return (
    <section className="animate-rise">
      <h2 className="mb-3 flex items-center gap-2.5 t-title3">
        <span className="num grid h-7 w-7 place-items-center rounded-full bg-accent t-subhead font-bold text-white">{n}</span>
        {title}
      </h2>
      {children}
    </section>
  );
}

function Chip({ active, onClick, children }: { active: boolean; onClick: () => void; children: React.ReactNode }) {
  return (
    <button type="button" aria-pressed={active} onClick={onClick}
      className={`rounded-full px-4 py-2 t-subhead font-medium transition ${active ? "bg-accent text-white" : "bg-card shadow-card hover:bg-paper"}`}>
      {children}
    </button>
  );
}

function PublicShell({ studio, children }: { studio?: PublicStudio; children: React.ReactNode }) {
  return (
    <div className="min-h-screen bg-paper">
      <header className="glass sticky top-0 z-20 border-b border-ink/10">
        <div className="mx-auto flex h-12 max-w-3xl items-center justify-between px-4">
          <span className="truncate t-headline">{studio?.name ?? "Prenotazione online"}</span>
          <span className="t-caption text-ink-3">con <Logo /></span>
        </div>
      </header>
      {studio && (
        <div className="mx-auto max-w-3xl px-4 pt-8">
          <p className="t-subhead font-semibold text-accent">Prenota online</p>
          <h1 className="text-[34px] leading-tight font-bold tracking-tight">{studio.name}</h1>
          <p className="mt-2 flex flex-wrap gap-x-4 gap-y-1 t-subhead text-ink-3">
            {studio.address && <span className="inline-flex items-center gap-1.5"><MapPin className="h-4 w-4" /> {studio.address}</span>}
            {studio.phone && <a href={`tel:${studio.phone}`} className="inline-flex items-center gap-1.5 hover:text-ink"><Phone className="h-4 w-4" /> {formatPhone(studio.phone) ?? studio.phone}</a>}
          </p>
        </div>
      )}
      <main className="mx-auto max-w-3xl px-4 py-8">{children}</main>
      <VersionFooter />
    </div>
  );
}
