"use client";

import { Building2, History, Search, Users } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { Segmented } from "@/components/Segmented";
import { useAction } from "@/components/auth/useAction";
import {
  AddRow, Disclosure, EmptyState, Field, Monogram, Notice, PageHeader, Panel, StatStrip, Tag,
  btnDanger, btnPrimary, btnSecondary, btnTinted, inputCls, selectCls,
} from "@/components/ui";
import { api } from "@/lib/api";
import { formatDateTime } from "@/lib/catalog";
import {
  ACTION_LABELS, TENANT_STATUS, daysLeft, type PlatformActivity, type PlatformStaff, type PlatformTenant, type StaffMe,
} from "@/lib/platform";

type Tab = "studi" | "team" | "registro";
interface BusinessType { code: string; label: string }

export function PlatformPanel({ me }: { me: StaffMe }) {
  const [tab, setTab] = useState<Tab>("studi");
  const [types, setTypes] = useState<BusinessType[]>([]);
  useEffect(() => {
    api<BusinessType[]>("/meta/business-types").then(setTypes, () => null);
  }, []);
  return (
    <>
      <PageHeader meta={`Ciao, ${me.full_name.split(" ")[0]}`} title="Pannello CoreNexus" />
      <Segmented label="Sezione" className="max-w-md" value={tab} onChange={setTab}
        options={[["studi", "Studi"], ["team", "Team"], ["registro", "Registro"]] as const} />
      {tab === "studi" && <Tenants types={types} />}
      {tab === "team" && <Team />}
      {tab === "registro" && <Activity />}
    </>
  );
}

// ---------------------------------------------------------------- studi

function Tenants({ types }: { types: BusinessType[] }) {
  const [q, setQ] = useState("");
  const [items, setItems] = useState<PlatformTenant[] | null>(null);
  const load = useCallback(() => {
    api<PlatformTenant[]>(`/platform/tenants${q.trim() ? `?q=${encodeURIComponent(q.trim())}` : ""}`).then(setItems, () => null);
  }, [q]);
  useEffect(() => {
    const t = setTimeout(load, q ? 250 : 0);
    return () => clearTimeout(t);
  }, [load, q]);

  const all = items ?? [];
  const label = (code: string) => types.find((t) => t.code === code)?.label ?? code;

  return (
    <>
      <StatStrip
        items={[
          { label: "Studi", value: all.length, tone: "accent", icon: <Building2 /> },
          { label: "In prova", value: all.filter((t) => t.status === "trial").length, tone: "warn" },
          { label: "Attivi", value: all.filter((t) => t.status === "active").length, tone: "go" },
          { label: "Sospesi", value: all.filter((t) => t.status === "suspended").length, tone: "stamp" },
        ]}
      />
      <div className="relative max-w-md">
        <Search aria-hidden className="pointer-events-none absolute top-1/2 left-3.5 h-4 w-4 -translate-y-1/2 text-ink-3" />
        <input type="search" aria-label="Cerca studi" placeholder="Cerca per nome" className={`${inputCls} pl-10`} value={q} onChange={(e) => setQ(e.target.value)} />
      </div>
      <Panel title="Studi" flush>
        {items && items.length === 0 && <EmptyState icon={<Building2 />} title="Nessuno studio" text="Crea il primo studio qui sotto." />}
        <ul>
          {all.map((t) => {
            const [statusLabel, tone] = TENANT_STATUS[t.status];
            const left = t.status === "trial" ? daysLeft(t.trial_ends_at) : null;
            return (
              <Disclosure
                key={t.id}
                leading={<Monogram name={t.name} size={34} />}
                title={t.name}
                subtitle={`${label(t.business_type)} · ${t.owner_name || "senza titolare"}${t.owner_email ? ` · ${t.owner_email}` : ""}`}
                muted={t.status === "cancelled"}
                trailing={
                  <>
                    {t.owner_invitation_pending && <Tag tone="warn">Invito in attesa</Tag>}
                    <Tag tone={tone}>{statusLabel}{left !== null ? ` · ${left > 0 ? `${left} gg` : "scaduta"}` : ""}</Tag>
                  </>
                }
              >
                <TenantDetail tenant={t} types={types} onChanged={load} />
              </Disclosure>
            );
          })}
        </ul>
        <AddRow label="Nuovo studio">
          <NewTenant types={types} onDone={load} />
        </AddRow>
      </Panel>
    </>
  );
}

