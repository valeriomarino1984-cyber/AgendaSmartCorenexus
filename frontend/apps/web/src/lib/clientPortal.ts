/** Tipi dell'area clienti (API /client-portal). */
export interface PortalAppointment {
  id: string;
  code: string;
  studio: string;
  studio_phone: string | null;
  studio_email: string | null;
  address: string | null;
  timezone: string;
  start_at: string;
  end_at: string;
  service: string;
  professional: string;
  status: "pending" | "confirmed" | "cancelled_by_client" | "cancelled_by_staff" | "completed" | "no_show";
  status_label: string;
  is_online: boolean;
  video_url: string | null;
  can_cancel: boolean;
  cancellation_min_hours: number;
}

export interface PortalOverview {
  email: string;
  upcoming: PortalAppointment[];
  past: PortalAppointment[];
}
