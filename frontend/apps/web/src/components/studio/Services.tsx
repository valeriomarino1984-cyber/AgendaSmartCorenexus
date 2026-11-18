"use client";

import { Sparkles, Stethoscope, Video } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import {
  AddRow, CheckRow, ColorDot, Disclosure, EmptyState, Field, Notice, PageHeader, Panel, Tag,
  btnPrimary, btnSecondary, btnTinted, inputCls,
} from "@/components/ui";
import { Segmented } from "@/components/Segmented";
import { useAction } from "@/components/auth/useAction";
import { ColorPicker } from "@/components/studio/ColorPicker";
import { api } from "@/lib/api";
import { MODE_LABELS, formatPrice, type ProfilePreview, type Professional, type Service, type ServiceMode } from "@/lib/catalog";
import { useMe } from "@/lib/me";

interface Draft {
  name: string;
  description: string;
  duration_minutes: string;
  preparation_minutes: string;
  price: string;
  color: string;
  mode: ServiceMode;
  public_visible: boolean;
  professional_ids: string[];
}

const EMPTY: Draft = {
  name: "",
  description: "",
  duration_minutes: "30",
  preparation_minutes: "0",
  price: "",
  color: "#0071e3",
  mode: "in_person",
  public_visible: true,
  professional_ids: [],
};

const MODES = [["in_person", "In studio"], ["online", "Online"], ["both", "Entrambe"]] as const;

function toDraft(s: Service): Draft {
  return {
    name: s.name,
    description: s.description ?? "",
    duration_minutes: String(s.duration_minutes),
    preparation_minutes: String(s.preparation_minutes),
    price: s.price ?? "",
    color: s.color,
    mode: s.mode,
    public_visible: s.public_visible,
    professional_ids: s.professional_ids,
  };
}

function toBody(d: Draft) {
  return {
    name: d.name.trim(),
    description: d.description.trim() || null,
    duration_minutes: Number(d.duration_minutes),
    preparation_minutes: Number(d.preparation_minutes || 0),
    price: d.price.trim() ? d.price.trim().replace(",", ".") : null,
    color: d.color,
    mode: d.mode,
    public_visible: d.public_visible,
    professional_ids: d.professional_ids,
  };
}

export function Services() {
  const { me } = useMe();
  const canEdit = me.role === "owner";
  const [services, setServices] = useState<Service[] | null>(null);
  const [professionals, setProfessionals] = useState<Professional[]>([]);
  const [loadError, setLoadError] = useState<string | null>(null);

  const load = useCallback(() => {
    api<Service[]>("/services").then(setServices, (e) => setLoadError(e.message));
    api<Professional[]>("/professionals").then(setProfessionals, () => null);
  }, []);
  useEffect(load, [load]);

  const active = services?.filter((s) => s.active) ?? [];
  const inactive = services?.filter((s) => !s.active) ?? [];
  const activeProfs = professionals.filter((p) => p.status === "active");

  return (
    <>
      <PageHeader meta={me.tenant.name} title="Prestazioni" />
      {loadError && <Notice state={{ error: loadError }} />}
      {!canEdit && <Notice state={{ ok: true, message: "Solo il titolare può modificare il catalogo delle prestazioni." }} />}

      <Panel title="Catalogo" meta={services ? `${active.length} attive` : undefined} flush>
        {services && services.length === 0 && (
          <EmptyState icon={<Stethoscope />} title="Nessuna prestazione" text="Aggiungi la prima prestazione o carica quelle consigliate per la tua attività." />
        )}
        <ul>
          {[...active, ...inactive].map((s) => (
            <Disclosure
              key={s.id}
              leading={<ColorDot color={s.color} size={14} />}
              title={s.name}
              subtitle={[`${s.duration_minutes} min`, s.preparation_minutes ? `+${s.preparation_minutes} min preparazione` : null, formatPrice(s.price)]
                .filter(Boolean)
                .join(" · ")}
              muted={!s.active}
              trailing={
                <>
                  {s.mode !== "in_person" && (
                    <Tag tone="accent">
                      <Video className="h-3.5 w-3.5" /> {MODE_LABELS[s.mode]}
                    </Tag>
                  )}
                  {!s.active && <Tag>Disattivata</Tag>}
                  {s.active && !s.public_visible && <Tag>Solo interna</Tag>}
                </>
              }
            >
              <ServiceForm initial={toDraft(s)} service={s} professionals={activeProfs} canEdit={canEdit} onDone={load} />
            </Disclosure>
          ))}
        </ul>
        {canEdit && (
          <AddRow label="Nuova prestazione">
            <ServiceForm initial={{ ...EMPTY, professional_ids: activeProfs.map((p) => p.id) }} professionals={activeProfs} canEdit onDone={load} />
          </AddRow>
        )}
      </Panel>

      {canEdit && <ProfilePanel onLoaded={load} />}
    </>
  );
}

