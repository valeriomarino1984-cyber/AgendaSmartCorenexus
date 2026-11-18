"use client";

import { Archive, Search, Users } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import {
  AddRow, CheckRow, Disclosure, EmptyState, Field, Monogram, Notice, PageHeader, Panel, Tag,
  btnDanger, btnPrimary, btnSecondary, btnTinted, inputCls, selectCls,
} from "@/components/ui";
import { Segmented } from "@/components/Segmented";
import { useAction } from "@/components/auth/useAction";
import { api, ApiError } from "@/lib/api";
import { formatDateTime, formatPhone, type Client, type Professional } from "@/lib/catalog";
import { useMe } from "@/lib/me";

const PAGE = 50;

interface Draft {
  first_name: string;
  last_name: string;
  phone: string;
  email: string;
  birth_date: string;
  reference_professional_id: string;
  preferred_channel: string;
  admin_notes: string;
  whatsapp_consent: boolean;
  email_consent: boolean;
  marketing_consent: boolean;
}

const EMPTY: Draft = {
  first_name: "",
  last_name: "",
  phone: "",
  email: "",
  birth_date: "",
  reference_professional_id: "",
  preferred_channel: "",
  admin_notes: "",
  whatsapp_consent: false,
  email_consent: false,
  marketing_consent: false,
};

function toDraft(c: Client): Draft {
  return {
    first_name: c.first_name,
    last_name: c.last_name,
    phone: c.phone ?? "",
    email: c.email ?? "",
    birth_date: c.birth_date ?? "",
    reference_professional_id: c.reference_professional_id ?? "",
    preferred_channel: c.preferred_channel ?? "",
    admin_notes: c.admin_notes ?? "",
    whatsapp_consent: c.whatsapp_consent,
    email_consent: c.email_consent,
    marketing_consent: c.marketing_consent,
  };
}

function toBody(d: Draft) {
  return {
    first_name: d.first_name.trim(),
    last_name: d.last_name.trim(),
    phone: d.phone.trim() || null,
    email: d.email.trim() || null,
    birth_date: d.birth_date || null,
    reference_professional_id: d.reference_professional_id || null,
    preferred_channel: d.preferred_channel || null,
    admin_notes: d.admin_notes.trim() || null,
    whatsapp_consent: d.whatsapp_consent,
    email_consent: d.email_consent,
    marketing_consent: d.marketing_consent,
  };
}

export function Clients() {
  const { me } = useMe();
  const [q, setQ] = useState("");
  const [status, setStatus] = useState<"active" | "archived">("active");
  const [page, setPage] = useState<{ items: Client[]; total: number } | null>(null);
  const [limit, setLimit] = useState(PAGE);
  const [professionals, setProfessionals] = useState<Professional[]>([]);
  const [loadError, setLoadError] = useState<string | null>(null);
  const request = useRef(0);

  const load = useCallback(() => {
    const id = ++request.current;
    const params = new URLSearchParams({ status, limit: String(limit) });
    if (q.trim()) params.set("q", q.trim());
    api<{ items: Client[]; total: number }>(`/clients?${params}`).then(
      (res) => id === request.current && setPage(res),
      (e) => setLoadError(e.message),
    );
  }, [q, status, limit]);

  useEffect(() => {
    const t = setTimeout(load, q ? 250 : 0);
    return () => clearTimeout(t);
  }, [load, q]);
  useEffect(() => {
    api<Professional[]>("/professionals").then(setProfessionals, () => null);
  }, []);

  const profName = (id: string | null) => professionals.find((p) => p.id === id)?.name;

  return (
    <>
      <PageHeader meta={me.tenant.name} title="Clienti" />
      {loadError && <Notice state={{ error: loadError }} />}
      <div className="flex flex-wrap items-center gap-3">
        <div className="relative min-w-0 flex-1 basis-64">
          <Search aria-hidden className="pointer-events-none absolute top-1/2 left-3.5 h-4 w-4 -translate-y-1/2 text-ink-3" />
          <input
            type="search"
            aria-label="Cerca clienti"
            placeholder="Cerca per nome, telefono o email"
            className={`${inputCls} pl-10`}
            value={q}
            onChange={(e) => {
              setQ(e.target.value);
              setLimit(PAGE);
            }}
          />
        </div>
        <Segmented
          label="Stato"
          options={[["active", "Attivi"], ["archived", "Archiviati"]] as const}
          value={status}
          onChange={(v) => {
            setStatus(v);
            setLimit(PAGE);
          }}
          className="w-56"
        />
      </div>

      <Panel title={status === "active" ? "Anagrafica" : "Archivio"} meta={page ? `${page.total} ${page.total === 1 ? "cliente" : "clienti"}` : undefined} flush>
        {page && page.items.length === 0 && (
          <EmptyState
            icon={<Users />}
            title={q ? "Nessun risultato" : status === "active" ? "Nessun cliente" : "Archivio vuoto"}
            text={q ? "Prova con un altro nome o numero." : status === "active" ? "Aggiungi il primo cliente qui sotto." : undefined}
          />
        )}
        <ul>
          {page?.items.map((c) => (
            <Disclosure
              key={c.id}
              leading={<Monogram name={`${c.first_name} ${c.last_name}`} size={34} />}
              title={`${c.last_name} ${c.first_name}`}
              subtitle={[formatPhone(c.phone), c.email].filter(Boolean).join(" · ") || "Nessun contatto"}
              muted={c.status === "archived"}
              trailing={
                <>
                  {profName(c.reference_professional_id) && <Tag>{profName(c.reference_professional_id)}</Tag>}
                  {c.email_consent && <Tag tone="accent">Email</Tag>}
                  {c.whatsapp_consent && <Tag tone="wa">WhatsApp</Tag>}
                </>
              }
            >
              <ClientDetail client={c} professionals={professionals} onChanged={load} />
            </Disclosure>
          ))}
        </ul>
        {page && page.items.length < page.total && (
          <div className="border-t border-rule px-5 py-3">
            <button type="button" className={btnSecondary} onClick={() => setLimit(limit + PAGE)}>
              Mostra altri
            </button>
          </div>
        )}
        {status === "active" && (
          <AddRow label="Nuovo cliente">
            <ClientForm professionals={professionals} onDone={load} />
          </AddRow>
        )}
      </Panel>
      <p className="t-footnote text-ink-3">
        Solo dati amministrativi: non inserire diagnosi o informazioni cliniche nelle note.
      </p>
    </>
  );
}

