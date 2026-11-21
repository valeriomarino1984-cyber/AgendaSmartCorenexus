import { Suspense } from "react";
import { AuthShell, FormSkeleton } from "@/components/AuthShell";
import { ClientEnter } from "@/components/clienti/ClientEnter";

export const instant = false;

export const metadata = { title: "Accesso area clienti", robots: { index: false, follow: false } };

export default function Page() {
  return (
    <AuthShell kicker="Area clienti" title="Un attimo…" subtitle="Stiamo aprendo i tuoi appuntamenti.">
      <Suspense fallback={<FormSkeleton />}>
        <ClientEnter />
      </Suspense>
    </AuthShell>
  );
}
