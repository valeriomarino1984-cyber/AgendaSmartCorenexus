"use client";

import { Check, Copy, ExternalLink, Globe } from "lucide-react";
import QRCode from "qrcode";
import { useEffect, useState } from "react";
import { useAction } from "@/components/auth/useAction";
import { CheckRow, Field, Notice, PageHeader, Panel, btnPrimary, btnSecondary, selectCls } from "@/components/ui";
import { api } from "@/lib/api";
import { useMe } from "@/lib/me";

interface Settings {
  slug: string;
  online_booking_enabled: boolean;
  online_booking_days_ahead: number;
  online_booking_min_notice_hours: number;
  online_booking_requires_confirmation: boolean;
}

/** Prenotazioni online: attivazione, link da condividere, QR da stampare e regole. */
export function OnlineBooking() {
  const { me } = useMe();
  const canEdit = me.role === "owner";
  const [st, setSt] = useState<Settings | null>(null);
  const [qr, setQr] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [saved, setSaved] = useState(false);
  const { pending, error, run } = useAction();

  useEffect(() => {
    api<Settings>("/tenants/current").then(setSt, () => null);
  }, []);

  const url = st ? `${typeof window === "undefined" ? "" : window.location.origin}/prenota/${st.slug}` : "";
  useEffect(() => {
    if (!url) return;
    QRCode.toString(url, { type: "svg", margin: 1 }).then(setQr, () => null);
  }, [url]);

  if (!st) return <PageHeader title="Prenotazioni online" />;
  const set = <K extends keyof Settings>(k: K, v: Settings[K]) => {
    setSaved(false);
    setSt({ ...st, [k]: v });
  };

  async function save() {
    if (!st) return;
    const r = await run(() =>
      api<Settings>("/tenants/current", {
        method: "PUT",
        body: {
          online_booking_enabled: st.online_booking_enabled,
          online_booking_days_ahead: st.online_booking_days_ahead,
          online_booking_min_notice_hours: st.online_booking_min_notice_hours,
          online_booking_requires_confirmation: st.online_booking_requires_confirmation,
        },
      }),
    );
    if (r) {
      setSt(r);
      setSaved(true);
    }
  }

  return (
    <>
      <PageHeader meta={me.tenant.name} title="Prenotazioni online" />
      <p className="max-w-2xl t-subhead text-ink-3">
        Una pagina dello studio dove i clienti prenotano da soli tra gli orari liberi. Si vedono solo le prestazioni e i professionisti
        segnati come «Prenotabile online».
      </p>
      {!canEdit && <Notice state={{ ok: true, message: "Solo il titolare può modificare queste impostazioni." }} />}

      <Panel title="La tua pagina">
        <div className="flex flex-col gap-6 md:flex-row md:items-center">
          {qr && st.online_booking_enabled && (
            <div className="mx-auto h-40 w-40 shrink-0 rounded-[16px] bg-white p-2 ring-1 ring-rule" dangerouslySetInnerHTML={{ __html: qr.replace("<svg", '<svg width="100%" height="100%"') }} />
          )}
          <div className="min-w-0 flex-1 space-y-3">
            <p className={`inline-flex items-center gap-1.5 t-subhead font-semibold ${st.online_booking_enabled ? "text-go" : "text-ink-3"}`}>
              <Globe className="h-4 w-4" /> {st.online_booking_enabled ? "Attiva: i clienti possono prenotare" : "Spenta: la pagina non è visibile"}
            </p>
            <p className="num truncate rounded-[10px] bg-paper-2 px-3 py-2 t-subhead">{url}</p>
            <div className="flex flex-wrap gap-2">
              <button type="button" className={btnSecondary} onClick={async () => { await navigator.clipboard?.writeText(url).catch(() => null); setCopied(true); }}>
                {copied ? <><Check className="h-4 w-4" /> Copiato</> : <><Copy className="h-4 w-4" /> Copia il link</>}
              </button>
              {st.online_booking_enabled && (
                <a href={url} target="_blank" rel="noopener noreferrer" className={btnSecondary}><ExternalLink className="h-4 w-4" /> Apri la pagina</a>
              )}
            </div>
            <p className="t-footnote text-ink-3">Mettilo sul sito, su Instagram o Google; il QR si può stampare per la sala d&apos;attesa.</p>
          </div>
        </div>
      </Panel>

      <Panel title="Regole">
        <fieldset disabled={!canEdit} className="space-y-5">
          <CheckRow label="Prenotazione online attiva" checked={st.online_booking_enabled} onChange={(v) => set("online_booking_enabled", v)}
            description="Spenta, la pagina risponde «non disponibile»." />
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Prenotabile fino a">
              <select className={selectCls} value={st.online_booking_days_ahead} onChange={(e) => set("online_booking_days_ahead", Number(e.target.value))}>
                {[7, 14, 30, 60, 90, 180].map((d) => <option key={d} value={d}>{d} giorni in avanti</option>)}
              </select>
            </Field>
            <Field label="Preavviso minimo">
              <select className={selectCls} value={st.online_booking_min_notice_hours} onChange={(e) => set("online_booking_min_notice_hours", Number(e.target.value))}>
                {[0, 1, 2, 4, 12, 24, 48].map((h) => <option key={h} value={h}>{h === 0 ? "Nessuno" : `${h} ore`}</option>)}
              </select>
            </Field>
          </div>
          <CheckRow label="Conferma manuale" checked={st.online_booking_requires_confirmation} onChange={(v) => set("online_booking_requires_confirmation", v)}
            description="Le prenotazioni arrivano «Da confermare» e il cliente riceve la conferma quando le confermi in agenda." />
        </fieldset>
        {canEdit && (
          <div className="mt-5 flex flex-wrap items-center gap-3">
            <button type="button" className={btnPrimary} disabled={pending} onClick={save}>{pending ? "Salvataggio…" : "Salva"}</button>
            {saved && <Notice state={{ ok: true, message: "Impostazioni salvate" }} />}
            {error && <Notice state={{ error: error.message }} />}
          </div>
        )}
      </Panel>
    </>
  );
}
