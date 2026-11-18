"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { Notice, btnPrimary } from "@/components/ui";
import { api } from "@/lib/api";

/** Apre l'area clienti dal link ricevuto via email (monouso). */
export function ClientEnter() {
  const router = useRouter();
  const params = useSearchParams();
  const [error, setError] = useState<string | null>(null);
  const started = useRef(false);

  useEffect(() => {
    if (started.current) return;
    started.current = true;
    const token = params.get("token") ?? "";
    api("/client-portal/login", { body: { token } }).then(
      () => router.replace("/area-clienti"),
      (e: Error) => setError(e.message),
    );
  }, [params, router]);

  if (!error) return <p className="text-center t-body text-ink-3">Accesso in corso…</p>;
  return (
    <div className="space-y-4">
      <Notice state={{ error }} />
      <Link href="/area-clienti" className={`${btnPrimary} w-full`}>Richiedi un nuovo link</Link>
    </div>
  );
}
