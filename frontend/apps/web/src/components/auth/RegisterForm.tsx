"use client";

import { useEffect, useState } from "react";
import { MailCheck } from "lucide-react";
import { api } from "@/lib/api";
import { Field, Notice, btnPrimary, btnTinted, inputCls, selectCls } from "../ui";
import { useAction } from "./useAction";

interface BusinessType {
  code: string;
  label: string;
}

export function RegisterForm() {
  const { pending, error, run } = useAction();
  const [types, setTypes] = useState<BusinessType[]>([]);
  const [open, setOpen] = useState<boolean | null>(null);
  const [form, setForm] = useState({
    studio_name: "", business_type: "", full_name: "", email: "", password: "", accept_terms: false,
  });
  const [sentTo, setSentTo] = useState<string | null>(null);
  const [resent, setResent] = useState(false);

  useEffect(() => {
    api<{ signup_open: boolean }>("/meta/config").then((c) => setOpen(c.signup_open), () => setOpen(false));
    api<BusinessType[]>("/meta/business-types").then(setTypes, () => setTypes([]));
  }, []);

  const set = (key: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) =>
    setForm({ ...form, [key]: e.target.type === "checkbox" ? (e.target as HTMLInputElement).checked : e.target.value });

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    const ok = await run(() => api("/auth/register", { body: form }));
    if (ok) setSentTo(form.email);
  }

  if (open === false)
    return <Notice state={{ error: "La registrazione di nuovi studi al momento è chiusa. Contatta CoreNexus per una prova." }} />;

  if (sentTo)
    return (
      <div className="space-y-4 text-center">
        <MailCheck className="mx-auto h-10 w-10 text-go" />
        <p className="t-headline">Controlla la tua email</p>
        <p className="t-subhead text-ink-2">
          Abbiamo inviato un link di conferma a <strong>{sentTo}</strong>. Aprilo per attivare l&apos;account.
          Se non arriva entro qualche minuto, controlla lo spam.
        </p>
        {resent ? (
          <Notice state={{ ok: true, message: "Email inviata di nuovo." }} />
        ) : (
          <button type="button" className={`${btnTinted} w-full`}
            onClick={async () => { await run(() => api("/auth/verify-email/resend", { body: { email: sentTo } })); setResent(true); }}>
            Invia di nuovo
          </button>
        )}
      </div>
    );

  return (
    <form onSubmit={onSubmit} className="space-y-4" noValidate>
      {error && <Notice state={{ error: error.message }} />}
      <Field label="Nome dello studio">
        <input className={inputCls} required maxLength={120} value={form.studio_name} onChange={set("studio_name")}
          placeholder="es. Studio di Nutrizione Rossi" />
      </Field>
      <Field label="Attività">
        <select className={selectCls} required value={form.business_type} onChange={set("business_type")}>
          <option value="" disabled>Scegli…</option>
          {types.map((t) => (
            <option key={t.code} value={t.code}>{t.label}</option>
          ))}
        </select>
      </Field>
      <Field label="Nome e cognome">
        <input className={inputCls} required autoComplete="name" maxLength={120} value={form.full_name} onChange={set("full_name")} />
      </Field>
      <Field label="Email">
        <input className={inputCls} type="email" required autoComplete="email" value={form.email} onChange={set("email")} />
      </Field>
      <Field label="Password" hint="Almeno 10 caratteri. Evita nome ed email.">
        <input className={inputCls} type="password" required autoComplete="new-password" minLength={10} value={form.password}
          onChange={set("password")} />
      </Field>
      <label className="flex items-start gap-2.5 t-subhead text-ink-2">
        <input type="checkbox" className="mt-0.5 h-4 w-4 accent-[var(--color-accent)]" checked={form.accept_terms}
          onChange={set("accept_terms")} />
        <span>Accetto le condizioni del servizio e l&apos;informativa sul trattamento dei dati.</span>
      </label>
      <button className={`${btnPrimary} cta w-full`}
        disabled={pending || !form.accept_terms || !form.business_type || !form.email || !form.password}>
        {pending ? "Registrazione…" : "Crea il tuo studio"}
      </button>
      <p className="text-center t-footnote text-ink-3">14 giorni di prova gratuita, senza carta di credito.</p>
    </form>
  );
}
