"use client";

import { useRouter, useSearchParams } from "next/navigation";
import QRCode from "qrcode";
import { useEffect, useState } from "react";
import { useAction } from "@/components/auth/useAction";
import { Field, Notice, btnPrimary, inputCls } from "@/components/ui";
import { api } from "@/lib/api";

interface Info { email: string; full_name: string; otpauth_uri: string; secret: string }

/** Invito (anche prima configurazione): nome, password e collegamento dell'app dei codici con il QR. */
export function PlatformInvite() {
  const router = useRouter();
  const params = useSearchParams();
  const token = params.get("token") ?? "";
  const [info, setInfo] = useState<Info | null>(null);
  const [qr, setQr] = useState<string | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [f, setF] = useState({ full_name: "", password: "", password2: "", code: "" });
  const { pending, error, run } = useAction();

  useEffect(() => {
    api<Info>(`/platform/invite?token=${encodeURIComponent(token)}`).then(
      async (i) => {
        setInfo(i);
        setF((prev) => ({ ...prev, full_name: i.full_name }));
        setQr(await QRCode.toString(i.otpauth_uri, { type: "svg", margin: 1 }));
      },
      (e: Error) => setLoadError(e.message),
    );
  }, [token]);

  if (loadError) return <Notice state={{ error: loadError }} />;
  if (!info) return <p className="t-body text-ink-3">Caricamento…</p>;

  const mismatch = f.password2.length > 0 && f.password !== f.password2;

  return (
    <form
      className="mx-auto max-w-[520px] space-y-6"
      noValidate
      onSubmit={async (e) => {
        e.preventDefault();
        const ok = await run(() => api("/platform/invite/accept", { body: { token, full_name: f.full_name, password: f.password, code: f.code } }));
        if (ok) router.replace("/piattaforma");
      }}
    >
      <div className="text-center">
        <h1 className="text-[30px] font-semibold tracking-tight">Configura l&apos;accesso</h1>
        <p className="mt-1 t-subhead text-ink-3">{info.email}</p>
      </div>
      <section className="space-y-4 rounded-[18px] bg-card p-6 shadow-card">
        <p className="t-headline">1. Nome e password</p>
        <Field label="Nome e cognome"><input className={inputCls} value={f.full_name} onChange={(e) => setF({ ...f, full_name: e.target.value })} /></Field>
        <Field label="Password" hint="Almeno 10 caratteri, senza il tuo nome o la tua email.">
          <input className={inputCls} type="password" autoComplete="new-password" value={f.password} onChange={(e) => setF({ ...f, password: e.target.value })} />
        </Field>
        <Field label="Ripeti la password"><input className={inputCls} type="password" autoComplete="new-password" value={f.password2} onChange={(e) => setF({ ...f, password2: e.target.value })} /></Field>
        {mismatch && <p className="t-footnote text-stamp">Le password non coincidono.</p>}
      </section>
      <section className="space-y-4 rounded-[18px] bg-card p-6 shadow-card">
        <p className="t-headline">2. App dei codici</p>
        <p className="t-subhead text-ink-2">Con Google Authenticator, Microsoft Authenticator o un&apos;app simile inquadra il QR. Non riesci? Inserisci a mano la chiave qui sotto.</p>
        {qr && <div className="mx-auto h-48 w-48 rounded-[16px] bg-white p-2 ring-1 ring-rule" dangerouslySetInnerHTML={{ __html: qr.replace("<svg", '<svg width="100%" height="100%"') }} />}
        <p className="num rounded-[10px] bg-paper-2 px-3 py-2 text-center t-footnote break-all select-all">{info.secret.match(/.{1,4}/g)?.join(" ")}</p>
        <Field label="Codice a 6 cifre mostrato dall'app">
          <input className={`${inputCls} num text-center text-[24px] tracking-[0.3em]`} inputMode="numeric" autoComplete="one-time-code" maxLength={7} value={f.code} onChange={(e) => setF({ ...f, code: e.target.value })} />
        </Field>
      </section>
      {error && <Notice state={{ error: error.message }} />}
      <button className={`${btnPrimary} w-full`} disabled={pending || mismatch || !f.password || f.code.replace(/\D/g, "").length !== 6}>
        {pending ? "Attivazione…" : "Attiva l'accesso"}
      </button>
    </form>
  );
}
