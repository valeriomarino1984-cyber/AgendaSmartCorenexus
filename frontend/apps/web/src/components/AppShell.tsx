import type { ReactNode } from "react";
import { BottomNav, SideNav, type NavItem } from "./AppNav";
import { Logo } from "./Logo";
import { Monogram } from "./ui";

/**
 * Struttura dell'area riservata (come Presenze): barra laterale traslucida su desktop,
 * barra in alto e barra delle schede in basso su telefono.
 * Account e uscita (`account`) saranno collegati all'autenticazione nello Sprint 1.
 */
export function AppShell({
  items,
  studioName,
  roleLabel,
  userName,
  account,
  banner,
  children,
}: {
  items: NavItem[];
  studioName: ReactNode;
  roleLabel: string;
  userName: string;
  account?: ReactNode;
  banner?: ReactNode;
  children: ReactNode;
}) {
  return (
    <div className="min-h-screen lg:grid lg:grid-cols-[256px_1fr]">
      <aside className="vibrant sticky top-0 hidden h-screen flex-col justify-between border-r border-ink/[0.08] px-3 pt-5 pb-4 lg:flex">
        <div className="min-h-0 space-y-6 overflow-y-auto">
          <div className="px-2.5">
            <Logo href="/app" />
            <p className="mt-1.5 truncate t-footnote text-ink-3">
              {studioName} · <span className="text-accent">{roleLabel}</span>
            </p>
          </div>
          <SideNav items={items} />
        </div>
        <div className="flex items-center gap-2.5 rounded-[10px] px-2.5 py-2 hover:bg-ink/[0.05]">
          <Monogram name={userName} size={32} />
          <div className="min-w-0 flex-1">
            <p className="truncate t-footnote font-semibold">{userName}</p>
            {account && <div className="flex items-center gap-3 t-footnote leading-none">{account}</div>}
          </div>
        </div>
      </aside>

      <div className="min-w-0">
        <header className="glass sticky top-0 z-20 flex h-12 items-center justify-between border-b border-ink/10 px-4 lg:hidden">
          <Logo href="/app" />
          <div className="flex items-center gap-3">
            {account && <div className="flex items-center gap-3 t-subhead">{account}</div>}
            <Monogram name={userName} size={30} />
          </div>
        </header>
        <main className="mx-auto max-w-6xl space-y-8 px-4 pt-6 pb-28 sm:px-6 lg:px-10 lg:pt-12 lg:pb-8">
          {banner}
          {children}
        </main>
      </div>
      <BottomNav items={items} />
    </div>
  );
}
