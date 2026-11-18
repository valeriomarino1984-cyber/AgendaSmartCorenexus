/**
 * Componenti di base del design system CoreNexus (stessi stili di Presenze, vedi docs/06-design-system.md).
 */
import { ChevronRight, CircleAlert, CircleCheck, CirclePlus } from "lucide-react";
import type { ReactNode } from "react";

export const inputCls =
  "h-11 w-full rounded-[10px] border border-rule-strong bg-card px-3.5 t-body text-ink outline-none transition placeholder:text-ink-3 focus:border-accent focus:ring-4 focus:ring-accent/20";
export const selectCls = `${inputCls} appearance-none bg-[url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='14' height='14' fill='none' stroke='%2386868b' stroke-width='2.2' viewBox='0 0 24 24'%3E%3Cpath d='m7 10 5 5 5-5'/%3E%3C/svg%3E")] bg-[length:14px] bg-[right_0.9rem_center] bg-no-repeat pr-9`;

const btnBase =
  "inline-flex h-11 items-center justify-center gap-1.5 whitespace-nowrap rounded-full px-5 t-subhead font-medium transition active:opacity-75 disabled:pointer-events-none disabled:opacity-40";
/** Pulsante pieno (azione principale). */
export const btnPrimary = `${btnBase} bg-accent text-white hover:bg-accent-hover`;
/** Pulsante grigio (azione secondaria). */
export const btnSecondary = `${btnBase} bg-paper-2 text-ink hover:brightness-95 dark:hover:brightness-125`;
/** Pulsante colorato tenue, come i "tinted button" di iOS. */
export const btnTinted = `${btnBase} bg-accent/12 text-accent hover:bg-accent/18`;
/** Pulsante per azioni distruttive (es. cancellare un appuntamento). */
export const btnDanger = `${btnBase} bg-stamp-soft text-stamp hover:brightness-95 dark:hover:brightness-125`;
export const btnGhost = `${btnBase} text-link hover:underline`;
export const linkCls = "text-link hover:underline";

/** Gruppo arrotondato, come le sezioni delle Impostazioni di iPhone. */
export function Panel({
  title,
  meta,
  actions,
  children,
  flush = false,
  className = "",
}: {
  title?: ReactNode;
  meta?: ReactNode;
  actions?: ReactNode;
  children: ReactNode;
  flush?: boolean;
  className?: string;
}) {
  return (
    <section className={`animate-rise ${className}`}>
      {(title || actions) && (
        <header className="mb-2.5 flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1 px-1">
          <div className="flex min-w-0 flex-wrap items-baseline gap-x-2">
            {title && <h2 className="t-title3 text-ink">{title}</h2>}
            {meta && <span className="t-subhead text-ink-3">{meta}</span>}
          </div>
          {actions && <div className="t-subhead">{actions}</div>}
        </header>
      )}
      <div className={`overflow-hidden rounded-[14px] bg-card shadow-card ${flush ? "" : "p-5"}`}>{children}</div>
    </section>
  );
}

export function PageHeader({ title, meta, actions }: { title: ReactNode; meta?: ReactNode; actions?: ReactNode }) {
  return (
    <div className="flex flex-wrap items-end justify-between gap-4 pb-1">
      <div className="min-w-0">
        {meta && <p className="t-subhead font-semibold text-ink-3 first-letter:uppercase">{meta}</p>}
        <h1 className="t-large-title text-ink">{title}</h1>
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </div>
  );
}

export { Field } from "./Field";

export function Notice({ state }: { state: { ok?: boolean; error?: string; message?: string; detail?: string } }) {
  if (state.error)
    return (
      <p role="alert" className="flex animate-rise items-start gap-2 rounded-[12px] bg-stamp-soft px-3.5 py-2.5 t-subhead text-stamp">
        <CircleAlert className="mt-px h-[18px] w-[18px] shrink-0" strokeWidth={2} />
        <span>{state.error}</span>
      </p>
    );
  if (state.ok && state.message)
    return (
      <p role="status" className="flex animate-rise items-start gap-2 rounded-[12px] bg-go-soft px-3.5 py-2.5 t-subhead text-go">
        <CircleCheck className="mt-px h-[18px] w-[18px] shrink-0" strokeWidth={2} />
        <span>
          <strong className="font-semibold">{state.message}</strong>
          {state.detail && <span className="tabular-nums"> · {state.detail}</span>}
        </span>
      </p>
    );
  return null;
}

