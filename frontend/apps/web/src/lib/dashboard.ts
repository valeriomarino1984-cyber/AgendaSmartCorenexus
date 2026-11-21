import { addDays, addMonths, startOfMonth, startOfWeek, type Day } from "./agenda";

export interface Summary {
  appointments: number;
  completed: number;
  upcoming: number;
  pending: number;
  cancelled: number;
  cancelled_by_client: number;
  cancelled_by_staff: number;
  no_show: number;
  cancellation_rate: number | null;
  no_show_rate: number | null;
  online: number;
  online_rate: number | null;
  value_done: string;
  value_expected: string;
  booked_minutes: number;
  available_minutes: number | null;
  occupancy: number | null;
}

export interface TrendPoint {
  key: string;
  appointments: number;
  completed: number;
  cancelled: number;
  no_show: number;
}

export interface Stats {
  from: Day;
  to: Day;
  timezone: string;
  scope: "studio" | "own";
  professional_id: string | null;
  summary: Summary & { clients_seen: number; new_clients: number };
  trend: { granularity: "day" | "month"; points: TrendPoint[] };
  services: { id: string; name: string; appointments: number; completed: number; value_done: string; value_expected: string }[];
  professionals: (Summary & { id: string; name: string; color: string })[];
}

export type PeriodId = "week" | "month" | "last_month" | "quarter" | "year";

export const PERIODS: readonly (readonly [PeriodId, string])[] = [
  ["week", "Questa settimana"],
  ["month", "Questo mese"],
  ["last_month", "Mese scorso"],
  ["quarter", "Ultimi 3 mesi"],
  ["year", "Quest'anno"],
];

export function periodRange(id: PeriodId, today: Day): { from: Day; to: Day } {
  const month = startOfMonth(today);
  switch (id) {
    case "week": {
      const from = startOfWeek(today);
      return { from, to: addDays(from, 6) };
    }
    case "month":
      return { from: month, to: addDays(addMonths(month, 1), -1) };
    case "last_month":
      return { from: addMonths(month, -1), to: addDays(month, -1) };
    case "quarter":
      return { from: addMonths(month, -2), to: addDays(addMonths(month, 1), -1) };
    case "year":
      return { from: `${today.slice(0, 4)}-01-01`, to: `${today.slice(0, 4)}-12-31` };
  }
}

const pctFmt = new Intl.NumberFormat("it-IT", { style: "percent", maximumFractionDigits: 0 });
const euroFmt = new Intl.NumberFormat("it-IT", { style: "currency", currency: "EUR", maximumFractionDigits: 0 });

export function pct(v: number | null): string {
  return v === null ? "—" : pctFmt.format(v);
}

export function euro(v: string): string {
  return euroFmt.format(Number(v));
}

export function hours(minutes: number): string {
  const h = minutes / 60;
  return `${new Intl.NumberFormat("it-IT", { maximumFractionDigits: 1 }).format(h)} h`;
}

/** Etichetta breve di un punto dell'andamento: "12 nov" oppure "nov 2026". */
export function pointLabel(key: string, granularity: "day" | "month", long = false): string {
  if (granularity === "month") {
    const [y, m] = key.split("-").map(Number);
    return new Intl.DateTimeFormat("it-IT", { month: long ? "long" : "short", year: "numeric", timeZone: "UTC" }).format(new Date(Date.UTC(y!, m! - 1, 1)));
  }
  const [y, m, d] = key.split("-").map(Number);
  return new Intl.DateTimeFormat("it-IT", long ? { weekday: "long", day: "numeric", month: "long", timeZone: "UTC" } : { day: "numeric", month: "short", timeZone: "UTC" }).format(new Date(Date.UTC(y!, m! - 1, d!)));
}
