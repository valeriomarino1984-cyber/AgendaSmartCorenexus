/**
 * Tipi e utilità dell'agenda. Le date si mostrano sempre nel fuso della sede (non in quello del
 * computer di chi guarda): l'API restituisce istanti UTC ("…Z") e riceve orari con il fuso.
 */

export type AppointmentStatus = "pending" | "confirmed" | "cancelled_by_client" | "cancelled_by_staff" | "completed" | "no_show";

export interface Appointment {
  id: string;
  public_code: string;
  client_id: string;
  professional_id: string;
  service_id: string;
  location_id: string;
  start_at: string;
  end_at: string;
  buffer_end_at: string;
  duration_minutes: number;
  preparation_minutes: number;
  status: AppointmentStatus;
  status_label: string;
  source: string;
  is_online: boolean;
  video_url: string | null;
  price: string | null;
  notes: string | null;
  cancellation_reason: string | null;
  version: number;
  client_name?: string;
  client_phone?: string | null;
  service_name?: string;
  color?: string;
  professional_name?: string;
  professional_color?: string;
  events?: { type: string; actor_type: string; at: string; previous: Record<string, unknown> | null; new: Record<string, unknown> | null }[];
}

export interface WeeklyRule {
  id?: string;
  weekday: number;
  start_time: string;
  end_time: string;
}

export interface AvailabilityException {
  id: string;
  professional_id: string | null;
  kind: "vacation" | "unavailable" | "closure" | "extra";
  start_at: string;
  end_at: string;
  reason: string | null;
}

export const WEEKDAYS = ["Lunedì", "Martedì", "Mercoledì", "Giovedì", "Venerdì", "Sabato", "Domenica"];
export const WEEKDAYS_SHORT = ["Lun", "Mar", "Mer", "Gio", "Ven", "Sab", "Dom"];
export const EXCEPTION_LABELS: Record<AvailabilityException["kind"], string> = {
  vacation: "Ferie",
  unavailable: "Non disponibile",
  closure: "Chiusura dello studio",
  extra: "Apertura straordinaria",
};

/** Giorno di calendario "YYYY-MM-DD" (senza fuso). */
export type Day = string;

export interface ZonedParts {
  day: Day;
  hour: number;
  minute: number;
  /** Minuti dalla mezzanotte locale. */
  minutes: number;
}

const partsCache = new Map<string, Intl.DateTimeFormat>();
function fmt(tz: string): Intl.DateTimeFormat {
  let f = partsCache.get(tz);
  if (!f) {
    f = new Intl.DateTimeFormat("en-CA", {
      timeZone: tz,
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
      hourCycle: "h23",
    });
    partsCache.set(tz, f);
  }
  return f;
}

export function zoned(iso: string | Date, tz: string): ZonedParts {
  const parts = Object.fromEntries(fmt(tz).formatToParts(typeof iso === "string" ? new Date(iso) : iso).map((p) => [p.type, p.value]));
  const hour = Number(parts.hour);
  const minute = Number(parts.minute);
  return { day: `${parts.year}-${parts.month}-${parts.day}`, hour, minute, minutes: hour * 60 + minute };
}

/** Scarto del fuso (minuti) in un certo istante, es. +60 per Roma d'inverno. */
function offsetAt(utcMs: number, tz: string): number {
  const p = zoned(new Date(utcMs), tz);
  const [y, m, d] = p.day.split("-").map(Number);
  return (Date.UTC(y!, m! - 1, d!, p.hour, p.minute) - Math.floor(utcMs / 60000) * 60000) / 60000;
}

/** Ora locale della sede → istante ISO con fuso (per l'API). */
export function toInstant(day: Day, minutes: number, tz: string): string {
  const [y, m, d] = day.split("-").map(Number);
  const guess = Date.UTC(y!, m! - 1, d!, Math.floor(minutes / 60), minutes % 60);
  let utc = guess - offsetAt(guess, tz) * 60000;
  utc = guess - offsetAt(utc, tz) * 60000;
  return new Date(utc).toISOString();
}

export function addDays(day: Day, n: number): Day {
  const [y, m, d] = day.split("-").map(Number);
  const t = new Date(Date.UTC(y!, m! - 1, d! + n));
  return t.toISOString().slice(0, 10);
}

/** 1 = lunedì … 7 = domenica. */
export function isoWeekday(day: Day): number {
  const [y, m, d] = day.split("-").map(Number);
  const wd = new Date(Date.UTC(y!, m! - 1, d!)).getUTCDay();
  return wd === 0 ? 7 : wd;
}

export function startOfWeek(day: Day): Day {
  return addDays(day, 1 - isoWeekday(day));
}

export function startOfMonth(day: Day): Day {
  return `${day.slice(0, 7)}-01`;
}

export function addMonths(day: Day, n: number): Day {
  const [y, m] = day.split("-").map(Number);
  const t = new Date(Date.UTC(y!, m! - 1 + n, 1));
  return t.toISOString().slice(0, 10);
}

export function today(tz: string): Day {
  return zoned(new Date(), tz).day;
}

export function hhmm(minutes: number): string {
  return `${String(Math.floor(minutes / 60)).padStart(2, "0")}:${String(minutes % 60).padStart(2, "0")}`;
}

export function parseHHMM(value: string): number {
  const [h, m] = value.split(":").map(Number);
  return (h ?? 0) * 60 + (m ?? 0);
}

export function formatDay(day: Day, options: Intl.DateTimeFormatOptions = { weekday: "long", day: "numeric", month: "long" }): string {
  const [y, m, d] = day.split("-").map(Number);
  return new Intl.DateTimeFormat("it-IT", { ...options, timeZone: "UTC" }).format(new Date(Date.UTC(y!, m! - 1, d!)));
}

export function formatTime(iso: string, tz: string): string {
  return hhmm(zoned(iso, tz).minutes);
}

export const STATUS_TONE: Record<AppointmentStatus, "warn" | "go" | "stamp" | "neutral" | "ink"> = {
  pending: "warn",
  confirmed: "go",
  cancelled_by_client: "stamp",
  cancelled_by_staff: "stamp",
  completed: "neutral",
  no_show: "ink",
};
