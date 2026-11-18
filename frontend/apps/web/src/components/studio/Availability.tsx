"use client";

import { CalendarOff, Minus, Plus, Trash2 } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import {
  AddRow, EmptyState, Field, Notice, PageHeader, Panel, Tag,
  btnGhost, btnPrimary, btnSecondary, inputCls, selectCls,
} from "@/components/ui";
import { useAction } from "@/components/auth/useAction";
import { api } from "@/lib/api";
import {
  EXCEPTION_LABELS, WEEKDAYS, addDays, formatDay, formatTime, hhmm, parseHHMM, today, toInstant, zoned,
  type AvailabilityException, type WeeklyRule,
} from "@/lib/agenda";
import type { Location, Professional } from "@/lib/catalog";
import { useMe } from "@/lib/me";

type Ranges = Record<number, { start: string; end: string }[]>;

function toRanges(rules: WeeklyRule[]): Ranges {
  const out: Ranges = {};
  for (let d = 1; d <= 7; d++) out[d] = [];
  for (const r of rules) out[r.weekday]!.push({ start: r.start_time, end: r.end_time });
  return out;
}

export function Availability() {
  const { me } = useMe();
  const [profs, setProfs] = useState<Professional[]>([]);
  const [profId, setProfId] = useState<string>("");
  const [tz, setTz] = useState("Europe/Rome");

  useEffect(() => {
    api<Professional[]>("/professionals").then((all) => {
      const active = all.filter((p) => p.status === "active");
      setProfs(active);
      const mine = active.find((p) => p.user_id === me.user.id);
      setProfId((current) => current || mine?.id || active[0]?.id || "");
    }, () => null);
    api<Location[]>("/locations").then((l) => setTz(l.find((x) => x.is_default)?.timezone ?? "Europe/Rome"), () => null);
  }, [me.user.id]);

  const mineId = profs.find((p) => p.user_id === me.user.id)?.id;
  const canEdit = me.role !== "professional" || profId === mineId;
  const selectable = me.role === "professional" ? profs.filter((p) => p.id === mineId) : profs;

  return (
    <>
      <PageHeader meta={me.tenant.name} title="Disponibilità" />
      {selectable.length > 1 && (
        <div className="w-72">
          <Field label="Professionista">
            <select className={selectCls} value={profId} onChange={(e) => setProfId(e.target.value)}>
              {selectable.map((p) => (
                <option key={p.id} value={p.id}>{p.name}</option>
              ))}
            </select>
          </Field>
        </div>
      )}
      {profId && <WeeklyEditor key={profId} professionalId={profId} canEdit={canEdit} />}
      {profId && <Exceptions professionalId={profId} professionals={profs} tz={tz} canEditOwn={canEdit} isOwner={me.role === "owner"} />}
    </>
  );
}

