"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useState } from "react";
import { api } from "@/lib/api";
import { Field, Notice, btnPrimary, btnTinted, inputCls, linkCls } from "../ui";
import { safeNext, useAction } from "./useAction";

export function LoginForm() {
  const router = useRouter();
  const params = useSearchParams();
  const { pending, error, run } = useAction();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [resent, setResent] = useState(false);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    const ok = await run(() => api("/auth/login", { body: { email, password } }));
    if (ok) router.replace(safeNext(params.get("next")));
  }

  async function resend() {
    await run(() => api("/auth/verify-email/resend", { body: { email } }));
    setResent(true);
  }

  return (
    <form onSubmit={onSubmit} className="space-y-4" noValidate>
      {params.get("uscito") && <Notice state={{ ok: true, message: "Sei uscito dall'area riservata." }} />}
      {error && <Notice state={{ error: error.message }} />}
      {error?.code === "email_non_verificata" && !resent && (
        <button type="button" onClick={resend} className={`${btnTinted} w-full`}>
          Invia di nuovo il link di conferma
        </button>
      )}
      {resent && <Notice state={{ ok: true, message: "Se l'indirizzo è corretto riceverai una nuova email." }} />}
      <Field label="Email">
        <input className={inputCls} type="email" autoComplete="email" required value={email}
          onChange={(e) => setEmail(e.target.value)} />
      </Field>
      <Field label="Password">
        <input className={inputCls} type="password" autoComplete="current-password" required value={password}
          onChange={(e) => setPassword(e.target.value)} />
      </Field>
      <button className={`${btnPrimary} cta w-full`} disabled={pending || !email || !password}>
        {pending ? "Accesso in corso…" : "Accedi"}
      </button>
      <p className="text-center t-subhead">
        <Link href="/password-dimenticata" className={linkCls}>
          Password dimenticata?
        </Link>
      </p>
    </form>
  );
}