function ServiceForm({
  initial,
  service,
  professionals,
  canEdit,
  onDone,
}: {
  initial: Draft;
  service?: Service;
  professionals: Professional[];
  canEdit: boolean;
  onDone: () => void;
}) {
  const [d, setD] = useState<Draft>(initial);
  const [saved, setSaved] = useState(false);
  const { pending, error, run } = useAction();
  const set = <K extends keyof Draft>(key: K, value: Draft[K]) => {
    setSaved(false);
    setD({ ...d, [key]: value });
  };

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    const res = await run(() =>
      service
        ? api<Service>(`/services/${service.id}`, { method: "PATCH", body: toBody(d) })
        : api<Service>("/services", { body: toBody(d) }),
    );
    if (res) {
      setSaved(true);
      if (!service) setD(initial);
      onDone();
    }
  }

  async function toggleActive() {
    if (!service) return;
    const res = await run(() => api<Service>(`/services/${service.id}`, { method: "PATCH", body: { active: !service.active } }));
    if (res) onDone();
  }

  function toggleProf(id: string, on: boolean) {
    set("professional_ids", on ? [...d.professional_ids, id] : d.professional_ids.filter((p) => p !== id));
  }

  return (
    <form onSubmit={onSubmit} className="space-y-5" noValidate>
      <fieldset disabled={!canEdit} className="space-y-5">
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Nome">
            <input className={inputCls} required maxLength={120} value={d.name} onChange={(e) => set("name", e.target.value)} />
          </Field>
          <Field label="Prezzo (€)" hint="Facoltativo: solo indicativo, nessun pagamento online.">
            <input className={inputCls} inputMode="decimal" placeholder="Es. 60" value={d.price} onChange={(e) => set("price", e.target.value)} />
          </Field>
          <Field label="Durata (minuti)">
            <input className={inputCls} type="number" min={5} max={600} step={5} required value={d.duration_minutes}
              onChange={(e) => set("duration_minutes", e.target.value)} />
          </Field>
          <Field label="Preparazione (minuti)" hint="Tempo libero dopo l'appuntamento, ad esempio per riordinare.">
            <input className={inputCls} type="number" min={0} max={240} step={5} value={d.preparation_minutes}
              onChange={(e) => set("preparation_minutes", e.target.value)} />
          </Field>
          <div className="sm:col-span-2">
            <Field label="Descrizione">
              <textarea className={`${inputCls} h-auto min-h-20 py-2.5`} maxLength={2000} value={d.description}
                onChange={(e) => set("description", e.target.value)} />
            </Field>
          </div>
        </div>
        <div className="space-y-1.5">
          <p className="px-1 t-footnote font-medium text-ink-3">Modalità</p>
          <Segmented label="Modalità" options={MODES} value={d.mode} onChange={(v) => set("mode", v)} className="max-w-md" />
          {d.mode !== "in_person" && (
            <p className="px-1 t-caption text-ink-3">Per le visite online il link della videochiamata sarà creato per ogni appuntamento (con l&apos;agenda).</p>
          )}
        </div>
        <ColorPicker value={d.color} onChange={(c) => set("color", c)} />
        {professionals.length > 0 && (
          <div className="space-y-2">
            <p className="px-1 t-footnote font-medium text-ink-3">Chi la eroga</p>
            {professionals.map((p) => (
              <CheckRow key={p.id} label={p.name} checked={d.professional_ids.includes(p.id)} onChange={(on) => toggleProf(p.id, on)} />
            ))}
          </div>
        )}
        <CheckRow
          label="Prenotabile online"
          description="Visibile nella pagina di prenotazione pubblica (quando sarà attiva)."
          checked={d.public_visible}
          onChange={(v) => set("public_visible", v)}
        />
      </fieldset>
      {error && <Notice state={{ error: error.message }} />}
      {saved && service && <Notice state={{ ok: true, message: "Prestazione salvata" }} />}
      {canEdit && (
        <div className="flex flex-wrap gap-3">
          <button className={btnPrimary} disabled={pending || !d.name.trim()}>
            {pending ? "Salvataggio…" : service ? "Salva" : "Aggiungi prestazione"}
          </button>
          {service && (
            <button type="button" className={btnSecondary} disabled={pending} onClick={toggleActive}>
              {service.active ? "Disattiva" : "Riattiva"}
            </button>
          )}
        </div>
      )}
    </form>
  );
}

function ProfilePanel({ onLoaded }: { onLoaded: () => void }) {
  const [preview, setPreview] = useState<ProfilePreview | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const { pending, error, run } = useAction();

  const refresh = useCallback(() => {
    api<ProfilePreview>("/services/profile").then(setPreview, () => null);
  }, []);
  useEffect(refresh, [refresh]);

  if (!preview) return null;
  const missing = preview.services.filter((s) => !s.already_present);

  async function load() {
    const res = await run(() => api<{ created: number }>("/services/profile", { method: "POST" }));
    if (res) {
      setMessage(res.created === 1 ? "Aggiunta 1 prestazione" : `Aggiunte ${res.created} prestazioni`);
      refresh();
      onLoaded();
    }
  }

  return (
    <Panel title="Prestazioni consigliate" meta={preview.label}>
      <div className="space-y-4">
        <p className="t-subhead text-ink-2">
          Il profilo della tua attività propone queste prestazioni. Puoi modificarle o disattivarle in qualsiasi momento.
        </p>
        <ul className="space-y-1.5">
          {preview.services.map((s) => (
            <li key={s.name} className="flex items-center gap-2 t-subhead">
              <span className={s.already_present ? "text-ink-3" : "text-ink"}>{s.name}</span>
              <span className="text-ink-3">· {s.duration_minutes} min</span>
              {s.mode !== "in_person" && <Tag tone="accent">{MODE_LABELS[s.mode]}</Tag>}
              {s.already_present && <Tag>Già presente</Tag>}
            </li>
          ))}
        </ul>
        {error && <Notice state={{ error: error.message }} />}
        {message && <Notice state={{ ok: true, message }} />}
        <button type="button" className={btnTinted} disabled={pending || missing.length === 0} onClick={load}>
          <Sparkles className="h-4 w-4" />
          {missing.length === 0 ? "Tutte già presenti" : `Aggiungi le ${missing.length} mancanti`}
        </button>
      </div>
    </Panel>
  );
}
