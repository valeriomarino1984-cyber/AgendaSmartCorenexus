"use client";

import { Check, Copy, Phone, Search, Video, X } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { Field, Notice, Tag, btnDanger, btnPrimary, btnSecondary, btnTinted, inputCls, selectCls } from "@/components/ui";
import { Segmented } from "@/components/Segmented";
import { useAction } from "@/components/auth/useAction";
import { api, ApiError } from "@/lib/api";
import { STATUS_TONE, formatDay, formatTime, hhmm, parseHHMM, toInstant, zoned, type Appointment, type Day } from "@/lib/agenda";
import { MODE_LABELS, formatDateTime, formatPhone, formatPrice, type Client, type Professional, type Service } from "@/lib/catalog";
import { NOTIFICATION_TONE } from "@/lib/notifications";

export interface SheetContext {
  tz: string;
  services: Service[];
  professionals: Professional[];
  /** Il professionista vede e gestisce solo la propria agenda. */
  onlyProfessionalId: string | null;
}

/** Pannello laterale: nuovo appuntamento (`draft`) o dettaglio (`appointmentId`). */
export function AppointmentSheet({
  ctx,
  appointmentId,
  draft,
  onClose,
  onChanged,
}: {
  ctx: SheetContext;
  appointmentId?: string;
  draft?: { day: Day; minutes: number; professionalId?: string };
  onClose: () => void;
  onChanged: () => void;
}) {
  const panel = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    panel.current?.focus();
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  return (
    <div className="fixed inset-0 z-40 flex justify-end">
      <button type="button" aria-label="Chiudi" className="absolute inset-0 bg-black/25 backdrop-blur-[2px]" onClick={onClose} />
      <div
        ref={panel}
        tabIndex={-1}
        role="dialog"
        aria-modal="true"
        aria-label={appointmentId ? "Appuntamento" : "Nuovo appuntamento"}
        className="relative flex h-full w-full max-w-[460px] animate-rise flex-col overflow-y-auto bg-canvas shadow-[0_0_60px_rgb(0_0_0/0.25)] outline-none"
      >
        <div className="glass sticky top-0 z-10 flex items-center justify-between border-b border-ink/10 px-5 py-3">
          <h2 className="t-headline">{appointmentId ? "Appuntamento" : "Nuovo appuntamento"}</h2>
          <button type="button" aria-label="Chiudi" onClick={onClose} className="grid h-8 w-8 place-items-center rounded-full bg-ink/[0.06] text-ink-2 hover:bg-ink/10">
            <X className="h-4 w-4" />
          </button>
        </div>
        <div className="space-y-6 p-5">
          {appointmentId ? (
            <AppointmentDetail ctx={ctx} id={appointmentId} onChanged={onChanged} onClose={onClose} />
          ) : (
            <AppointmentForm ctx={ctx} initial={draft} onSaved={() => { onChanged(); onClose(); }} />
          )}
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------- modulo (nuovo / modifica)

interface FormState {
  client: { id: string; name: string } | null;
  serviceId: string;
  professionalId: string;
  day: Day;
  time: string;
  online: boolean;
  pending: boolean;
  notes: string;
}

function AppointmentForm({
  ctx,
  initial,
  existing,
  onSaved,
}: {
  ctx: SheetContext;
  initial?: { day: Day; minutes: number; professionalId?: string };
  existing?: Appointment;
  onSaved: (a: Appointment) => void;
}) {
  const services = ctx.services.filter((s) => s.active);
  const startParts = existing ? zoned(existing.start_at, ctx.tz) : null;
  const [f, setF] = useState<FormState>(() => {
    const prof = existing?.professional_id ?? initial?.professionalId ?? ctx.onlyProfessionalId ?? "";
    const svc = existing?.service_id ?? services.find((s) => !prof || s.professional_ids.includes(prof))?.id ?? "";
    return {
      client: existing ? { id: existing.client_id, name: existing.client_name ?? "" } : null,
      serviceId: svc,
      professionalId: prof || services.find((s) => s.id === svc)?.professional_ids[0] || "",
      day: startParts?.day ?? initial?.day ?? zoned(new Date(), ctx.tz).day,
      time: hhmm(startParts?.minutes ?? initial?.minutes ?? 9 * 60),
      online: existing?.is_online ?? false,
      pending: false,
      notes: existing?.notes ?? "",
    };
  });
  const [warning, setWarning] = useState<string | null>(null);
  const [slots, setSlots] = useState<string[] | null>(null);
  const { pending, error, run } = useAction();
  const service = services.find((s) => s.id === f.serviceId);
  const professionals = ctx.professionals.filter(
    (p) => p.status === "active" && (!service || service.professional_ids.includes(p.id)) && (!ctx.onlyProfessionalId || p.id === ctx.onlyProfessionalId),
  );
  const set = (patch: Partial<FormState>) => {
    setWarning(null);
    setF((prev) => ({ ...prev, ...patch }));
  };

  // Orari liberi del giorno scelto, come suggerimenti.
  useEffect(() => {
    if (!f.serviceId || !f.professionalId || !f.day) return;
    let alive = true;
    const q = new URLSearchParams({ professional_id: f.professionalId, service_id: f.serviceId, from: f.day, to: f.day });
    api<{ slots: { local: string }[] }>(`/slots?${q}`).then(
      (r) => alive && setSlots(r.slots.map((s) => s.local.slice(11))),
      () => alive && setSlots(null),
    );
    return () => {
      alive = false;
    };
  }, [f.serviceId, f.professionalId, f.day]);

  async function save(force = false) {
    if (!f.client || !service) return;
    const start_at = toInstant(f.day, parseHHMM(f.time), ctx.tz);
    const is_online = service.mode === "both" ? f.online : undefined;
    const res = await run(() =>
      (existing
        ? api<Appointment>(`/appointments/${existing.id}`, {
            method: "PATCH",
            body: {
              version: existing.version,
              client_id: f.client!.id,
              service_id: f.serviceId,
              professional_id: f.professionalId,
              start_at,
              notes: f.notes || null,
              force,
              ...(is_online !== undefined ? { is_online } : {}),
            },
          })
        : api<Appointment>("/appointments", {
            body: {
              client_id: f.client!.id,
              service_id: f.serviceId,
              professional_id: f.professionalId,
              start_at,
              status: f.pending ? "pending" : "confirmed",
              notes: f.notes || null,
              force,
              ...(is_online !== undefined ? { is_online } : {}),
            },
          })
      ).catch((e: unknown) => {
        if (e instanceof ApiError && e.code === "fuori_orario") {
          setWarning(e.message);
          return null;
        }
        throw e;
      }),
    );
    if (res) onSaved(res);
  }

  return (
    <form
      className="space-y-5"
      noValidate
      onSubmit={(e) => {
        e.preventDefault();
        void save();
      }}
    >
      <ClientPicker value={f.client} onChange={(client) => set({ client })} />
      <Field label="Prestazione">
        <select
          className={selectCls}
          value={f.serviceId}
          onChange={(e) => {
            const svc = services.find((s) => s.id === e.target.value);
            set({
              serviceId: e.target.value,
              professionalId: svc && !svc.professional_ids.includes(f.professionalId) ? (svc.professional_ids[0] ?? "") : f.professionalId,
            });
          }}
        >
          {services.map((s) => (
            <option key={s.id} value={s.id}>
              {s.name} · {s.duration_minutes} min{s.mode !== "in_person" ? ` · ${MODE_LABELS[s.mode]}` : ""}
            </option>
          ))}
        </select>
      </Field>
      {!ctx.onlyProfessionalId && (
        <Field label="Professionista">
          <select className={selectCls} value={f.professionalId} onChange={(e) => set({ professionalId: e.target.value })}>
            {professionals.length === 0 && <option value="">Nessuno abilitato a questa prestazione</option>}
            {professionals.map((p) => (
              <option key={p.id} value={p.id}>{p.name}</option>
            ))}
          </select>
        </Field>
      )}
      {service?.mode === "both" && (
        <div className="space-y-1.5">
          <p className="px-1 t-footnote font-medium text-ink-3">Modalità</p>
          <Segmented label="Modalità" options={[["studio", "In studio"], ["online", "Online"]] as const} value={f.online ? "online" : "studio"} onChange={(v) => set({ online: v === "online" })} />
        </div>
      )}
      {service && service.mode !== "in_person" && (service.mode === "online" || f.online) && (
        <p className="flex items-center gap-2 rounded-[10px] bg-accent/10 px-3 py-2 t-footnote text-accent">
          <Video className="h-4 w-4 shrink-0" /> Il link della videochiamata viene creato al salvataggio.
        </p>
      )}
      <div className="grid grid-cols-2 gap-3">
        <Field label="Giorno">
          <input type="date" className={inputCls} required value={f.day} onChange={(e) => set({ day: e.target.value })} />
        </Field>
        <Field label="Ora">
          <input type="time" step={300} className={inputCls} required value={f.time} onChange={(e) => set({ time: e.target.value })} />
        </Field>
      </div>
      {slots && (
        <div className="space-y-1.5">
          <p className="px-1 t-footnote font-medium text-ink-3">{slots.length ? `Orari liberi · ${formatDay(f.day, { weekday: "long", day: "numeric", month: "long" })}` : "Nessun orario libero in questo giorno"}</p>
          <div className="flex flex-wrap gap-1.5">
            {slots.slice(0, 24).map((t) => (
              <button
                key={t}
                type="button"
                onClick={() => set({ time: t })}
                className={`num rounded-full px-2.5 py-1 t-footnote font-medium transition ${f.time === t ? "bg-accent text-white" : "bg-paper-2 text-ink hover:bg-ink/10"}`}
              >
                {t}
              </button>
            ))}
          </div>
        </div>
      )}
      {!existing && (
        <label className="flex items-center gap-2">
          <input type="checkbox" className="h-4 w-4 accent-[var(--color-accent)]" checked={f.pending} onChange={(e) => set({ pending: e.target.checked })} />
          <span className="t-body">Da confermare</span>
        </label>
      )}
      <Field label="Note per lo studio" hint="Visibili solo allo staff, mai nei messaggi al cliente.">
        <textarea className={`${inputCls} h-auto min-h-16 py-2.5`} maxLength={2000} value={f.notes} onChange={(e) => set({ notes: e.target.value })} />
      </Field>
      {error && <Notice state={{ error: error.message }} />}
      {warning && (
        <div role="alert" className="space-y-3 rounded-[12px] bg-warn-soft px-3.5 py-3 t-subhead text-warn">
          <p>{warning}</p>
          <button type="button" className={btnSecondary} disabled={pending} onClick={() => void save(true)}>Prenota comunque</button>
        </div>
      )}
      <button className={`${btnPrimary} w-full`} disabled={pending || !f.client || !f.serviceId || !f.professionalId}>
        {pending ? "Salvataggio…" : existing ? "Salva modifiche" : "Prenota"}
      </button>
    </form>
  );
}

function ClientPicker({ value, onChange }: { value: { id: string; name: string } | null; onChange: (c: { id: string; name: string } | null) => void }) {
  const [q, setQ] = useState("");
  const [results, setResults] = useState<Client[]>([]);
  const [creating, setCreating] = useState(false);
  const [nc, setNc] = useState({ first_name: "", last_name: "", phone: "" });
  const { pending, error, run } = useAction();

  useEffect(() => {
    if (value || q.trim().length < 2) return;
    let alive = true;
    const t = setTimeout(() => {
      api<{ items: Client[] }>(`/clients?limit=8&q=${encodeURIComponent(q.trim())}`).then((r) => alive && setResults(r.items), () => null);
    }, 200);
    return () => {
      alive = false;
      clearTimeout(t);
    };
  }, [q, value]);

  async function create() {
    const res = await run(() =>
      api<Client>("/clients", { body: { first_name: nc.first_name, last_name: nc.last_name, phone: nc.phone || null } }).catch(async (e: unknown) => {
        // Esiste già: si usa la scheda esistente.
        if (e instanceof ApiError && e.code === "cliente_duplicato") {
          const id = (e.details as { existing_id?: string })?.existing_id;
          if (id) return api<Client>(`/clients/${id}`);
        }
        throw e;
      }),
    );
    if (res) {
      onChange({ id: res.id, name: `${res.first_name} ${res.last_name}` });
      setCreating(false);
    }
  }

  if (value)
    return (
      <div className="space-y-1.5">
        <p className="px-1 t-footnote font-medium text-ink-3">Cliente</p>
        <div className="flex items-center justify-between gap-2 rounded-[10px] border border-rule-strong bg-card px-3.5 py-2.5">
          <span className="t-body font-medium">{value.name}</span>
          <button type="button" className="t-subhead text-link hover:underline" onClick={() => onChange(null)}>Cambia</button>
        </div>
      </div>
    );

  if (creating)
    return (
      <div className="space-y-3 rounded-[12px] bg-paper-2/70 p-3.5">
        <p className="t-subhead font-semibold">Nuovo cliente</p>
        <div className="grid grid-cols-2 gap-3">
          <Field label="Nome"><input className={inputCls} value={nc.first_name} onChange={(e) => setNc({ ...nc, first_name: e.target.value })} /></Field>
          <Field label="Cognome"><input className={inputCls} value={nc.last_name} onChange={(e) => setNc({ ...nc, last_name: e.target.value })} /></Field>
        </div>
        <Field label="Cellulare"><input type="tel" className={inputCls} value={nc.phone} onChange={(e) => setNc({ ...nc, phone: e.target.value })} /></Field>
        {error && <Notice state={{ error: error.message }} />}
        <div className="flex gap-2">
          <button type="button" className={btnTinted} disabled={pending || !nc.first_name.trim() || !nc.last_name.trim()} onClick={create}>Crea e scegli</button>
          <button type="button" className={btnSecondary} onClick={() => setCreating(false)}>Annulla</button>
        </div>
      </div>
    );

  return (
    <div className="space-y-1.5">
      <label htmlFor="cerca-cliente" className="block px-1 t-footnote font-medium text-ink-3">Cliente</label>
      <div className="relative">
        <Search aria-hidden className="pointer-events-none absolute top-1/2 left-3.5 h-4 w-4 -translate-y-1/2 text-ink-3" />
        <input id="cerca-cliente" type="search" autoComplete="off" placeholder="Cerca per nome o telefono" className={`${inputCls} pl-10`} value={q} onChange={(e) => setQ(e.target.value)} />
      </div>
      {q.trim().length >= 2 && (
        <ul className="overflow-hidden rounded-[10px] bg-card shadow-card">
          {results.map((c) => (
            <li key={c.id}>
              <button type="button" className="flex w-full items-center justify-between gap-2 border-t border-rule px-3.5 py-2.5 text-left first:border-t-0 hover:bg-ink/[0.04]"
                onClick={() => onChange({ id: c.id, name: `${c.first_name} ${c.last_name}` })}>
                <span className="t-body">{c.last_name} {c.first_name}</span>
                <span className="t-footnote text-ink-3">{formatPhone(c.phone) ?? c.email ?? ""}</span>
              </button>
            </li>
          ))}
          {results.length === 0 && <li className="px-3.5 py-2.5 t-subhead text-ink-3">Nessun cliente trovato</li>}
        </ul>
      )}
      <button type="button" className="px-1 t-subhead text-link hover:underline" onClick={() => {
        const [first = "", ...rest] = q.trim().split(/\s+/);
        setNc({ first_name: first, last_name: rest.join(" "), phone: "" });
        setCreating(true);
      }}>
        + Nuovo cliente
      </button>
    </div>
  );
}

// ---------------------------------------------------------------- dettaglio

const EVENT_LABELS: Record<string, string> = {
  created: "Creato",
  rescheduled: "Spostato",
  updated: "Modificato",
  confirmed: "Confermato",
  cancelled_by_client: "Disdetto dal cliente",
  cancelled_by_staff: "Cancellato dallo studio",
  completed: "Segnato come svolto",
  no_show: "Segnato come assente",
};

function AppointmentDetail({ ctx, id, onChanged, onClose }: { ctx: SheetContext; id: string; onChanged: () => void; onClose: () => void }) {
  const [a, setA] = useState<Appointment | null>(null);
  const [editing, setEditing] = useState(false);
  const [cancelling, setCancelling] = useState<"cancelled_by_client" | "cancelled_by_staff" | null>(null);
  const [reason, setReason] = useState("");
  const [copied, setCopied] = useState(false);
  const { pending, error, run } = useAction();
  const [openedAt] = useState(() => Date.now());

  const load = useMemo(() => () => api<Appointment>(`/appointments/${id}`).then(setA, () => null), [id]);
  useEffect(() => {
    void load();
  }, [load]);

  if (!a) return <p className="t-subhead text-ink-3">Caricamento…</p>;

  if (editing)
    return (
      <>
        <button type="button" className="t-subhead text-link hover:underline" onClick={() => setEditing(false)}>‹ Torna al dettaglio</button>
        <AppointmentForm ctx={ctx} existing={a} onSaved={(updated) => { setA({ ...a, ...updated }); setEditing(false); onChanged(); void load(); }} />
      </>
    );

  const active = a.status === "pending" || a.status === "confirmed";
  const past = new Date(a.start_at).getTime() <= openedAt;
  const start = zoned(a.start_at, ctx.tz);

  async function setStatus(status: string, why?: string) {
    if (!a) return;
    const res = await run(() => api<Appointment>(`/appointments/${a.id}/status`, { body: { version: a.version, status, reason: why || null } }));
    if (res) {
      setCancelling(null);
      onChanged();
      await load();
    }
  }

  return (
    <div className="space-y-6">
      <div className="space-y-2">
        <div className="flex items-start gap-3">
          <span aria-hidden className="mt-1.5 h-3 w-3 shrink-0 rounded-full" style={{ background: a.color }} />
          <div className="min-w-0 flex-1">
            <p className="t-title3">{a.client_name}</p>
            <p className="t-subhead text-ink-2">{a.service_name} · {a.professional_name}</p>
          </div>
          <Tag tone={STATUS_TONE[a.status]}>{a.status_label}</Tag>
        </div>
        <p className="t-body first-letter:uppercase">
          {formatDay(start.day)} · <span className="num">{formatTime(a.start_at, ctx.tz)}–{formatTime(a.end_at, ctx.tz)}</span>
        </p>
        <p className="t-footnote text-ink-3">
          Codice {a.public_code}
          {a.preparation_minutes ? ` · ${a.preparation_minutes} min di preparazione dopo` : ""}
          {a.price ? ` · ${formatPrice(a.price)}` : ""}
        </p>
        {a.client_phone && (
          <a href={`tel:${a.client_phone}`} className="inline-flex items-center gap-1.5 t-subhead text-link hover:underline">
            <Phone className="h-4 w-4" /> {formatPhone(a.client_phone)}
          </a>
        )}
      </div>

      {a.is_online && a.video_url && (
        <div className="space-y-2 rounded-[12px] bg-accent/10 p-3.5">
          <p className="flex items-center gap-2 t-subhead font-semibold text-accent"><Video className="h-4 w-4" /> Visita online</p>
          <p className="truncate t-footnote text-ink-2">{a.video_url}</p>
          <div className="flex flex-wrap gap-2">
            <a href={a.video_url} target="_blank" rel="noopener noreferrer" className={btnPrimary}>Apri videochiamata</a>
            <button type="button" className={btnSecondary} onClick={async () => {
              await navigator.clipboard?.writeText(a.video_url!).catch(() => null);
              setCopied(true);
            }}>
              {copied ? <><Check className="h-4 w-4" /> Copiato</> : <><Copy className="h-4 w-4" /> Copia link</>}
            </button>
          </div>
          <p className="t-caption text-ink-3">Il link è nelle email di conferma e di promemoria inviate al cliente.</p>
        </div>
      )}

      {a.notes && (
        <div>
          <p className="t-footnote font-medium text-ink-3">Note per lo studio</p>
          <p className="whitespace-pre-line t-body">{a.notes}</p>
        </div>
      )}
      {a.cancellation_reason && <p className="t-subhead text-ink-2">Motivo: {a.cancellation_reason}</p>}

      {error && <Notice state={{ error: error.message }} />}

      {active && !cancelling && (
        <div className="flex flex-wrap gap-2">
          {a.status === "pending" && <button type="button" className={btnPrimary} disabled={pending} onClick={() => setStatus("confirmed")}>Conferma</button>}
          <button type="button" className={btnTinted} disabled={pending} onClick={() => setEditing(true)}>Sposta o modifica</button>
          {past && <button type="button" className={btnSecondary} disabled={pending} onClick={() => setStatus("completed")}>Svolto</button>}
          {past && <button type="button" className={btnSecondary} disabled={pending} onClick={() => setStatus("no_show")}>Assente</button>}
          <button type="button" className={btnDanger} disabled={pending} onClick={() => setCancelling("cancelled_by_client")}>Disdici</button>
        </div>
      )}
      {cancelling && (
        <div className="space-y-3 rounded-[12px] bg-stamp-soft/60 p-3.5">
          <Segmented
            label="Chi disdice"
            options={[["cancelled_by_client", "Il cliente"], ["cancelled_by_staff", "Lo studio"]] as const}
            value={cancelling}
            onChange={setCancelling}
          />
          <Field label="Motivo (facoltativo)">
            <input className={inputCls} maxLength={300} value={reason} onChange={(e) => setReason(e.target.value)} />
          </Field>
          <div className="flex gap-2">
            <button type="button" className={btnDanger} disabled={pending} onClick={() => setStatus(cancelling, reason)}>Conferma disdetta</button>
            <button type="button" className={btnSecondary} onClick={() => setCancelling(null)}>Annulla</button>
          </div>
        </div>
      )}
      {(a.status === "completed" || a.status === "no_show") && (
        <button type="button" className={btnSecondary} disabled={pending} onClick={() => setStatus(a.status === "completed" ? "no_show" : "completed")}>
          {a.status === "completed" ? "Correggi: assente" : "Correggi: svolto"}
        </button>
      )}

      {a.notifications && a.notifications.length > 0 && (
        <div className="space-y-1.5 border-t border-rule pt-4">
          <p className="t-footnote font-medium text-ink-3">Email al cliente</p>
          <ul className="space-y-1.5">
            {a.notifications.map((n) => (
              <li key={n.id} className="flex flex-wrap items-center gap-2 t-footnote">
                <span className="text-ink-2">{n.kind_label}</span>
                <Tag tone={NOTIFICATION_TONE[n.status]}>{n.status_label}</Tag>
                <span className="text-ink-3">
                  {n.status === "sent" && n.sent_at ? formatDateTime(n.sent_at) : n.status === "pending" ? `prevista ${formatDateTime(n.scheduled_at)}` : n.reason_label ?? ""}
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {a.events && a.events.length > 0 && (
        <div className="space-y-1.5 border-t border-rule pt-4">
          <p className="t-footnote font-medium text-ink-3">Storico</p>
          <ul className="space-y-1 t-footnote text-ink-2">
            {a.events.map((e, i) => (
              <li key={i}>{formatDateTime(e.at)} · {EVENT_LABELS[e.type] ?? e.type}</li>
            ))}
          </ul>
        </div>
      )}
      <button type="button" className="t-subhead text-link hover:underline" onClick={onClose}>Chiudi</button>
    </div>
  );
}
