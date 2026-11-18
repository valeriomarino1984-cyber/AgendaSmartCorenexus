/** Notifiche ai clienti (API /notifications e dettaglio appuntamento). */
export interface NotificationItem {
  id: string;
  appointment_id: string;
  kind: "confirmation" | "reminder" | "rescheduled" | "cancelled";
  kind_label: string;
  channel: string;
  status: "pending" | "sending" | "sent" | "failed" | "skipped" | "cancelled";
  status_label: string;
  reason: string | null;
  reason_label: string | null;
  scheduled_at: string;
  sent_at: string | null;
  attempts: number;
  client_name?: string;
  appointment_start_at?: string;
}

export const NOTIFICATION_TONE: Record<NotificationItem["status"], "go" | "warn" | "stamp" | "neutral"> = {
  sent: "go",
  pending: "warn",
  sending: "warn",
  failed: "stamp",
  skipped: "neutral",
  cancelled: "neutral",
};
