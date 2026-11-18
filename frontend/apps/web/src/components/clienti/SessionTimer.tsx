"use client";

import { Timer } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { btnPrimary, btnSecondary } from "@/components/ui";
import { api } from "@/lib/api";

const WARN_SECONDS = 30;
const ACTIVITY_PING_EVERY = 60_000;

/**
 * Timer di disconnessione dell'area clienti (in alto a destra).
 * - Ogni attività sulla pagina (tocco, tasto, scorrimento) rinnova la sessione, al massimo una volta al minuto.
 * - 30 secondi prima della scadenza compare l'avviso "Vuoi restare connesso?": da lì serve il pulsante.
 * - Allo scadere si esce da soli. Il limite vale anche sul server, che chiude la sessione comunque.
 */
export function SessionTimer({ idleSeconds, onExpire }: { idleSeconds: number; onExpire: () => void }) {
  const [deadline, setDeadline] = useState(() => Date.now() + idleSeconds * 1000);
  const [now, setNow] = useState(() => Date.now());
  const lastPing = useRef(0);
  const expired = useRef(false);
  const left = Math.min(idleSeconds, Math.max(0, Math.ceil((deadline - now) / 1000)));
  const warning = left <= WARN_SECONDS;

  const renew = useCallback(async () => {
    lastPing.current = Date.now();
    try {
      const res = await api<{ idle_seconds: number }>("/client-portal/keepalive", { method: "POST" });
      const t = Date.now();
      setNow(t);
      setDeadline(t + res.idle_seconds * 1000);
    } catch {
      // Sessione già chiusa dal server: si esce.
      if (!expired.current) {
        expired.current = true;
        onExpire();
      }
    }
  }, [onExpire]);

  useEffect(() => {
    lastPing.current = Date.now(); // la sessione è appena stata rinnovata dal caricamento della pagina
    const t = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(t);
  }, []);

  useEffect(() => {
    if (left > 0 || expired.current) return;
    expired.current = true;
    api("/client-portal/logout", { method: "POST" }).catch(() => null).finally(onExpire);
  }, [left, onExpire]);

  useEffect(() => {
    const onActivity = () => {
      if (warning || Date.now() - lastPing.current < ACTIVITY_PING_EVERY) return;
      void renew();
    };
    const events = ["pointerdown", "keydown", "scroll", "touchstart"] as const;
    events.forEach((e) => window.addEventListener(e, onActivity, { passive: true }));
    return () => events.forEach((e) => window.removeEventListener(e, onActivity));
  }, [warning, renew]);

  const mm = String(Math.floor(left / 60)).padStart(1, "0");
  const ss = String(left % 60).padStart(2, "0");

  return (
    <>
      <span
        role="timer"
        aria-label={`Disconnessione automatica tra ${mm} minuti e ${ss} secondi`}
        title="Per sicurezza l'area clienti si chiude dopo 5 minuti senza attività"
        className={`num inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 t-footnote font-semibold tabular-nums transition-colors ${
          warning ? "bg-stamp-soft text-stamp" : "bg-paper-2 text-ink-2"
        }`}
      >
        <Timer className="h-3.5 w-3.5" />
        {mm}:{ss}
      </span>
      {warning && left > 0 && (
        <div className="fixed inset-x-0 top-14 z-50 flex justify-center px-4">
          <div
            role="alertdialog"
            aria-modal="false"
            aria-labelledby="sessione-titolo"
            aria-describedby="sessione-testo"
            className="w-full max-w-md animate-banner rounded-[16px] bg-card p-5 shadow-[0_20px_50px_-15px_rgb(0_0_0/0.45)] ring-1 ring-stamp/30"
          >
            <p id="sessione-titolo" className="t-headline">Vuoi restare connesso?</p>
            <p id="sessione-testo" className="mt-1 t-subhead text-ink-2">
              Per sicurezza l&apos;area clienti si chiude tra <span className="num font-semibold text-stamp">{left}</span> secondi.
            </p>
            <div className="mt-4 flex flex-wrap gap-2">
              <button type="button" autoFocus className={btnPrimary} onClick={() => void renew()}>
                Resta connesso
              </button>
              <button
                type="button"
                className={btnSecondary}
                onClick={() => {
                  expired.current = true;
                  api("/client-portal/logout", { method: "POST" }).catch(() => null).finally(onExpire);
                }}
              >
                Esci ora
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
