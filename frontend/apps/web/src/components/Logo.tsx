import Link from "next/link";
import { APP_NAME } from "@/lib/brand";

/** Squircle blu della famiglia CoreNexus (come Presenze) con un calendario e la spunta di conferma. */
export function LogoMark({ className = "h-7 w-7", animated = false }: { className?: string; animated?: boolean }) {
  return (
    <svg viewBox="0 0 64 64" className={className} aria-hidden>
      <path d="M32 0c16.5 0 23 0 27.5 4.5S64 15.5 64 32s0 23-4.5 27.5S48.5 64 32 64 9 64 4.5 59.5 0 48.5 0 32 0 9 4.5 4.5 15.5 0 32 0Z" fill="#0071e3" />
      <path d="M32 0c16.5 0 23 0 27.5 4.5S64 15.5 64 32H0C0 15.5 0 9 4.5 4.5S15.5 0 32 0Z" fill="#fff" fillOpacity="0.14" />
      <rect x="15" y="18" width="34" height="31" rx="6" fill="#fff" />
      <path d="M15 24a6 6 0 0 1 6-6h22a6 6 0 0 1 6 6v3H15Z" fill="#cfe3fb" />
      <rect x="22" y="13" width="4.5" height="10" rx="2.25" fill="#fff" />
      <rect x="37.5" y="13" width="4.5" height="10" rx="2.25" fill="#fff" />
      <path
        d="M24.5 38l5.5 5.2L40 33"
        className={animated ? "splash-check" : undefined}
        fill="none"
        stroke="#0071e3"
        strokeWidth="4.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

export function Logo({ href = "/", tone = "dark" }: { href?: string; tone?: "dark" | "light" }) {
  return (
    <Link href={href} className="flex items-center gap-2" aria-label={`${APP_NAME}, home`}>
      <LogoMark />
      <span className={`text-[17px] font-semibold tracking-tight ${tone === "light" ? "text-white" : "text-ink"}`}>{APP_NAME}</span>
    </Link>
  );
}
