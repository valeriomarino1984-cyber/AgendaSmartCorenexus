import Link from "next/link";
import { APP_NAME, APP_UPDATED, APP_VERSION, DEVELOPER, DEVELOPER_URL } from "@/lib/brand";

/** Piè di pagina con versione, data dell'ultimo aggiornamento e sviluppatore (come in Presenze). */
export function VersionFooter({ className = "" }: { className?: string }) {
  return (
    <footer className={`px-4 py-6 text-center t-caption text-ink-3 ${className}`}>
      <Link href="/novita" className="hover:text-ink" title="Cosa c'è di nuovo">
        {APP_NAME} <span className="num">{APP_VERSION}</span>
      </Link>
      <span aria-hidden> · </span>
      aggiornata al <span className="num">{APP_UPDATED}</span>
      <span aria-hidden> · </span>
      Sviluppato da{" "}
      <a href={DEVELOPER_URL} target="_blank" rel="noopener noreferrer" className="hover:text-ink">
        {DEVELOPER}
      </a>
    </footer>
  );
}
