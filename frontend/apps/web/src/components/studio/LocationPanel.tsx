"use client";

import { useEffect, useState } from "react";
import { Field, Notice, Panel, btnPrimary, inputCls } from "@/components/ui";
import { useAction } from "@/components/auth/useAction";
import { api } from "@/lib/api";
import type { Location } from "@/lib/catalog";

/** Sede principale dello studio (le sedi multiple arriveranno con l'agenda). */
export function LocationPanel({ canEdit }: { canEdit: boolean }) {
  const [loc, setLoc] = useState<Location | null>(null);
  const [saved, setSaved] = useState(false);
  const { pending, error, run } = useAction();

  useEffect(() => {
    api<Location[]>("/locations").then((all) => setLoc(all.find((l) => l.is_default) ?? all[0] ?? null), () => null);
  }, []);

  if (!loc) return null;

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!loc) return;
    const res = await run(() =>
      api<Location>(`/locations/${loc.id}`, { method: "PATCH", body: { name: loc.name.trim(), address: loc.address?.trim() || null } }),
    );
    if (res) {
      setLoc(res);
      setSaved(true);
    }
  }

  return (
    <form onSubmit={onSubmit} className="space-y-4">
      <Panel title="Sede principale" meta="Dove si svolgono gli appuntamenti in studio">
        <fieldset disabled={!canEdit} className="grid gap-4 sm:grid-cols-2">
          <Field label="Nome della sede">
            <input className={inputCls} required maxLength={120} value={loc.name}
              onChange={(e) => { setSaved(false); setLoc({ ...loc, name: e.target.value }); }} />
          </Field>
          <Field label="Indirizzo della sede">
            <input className={inputCls} maxLength={200} value={loc.address ?? ""}
              onChange={(e) => { setSaved(false); setLoc({ ...loc, address: e.target.value }); }} />
          </Field>
        </fieldset>
      </Panel>
      {canEdit && (
        <div className="flex flex-wrap items-center gap-3">
          <button className={btnPrimary} disabled={pending || !loc.name.trim()}>{pending ? "Salvataggio…" : "Salva sede"}</button>
          {saved && <Notice state={{ ok: true, message: "Sede salvata" }} />}
          {error && <Notice state={{ error: error.message }} />}
        </div>
      )}
    </form>
  );
}
