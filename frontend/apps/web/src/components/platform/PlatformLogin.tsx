"use client";

import { KeyRound } from "lucide-react";
import { useEffect, useState } from "react";
import { useAction } from "@/components/auth/useAction";
import { Field, Notice, btnPrimary, btnSecondary, inputCls } from "@/components/ui";
import { api } from "@/lib/api";
import type { StaffMe } from "@/lib/platform";

/** Accesso in due passaggi: email e password, poi il codice a 6 cifre dell'app. Oppure prima configurazione. */
export function PlatformLogin({ onLogged }: { onLogged: (me: StaffMe) => void }) {
  const [st, setSt] = useState<{ configured: boolean; setup_available: boolean } | null>(null);
  const [step, setStep] = useState<"login" | "code" | "setup" | "sent">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [code, setCode] = useState("");
  const [sent, setSent] = useState("");
  const { pending, error, run } = useAction();

  useEffect(() => {
    api<{ configured: boolean; setup_available: boolean }>("/platform/status").then((s) => {
      setSt(s);
      if (s.setup_available) setStep("setup");
    }, () => null);
  }, []);

  if (!st) return null;
  if (!st.configured)
    return <Notice state={{ error: "L'area piattaforma non è ancora attiva: manca PLATFORM_SECRET_KEY nelle impostazioni del server." }} />;

  return (
    <div className="mx-auto w-full max-w-[420px] space-y-6">
      <div className="text-center">
        <span className="mx-auto grid h-14 w-14 place-items-center rounded-[16px] bg-[#111114] text-[#64d2ff]"><KeyRound className="h-7 w-7" /></span>
        <h1 className="mt-4 text-[30px] font-semibold tracking-tight">
          {step === "setup" || step === "sent" ? "Prima configurazione" : "Accesso piattaforma"}
        </h1>
        <p className="mt-1 t-subhead text-ink-3">Riservato al team CoreNexus.</p>
      </div>
      <div className="rounded-[18px] bg-card p-6 shadow-card">
        {error && <div className="mb-4"><Notice state={{ error: error.message }} /></div>}
        {step === "setup" && (
          <form
            className="space-y-4"
            noValidate
            onSubmit={async (e) => {
              e.preventDefault();
              const r = await run(() => api<{ message: string }>("/platform/setup", { body: { email } }));
              if (r) {
                setSent(r.message);
                setStep("sent");
              }
            }}
          >
            <p className="t-subhead text-ink-2">Non esiste ancora nessun account. Inserisci l&apos;email indicata nelle impostazioni del server: riceverai il link per scegliere la password e collegare l&apos;app dei codici.</p>
            <Field label="Email"><input className={inputCls} type="email" autoComplete="email" value={email} onChange={(e) => setEmail(e.target.value)} /></Field>
            <button className={`${btnPrimary} w-full`} disabled={pending || !email.includes("@")}>Invia il link</button>
          </form>
        )}
        {step === "sent" && <Notice state={{ ok: true, message: sent }} />}
        {step === "login" && (
          <form
            className="space-y-4"
            noValidate
            onSubmit={async (e) => {
              e.preventDefault();
              const r = await run(() => api("/platform/login", { body: { email, password } }));
              if (r) setStep("code");
            }}
          >
            <Field label="Email"><input className={inputCls} type="email" autoComplete="username" value={email} onChange={(e) => setEmail(e.target.value)} /></Field>
            <Field label="Password"><input className={inputCls} type="password" autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} /></Field>
            <button className={`${btnPrimary} w-full`} disabled={pending || !email || !password}>Continua</button>
          </form>
        )}
        {step === "code" && (
          <form
            className="space-y-4"
            noValidate
            onSubmit={async (e) => {
              e.preventDefault();
              const me = await run(() => api<StaffMe>("/platform/login/mfa", { body: { code } }));
              if (me) onLogged(me);
            }}
          >
            <p className="t-subhead text-ink-2">Apri l&apos;app di autenticazione e inserisci il codice a 6 cifre di CoreNexus Agenda.</p>
            <Field label="Codice">
              <input className={`${inputCls} num text-center text-[24px] tracking-[0.3em]`} inputMode="numeric" autoComplete="one-time-code" maxLength={7} autoFocus value={code} onChange={(e) => setCode(e.target.value)} />
            </Field>
            <button className={`${btnPrimary} w-full`} disabled={pending || code.replace(/\D/g, "").length !== 6}>Accedi</button>
            <button type="button" className={`${btnSecondary} w-full`} onClick={() => { setStep("login"); setCode(""); }}>Indietro</button>
          </form>
        )}
      </div>
    </div>
  );
}
