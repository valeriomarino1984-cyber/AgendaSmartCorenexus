"use client";

import { ChevronLeft, ChevronRight, Plus, Video } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Notice, PageHeader, btnPrimary, btnSecondary, selectCls } from "@/components/ui";
import { Segmented } from "@/components/Segmented";
import { AppointmentSheet, type SheetContext } from "@/components/agenda/AppointmentSheet";
import { api, ApiError } from "@/lib/api";
import {
  WEEKDAYS_SHORT, addDays, addMonths, formatDay, formatTime, hhmm, isoWeekday, startOfMonth, startOfWeek, toInstant, today, zoned,
  type Appointment, type Day, type WeeklyRule,
} from "@/lib/agenda";
import type { Location, Professional, Service } from "@/lib/catalog";
import { useMe } from "@/lib/me";

type View = "day" | "week" | "month";
const FIRST_HOUR = 7;
const LAST_HOUR = 21;
const HOUR_PX = 56;
const SLOT_MIN = 15;
const PX_PER_MIN = HOUR_PX / 60;

interface Placed {
  a: Appointment;
  day: Day;
  top: number;
  height: number;
  lane: number;
  lanes: number;
}

/** Disposizione a corsie degli appuntamenti che si sovrappongono (es. più professionisti). */
function layout(items: Appointment[], days: Day[], tz: string): Placed[] {
  const out: Placed[] = [];
  for (const day of days) {
    const list = items
      .map((a) => ({ a, s: zoned(a.start_at, tz), e: zoned(a.end_at, tz) }))
      .filter((x) => x.s.day === day)
      .sort((x, y) => x.s.minutes - y.s.minutes);
    let cluster: Placed[] = [];
    let clusterEnd = -1;
    const laneEnds: number[] = [];
    const flush = () => {
      const lanes = Math.max(1, ...cluster.map((p) => p.lane + 1));
      cluster.forEach((p) => (p.lanes = lanes));
      out.push(...cluster);
      cluster = [];
      laneEnds.length = 0;
    };
    for (const { a, s, e } of list) {
      const end = e.day === day ? e.minutes : 24 * 60;
      if (s.minutes >= clusterEnd) flush();
      let lane = laneEnds.findIndex((le) => le <= s.minutes);
      if (lane === -1) lane = laneEnds.length;
      laneEnds[lane] = end;
      clusterEnd = Math.max(clusterEnd, end);
      cluster.push({ a, day, top: (s.minutes - FIRST_HOUR * 60) * PX_PER_MIN, height: Math.max((end - s.minutes) * PX_PER_MIN, 18), lane, lanes: 1 });
    }
    flush();
  }
  return out;
}

