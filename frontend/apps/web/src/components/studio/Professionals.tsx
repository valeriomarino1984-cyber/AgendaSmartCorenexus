"use client";

import { UserRound } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import {
  AddRow, CheckRow, ColorDot, Disclosure, EmptyState, Field, Notice, PageHeader, Panel, Tag,
  btnPrimary, btnSecondary, inputCls,
} from "@/components/ui";
import { useAction } from "@/components/auth/useAction";
import { ColorPicker } from "@/components/studio/ColorPicker";
import { api } from "@/lib/api";
import type { Professional } from "@/lib/catalog";
import { useMe } from "@/lib/me";

interface Draft {
  name: string;
  specialization: string;
  color: string;
  public_booking: boolean;
}

export function Professionals() {
  const { me } = useMe();
  const canEdit = me.role === "owner";
  const [items, setItems] = useState<Professional[] | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);

  const load = useCallback(() => {
    api<Professional[]>("/professionals").then(setItems, (e) => setLoadError(e.message));
  }, []);
  useEffect(load, [load]);

  return (
    <>
      <PageHeader meta={me.tenant.name} title="Professionisti" />
      {loadError && <Notice state={{ error: loadError }} />}
      <p className="max-w-2xl t-subhead text-ink-3">
        Chi riceve gli appuntamenti. Titolari e professionisti invitati da Collaboratori hanno già la loro scheda; qui puoi aggiungere
        anche chi lavora nello studio senza un account.
      </p>
      <Panel title="Elenco" meta={items ? `${items.filter((p) => p.status === "active").length} attivi` : undefined} flush>
        {items && items.length === 0 && <EmptyState icon={<UserRound />} title="Nessun professionista" />}
        <ul>
          {items?.map((p) => (
            <Disclosure
              key={p.id}
              leading={<ColorDot color={p.color} size={14} />}
              title={p.user_id === me.user.id ? `${p.name} (tu)` : p.name}
              subtitle={[p.specialization, p.account_email].filter(Boolean).join(" · ") || "Senza account"}
              muted={p.status === "inactive"}
              trailing={
                <>
                  {p.user_id ? <Tag tone="accent">Con account</Tag> : <Tag>Senza account</Tag>}
                  {p.status === "inactive" && <Tag>Inattivo</Tag>}
                </>
              }
            >
              <ProfessionalForm professional={p} canEdit={canEdit} onDone={load} />
            </Disclosure>
          ))}
        </ul>
        {canEdit && (
          <AddRow label="Aggiungi professionista">
            <ProfessionalForm canEdit onDone={load} />
          </AddRow>
        )}
      </Panel>
    </>
  );
}

function ProfessionalForm({ professional, canEdit, onDone }: { professional?: Professional; canEdit: boolean; onDone: () => void }) {
  const initial: Draft = {
    name: professional?.name ?? "",
    specialization: professional?.specialization ?? "",
    color: professional?.color ?? "#0071e3",
    public_booking: professional?.public_booking ?? true,
  };
  const [d, setD] = useState<Draft>(initial);
  const [saved, setSaved] = useState(false);
  const { pending, error, run } = useAction();
  const set = <K extends keyof Draft>(key: K, value: Draft[K]) => {
    setSaved(false);
    setD({ ...d, [key]: value });
  };

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    const body = { name: d.name.trim(), specialization: d.specialization.trim() || null, color: d.color, public_booking: d.public_booking };
    const res = await run(() =>
      professional
        ? api<Professional>(`/professionals/${professional.id}`, { method: "PATCH", body })
        : api<Professional>("/professionals", { body }),
    );
    if (res) {
      setSaved(true);
      if (!professional) setD(initial);
      onDone();
    }
  }

  async function toggleStatus() {
    if (!professional) return;
    const status = professional.status === "active" ? "inactive" : "active";
    const res = await run(() => api(`/professionals/${professional.id}`, { method: "PATCH", body: { status } }).then(() => true));
    if (res) onDone();
  }

  return (
    <form onSubmit={onSubmit} className="space-y-5" noValidate>
      <fieldset disabled={!canEdit} className="space-y-5">
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Nome visualizzato">
            <input className={inputCls} required maxLength={120} value={d.name} onChange={(e) => set("name", e.target.value)} />
          </Field>
          <Field label="Specializzazione" hint="Facoltativa, ad esempio «Fisioterapista sportivo».">
            <input className={inputCls} maxLength={120} value={d.specialization} onChange={(e) => set("specialization", e.target.value)} />
          </Field>
        </div>
        <ColorPicker value={d.color} onChange={(c) => set("color", c)} label="Colore in agenda" />
        <CheckRow
          label="Prenotabile online"
          description="Compare nella pagina di prenotazione pubblica (quando sarà attiva)."
          checked={d.public_booking}
          onChange={(v) => set("public_booking", v)}
        />
      </fieldset>
      {error && <Notice state={{ error: error.message }} />}
      {saved && professional && <Notice state={{ ok: true, message: "Scheda salvata" }} />}
      {canEdit && (
        <div className="flex flex-wrap gap-3">
          <button className={btnPrimary} disabled={pending || !d.name.trim()}>
            {pending ? "Salvataggio…" : professional ? "Salva" : "Aggiungi"}
          </button>
          {professional && (
            <button type="button" className={btnSecondary} disabled={pending} onClick={toggleStatus}>
              {professional.status === "active" ? "Segna come inattivo" : "Riattiva"}
            </button>
          )}
        </div>
      )}
    </form>
  );
}