function TenantDetail({ tenant, types, onChanged }: { tenant: PlatformTenant; types: BusinessType[]; onChanged: () => void }) {
  const { pending, error, run } = useAction();
  const [message, setMessage] = useState<string | null>(null);
  const [btype, setBtype] = useState(tenant.business_type);

  async function patch(body: Record<string, unknown>, done: string) {
    setMessage(null);
    const r = await run(() => api(`/platform/tenants/${tenant.id}`, { method: "PATCH", body }));
    if (r) {
      setMessage(done);
      onChanged();
    }
  }

  return (
    <div className="space-y-5">
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        {[["Professionisti", tenant.professionals], ["Clienti", tenant.clients], ["Appuntamenti futuri", tenant.upcoming_appointments], ["Creato il", new Date(tenant.created_at).toLocaleDateString("it-IT")]].map(([l, val]) => (
          <div key={String(l)} className="rounded-[12px] bg-card px-3 py-2.5">
            <p className="t-caption text-ink-3">{l}</p>
            <p className="num t-title3">{val}</p>
          </div>
        ))}
      </div>
      <p className="t-footnote text-ink-3">Solo dati amministrativi e conteggi: nomi di clienti e appuntamenti non sono visibili dalla piattaforma.</p>
      {error && <Notice state={{ error: error.message }} />}
      {message && <Notice state={{ ok: true, message }} />}

      <div className="space-y-2">
        <p className="t-footnote font-medium text-ink-3">Stato e prova</p>
        <div className="flex flex-wrap gap-2">
          {tenant.status !== "active" && <button type="button" className={btnPrimary} disabled={pending} onClick={() => patch({ status: "active" }, "Studio attivato")}>Attiva</button>}
          {tenant.status === "trial" && <button type="button" className={btnTinted} disabled={pending} onClick={() => patch({ extend_trial_days: 14 }, "Prova estesa di 14 giorni")}>Prova +14 giorni</button>}
          {tenant.status === "trial" && <button type="button" className={btnTinted} disabled={pending} onClick={() => patch({ extend_trial_days: 30 }, "Prova estesa di 30 giorni")}>+30 giorni</button>}
          {tenant.status !== "suspended" && tenant.status !== "cancelled" && (
            <button type="button" className={btnDanger} disabled={pending} onClick={() => patch({ status: "suspended" }, "Studio sospeso: lo staff non può più accedere")}>Sospendi</button>
          )}
          {tenant.status === "suspended" && <button type="button" className={btnSecondary} disabled={pending} onClick={() => patch({ status: "trial", extend_trial_days: 14 }, "Studio riattivato in prova")}>Riattiva in prova</button>}
        </div>
      </div>

      <div className="flex flex-wrap items-end gap-3">
        <div className="w-64">
          <Field label="Profilo professionale">
            <select className={selectCls} value={btype} onChange={(e) => setBtype(e.target.value)}>
              {types.map((t) => <option key={t.code} value={t.code}>{t.label}</option>)}
            </select>
          </Field>
        </div>
        <button type="button" className={btnTinted} disabled={pending || btype === tenant.business_type} onClick={() => patch({ business_type: btype }, "Profilo aggiornato")}>Cambia profilo</button>
        <button type="button" className={btnSecondary} disabled={pending} onClick={async () => {
          const r = await run(() => api<{ created: number }>(`/platform/tenants/${tenant.id}/profile`, { method: "POST" }));
          if (r) { setMessage(r.created ? `Aggiunte ${r.created} prestazioni consigliate` : "Le prestazioni consigliate ci sono già"); onChanged(); }
        }}>Aggiungi prestazioni consigliate</button>
      </div>

      {tenant.owner_invitation_pending && (
        <button type="button" className={btnSecondary} disabled={pending} onClick={async () => {
          const r = await run(() => api<{ message: string }>(`/platform/tenants/${tenant.id}/resend-invite`, { method: "POST" }));
          if (r) setMessage(r.message);
        }}>Invia di nuovo l&apos;invito al titolare</button>
      )}

      <div className="rounded-[12px] border border-dashed border-rule-strong px-4 py-3">
        <p className="t-subhead font-semibold">Moduli <Tag>In arrivo</Tag></p>
        <p className="t-footnote text-ink-3">Il modulo Campagne (offerte via WhatsApp con consenso marketing) si attiverà da qui quando sarà disponibile.</p>
      </div>
    </div>
  );
}

function NewTenant({ types, onDone }: { types: BusinessType[]; onDone: () => void }) {
  const empty = { name: "", business_type: "fisioterapista", owner_name: "", owner_email: "", trial_days: 14 };
  const [f, setF] = useState(empty);
  const [done, setDone] = useState<string | null>(null);
  const { pending, error, run } = useAction();

  return (
    <form
      className="space-y-4"
      noValidate
      onSubmit={async (e) => {
        e.preventDefault();
        setDone(null);
        const r = await run(() => api<PlatformTenant & { email_sent: boolean | null }>("/platform/tenants", { body: { ...f, trial_days: Number(f.trial_days) } }));
        if (r) {
          setDone(r.email_sent === false ? "Studio creato, ma l'email al titolare non è partita: usa «Invia di nuovo l'invito»." : `Studio creato: invito inviato a ${f.owner_email}`);
          setF(empty);
          onDone();
        }
      }}
    >
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="Nome dello studio"><input className={inputCls} value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} /></Field>
        <Field label="Attività">
          <select className={selectCls} value={f.business_type} onChange={(e) => setF({ ...f, business_type: e.target.value })}>
            {types.map((t) => <option key={t.code} value={t.code}>{t.label}</option>)}
          </select>
        </Field>
        <Field label="Nome del titolare"><input className={inputCls} value={f.owner_name} onChange={(e) => setF({ ...f, owner_name: e.target.value })} /></Field>
        <Field label="Email del titolare" hint="Riceve l'invito a scegliere la password."><input className={inputCls} type="email" value={f.owner_email} onChange={(e) => setF({ ...f, owner_email: e.target.value })} /></Field>
        <Field label="Giorni di prova" hint="0 = attivo subito, senza prova.">
          <input className={inputCls} type="number" min={0} max={365} value={f.trial_days} onChange={(e) => setF({ ...f, trial_days: Number(e.target.value) })} />
        </Field>
      </div>
      {error && <Notice state={{ error: error.message }} />}
      {done && <Notice state={{ ok: true, message: done }} />}
      <button className={btnPrimary} disabled={pending || !f.name || !f.owner_name || !f.owner_email.includes("@")}>{pending ? "Creazione…" : "Crea studio e invita il titolare"}</button>
    </form>
  );
}