export type TagTone = "neutral" | "go" | "stamp" | "ink" | "warn" | "accent" | "wa";
const TAG_TONES: Record<TagTone, string> = {
  neutral: "bg-paper-2 text-ink-2",
  go: "bg-go-soft text-go",
  stamp: "bg-stamp-soft text-stamp",
  warn: "bg-warn-soft text-warn",
  ink: "bg-ink text-canvas",
  accent: "bg-accent/12 text-accent",
  wa: "bg-wa-soft text-wa",
};

export function Tag({ tone = "neutral", children }: { tone?: TagTone; children: ReactNode }) {
  return (
    <span className={`inline-flex items-center gap-1 whitespace-nowrap rounded-full px-2.5 py-0.5 t-footnote font-medium ${TAG_TONES[tone]}`}>
      {children}
    </span>
  );
}

/** Stati dell'appuntamento (docs/02-schema-database.md) con etichetta e tono coerenti in tutta l'app. */
export type AppointmentStatus = "pending" | "confirmed" | "cancelled_by_client" | "cancelled_by_staff" | "completed" | "no_show";
const STATUS: Record<AppointmentStatus, [string, TagTone]> = {
  pending: ["Da confermare", "warn"],
  confirmed: ["Confermato", "go"],
  cancelled_by_client: ["Disdetto dal cliente", "stamp"],
  cancelled_by_staff: ["Cancellato dallo studio", "stamp"],
  completed: ["Svolto", "neutral"],
  no_show: ["Assente", "ink"],
};
export function StatusTag({ status }: { status: AppointmentStatus }) {
  const [label, tone] = STATUS[status];
  return <Tag tone={tone}>{label}</Tag>;
}

type StatTone = "go" | "warn" | "accent" | "indigo" | "teal" | "pink" | "stamp" | "neutral";
const STAT_TONE: Record<StatTone, string> = {
  go: "text-sys-green",
  warn: "text-sys-orange",
  accent: "text-accent",
  indigo: "text-sys-indigo",
  teal: "text-sys-teal",
  pink: "text-sys-pink",
  stamp: "text-sys-red",
  neutral: "text-ink-3",
};

export interface Stat {
  label: string;
  value: ReactNode;
  unit?: string;
  note?: ReactNode;
  icon?: ReactNode;
  tone?: StatTone;
  /** Colora anche il numero (per valori da notare). */
  emphasize?: boolean;
}

/** Riquadri dei numeri in stile app Salute: titolo colorato con simbolo, numero grande arrotondato. */
export function StatStrip({ items }: { items: Stat[] }) {
  return (
    <dl className="grid animate-rise grid-cols-2 gap-3 lg:grid-cols-4">
      {items.map((it) => {
        const tone = STAT_TONE[it.tone ?? "neutral"];
        return (
          <div key={it.label} className="flex flex-col justify-between gap-3 rounded-[14px] bg-card px-4 py-3.5 shadow-card">
            <dt className={`flex items-center gap-1.5 t-subhead font-semibold ${tone}`}>
              {it.icon && <span className="shrink-0 [&>svg]:h-[17px] [&>svg]:w-[17px]">{it.icon}</span>}
              <span className="truncate">{it.label}</span>
            </dt>
            <dd>
              <span className={`num text-[32px] leading-none font-bold tracking-tight ${it.emphasize ? tone : "text-ink"}`}>{it.value}</span>
              {it.unit && <span className="ml-1 t-subhead font-semibold text-ink-3">{it.unit}</span>}
              {it.note && <span className="mt-1.5 block t-footnote text-ink-3">{it.note}</span>}
            </dd>
          </div>
        );
      })}
    </dl>
  );
}

