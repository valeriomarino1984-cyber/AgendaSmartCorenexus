import Link from "next/link";
import { Briefcase, UserRound } from "lucide-react";

/** Scelta dell'area in cima alle pagine di accesso: professionisti e clienti hanno accessi separati. */
export function AreaSwitch({ current }: { current: "professionisti" | "clienti" }) {
  const items = [
    { id: "professionisti", href: "/accedi", label: "Professionisti", icon: <Briefcase className="h-4 w-4" /> },
    { id: "clienti", href: "/area-clienti", label: "Clienti", icon: <UserRound className="h-4 w-4" /> },
  ] as const;
  return (
    <nav aria-label="Scegli l'area" className="mb-6 grid grid-cols-2 rounded-[11px] bg-paper-2 p-[3px]">
      {items.map((it) => {
        const active = it.id === current;
        return (
          <Link
            key={it.id}
            href={it.href}
            aria-current={active ? "page" : undefined}
            className={`flex items-center justify-center gap-1.5 rounded-[9px] py-2 t-subhead font-medium transition ${
              active ? "bg-thumb text-ink shadow-[0_3px_8px_rgb(0_0_0/0.12)]" : "text-ink-2 hover:text-ink"
            }`}
          >
            {it.icon}
            {it.label}
          </Link>
        );
      })}
    </nav>
  );
}