function WeeklyEditor({ professionalId, canEdit }: { professionalId: string; canEdit: boolean }) {
  const [ranges, setRanges] = useState<Ranges | null>(null);
  const [saved, setSaved] = useState(false);
  const { pending, error, run } = useAction();

  useEffect(() => {
    api<WeeklyRule[]>(`/professionals/${professionalId}/availability`).then((r) => setRanges(toRanges(r)), () => null);
  }, [professionalId]);

  if (!ranges) return null;

  const update = (day: number, list: { start: string; end: string }[]) => {
    setSaved(false);
    setRanges({ ...ranges, [day]: list });
  };

  function copyMondayToWeekdays() {
    if (!ranges) return;
    setSaved(false);
    const next = { ...ranges };
    for (let d = 2; d <= 5; d++) next[d] = ranges[1]!.map((r) => ({ ...r }));
    setRanges(next);
  }

  async function save() {
    if (!ranges) return;
    const rules = Object.entries(ranges).flatMap(([d, list]) =>
      list.map((r) => ({ weekday: Number(d), start_time: r.start, end_time: r.end })),
    );
    const res = await run(() => api<WeeklyRule[]>(`/professionals/${professionalId}/availability`, { method: "PUT", body: { rules } }));
    if (res) {
      setRanges(toRanges(res));
      setSaved(true);
    }
  }

  return (
    <Panel
      title="Orario settimanale"
      meta="Ora della sede"
      actions={canEdit ? <button type="button" className={btnGhost} onClick={copyMondayToWeekdays}>Copia il lunedì fino al venerdì</button> : undefined}
    >
      <fieldset disabled={!canEdit} className="divide-y divide-rule">
        {WEEKDAYS.map((label, i) => {
          const day = i + 1;
          const list = ranges[day]!;
          return (
            <div key={day} className="flex flex-wrap items-center gap-x-4 gap-y-2 py-3 first:pt-0 last:pb-0">
              <span className="w-24 t-body font-medium">{label}</span>
              <div className="flex flex-1 flex-wrap items-center gap-2">
                {list.length === 0 && <span className="t-subhead text-ink-3">Non lavora</span>}
                {list.map((r, j) => (
                  <span key={j} className="inline-flex items-center gap-1.5 rounded-[10px] bg-paper-2 py-1 pr-1 pl-2">
                    <input type="time" step={900} aria-label={`${label}: inizio fascia ${j + 1}`} className="rounded-[6px] bg-card px-1.5 py-1 t-subhead"
                      value={r.start} onChange={(e) => update(day, list.map((x, k) => (k === j ? { ...x, start: e.target.value } : x)))} />
                    <span className="text-ink-3">–</span>
                    <input type="time" step={900} aria-label={`${label}: fine fascia ${j + 1}`} className="rounded-[6px] bg-card px-1.5 py-1 t-subhead"
                      value={r.end} onChange={(e) => update(day, list.map((x, k) => (k === j ? { ...x, end: e.target.value } : x)))} />
                    {canEdit && (
                      <button type="button" aria-label={`Togli fascia ${j + 1} di ${label}`} className="grid h-7 w-7 place-items-center rounded-full text-ink-3 hover:bg-ink/[0.06]"
                        onClick={() => update(day, list.filter((_, k) => k !== j))}>
                        <Minus className="h-4 w-4" />
                      </button>
                    )}
                  </span>
                ))}
                {canEdit && (
                  <button type="button" aria-label={`Aggiungi fascia a ${label}`} className="grid h-8 w-8 place-items-center rounded-full text-accent hover:bg-accent/10"
                    onClick={() => {
                      const last = list[list.length - 1];
                      const start = last ? Math.min(parseHHMM(last.end) + 60, 22 * 60) : 9 * 60;
                      update(day, [...list, { start: hhmm(start), end: hhmm(Math.min(start + 4 * 60, 23 * 60 + 45)) }]);
                    }}>
                    <Plus className="h-4 w-4" />
                  </button>
                )}
              </div>
            </div>
          );
        })}
      </fieldset>
      {canEdit && (
        <div className="mt-5 flex flex-wrap items-center gap-3">
          <button type="button" className={btnPrimary} disabled={pending} onClick={save}>{pending ? "Salvataggio…" : "Salva orario"}</button>
          {saved && <Notice state={{ ok: true, message: "Orario salvato" }} />}
          {error && <Notice state={{ error: error.message }} />}
        </div>
      )}
      <p className="mt-4 t-footnote text-ink-3">Nelle festività nazionali lo studio risulta chiuso. Per lavorare in un giorno festivo aggiungi un&apos;apertura straordinaria.</p>
    </Panel>
  );
}

function Exceptions({
  professionalId, professionals, tz, canEditOwn, isOwner,
}: { professionalId: string; professionals: Professional[]; tz: string; canEditOwn: boolean; isOwner: boolean }) {
  const [items, setItems] = useState<AvailabilityException[] | null>(null);
  const { pending, error, run } = useAction();
  const from = useMemo(() => today(tz), [tz]);

  const load = useCallback(() => {
    api<AvailabilityException[]>(`/availability-exceptions?from=${encodeURIComponent(toInstant(from, 0, tz))}&to=${encodeURIComponent(toInstant(addDays(from, 366), 0, tz))}`)
      .then(setItems, () => null);
  }, [from, tz]);
  useEffect(load, [load]);

  const visible = items?.filter((e) => e.professional_id === null || e.professional_id === professionalId) ?? [];
  const name = (id: string | null) => (id ? professionals.find((p) => p.id === id)?.name : "Tutto lo studio");

  async function remove(id: string) {
    const ok = await run(() => api(`/availability-exceptions/${id}`, { method: "DELETE" }).then(() => true));
    if (ok) load();
  }

  function period(e: AvailabilityException) {
    const s = zoned(e.start_at, tz);
    const end = zoned(new Date(new Date(e.end_at).getTime() - 1).toISOString(), tz);
    const wholeDays = s.minutes === 0 && zoned(e.end_at, tz).minutes === 0;
    if (wholeDays) return s.day === end.day ? formatDay(s.day) : `${formatDay(s.day, { day: "numeric", month: "short" })} – ${formatDay(end.day, { day: "numeric", month: "short", year: "numeric" })}`;
    return `${formatDay(s.day, { weekday: "short", day: "numeric", month: "short" })}, ${formatTime(e.start_at, tz)}–${formatTime(e.end_at, tz)}`;
  }

  return (
    <Panel title="Ferie, chiusure e aperture straordinarie" flush>
      {error && <div className="p-4"><Notice state={{ error: error.message }} /></div>}
      {items && visible.length === 0 && <EmptyState icon={<CalendarOff />} title="Nessuna eccezione in programma" />}
      <ul>
        {visible.map((e) => (
          <li key={e.id} className="flex min-h-[56px] items-center gap-3 border-t border-rule px-5 py-2.5 first:border-t-0">
            <div className="min-w-0 flex-1">
              <p className="t-body">{period(e)}</p>
              <p className="truncate t-footnote text-ink-3">{[name(e.professional_id), e.reason].filter(Boolean).join(" · ")}</p>
            </div>
            <Tag tone={e.kind === "extra" ? "go" : e.kind === "closure" ? "stamp" : "warn"}>{EXCEPTION_LABELS[e.kind]}</Tag>
            {(e.professional_id ? canEditOwn : isOwner) && (
              <button type="button" aria-label="Elimina" className="grid h-8 w-8 place-items-center rounded-full text-ink-3 hover:bg-ink/[0.06]" disabled={pending} onClick={() => remove(e.id)}>
                <Trash2 className="h-4 w-4" />
              </button>
            )}
          </li>
        ))}
      </ul>
      {canEditOwn && (
        <AddRow label="Aggiungi ferie, chiusura o apertura">
          <ExceptionForm professionalId={professionalId} tz={tz} isOwner={isOwner} onDone={load} />
        </AddRow>
      )}
    </Panel>
  );
}