function ClientDetail({ client, professionals, onChanged }: { client: Client; professionals: Professional[]; onChanged: () => void }) {
  const { pending, error, run } = useAction();
  const [history, setHistory] = useState<Client["consent_history"] | null>(null);

  async function setStatus(action: "archive" | "restore") {
    const ok = await run(() =>
      (action === "archive"
        ? api(`/clients/${client.id}`, { method: "DELETE" })
        : api(`/clients/${client.id}/restore`, { method: "POST" })
      ).then(() => true),
    );
    if (ok) onChanged();
  }

  async function loadHistory() {
    const detail = await run(() => api<Client>(`/clients/${client.id}`));
    if (detail) setHistory(detail.consent_history ?? []);
  }

  return (
    <div className="space-y-6">
      {client.status === "archived" ? (
        <div className="space-y-3">
          <p className="t-subhead text-ink-2">Cliente archiviato: non compare nelle ricerche né nell&apos;agenda.</p>
          {error && <Notice state={{ error: error.message }} />}
          <button type="button" className={btnTinted} disabled={pending} onClick={() => setStatus("restore")}>
            Ripristina
          </button>
        </div>
      ) : (
        <>
          <ClientForm client={client} professionals={professionals} onDone={onChanged} />
          <div className="flex flex-wrap items-center gap-3 border-t border-rule pt-4">
            <button type="button" className={btnSecondary} disabled={pending} onClick={loadHistory}>
              Storico consensi
            </button>
            <button type="button" className={btnDanger} disabled={pending} onClick={() => setStatus("archive")}>
              <Archive className="h-4 w-4" /> Archivia
            </button>
          </div>
          {error && <Notice state={{ error: error.message }} />}
          {history && (
            <ul className="space-y-1 t-footnote text-ink-2">
              {history.length === 0 && <li>Nessun consenso registrato.</li>}
              {history.map((h, i) => (
                <li key={i}>
                  {formatDateTime(h.at)} · {CHANNEL_LABELS[h.channel] ?? h.channel}:{" "}
                  {h.action === "granted" ? "consenso dato" : "consenso revocato"} (dallo studio)
                </li>
              ))}
            </ul>
          )}
        </>
      )}
    </div>
  );
}

const CHANNEL_LABELS: Record<string, string> = { whatsapp: "WhatsApp", email: "Email", marketing: "Offerte e promozioni" };

