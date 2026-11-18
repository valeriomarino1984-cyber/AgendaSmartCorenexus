"use client";

import { Hourglass } from "lucide-react";
import { usePathname, useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { studioNav } from "@/components/AppNav";
import { AppShell } from "@/components/AppShell";
import { LogoMark } from "@/components/Logo";
import { api, ApiError, type Me } from "@/lib/api";
import { MeContext } from "@/lib/me";

/**
 * Area riservata: chiede il profilo all'API; senza sessione valida rimanda all'accesso.
 * Il controllo vero è nell'API (ogni rotta verifica la sessione): qui si decide solo cosa mostrare.
 */
export function AppGate({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const [me, setMeState] = useState<Me | null>(null);
  const [daysLeft, setDaysLeft] = useState<number | null>(null);
  const [failure, setFailure] = useState<string | null>(null);

  const setMe = useCallback((value: Me) => {
    setMeState(value);
    setDaysLeft(
      value.tenant.trial_ends_at
        ? Math.ceil((new Date(value.tenant.trial_ends_at).getTime() - Date.now()) / 86_400_000)
        : null,
    );
  }, []);

  const onError = useCallback(
    (e: unknown) => {
      if (e instanceof ApiError && e.status === 401) {
        router.replace(`/accedi?next=${encodeURIComponent(pathname)}`);
      } else {
        setFailure(e instanceof Error ? e.message : "Errore");
      }
    },
    [router, pathname],
  );

  const refresh = useCallback(async () => {
    await api<Me>("/auth/me").then(setMe, onError);
  }, [setMe, onError]);

  useEffect(() => {
    api<Me>("/auth/me").then(setMe, onError);
  }, [setMe, onError]);

  async function logout() {
    await api("/auth/logout", { method: "POST" }).catch(() => null);
    router.replace("/accedi?uscito=1");
  }

  async function switchTenant(tenantId: string) {
    setMe(await api<Me>("/auth/switch-tenant", { body: { tenant_id: tenantId } }));
    router.push("/app");
  }

  if (failure)
    return (
      <div className="grid min-h-screen place-items-center px-6 text-center">
        <div>
          <p className="t-headline">Non riusciamo a caricare l&apos;area riservata</p>
          <p className="mt-1 t-subhead text-ink-3">{failure}</p>
          <button className="mt-4 t-subhead text-link" onClick={() => location.reload()}>Riprova</button>
        </div>
      </div>
    );

  if (!me)
    return (
      <div className="grid min-h-screen place-items-center" aria-busy>
        <LogoMark className="h-14 w-14 animate-pulse" />
      </div>
    );

  const studio =
    me.tenants.length > 1 ? (
      <select
        aria-label="Cambia studio"
        className="max-w-[150px] truncate bg-transparent text-ink-3 outline-none"
        value={me.tenant.id}
        onChange={(e) => void switchTenant(e.target.value)}
      >
        {me.tenants.map((t) => (
          <option key={t.id} value={t.id}>{t.name}</option>
        ))}
      </select>
    ) : (
      me.tenant.name
    );

  return (
    <MeContext.Provider value={{ me, refresh }}>
      <AppShell
        items={studioNav(me.role)}
        studioName={studio}
        roleLabel={me.role_label}
        userName={me.user.full_name}
        account={
          <button onClick={logout} className="text-link hover:underline">
            Esci
          </button>
        }
        banner={
          me.tenant.status === "trial" && daysLeft !== null && daysLeft >= 0 ? (
            <div role="status" className={`flex items-center gap-3 rounded-[14px] px-5 py-3.5 ${daysLeft <= 3 ? "bg-warn-soft" : "bg-accent/10"}`}>
              <Hourglass className={`h-5 w-5 shrink-0 ${daysLeft <= 3 ? "text-warn" : "text-accent"}`} />
              <p className="t-subhead text-ink-2">
                <span className="font-semibold text-ink">
                  {daysLeft === 0 ? "Oggi è l'ultimo giorno di prova." : `Periodo di prova: ${daysLeft === 1 ? "manca 1 giorno" : `mancano ${daysLeft} giorni`}.`}
                </span>{" "}
                I dati restano tutti anche dopo la prova.
              </p>
            </div>
          ) : null
        }
      >
        {children}
      </AppShell>
    </MeContext.Provider>
  );
}
