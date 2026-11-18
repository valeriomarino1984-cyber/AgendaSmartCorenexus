import Link from "next/link";
import { VersionFooter } from "@/components/VersionFooter";
import { APP_NAME, APP_UPDATED } from "@/lib/brand";

/** Piè di pagina delle pagine pubbliche: copyright, collegamenti e versione (come presenze.corenexus.it). */
export function SiteFooter() {
  const year = APP_UPDATED.slice(-4);
  return (
    <footer className="bg-paper px-4 pb-8">
      <div className="mx-auto flex max-w-5xl flex-wrap justify-between gap-3 border-t border-rule-strong pt-5 text-[12px] text-ink-3">
        <span>
          Copyright © {year} {APP_NAME}. Un servizio{" "}
          <a href="https://www.corenexus.it" target="_blank" rel="noopener noreferrer" className="nav-u hover:text-ink">
            CoreNexus
          </a>
          . Tutti i diritti riservati.
        </span>
        <span className="flex flex-wrap gap-5">
          <Link href="/novita" className="nav-u hover:text-ink">Novità</Link>
          <Link href="/#contatti" className="nav-u hover:text-ink">Contatti</Link>
          <Link href="/accedi" className="nav-u hover:text-ink">Area professionisti</Link>
          <Link href="/area-clienti" className="nav-u hover:text-ink">Area clienti</Link>
        </span>
      </div>
      <VersionFooter className="px-0 pt-4 pb-0" />
    </footer>
  );
}