function ClientForm({ client, professionals, onDone }: { client?: Client; professionals: Professional[]; onDone: () => void }) {
  const initial = client ? toDraft(client) : EMPTY;
  const [d, setD] = useState<Draft>(initial);
  const [saved, setSaved] = useState(false);
  const [duplicate, setDuplicate] = useState<string | null>(null);
  const { pending, error, run } = useAction();
  const set = <K extends keyof Draft>(key: K, value: Draft[K]) => {
    setSaved(false);
    setDuplicate(null);
    setD({ ...d, [key]: value });
  };

  async function save(force = false) {
    setDuplicate(null);
    const body = toBody(d);
    const res = await run(() =>
      (client
        ? api<Client>(`/clients/${client.id}`, { method: "PATCH", body })
        : api<Client>(`/clients${force ? "?force=true" : ""}`, { body })
      ).catch((e: unknown) => {
        // Un possibile doppione non è un errore: si chiede conferma.
        if (e instanceof ApiError && e.code === "cliente_duplicato") {
          setDuplicate(e.message);
          return null;
        }
        throw e;
      }),
    );
    if (res) {
      setSaved(true);
      if (!client) setD(EMPTY);
      onDone();
    }
  }

  const consentAt = (at: string | null | undefined) => (at ? `aggiornato il ${formatDateTime(at)}` : undefined);

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        void save();
      }}
      className="space-y-5"
      noValidate
    >
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="Nome">
          <input className={inputCls} required maxLength={80} autoComplete="off" value={d.first_name} onChange={(e) => set("first_name", e.target.value)} />
        </Field>
        <Field label="Cognome">
          <input className={inputCls} required maxLength={80} autoComplete="off" value={d.last_name} onChange={(e) => set("last_name", e.target.value)} />
        </Field>
        <Field label="Cellulare" hint="Senza prefisso si assume +39.">
          <input className={inputCls} type="tel" maxLength={30} autoComplete="off" value={d.phone} onChange={(e) => set("phone", e.target.value)} />
        </Field>
        <Field label="Email">
          <input className={inputCls} type="email" maxLength={254} autoComplete="off" value={d.email} onChange={(e) => set("email", e.target.value)} />
        </Field>
        <Field label="Data di nascita">
          <input className={inputCls} type="date" value={d.birth_date} onChange={(e) => set("birth_date", e.target.value)} />
        </Field>
        <Field label="Professionista di riferimento">
          <select className={selectCls} value={d.reference_professional_id} onChange={(e) => set("reference_professional_id", e.target.value)}>
            <option value="">Nessuno</option>
            {professionals.map((p) => (
              <option key={p.id} value={p.id}>{p.name}</option>
            ))}
          </select>
        </Field>
        <Field label="Canale preferito">
          <select className={selectCls} value={d.preferred_channel} onChange={(e) => set("preferred_channel", e.target.value)}>
            <option value="">Non indicato</option>
            <option value="email">Email</option>
            <option value="whatsapp">WhatsApp</option>
            <option value="none">Nessun messaggio</option>
          </select>
        </Field>
        <div className="sm:col-span-2">
          <Field label="Note amministrative" hint="Ad esempio preferenze di orario. Niente dati clinici.">
            <textarea className={`${inputCls} h-auto min-h-20 py-2.5`} maxLength={4000} value={d.admin_notes}
              onChange={(e) => set("admin_notes", e.target.value)} />
          </Field>
        </div>
      </div>
      <fieldset className="space-y-3">
        <legend className="px-1 pb-1 t-footnote font-medium text-ink-3">Consensi raccolti dallo studio</legend>
        <CheckRow label="Promemoria via email" description={consentAt(client?.email_consent_at)} checked={d.email_consent}
          onChange={(v) => set("email_consent", v)} />
        <CheckRow label="Promemoria via WhatsApp" description={consentAt(client?.whatsapp_consent_at)} checked={d.whatsapp_consent}
          onChange={(v) => set("whatsapp_consent", v)} />
        <CheckRow
          label="Offerte e promozioni"
          description={consentAt(client?.marketing_consent_at) ?? "Consenso separato, facoltativo."}
          checked={d.marketing_consent}
          onChange={(v) => set("marketing_consent", v)}
        />
      </fieldset>
      {error && <Notice state={{ error: error.message }} />}
      {duplicate && (
        <div role="alert" className="space-y-3 rounded-[12px] bg-warn-soft px-3.5 py-3 t-subhead text-warn">
          <p>{duplicate}</p>
          <button type="button" className={btnSecondary} disabled={pending} onClick={() => void save(true)}>
            Crea comunque
          </button>
        </div>
      )}
      {saved && client && <Notice state={{ ok: true, message: "Cliente salvato" }} />}
      {saved && !client && <Notice state={{ ok: true, message: "Cliente aggiunto" }} />}
      <button className={btnPrimary} disabled={pending || !d.first_name.trim() || !d.last_name.trim()}>
        {pending ? "Salvataggio…" : client ? "Salva" : "Aggiungi cliente"}
      </button>
    </form>
  );
}
