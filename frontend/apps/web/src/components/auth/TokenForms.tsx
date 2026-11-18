"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import { Field, Notice, btnPrimary, inputCls, linkCls } from "../ui";
import { FormSkeleton } from "../AuthShell";
import { useAction } from "./useAction";

/** /verifica-email?token=… : conferma l'indirizzo ed entra nell'area riservata. */
export function VerifyEmail() {
  const router = useRouter();
  const token = useSearchParams().get("token") ?? "";
  const { error, run } = useAction();
  const started = useRef(false);
  const [email, setEmail] = useState("");
  const [resent, setResent] = useState(false);

  useEffect(() => {
    if (started.current) return; // in sviluppo React esegue gli effetti due volte
    started.current = true;
    run(() => api("/auth/verify-email", { body: { token } })).then((ok) => ok && router.replace("/app"));
  }, [token, router, run]);

  if (!error) return <FormSkeleton />;
  return (
    <div className="space-y-4">
      <Notice state={{ error: error.message }} />
      {resent ? (
        <Notice state={{ ok: true, message: "Se l'indirizzo è corretto riceverai un nuovo link." }} />
      ) : (
        <form className="space-y-3" onSubmit={async (e) => { e.preventDefault(); await api("/auth/verify-email/resend", { body: { email } }).catch(() => null); setResent(true); }}>
          <Field label="Ricevi un nuovo link">
            <input className={inputCls} type="email" required placeholder="La tua email" value={email}
              onChange={(e) => setEmail(e.target.value)} />
          </Field>
          <button className={`${btnPrimary} w-full`} disabled={!email}>Invia nuovo link</button>
        </form>
      )}
    </div>
  );
}

export function ForgotPassword() {
  const { pending, error, run } = useAction();
  const [email, setEmail] = useState("");
  const [done, setDone] = useState(false);
  if (done)
    return (
      <Notice state={{ ok: true, message: "Se l'indirizzo è registrato, riceverai un link entro pochi minuti.", detail: "valido 1 ora" }} />
    );
  return (
    <form className="space-y-4" noValidate
      onSubmit={async (e) => { e.preventDefault(); if (await run(() => api("/auth/password/forgot", { body: { email } }))) setDone(true); }}>
      {error && <Notice state={{ error: error.message }} />}
      <Field label="Email">
        <input className={inputCls} type="email" autoComplete="email" required value={email} onChange={(e) => setEmail(e.target.value)} />
      </Field>
      <button className={`${btnPrimary} w-full`} disabled={pending || !email}>
        {pending ? "Invio…" : "Invia il link"}
      </button>
    </form>
  );
}

function PasswordPair({ value, onChange }: { value: [string, string]; onChange: (v: [string, string]) => void }) {
  return (
    <>
      <Field label="Nuova password" hint="Almeno 10 caratteri. Evita nome ed email.">
        <input className={inputCls} type="password" autoComplete="new-password" required minLength={10} value={value[0]}
          onChange={(e) => onChange([e.target.value, value[1]])} />
      </Field>
      <Field label="Ripeti la password">
        <input className={inputCls} type="password" autoComplete="new-password" required value={value[1]}
          onChange={(e) => onChange([value[0], e.target.value])} />
      </Field>
      {value[1] && value[0] !== value[1] && <p className="t-footnote text-stamp">Le due password non coincidono.</p>}
    </>
  );
}

export function ResetPassword() {
  const token = useSearchParams().get("token") ?? "";
  const { pending, error, run } = useAction();
  const [pw, setPw] = useState<[string, string]>(["", ""]);
  const [done, setDone] = useState(false);
  if (done)
    return (
      <div className="space-y-4">
        <Notice state={{ ok: true, message: "Password aggiornata. Per sicurezza abbiamo chiuso le sessioni aperte." }} />
        <Link href="/accedi" className={`${btnPrimary} w-full`}>Accedi</Link>
      </div>
    );
  return (
    <form className="space-y-4" noValidate
      onSubmit={async (e) => { e.preventDefault(); if (await run(() => api("/auth/password/reset", { body: { token, password: pw[0] } }))) setDone(true); }}>
      {error && <Notice state={{ error: error.message }} />}
      {error?.code === "link_non_valido" && (
        <p className="t-subhead"><Link href="/password-dimenticata" className={linkCls}>Richiedi un nuovo link ›</Link></p>
      )}
      <PasswordPair value={pw} onChange={setPw} />
      <button className={`${btnPrimary} w-full`} disabled={pending || !pw[0] || pw[0] !== pw[1]}>
        {pending ? "Salvataggio…" : "Salva la nuova password"}
      </button>
    </form>
  );
}

interface InvitationInfo { studio: string; email: string; full_name: string; has_password: boolean }

export function AcceptInvitation() {
  const router = useRouter();
  const token = useSearchParams().get("token") ?? "";
  const { pending, error, run } = useAction();
  const [info, setInfo] = useState<InvitationInfo | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [pw, setPw] = useState<[string, string]>(["", ""]);

  useEffect(() => {
    api<InvitationInfo>(`/auth/invitation?token=${encodeURIComponent(token)}`).then(setInfo, (e) => setLoadError(e.message));
  }, [token]);

  if (loadError) return <Notice state={{ error: loadError }} />;
  if (!info) return <FormSkeleton />;
  return (
    <form className="space-y-4" noValidate
      onSubmit={async (e) => { e.preventDefault(); if (await run(() => api("/auth/invitation/accept", { body: { token, password: pw[0] } }))) router.replace("/app"); }}>
      <p className="t-subhead text-ink-2">
        Entri in <strong className="text-ink">{info.studio}</strong> come <strong className="text-ink">{info.email}</strong>.
      </p>
      {error && <Notice state={{ error: error.message }} />}
      {info.has_password ? (
        <Field label="La tua password attuale" hint="Hai già un account: usa la password che conosci.">
          <input className={inputCls} type="password" autoComplete="current-password" required value={pw[0]}
            onChange={(e) => setPw([e.target.value, e.target.value])} />
        </Field>
      ) : (
        <PasswordPair value={pw} onChange={setPw} />
      )}
      <button className={`${btnPrimary} w-full`} disabled={pending || !pw[0] || pw[0] !== pw[1]}>
        {pending ? "Accesso…" : "Accetta l'invito"}
      </button>
    </form>
  );
}
