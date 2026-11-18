import Link from "next/link";
import type { ReactNode } from "react";
import { Logo, LogoMark } from "./Logo";

/** Pagine di accesso nello stile di Presenze: barra in vetro, logo grande, titolo e modulo al centro. */
export function AuthShell({
  kicker,
  title,
  subtitle,
  children,
  footer,
}: {
  kicker?: string;
  title: string;
  subtitle?: ReactNode;
  children: ReactNode;
  footer?: ReactNode;
}) {
  return (
    <main className="flex min-h-screen flex-col bg-paper">
      <header className="glass sticky top-0 z-10 border-b border-ink/10">
        <div className="mx-auto flex h-12 max-w-5xl items-center justify-between px-4 sm:px-6">
          <Logo />
          <Link href="/" className="t-footnote text-link hover:underline">
            Torna al sito
          </Link>
        </div>
      </header>
      <div className="flex flex-1 items-start justify-center px-4 py-12 sm:py-20">
        <div className="w-full max-w-[420px] animate-rise">
          <div className="mb-8 text-center">
            <LogoMark className="mx-auto h-16 w-16" />
            {kicker && <p className="mt-5 t-subhead font-semibold text-accent">{kicker}</p>}
            <h1 className="mt-1 text-[32px] leading-tight font-semibold tracking-tight">{title}</h1>
            {subtitle && <p className="mt-2 t-body text-ink-3">{subtitle}</p>}
          </div>
          <div className="rounded-[18px] bg-card p-6 shadow-card">{children}</div>
          {footer && <div className="mt-6 text-center t-subhead text-ink-3">{footer}</div>}
        </div>
      </div>
    </main>
  );
}

export function FormSkeleton() {
  return (
    <div className="space-y-3" aria-hidden>
      <div className="h-11 animate-pulse rounded-[10px] bg-paper-2" />
      <div className="h-11 animate-pulse rounded-[10px] bg-paper-2" />
      <div className="h-11 animate-pulse rounded-full bg-paper-2" />
    </div>
  );
}