function ExceptionForm({ professionalId, tz, isOwner, onDone }: { professionalId: string; tz: string; isOwner: boolean; onDone: () => void }) {
  const start = today(tz);
  const [f, setF] = useState({ kind: "vacation", from: start, to: start, allDay: true, fromTime: "09:00", toTime: "13:00", reason: "" });
  const { pending, error, run } = useAction();
  const [done, setDone] = useState(false);
  const set = (patch: Partial<typeof f>) => {
    setDone(false);
    setF({ ...f, ...patch });
  };

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    const body = {
      kind: f.kind,
      professional_id: f.kind === "closure" ? null : professionalId,
      start_at: f.allDay ? toInstant(f.from, 0, tz) : toInstant(f.from, parseHHMM(f.fromTime), tz),
      end_at: f.allDay ? toInstant(addDays(f.to, 1), 0, tz) : toInstant(f.from, parseHHMM(f.toTime), tz),
      reason: f.reason || null,
    };
    const res = await run(() => api("/availability-exceptions", { body }));
    if (res) {
      setDone(true);
      onDone();
    }
  }

  return (
    <form onSubmit={submit} className="space-y-4" noValidate>
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="Tipo">
          <select className={selectCls} value={f.kind} onChange={(e) => set({ kind: e.target.value })}>
            <option value="vacation">Ferie</option>
            <option value="unavailable">Non disponibile</option>
            <option value="extra">Apertura straordinaria</option>
            {isOwner && <option value="closure">Chiusura dello studio (tutti)</option>}
          </select>
        </Field>
        <Field label="Motivo (facoltativo)">
          <input className={inputCls} maxLength={200} value={f.reason} onChange={(e) => set({ reason: e.target.value })} />
        </Field>
        <label className="flex items-center gap-2 sm:col-span-2">
          <input type="checkbox" className="h-4 w-4 accent-[var(--color-accent)]" checked={f.allDay} onChange={(e) => set({ allDay: e.target.checked })} />
          <span className="t-body">Giornate intere</span>
        </label>
        <Field label={f.allDay ? "Dal" : "Giorno"}>
          <input type="date" className={inputCls} value={f.from} onChange={(e) => set({ from: e.target.value, to: e.target.value > f.to ? e.target.value : f.to })} />
        </Field>
        {f.allDay ? (
          <Field label="Al (compreso)">
            <input type="date" className={inputCls} min={f.from} value={f.to} onChange={(e) => set({ to: e.target.value })} />
          </Field>
        ) : (
          <div className="grid grid-cols-2 gap-3">
            <Field label="Dalle">
              <input type="time" step={900} className={inputCls} value={f.fromTime} onChange={(e) => set({ fromTime: e.target.value })} />
            </Field>
            <Field label="Alle">
              <input type="time" step={900} className={inputCls} value={f.toTime} onChange={(e) => set({ toTime: e.target.value })} />
            </Field>
          </div>
        )}
      </div>
      {error && <Notice state={{ error: error.message }} />}
      {done && <Notice state={{ ok: true, message: "Aggiunta" }} />}
      <div className="flex gap-3">
        <button className={btnPrimary} disabled={pending}>{pending ? "Salvataggio…" : "Aggiungi"}</button>
        <button type="reset" className={btnSecondary} onClick={() => setF({ ...f, reason: "" })}>Annulla</button>
      </div>
    </form>
  );
}
