"use client";

import { useCallback, useEffect, useState } from "react";
import { PlatformLogin } from "@/components/platform/PlatformLogin";
import { PlatformPanel } from "@/components/platform/PlatformPanel";
import { PlatformShell } from "@/components/platform/PlatformShell";
import { api, ApiError } from "@/lib/api";
import type { StaffMe } from "@/lib/platform";

/** /piattaforma: senza sessione completa (password + codice) mostra l'accesso, altrimenti il pannello. */
export function PlatformApp() {
  const [me, setMe] = useState<StaffMe | null | "login">(null);
  const load = useCallback(() => {
    api<StaffMe>("/platform/me").then(setMe, (e) => {
      if (e instanceof ApiError && e.status === 401) setMe("login");
    });
  }, []);
  useEffect(load, [load]);

  if (me === null) return <div className="min-h-screen bg-paper" />;
  if (me === "login")
    return (
      <PlatformShell>
        <PlatformLogin onLogged={setMe} />
      </PlatformShell>
    );
  return (
    <PlatformShell
      who={me.email}
      onLogout={async () => {
        await api("/platform/logout", { method: "POST" }).catch(() => null);
        setMe("login");
      }}
    >
      <PlatformPanel me={me} />
    </PlatformShell>
  );
}
