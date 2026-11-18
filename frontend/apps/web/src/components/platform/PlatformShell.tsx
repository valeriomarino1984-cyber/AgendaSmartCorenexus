"use client";

import { LogOut, ShieldCheck } from "lucide-react";
import Link from "next/link";
import type { ReactNode } from "react";
import { LogoMark } from "@/components/Logo";
import { VersionFooter } from "@/components/VersionFooter";

/** Cornice dell'area piattaforma: barra scura, ben distinta dall'area degli studi. */
export function PlatformShell({ who, onLogout, children }: { who?: string; onLogout?: () => void; children: ReactNode }) {
  return (
    <div className="min-h-screen bg-paper">
      <header className="sticky top-0 z-20 border-b border-white/10 bg-[#111114] text-white">
        <div className="mx-auto flex h-12 max-w-6xl items-center justify-between px-4 sm:px-6">
          <Link href="/piattaforma" className="flex items-center gap-2">
            <LogoMark className="h-7 w-7" />
            <span className="t-subhead font-semibold">CoreNexus</span>
            <span className="inline-flex items-center gap-1 rounded-full bg-white/10 px-2 py-0.5 t-caption font-semibold text-[#64d2ff]">
              <ShieldCheck className="h-3.5 w-3.5" /> Piattaforma
            </span>
          </Link>
          {who && (
            <span className="flex items-center gap-4 t-footnote text-white/70">
              <span className="hidden sm:inline">{who}</span>
              {onLogout && (
                <button type="button" onClick={onLogout} className="inline-flex items-center gap-1.5 text-[#64d2ff] hover:underline">
                  <LogOut className="h-4 w-4" /> Esci
                </button>
              )}
            </span>
          )}
        </div>
      </header>
      <main className="mx-auto max-w-6xl space-y-8 px-4 py-8 sm:px-6 lg:py-12">{children}</main>
      <VersionFooter />
    </div>
  );
}
