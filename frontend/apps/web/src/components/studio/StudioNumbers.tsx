"use client";

import { BarChart3, CalendarCheck2, CalendarX2, Euro, Gauge, Globe, UserPlus, UserX } from "lucide-react";
import { useEffect, useState } from "react";
import { ColorDot, EmptyState, Panel, StatStrip, selectCls } from "@/components/ui";
import { api } from "@/lib/api";
import { today } from "@/lib/agenda";
import type { Professional } from "@/lib/catalog";
import { PERIODS, euro, hours, pct, periodRange, pointLabel, type PeriodId, type Stats, type TrendPoint } from "@/lib/dashboard";

/** Numeri dello studio nel periodo scelto: riquadri, andamento, prestazioni e professionisti. */
export function StudioNumbers({ tz, canFilter }: { tz: string; canFilter: boolean }) {
  const [period, setPeriod] = useState<PeriodId>("month");
  const [prof, setProf] = useState("");
  const [profs, setProfs] = useState<Professional[]>([]);
  const [result, setResult] = useState<{ key: string; data: Stats | null; error?: string } | null>(null);

  const range = periodRange(period, today(tz));
  const key = `${range.from}|${range.to}|${prof}`;

  useEffect(() => {
    if (canFilter) api<Professional[]>("/professionals").then(setProfs, () => null);
  }, [canFilter]);

  useEffect(() => {
    const [from, to, p] = key.split("|");
    const q = new URLSearchParams({ from: from!, to: to! });
    if (p) q.set("professional_id", p);
    let live = true;
    api<Stats>(`/dashboard/stats?${q}`).then(
      (data) => live && setResult({ key, data }),
      (e: Error) => live && setResult({ key, data: null, error: e.message }),
    );
    return () => {
      live = false;
    };
  }, [key]);

  const loading = result?.key !== key;
  const data = result?.data ?? null;
  const s = data?.summary;

  return (
    <section aria-labelledby="numeri" className="space-y-5">
      <div className="flex flex-wrap items-end justify-between gap-3 px-1">
        <h2 id="numeri" className="t-title2 text-ink">I numeri {data?.scope === "own" ? "della tua agenda" : "dello studio"}</h2>
        <div className="flex w-full flex-wrap gap-2 sm:w-auto">
          <label className="min-w-0 flex-1 sm:w-48 sm:flex-none">
            <span className="sr-only">Periodo</span>
            <select className={selectCls} value={period} onChange={(e) => setPeriod(e.target.value as PeriodId)}>
              {PERIODS.map(([id, label]) => <option key={id} value={id}>{label}</option>)}
            </select>
          </label>
          {canFilter && profs.length > 1 && (
            <label className="min-w-0 flex-1 sm:w-52 sm:flex-none">
              <span className="sr-only">Professionista</span>
              <select className={selectCls} value={prof} onChange={(e) => setProf(e.target.value)}>
                <option value="">Tutti i professionisti</option>
                {profs.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
              </select>
            </label>
          )}
        </div>
      </div>

      {result?.error && !loading && <p className="px-1 t-subhead text-stamp">{result.error}</p>}

      <div aria-busy={loading} className={`transition-opacity ${loading && data ? "opacity-60" : ""}`}>
        {s ? (
          <StatStrip
            items={[
              { label: "Appuntamenti", value: s.appointments, icon: <CalendarCheck2 />, tone: "accent", note: `${s.completed} svolti · ${s.upcoming} da svolgere` },
              { label: "Occupazione", value: pct(s.occupancy), icon: <Gauge />, tone: "indigo", note: s.available_minutes ? `${hours(s.booked_minutes)} su ${hours(s.available_minutes)} di orario` : "Imposta gli orari per calcolarla" },
              { label: "Clienti nuovi", value: s.new_clients, icon: <UserPlus />, tone: "teal", note: `${s.clients_seen} ${s.clients_seen === 1 ? "cliente" : "clienti"} in agenda` },
              { label: "Incassato", value: euro(s.value_done), icon: <Euro />, tone: "go", note: `${euro(s.value_expected)} previsti dagli appuntamenti da svolgere` },
              { label: "Disdette", value: pct(s.cancellation_rate), icon: <CalendarX2 />, tone: "warn", note: `${s.cancelled_by_client} dal cliente · ${s.cancelled_by_staff} dallo studio` },
              { label: "Assenze", value: pct(s.no_show_rate), icon: <UserX />, tone: "stamp", emphasize: (s.no_show_rate ?? 0) >= 0.1, note: s.no_show === 1 ? "1 cliente non si è presentato" : `${s.no_show} clienti non si sono presentati` },
              { label: "Prenotati online", value: s.online, icon: <Globe />, tone: "pink", note: s.appointments ? `${pct(s.online_rate)} degli appuntamenti` : "Dalla pagina di prenotazione" },
            ]}
          />
        ) : (
          <div className="grid grid-cols-2 gap-3 lg:grid-cols-4" aria-hidden>
            {Array.from({ length: 4 }, (_, i) => <div key={i} className="h-[104px] animate-pulse rounded-[14px] bg-card shadow-card" />)}
          </div>
        )}
      </div>

      {data && (
        <>
          <Panel title="Andamento" meta={data.trend.granularity === "month" ? "per mese" : "per giorno"}>
            {s && s.appointments === 0 ? (
              <EmptyState icon={<BarChart3 />} title="Nessun appuntamento nel periodo" text="Il grafico si riempie man mano che prenoti." />
            ) : (
              <Trend points={data.trend.points} granularity={data.trend.granularity} />
            )}
          </Panel>

          <div className="grid gap-5 lg:grid-cols-2">
            <Panel title="Prestazioni" flush>
              {data.services.length === 0 ? (
                <p className="px-5 py-4 t-subhead text-ink-3">Nessuna prestazione nel periodo.</p>
              ) : (
                <table className="w-full t-subhead">
                  <thead className="text-left t-footnote text-ink-3">
                    <tr>
                      <th className="px-5 py-2.5 font-semibold">Prestazione</th>
                      <th className="px-3 py-2.5 text-right font-semibold">Appuntamenti</th>
                      <th className="px-5 py-2.5 text-right font-semibold">Incassato</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.services.map((x) => (
                      <tr key={x.id} className="border-t border-rule">
                        <td className="px-5 py-3">{x.name}</td>
                        <td className="num px-3 py-3 text-right">{x.appointments}</td>
                        <td className="num px-5 py-3 text-right">{euro(x.value_done)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </Panel>

            {data.scope === "studio" && !data.professional_id && data.professionals.length > 0 && (
              <Panel title="Professionisti" flush>
                <table className="w-full t-subhead">
                  <thead className="text-left t-footnote text-ink-3">
                    <tr>
                      <th className="px-5 py-2.5 font-semibold">Nome</th>
                      <th className="px-3 py-2.5 text-right font-semibold">Appuntamenti</th>
                      <th className="hidden px-3 py-2.5 text-right font-semibold sm:table-cell">Assenze</th>
                      <th className="px-5 py-2.5 text-right font-semibold">Occupazione</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.professionals.map((p) => (
                      <tr key={p.id} className="border-t border-rule">
                        <td className="px-5 py-3">
                          <span className="flex items-center gap-2"><ColorDot color={p.color} size={10} />{p.name}</span>
                        </td>
                        <td className="num px-3 py-3 text-right">{p.appointments}</td>
                        <td className="num hidden px-3 py-3 text-right sm:table-cell">{pct(p.no_show_rate)}</td>
                        <td className="num px-5 py-3 text-right">{pct(p.occupancy)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </Panel>
            )}
          </div>
        </>
      )}
    </section>
  );
}

/** Barre degli appuntamenti per giorno o per mese; passando sopra (o con il tab) si leggono i dettagli. */
function Trend({ points, granularity }: { points: TrendPoint[]; granularity: "day" | "month" }) {
  const [active, setActive] = useState<number | null>(null);
  const max = Math.max(1, ...points.map((p) => p.appointments));
  const total = points.reduce((n, p) => n + p.appointments, 0);
  const shown = active === null ? null : points[active];
  const ticks = points.length <= 12 ? points.map((_, i) => i) : [0, Math.floor((points.length - 1) / 2), points.length - 1];

  return (
    <figure>
      <figcaption className="mb-3 min-h-[40px] t-subhead" aria-live="polite">
        {shown ? (
          <>
            <span className="block font-semibold text-ink first-letter:uppercase">{pointLabel(shown.key, granularity, true)}</span>
            <span className="text-ink-2">
              {shown.appointments} {shown.appointments === 1 ? "appuntamento" : "appuntamenti"} · {shown.completed} svolti · {shown.cancelled} disdetti · {shown.no_show} assenti
            </span>
          </>
        ) : (
          <>
            <span className="block font-semibold text-ink">{total} appuntamenti nel periodo</span>
            <span className="text-ink-3">Passa sopra una barra per i dettagli.</span>
          </>
        )}
      </figcaption>
      <div className="relative h-40" onMouseLeave={() => setActive(null)}>
        <span className="absolute inset-x-0 top-0 border-t border-dashed border-rule" aria-hidden />
        <span className="absolute top-0 right-0 -translate-y-full pb-0.5 t-caption num text-ink-3" aria-hidden>{max}</span>
        <ol className="absolute inset-0 flex items-end gap-[2px] border-b border-rule-strong">
          {points.map((p, i) => (
            <li
              key={p.key}
              tabIndex={0}
              aria-label={`${pointLabel(p.key, granularity, true)}: ${p.appointments} appuntamenti`}
              onMouseEnter={() => setActive(i)}
              onFocus={() => setActive(i)}
              onBlur={() => setActive(null)}
              className="group flex h-full min-w-0 flex-1 cursor-default items-end outline-none"
            >
              <span
                className={`block w-full rounded-t-[4px] transition-colors ${active === null || active === i ? "bg-accent" : "bg-accent/35"} group-focus-visible:ring-2 group-focus-visible:ring-accent/50`}
                style={{ height: p.appointments ? `${Math.max(3, (p.appointments / max) * 100)}%` : 0 }}
              />
            </li>
          ))}
        </ol>
      </div>
      <div className="relative mt-1.5 h-4 t-caption text-ink-3" aria-hidden>
        {ticks.map((i) => (
          <span
            key={i}
            className={`absolute whitespace-nowrap ${points.length <= 12 || (i > 0 && i < points.length - 1) ? "-translate-x-1/2" : i === 0 ? "" : "-translate-x-full"}`}
            style={{ left: points.length <= 12 ? `${((i + 0.5) / points.length) * 100}%` : `${(i / Math.max(1, points.length - 1)) * 100}%` }}
          >
            {pointLabel(points[i]!.key, granularity)}
          </span>
        ))}
      </div>
    </figure>
  );
}
