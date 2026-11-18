"use client";

import { BellRing, RotateCcw } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { Segmented } from "@/components/Segmented";
import { useAction } from "@/components/auth/useAction";
import { EmptyState, Notice, PageHeader, Panel, StatStrip, Tag, btnTinted } from "@/components/ui";
import { api } from "@/lib/api";
import { formatDateTime } from "@/lib/catalog";
import { NOTIFICATION_TONE, type NotificationItem } from "@/lib/notifications";
import { useMe } from "@/lib/me";

type Filter = "all" | "problems" | "pending";

export function Notifications() {
  const { me } = useMe();
  const [items, setItems] = useState<NotificationItem[] | null>(null);
  const [filter, setFilter] = useState<Filter>("all");
  const [message, setMessage] = useState<string | null>(null);
  const { pending, error, run } = useAction();

  const load = useCallback(() => {
    api<NotificationItem[]>("/notifications?limit=200").then(setItems, () => null);
  }, []);
  useEffect(load, [load]);

  const all = items ?? [];
  const shown = all.filter((n) =>
    filter === "problems" ? n.status === "failed" || n.status === "skipped" : filter === "pending" ? n.status === "pending" : true,
  );

  async function retry(n: NotificationItem) {
    setMessage(null);
    const r = await run(() => api(`/notifications/${n.id}/retry`, { method: "POST" }));
    if (r) {
      setMessage("Nuovo tentativo in corso");
      setTimeout(load, 1500);
    }
  }

  return (
    <>
      <PageHeader meta={me.tenant.name} title="Notifiche" />
      <p className="max-w-2xl t-subhead text-ink-3">
        Le email inviate ai clienti: conferme, promemoria, spostamenti e annullamenti. Si impostano in Impostazioni → Notifiche ai clienti.
      </p>
      <StatStrip
        items={[
          { label: "Inviate", value: all.filter((n) => n.status === "sent").length, tone: "go", icon: <BellRing /> },
          { label: "In programma", value: all.filter((n) => n.status === "pending").length, tone: "accent" },
          { label: "Non inviate", value: all.filter((n) => n.status === "skipped").length, tone: "neutral" },
          { label: "Non riuscite", value: all.filter((n) => n.status === "failed").length, tone: "stamp", emphasize: all.some((n) => n.status === "failed") },
        ]}
      />
      <Segmented label="Filtro" className="max-w-md" value={filter} onChange={setFilter}
        options={[["all", "Tutte"], ["pending", "In programma"], ["problems", "Da controllare"]] as const} />
      {error && <Notice state={{ error: error.message }} />}
      {message && <Notice state={{ ok: true, message }} />}
      <Panel title="Ultime notifiche" meta={items ? `${shown.length}` : undefined} flush>
        {items && shown.length === 0 && <EmptyState icon={<BellRing />} title="Nessuna notifica" text="Le email ai clienti compariranno qui." />}
        <ul>
          {shown.map((n) => (
            <li key={n.id} className="flex flex-wrap items-center gap-x-3 gap-y-1 border-t border-rule px-5 py-3 first:border-t-0">
              <span className="min-w-0 flex-1">
                <span className="block truncate t-body">{n.kind_label} · {n.client_name}</span>
                <span className="block t-footnote text-ink-3">
                  {n.status === "sent" && n.sent_at ? `Inviata ${formatDateTime(n.sent_at)}` : n.status === "pending" ? `Prevista ${formatDateTime(n.scheduled_at)}` : formatDateTime(n.scheduled_at)}
                  {n.appointment_start_at ? ` · appuntamento ${formatDateTime(n.appointment_start_at)}` : ""}
                  {n.reason_label ? ` · ${n.reason_label}` : ""}
                </span>
              </span>
              <Tag tone={NOTIFICATION_TONE[n.status]}>{n.status_label}</Tag>
              {(n.status === "failed" || n.status === "skipped") && (
                <button type="button" className={`${btnTinted} h-9 px-3`} disabled={pending} onClick={() => retry(n)}>
                  <RotateCcw className="h-4 w-4" /> Riprova
                </button>
              )}
            </li>
          ))}
        </ul>
      </Panel>
    </>
  );
}
