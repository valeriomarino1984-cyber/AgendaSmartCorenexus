"use client";

import { Users } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import {
  AddRow, Disclosure, EmptyState, Field, Monogram, Notice, PageHeader, Panel, Tag,
  btnDanger, btnPrimary, btnTinted, inputCls, selectCls,
} from "@/components/ui";
import { useAction } from "@/components/auth/useAction";
import { api } from "@/lib/api";
import { useMe } from "@/lib/me";

interface Member {
  id: string;
  full_name: string;
  email: string;
  role: "owner" | "professional" | "secretary";
  role_label: string;
  status: "active" | "disabled";
  invitation_pending: boolean;
  is_me: boolean;
}

const ROLES = [
  ["professional", "Professionista", "Gestisce la propria agenda e i propri clienti."],
  ["secretary", "Segreteria", "Crea e sposta appuntamenti, gestisce l'anagrafica."],
  ["owner", "Titolare", "Accesso completo, compresi collaboratori e impostazioni."],
] as const;

export function Collaborators() {
  const { me } = useMe();
  const [members, setMembers] = useState<Member[] | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);

  const load = useCallback(() => {
    api<Member[]>("/tenants/current/users").then(setMembers, (e) => setLoadError(e.message));
  }, []);
  useEffect(load, [load]);

  if (me.role !== "owner")
    return (
      <>
        <PageHeader title="Collaboratori" />
        <Notice state={{ error: "Questa sezione è riservata al titolare dello studio." }} />
      </>
    );

  return (
    <>
      <PageHeader meta={me.tenant.name} title="Collaboratori" />
      {loadError && <Notice state={{ error: loadError }} />}
      <Panel title="Team" meta={members ? `${members.filter((m) => m.status === "active").length} attivi` : undefined} flush>
        {members && members.length === 0 && <EmptyState icon={<Users />} title="Nessun collaboratore" />}
        <ul>
          {members?.map((m) => (
            <Disclosure
              key={m.id}
              leading={<Monogram name={m.full_name} size={34} />}
              title={m.is_me ? `${m.full_name} (tu)` : m.full_name}
              subtitle={m.email}
              muted={m.status === "disabled"}
              trailing={
                <>
                  {m.invitation_pending && <Tag tone="warn">Invito in attesa</Tag>}
                  {m.status === "disabled" ? <Tag tone="neutral">Disattivato</Tag> : <Tag tone="accent">{m.role_label}</Tag>}
                </>
              }
            >
              <MemberEditor member={m} onChanged={load} />
            </Disclosure>
          ))}
        </ul>
        <AddRow label="Invita un collaboratore">
          <InviteForm onDone={load} />
        </AddRow>
      </Panel>
    </>
  );
}

function MemberEditor({ member, onChanged }: { member: Member; onChanged: () => void }) {
  const { pending, error, run } = useAction();
  const [role, setRole] = useState(member.role);

  async function patch(body: Record<string, string>) {
    const ok = await run(() => api(`/tenants/current/users/${member.id}`, { method: "PATCH", body }).then(() => true));
    if (ok) onChanged();
  }

  return (
    <div className="space-y-4">
      {error && <Notice state={{ error: error.message }} />}
      <div className="flex flex-wrap items-end gap-3">
        <div className="w-60">
          <Field label="Ruolo">
            <select className={selectCls} value={role} onChange={(e) => setRole(e.target.value as Member["role"])}>
              {ROLES.map(([value, label]) => (
                <option key={value} value={value}>{label}</option>
              ))}
            </select>
          </Field>
        </div>
        <button type="button" className={btnTinted} disabled={pending || role === member.role} onClick={() => patch({ role })}>
          Cambia ruolo
        </button>
        {member.status === "active" ? (
          <button type="button" className={btnDanger} disabled={pending} onClick={() => patch({ status: "disabled" })}>
            Disattiva accesso
          </button>
        ) : (
          <button type="button" className={btnTinted} disabled={pending} onClick={() => patch({ status: "active" })}>
            Riattiva
          </button>
        )}
      </div>
      <p className="t-footnote text-ink-3">{ROLES.find(([v]) => v === role)?.[2]}</p>
    </div>
  );
}

function InviteForm({ onDone }: { onDone: () => void }) {
  const { pending, error, run } = useAction();
  const [form, setForm] = useState({ full_name: "", email: "", role: "professional" });
  const [result, setResult] = useState<string | null>(null);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    const res = await run(() => api<{ message: string }>("/tenants/current/users", { body: form }));
    if (res) {
      setResult(res.message);
      setForm({ full_name: "", email: "", role: "professional" });
      onDone();
    }
  }

  return (
    <form onSubmit={onSubmit} className="space-y-4" noValidate>
      {error && <Notice state={{ error: error.message }} />}
      {result && <Notice state={{ ok: true, message: result }} />}
      <div className="grid gap-4 sm:grid-cols-3">
        <Field label="Nome e cognome">
          <input className={inputCls} required value={form.full_name} onChange={(e) => setForm({ ...form, full_name: e.target.value })} />
        </Field>
        <Field label="Email">
          <input className={inputCls} type="email" required value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} />
        </Field>
        <Field label="Ruolo">
          <select className={selectCls} value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value })}>
            {ROLES.map(([value, label]) => (
              <option key={value} value={value}>{label}</option>
            ))}
          </select>
        </Field>
      </div>
      <button className={btnPrimary} disabled={pending || !form.full_name || !form.email}>
        {pending ? "Invio…" : "Invia invito"}
      </button>
    </form>
  );
}