export function Agenda() {
  const { me } = useMe();
  const [tz, setTz] = useState("Europe/Rome");
  const [view, setView] = useState<View>("week");
  const [anchor, setAnchor] = useState<Day>(() => today("Europe/Rome"));
  const [profFilter, setProfFilter] = useState<string>("");
  const [professionals, setProfessionals] = useState<Professional[]>([]);
  const [services, setServices] = useState<Service[]>([]);
  const [items, setItems] = useState<Appointment[] | null>(null);
  const [rulesOf, setRulesOf] = useState<{ prof: string; rules: WeeklyRule[] }>({ prof: "", rules: [] });
  const [sheet, setSheet] = useState<{ id?: string; draft?: { day: Day; minutes: number; professionalId?: string } } | null>(null);
  const [notice, setNotice] = useState<{ error?: string; ok?: boolean; message?: string } | null>(null);
  const [confirmMove, setConfirmMove] = useState<{ a: Appointment; day: Day; minutes: number; message: string } | null>(null);

  const myProf = professionals.find((p) => p.user_id === me.user.id)?.id ?? null;
  const onlyProfessionalId = me.role === "professional" ? myProf : null;
  const effectiveFilter = onlyProfessionalId ?? profFilter;

  useEffect(() => {
    api<Location[]>("/locations").then((l) => {
      const zone = l.find((x) => x.is_default)?.timezone ?? "Europe/Rome";
      setTz(zone);
      // Solo se l'utente non ha già cambiato giorno mentre la sede si caricava.
      setAnchor((current) => (current === today("Europe/Rome") ? today(zone) : current));
    }, () => null);
    api<Professional[]>("/professionals").then((p) => setProfessionals(p.filter((x) => x.status === "active")), () => null);
    api<Service[]>("/services").then(setServices, () => null);
  }, []);

  const days: Day[] = useMemo(() => {
    if (view === "day") return [anchor];
    if (view === "week") return Array.from({ length: 7 }, (_, i) => addDays(startOfWeek(anchor), i));
    const first = startOfWeek(startOfMonth(anchor));
    return Array.from({ length: 42 }, (_, i) => addDays(first, i));
  }, [view, anchor]);

  const load = useCallback(() => {
    const q = new URLSearchParams({ from: toInstant(days[0]!, 0, tz), to: toInstant(addDays(days[days.length - 1]!, 1), 0, tz) });
    if (effectiveFilter) q.set("professional_id", effectiveFilter);
    api<Appointment[]>(`/appointments?${q}`).then(setItems, (e) => setNotice({ error: e.message }));
  }, [days, tz, effectiveFilter]);
  useEffect(load, [load]);

  // Ombreggia le ore fuori orario quando si guarda un solo professionista.
  const shadeFor = effectiveFilter || (professionals.length === 1 ? professionals[0]!.id : "");
  useEffect(() => {
    if (!shadeFor) return;
    api<WeeklyRule[]>(`/professionals/${shadeFor}/availability`).then(
      (rules) => setRulesOf({ prof: shadeFor, rules }),
      () => setRulesOf({ prof: shadeFor, rules: [] }),
    );
  }, [shadeFor]);
  const rules = shadeFor && rulesOf.prof === shadeFor ? rulesOf.rules : [];

  const ctx: SheetContext = { tz, services, professionals, onlyProfessionalId };

  function move(step: number) {
    setAnchor(view === "day" ? addDays(anchor, step) : view === "week" ? addDays(anchor, 7 * step) : addMonths(anchor, step));
  }

  async function reschedule(a: Appointment, day: Day, minutes: number, force = false) {
    setNotice(null);
    try {
      await api(`/appointments/${a.id}`, { method: "PATCH", body: { version: a.version, start_at: toInstant(day, minutes, tz), force } });
      setConfirmMove(null);
      setNotice({ ok: true, message: `Spostato a ${formatDay(day, { weekday: "short", day: "numeric", month: "short" })} alle ${hhmm(minutes)}` });
    } catch (e) {
      if (e instanceof ApiError && e.code === "fuori_orario") {
        setConfirmMove({ a, day, minutes, message: e.message });
      } else {
        setNotice({ error: e instanceof Error ? e.message : "Spostamento non riuscito." });
      }
    }
    load();
  }

  const title =
    view === "month"
      ? formatDay(anchor, { month: "long", year: "numeric" })
      : view === "week"
        ? `${formatDay(days[0]!, { day: "numeric", month: "short" })} – ${formatDay(days[6]!, { day: "numeric", month: "short", year: "numeric" })}`
        : formatDay(anchor, { weekday: "long", day: "numeric", month: "long", year: "numeric" });

  return (
    <>
      <PageHeader
        meta={me.tenant.name}
        title="Agenda"
        actions={
          <button type="button" className={btnPrimary} onClick={() => setSheet({ draft: { day: view === "month" ? today(tz) : anchor, minutes: 9 * 60, professionalId: effectiveFilter || undefined } })}>
            <Plus className="h-4 w-4" /> Nuovo appuntamento
          </button>
        }
      />
      <div className="flex flex-wrap items-center gap-3">
        <div className="flex items-center gap-1">
          <button type="button" className={`${btnSecondary} h-9 px-3`} onClick={() => setAnchor(today(tz))}>Oggi</button>
          <button type="button" aria-label="Precedente" className="grid h-9 w-9 place-items-center rounded-full hover:bg-ink/[0.06]" onClick={() => move(-1)}><ChevronLeft className="h-5 w-5" /></button>
          <button type="button" aria-label="Successivo" className="grid h-9 w-9 place-items-center rounded-full hover:bg-ink/[0.06]" onClick={() => move(1)}><ChevronRight className="h-5 w-5" /></button>
        </div>
        <h2 className="min-w-0 flex-1 t-title3 first-letter:uppercase">{title}</h2>
        {!onlyProfessionalId && professionals.length > 1 && (
          <select aria-label="Professionista" className={`${selectCls} h-9 w-52`} value={profFilter} onChange={(e) => setProfFilter(e.target.value)}>
            <option value="">Tutti i professionisti</option>
            {professionals.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
          </select>
        )}
        <Segmented label="Vista" size="sm" className="w-64" options={[["day", "Giorno"], ["week", "Settimana"], ["month", "Mese"]] as const} value={view} onChange={setView} />
      </div>
      {notice && <Notice state={notice} />}
      {confirmMove && (
        <div role="alert" className="flex flex-wrap items-center gap-3 rounded-[12px] bg-warn-soft px-3.5 py-3 t-subhead text-warn">
          <span className="flex-1">{confirmMove.message}</span>
          <button type="button" className={btnSecondary} onClick={() => reschedule(confirmMove.a, confirmMove.day, confirmMove.minutes, true)}>Sposta comunque</button>
          <button type="button" className="t-subhead underline" onClick={() => setConfirmMove(null)}>Annulla</button>
        </div>
      )}

      {view === "month" ? (
        <MonthGrid days={days} anchor={anchor} items={items ?? []} tz={tz} onPickDay={(d) => { setAnchor(d); setView("day"); }} onOpen={(id) => setSheet({ id })} />
      ) : (
        <TimeGrid
          days={days}
          items={items ?? []}
          tz={tz}
          rules={rules}
          showProfessional={!effectiveFilter && professionals.length > 1}
          onOpen={(id) => setSheet({ id })}
          onCreate={(day, minutes) => setSheet({ draft: { day, minutes, professionalId: effectiveFilter || undefined } })}
          onMove={reschedule}
        />
      )}

      {sheet && (
        <AppointmentSheet ctx={ctx} appointmentId={sheet.id} draft={sheet.draft} onClose={() => setSheet(null)} onChanged={load} />
      )}
    </>
  );
}

// ---------------------------------------------------------------- giorno / settimana

function TimeGrid({
  days, items, tz, rules, showProfessional, onOpen, onCreate, onMove,
}: {
  days: Day[];
  items: Appointment[];
  tz: string;
  rules: WeeklyRule[];
  showProfessional: boolean;
  onOpen: (id: string) => void;
  onCreate: (day: Day, minutes: number) => void;
  onMove: (a: Appointment, day: Day, minutes: number) => void;
}) {
  const cols = useRef<HTMLDivElement>(null);
  const placed = useMemo(() => layout(items, days, tz), [items, days, tz]);
  const [drag, setDrag] = useState<{ id: string; dx: number; dy: number; moved: boolean; startX: number; startY: number; dest: { day: Day; minutes: number } | null } | null>(null);
  const [now, setNow] = useState(() => zoned(new Date(), tz));
  useEffect(() => {
    const t = setInterval(() => setNow(zoned(new Date(), tz)), 60_000);
    return () => clearInterval(t);
  }, [tz]);
  const todayDay = now.day;
  const hours = Array.from({ length: LAST_HOUR - FIRST_HOUR }, (_, i) => FIRST_HOUR + i);
  const height = (LAST_HOUR - FIRST_HOUR) * HOUR_PX;

  function target(p: Placed, dx: number, dy: number): { day: Day; minutes: number } {
    // Il contenitore ha display: contents (nessuna misura propria): si misura una colonna.
    const width = cols.current?.querySelector("[data-day]")?.getBoundingClientRect().width || 1;
    const dayIndex = Math.min(days.length - 1, Math.max(0, days.indexOf(p.day) + Math.round(dx / width)));
    const start = zoned(p.a.start_at, tz).minutes;
    const minutes = Math.min((LAST_HOUR * 60) - SLOT_MIN, Math.max(FIRST_HOUR * 60, start + Math.round(dy / PX_PER_MIN / SLOT_MIN) * SLOT_MIN));
    return { day: days[dayIndex]!, minutes };
  }

  function workingBands(day: Day): { top: number; height: number }[] {
    return rules
      .filter((r) => r.weekday === isoWeekday(day))
      .map((r) => {
        const [sh, sm] = r.start_time.split(":").map(Number);
        const [eh, em] = r.end_time.split(":").map(Number);
        const s = sh! * 60 + sm! - FIRST_HOUR * 60;
        const e = eh! * 60 + em! - FIRST_HOUR * 60;
        return { top: s * PX_PER_MIN, height: (e - s) * PX_PER_MIN };
      });
  }

  return (
    <div className="overflow-hidden rounded-[14px] bg-card shadow-card">
      <div className="overflow-x-auto">
        <div style={{ minWidth: days.length > 1 ? 760 : undefined }}>
          <div className="grid border-b border-rule" style={{ gridTemplateColumns: `56px repeat(${days.length}, minmax(0,1fr))` }}>
            <span />
            {days.map((d) => (
              <div key={d} className="px-2 py-2 text-center">
                <p className={`t-caption font-semibold ${d === todayDay ? "text-accent" : "text-ink-3"}`}>{WEEKDAYS_SHORT[isoWeekday(d) - 1]}</p>
                <p className={`num mx-auto grid h-8 w-8 place-items-center rounded-full t-title3 ${d === todayDay ? "bg-accent text-white" : ""}`}>{Number(d.slice(8))}</p>
              </div>
            ))}
          </div>
          <div className="relative max-h-[70vh] overflow-y-auto">
            <div className="grid" style={{ gridTemplateColumns: `56px repeat(${days.length}, minmax(0,1fr))`, height }}>
              <div className="relative">
                {hours.map((h) => (
                  <span key={h} className="num absolute right-2 -translate-y-1/2 t-caption text-ink-3" style={{ top: (h - FIRST_HOUR) * HOUR_PX }}>
                    {h > FIRST_HOUR ? `${h}:00` : ""}
                  </span>
                ))}
              </div>
              <div ref={cols} className="contents">
                {days.map((d) => (
                  <div
                    key={d}
                    data-day={d}
                    className={`relative border-l border-rule ${rules.length ? "bg-ink/[0.035]" : ""}`}
                    onClick={(e) => {
                      if (e.target !== e.currentTarget && !(e.target as HTMLElement).dataset.band) return;
                      const y = e.clientY - e.currentTarget.getBoundingClientRect().top;
                      const minutes = FIRST_HOUR * 60 + Math.floor(y / PX_PER_MIN / SLOT_MIN) * SLOT_MIN;
                      onCreate(d, minutes);
                    }}
                  >
                    {workingBands(d).map((b, i) => (
                      <div key={i} data-band="1" className="absolute inset-x-0 bg-card" style={{ top: b.top, height: b.height }} />
                    ))}
                    {hours.map((h) => (
                      <div key={h} className="pointer-events-none absolute inset-x-0 border-t border-rule/70" style={{ top: (h - FIRST_HOUR) * HOUR_PX }} />
                    ))}
                    {d === todayDay && now.minutes >= FIRST_HOUR * 60 && now.minutes <= LAST_HOUR * 60 && (
                      <div className="pointer-events-none absolute inset-x-0 z-20 h-0.5 bg-sys-red" style={{ top: (now.minutes - FIRST_HOUR * 60) * PX_PER_MIN }}>
                        <span className="absolute -top-[4px] -left-[4px] h-2.5 w-2.5 rounded-full bg-sys-red" />
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
            {/* Appuntamenti sopra la griglia, posizionati per colonna. */}
            <div className="pointer-events-none absolute inset-0 grid" style={{ gridTemplateColumns: `56px repeat(${days.length}, minmax(0,1fr))` }}>
              <span />
              {days.map((d) => (
                <div key={d} className="relative">
                  {placed.filter((p) => p.day === d).map((p) => {
                    const dragging = drag?.id === p.a.id && drag.moved;
                    const t = dragging ? drag.dest : null;
                    const color = p.a.color ?? "#0071e3";
                    const pending = p.a.status === "pending";
                    return (
                      <button
                        key={p.a.id}
                        type="button"
                        aria-label={`${formatTime(p.a.start_at, tz)} ${p.a.client_name}, ${p.a.service_name}`}
                        className={`svc-chip pointer-events-auto absolute touch-none overflow-hidden rounded-[7px] px-1.5 py-0.5 text-left transition-shadow ${dragging ? "z-30 cursor-grabbing opacity-90 shadow-lg" : "z-10 cursor-grab hover:shadow-md"} ${pending ? "border border-dashed border-current" : ""}`}
                        style={{
                          "--sc": color,
                          top: p.top,
                          height: p.height,
                          left: `calc(${(p.lane / p.lanes) * 100}% + 2px)`,
                          width: `calc(${100 / p.lanes}% - 4px)`,
                          transform: dragging ? `translate(${drag.dx}px, ${drag.dy}px)` : undefined,
                        } as React.CSSProperties}
                        onPointerDown={(e) => {
                          if (e.button !== 0) return;
                          e.currentTarget.setPointerCapture(e.pointerId);
                          setDrag({ id: p.a.id, dx: 0, dy: 0, moved: false, startX: e.clientX, startY: e.clientY, dest: null });
                        }}
                        onPointerMove={(e) => {
                          if (!drag || drag.id !== p.a.id) return;
                          const dx = e.clientX - drag.startX;
                          const dy = e.clientY - drag.startY;
                          setDrag({ ...drag, dx, dy, moved: drag.moved || Math.abs(dx) + Math.abs(dy) > 5, dest: target(p, dx, dy) });
                        }}
                        onPointerUp={() => {
                          const d0 = drag;
                          setDrag(null);
                          if (!d0 || d0.id !== p.a.id) return;
                          if (!d0.moved) return onOpen(p.a.id);
                          const dest = d0.dest ?? target(p, d0.dx, d0.dy);
                          const orig = zoned(p.a.start_at, tz);
                          if (dest.day !== orig.day || dest.minutes !== orig.minutes) onMove(p.a, dest.day, dest.minutes);
                        }}
                        onPointerCancel={() => setDrag(null)}
                        onKeyDown={(e) => e.key === "Enter" && onOpen(p.a.id)}
                      >
                        {p.height < 36 ? (
                          // Visita breve: ora e cliente su una riga sola.
                          <p className="truncate t-caption leading-tight">
                            <span className="num font-semibold">{t ? `${hhmm(t.minutes)} →` : formatTime(p.a.start_at, tz)}</span>
                            {p.a.is_online && <Video className="ml-1 inline h-3 w-3 align-[-2px]" />}{" "}
                            <span className="font-semibold">{p.a.client_name}</span>
                          </p>
                        ) : (
                          <>
                            <p className="num truncate t-caption font-semibold">
                              {t ? `${hhmm(t.minutes)} →` : formatTime(p.a.start_at, tz)}
                              {p.a.is_online && <Video className="ml-1 inline h-3 w-3 align-[-2px]" />}
                            </p>
                            <p className="truncate t-footnote font-semibold leading-tight">{p.a.client_name}</p>
                          </>
                        )}
                        {p.height > 40 && (
                          <p className="truncate t-caption opacity-80">
                            {p.a.service_name}{showProfessional ? ` · ${p.a.professional_name}` : ""}
                          </p>
                        )}
                      </button>
                    );
                  })}
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
      <p className="border-t border-rule px-4 py-2 t-caption text-ink-3">
        Tocca uno spazio libero per prenotare · trascina un appuntamento per spostarlo · bordo tratteggiato = da confermare
      </p>
    </div>
  );
}

// ---------------------------------------------------------------- mese

function MonthGrid({ days, anchor, items, tz, onPickDay, onOpen }: {
  days: Day[]; anchor: Day; items: Appointment[]; tz: string; onPickDay: (d: Day) => void; onOpen: (id: string) => void;
}) {
  const month = anchor.slice(0, 7);
  const byDay = useMemo(() => {
    const m = new Map<Day, Appointment[]>();
    for (const a of items) {
      const d = zoned(a.start_at, tz).day;
      m.set(d, [...(m.get(d) ?? []), a]);
    }
    return m;
  }, [items, tz]);
  const todayDay = today(tz);

  return (
    <div className="overflow-hidden rounded-[14px] bg-card shadow-card">
      <div className="grid grid-cols-7 border-b border-rule">
        {WEEKDAYS_SHORT.map((w) => <p key={w} className="py-2 text-center t-caption font-semibold text-ink-3">{w}</p>)}
      </div>
      <div className="grid grid-cols-7">
        {days.map((d) => {
          const list = byDay.get(d) ?? [];
          const inMonth = d.startsWith(month);
          return (
            <div key={d} className={`min-h-24 border-t border-l border-rule p-1.5 first:border-l-0 [&:nth-child(7n+1)]:border-l-0 ${inMonth ? "" : "bg-paper/60"}`}>
              <button type="button" onClick={() => onPickDay(d)} className={`num mb-1 grid h-7 w-7 place-items-center rounded-full t-footnote font-semibold hover:bg-ink/[0.06] ${d === todayDay ? "bg-accent text-white hover:bg-accent" : inMonth ? "text-ink" : "text-ink-3"}`}>
                {Number(d.slice(8))}
              </button>
              <ul className="space-y-0.5">
                {list.slice(0, 3).map((a) => (
                  <li key={a.id}>
                    <button type="button" onClick={() => onOpen(a.id)} className="flex w-full items-center gap-1 truncate rounded-[4px] px-1 text-left t-caption hover:bg-ink/[0.05]">
                      <span aria-hidden className="h-1.5 w-1.5 shrink-0 rounded-full" style={{ background: a.color }} />
                      <span className="num text-ink-3">{formatTime(a.start_at, tz)}</span>
                      <span className="truncate">{a.client_name}</span>
                    </button>
                  </li>
                ))}
                {list.length > 3 && (
                  <li><button type="button" onClick={() => onPickDay(d)} className="px-1 t-caption text-link">altri {list.length - 3}</button></li>
                )}
              </ul>
            </div>
          );
        })}
      </div>
    </div>
  );
}