// ---------------------------------------------------------------- team

function Team() {
  const [items, setItems] = useState<PlatformStaff[] | null>(null);
  const [f, setF] = useState({ full_name: "", email: "" });
  const [done, setDone] = useState<string | null>(null);
  const { pending, error, run } = useAction();
  const load = useCallback(() => {
    api<PlatformStaff[]>("/platform/staff").then(setItems, () => null);
  }, []);
  useEffect(load, [load]);

  return (
    <Panel title="Team CoreNexus" meta="Accesso con password e codice a 6 cifre" flush>
      {error && <div className="p-4"><Notice state={{ error: error.message }} /></div>}
      <ul>
        {items?.map((p) => (
          <li key={p.id} className="flex min-h-[56px] items-center gap-3.5 border-t border-rule px-5 py-2.5 first:border-t-0">
            <Monogram name={p.full_name} size={34} />
            <span className="min-w-0 flex-1">
              <span className={`block truncate t-body ${p.status === "disabled" ? "text-ink-3 line-through" : ""}`}>{p.full_name}{p.is_me ? " (tu)" : ""}</span>
              <span className="block truncate t-footnote text-ink-3">{p.email}{p.last_login_at ? ` · ultimo accesso ${formatDateTime(p.last_login_at)}` : ""}</span>
            </span>
            {p.status === "invited" && <Tag tone="warn">Invito in attesa</Tag>}
            {!p.is_me && p.status === "active" && (
              <button type="button" className={btnDanger} disabled={pending} onClick={async () => {
                if (await run(() => api(`/platform/staff/${p.id}`, { method: "PATCH", body: { status: "disabled" } }).then(() => true))) load();
              }}>Disattiva</button>
            )}
            {p.status === "disabled" && (
              <button type="button" className={btnSecondary} disabled={pending} onClick={async () => {
                if (await run(() => api(`/platform/staff/${p.id}`, { method: "PATCH", body: { status: "active" } }).then(() => true))) load();
              }}>Riattiva</button>
            )}
          </li>
        ))}
      </ul>
      <AddRow label="Invita una persona del team">
        <form className="space-y-4" noValidate onSubmit={async (e) => {
          e.preventDefault();
          const r = await run(() => api<{ message: string }>("/platform/staff", { body: f }));
          if (r) { setDone(`Invito inviato a ${f.email}`); setF({ full_name: "", email: "" }); load(); }
        }}>
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Nome e cognome"><input className={inputCls} value={f.full_name} onChange={(e) => setF({ ...f, full_name: e.target.value })} /></Field>
            <Field label="Email"><input className={inputCls} type="email" value={f.email} onChange={(e) => setF({ ...f, email: e.target.value })} /></Field>
          </div>
          {done && <Notice state={{ ok: true, message: done }} />}
          <button className={btnPrimary} disabled={pending || !f.full_name || !f.email.includes("@")}>Invia invito</button>
        </form>
      </AddRow>
      {items && items.length === 0 && <EmptyState icon={<Users />} title="Nessuno" />}
    </Panel>
  );
}

// ---------------------------------------------------------------- registro

function Activity() {
  const [items, setItems] = useState<PlatformActivity[] | null>(null);
  useEffect(() => {
    api<PlatformActivity[]>("/platform/activity").then(setItems, () => null);
  }, []);
  return (
    <Panel title="Registro delle azioni" meta="Ultime 100" flush>
      {items && items.length === 0 && <EmptyState icon={<History />} title="Nessuna azione registrata" />}
      <ul>
        {items?.map((a, i) => (
          <li key={i} className="flex flex-wrap items-baseline gap-x-3 gap-y-0.5 border-t border-rule px-5 py-2.5 first:border-t-0">
            <span className="num w-36 shrink-0 t-footnote text-ink-3">{formatDateTime(a.at)}</span>
            <span className="t-body">{ACTION_LABELS[a.action] ?? a.action}</span>
            {a.tenant && <Tag>{a.tenant}</Tag>}
            <span className="ml-auto t-footnote text-ink-3">{a.staff ?? "—"}{a.ip ? ` · ${a.ip}` : ""}</span>
          </li>
        ))}
      </ul>
    </Panel>
  );
}
