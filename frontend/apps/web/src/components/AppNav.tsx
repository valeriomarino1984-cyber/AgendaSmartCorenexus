"use client";

import {
  BarChart3, Bell, CalendarDays, Clock3, CreditCard, Globe, Hourglass, LayoutGrid, Settings, Stethoscope, UserRound, Users,
} from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";

const ICONS = {
  dashboard: LayoutGrid,
  agenda: CalendarDays,
  clienti: Users,
  prestazioni: Stethoscope,
  professionisti: UserRound,
  disponibilita: Clock3,
  prenotazioni: Globe,
  notifiche: Bell,
  attesa: Hourglass,
  report: BarChart3,
  impostazioni: Settings,
  abbonamento: CreditCard,
};
export type NavIcon = keyof typeof ICONS;

export interface NavItem {
  href: string;
  label: string;
  /** Etichetta corta per la barra in basso del telefono. */
  short?: string;
  icon: NavIcon;
  /** false = solo nella barra laterale (la barra in basso del telefono ha poco spazio). */
  mobile?: boolean;
  badge?: number;
  /** Sezione della barra laterale. */
  section?: string;
  /** Voce non ancora disponibile: mostrata ma non cliccabile, con la release prevista. */
  comingIn?: string;
}

/** Menu principale dello studio (specifica §15). Le voci con `comingIn` arrivano nelle release successive. */
export const STUDIO_NAV: NavItem[] = [
  { href: "/app", label: "Dashboard", short: "Oggi", icon: "dashboard", section: "Panoramica" },
  { href: "/app/agenda", label: "Agenda", icon: "agenda", section: "Panoramica" },
  { href: "/app/clienti", label: "Clienti", icon: "clienti", section: "Studio" },
  { href: "/app/prestazioni", label: "Prestazioni", icon: "prestazioni", mobile: false, section: "Studio" },
  { href: "/app/professionisti", label: "Professionisti", icon: "professionisti", mobile: false, section: "Studio" },
  { href: "/app/disponibilita", label: "Disponibilità", icon: "disponibilita", mobile: false, section: "Studio" },
  { href: "/app/prenotazioni-online", label: "Prenotazioni online", short: "Online", icon: "prenotazioni", mobile: false, section: "Comunicazioni" },
  { href: "/app/notifiche", label: "Notifiche", icon: "notifiche", section: "Comunicazioni" },
  { href: "/app/lista-attesa", label: "Lista d'attesa", icon: "attesa", mobile: false, section: "Comunicazioni", comingIn: "R2" },
  { href: "/app/report", label: "Report", icon: "report", mobile: false, section: "Sistema", comingIn: "R2" },
  { href: "/app/impostazioni", label: "Impostazioni", icon: "impostazioni", mobile: false, section: "Sistema" },
  { href: "/app/abbonamento", label: "Abbonamento", icon: "abbonamento", mobile: false, section: "Sistema", comingIn: "R4" },
];

function useActive() {
  const path = usePathname();
  return (href: string) => (href === "/app" ? path === "/app" : path.startsWith(href));
}

export function SideNav({ items }: { items: NavItem[] }) {
  const isActive = useActive();
  const sections = [...new Set(items.map((i) => i.section ?? ""))];
  return (
    <nav className="space-y-5">
      {sections.map((sec) => (
        <div key={sec || "main"}>
          {sec && <p className="px-2.5 pb-1 t-caption font-semibold text-ink-3">{sec}</p>}
          <div className="space-y-px">
            {items
              .filter((i) => (i.section ?? "") === sec)
              .map(({ href, label, icon, badge, comingIn }) => {
                const Icon = ICONS[icon];
                if (comingIn)
                  return (
                    <span key={href} aria-disabled className="flex h-8 items-center gap-2.5 rounded-[7px] px-2.5 t-subhead text-ink-3">
                      <Icon className="h-[17px] w-[17px] shrink-0 opacity-60" strokeWidth={1.9} />
                      <span className="flex-1 truncate">{label}</span>
                      <span className="rounded-full bg-ink/[0.06] px-1.5 t-caption">In arrivo</span>
                    </span>
                  );
                const active = isActive(href);
                return (
                  <Link
                    key={href}
                    href={href}
                    aria-current={active ? "page" : undefined}
                    className={`flex h-8 items-center gap-2.5 rounded-[7px] px-2.5 t-subhead transition-colors ${
                      active ? "bg-accent text-white" : "text-ink hover:bg-ink/[0.06]"
                    }`}
                  >
                    <Icon className={`h-[17px] w-[17px] shrink-0 ${active ? "text-white" : "text-accent"}`} strokeWidth={1.9} />
                    <span className="flex-1 truncate">{label}</span>
                    {badge ? (
                      <span className={`num min-w-5 rounded-full px-1.5 text-center t-caption font-semibold ${active ? "bg-white/25 text-white" : "bg-ink/[0.08] text-ink-2"}`}>
                        {badge}
                      </span>
                    ) : null}
                  </Link>
                );
              })}
          </div>
        </div>
      ))}
    </nav>
  );
}

export function BottomNav({ items }: { items: NavItem[] }) {
  const isActive = useActive();
  const visible = items.filter((i) => i.mobile !== false && !i.comingIn);
  return (
    <nav className="glass fixed inset-x-0 bottom-0 z-30 border-t border-ink/10 pb-[env(safe-area-inset-bottom)] lg:hidden">
      <div className="mx-auto grid max-w-lg" style={{ gridTemplateColumns: `repeat(${visible.length}, minmax(0, 1fr))` }}>
        {visible.map(({ href, label, short, icon, badge }) => {
          const Icon = ICONS[icon];
          const active = isActive(href);
          return (
            <Link
              key={href}
              href={href}
              aria-label={label}
              aria-current={active ? "page" : undefined}
              className={`relative flex flex-col items-center gap-[3px] pt-[7px] pb-[5px] text-[10px] font-medium tracking-[0.01em] ${active ? "text-accent" : "text-ink-3"}`}
            >
              <Icon className="h-[25px] w-[25px]" strokeWidth={active ? 2.2 : 1.6} />
              {badge ? (
                <span className="num absolute top-[3px] left-1/2 ml-2 min-w-[18px] rounded-full bg-sys-red px-1 text-center text-[11px] leading-[18px] font-semibold text-white">
                  {badge}
                </span>
              ) : null}
              {short ?? label}
            </Link>
          );
        })}
      </div>
    </nav>
  );
}