/** Stato vuoto: simbolo, titolo e una riga di spiegazione. */
export function EmptyState({ icon, title, text, action }: { icon: ReactNode; title: string; text?: ReactNode; action?: ReactNode }) {
  return (
    <div className="flex flex-col items-center px-6 py-10 text-center">
      <span className="text-ink-3 [&>svg]:h-10 [&>svg]:w-10">{icon}</span>
      <p className="mt-3 t-headline text-ink">{title}</p>
      {text && <p className="mt-1 max-w-sm t-subhead text-ink-3">{text}</p>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}

/** Monogramma in stile Contatti di iOS. */
export function Monogram({ name, size = 32 }: { name: string; size?: number }) {
  const initials = name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((p) => p[0]!.toUpperCase())
    .join("");
  return (
    <span
      aria-hidden
      className="grid shrink-0 place-items-center rounded-full bg-gradient-to-b from-[#a8a8ad] to-[#86868b] font-semibold text-white dark:from-[#6c6c70] dark:to-[#545458]"
      style={{ width: size, height: size, fontSize: size * 0.4 }}
    >
      {initials}
    </span>
  );
}

/** Simbolo su riquadro colorato, come nelle Impostazioni di iPhone. */
export function IconTile({ icon, className = "bg-accent" }: { icon: ReactNode; className?: string }) {
  return (
    <span aria-hidden className={`grid h-[30px] w-[30px] shrink-0 place-items-center rounded-[8px] text-white [&>svg]:h-[18px] [&>svg]:w-[18px] ${className}`}>
      {icon}
    </span>
  );
}

/** Blocco orario dell'agenda colorato con il colore della prestazione. */
export function ServiceChip({ color, time, title, subtitle }: { color: string; time: string; title: string; subtitle?: string }) {
  return (
    <div className="svc-chip rounded-[8px] px-2.5 py-1.5" style={{ "--sc": color } as React.CSSProperties}>
      <p className="num t-caption font-semibold">{time}</p>
      <p className="truncate t-footnote font-semibold">{title}</p>
      {subtitle && <p className="truncate t-caption opacity-80">{subtitle}</p>}
    </div>
  );
}

/** Riga di elenco in stile iOS che si apre sul posto. */
export function Disclosure({
  leading,
  title,
  subtitle,
  trailing,
  muted = false,
  children,
}: {
  leading?: ReactNode;
  title: ReactNode;
  subtitle?: ReactNode;
  trailing?: ReactNode;
  muted?: boolean;
  children: ReactNode;
}) {
  return (
    <li className="group/row">
      <details className="group">
        <summary className="flex min-h-[56px] cursor-pointer list-none items-center gap-3.5 pl-5 transition-colors hover:bg-ink/[0.03] [&::-webkit-details-marker]:hidden">
          {leading}
          <span className="flex min-h-[56px] min-w-0 flex-1 items-center gap-3 border-t border-rule py-2.5 pr-4 group-first/row:border-t-0">
            <span className="min-w-0 flex-1">
              <span className={`block truncate t-body ${muted ? "text-ink-3 line-through" : "text-ink"}`}>{title}</span>
              {subtitle && <span className="block truncate t-footnote text-ink-3">{subtitle}</span>}
            </span>
            {trailing && <span className="hidden shrink-0 items-center gap-1.5 sm:flex">{trailing}</span>}
            <ChevronRight className="h-[17px] w-[17px] shrink-0 text-ink-3/60 transition-transform duration-200 group-open:rotate-90" strokeWidth={2.4} />
          </span>
        </summary>
        <div className="animate-rise border-t border-rule bg-paper/60 px-5 py-5">{children}</div>
      </details>
    </li>
  );
}

/** Riga "Aggiungi…" in fondo a un elenco: si apre e mostra il modulo. */
export function AddRow({ label, children }: { label: string; children: ReactNode }) {
  return (
    <details className="group border-t border-rule">
      <summary className="flex min-h-[52px] cursor-pointer list-none items-center gap-3 px-5 t-body text-link transition-colors hover:bg-ink/[0.03] [&::-webkit-details-marker]:hidden">
        <CirclePlus className="h-[22px] w-[22px] fill-go-fill text-card" strokeWidth={2} />
        {label}
      </summary>
      <div className="animate-rise border-t border-rule bg-paper/60 px-5 py-5">{children}</div>
    </details>
  );
}
