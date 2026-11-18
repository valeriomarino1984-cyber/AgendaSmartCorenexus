/** Tipi delle anagrafiche dello studio (API /locations, /professionals, /services, /clients). */

export interface Location {
  id: string;
  name: string;
  address: string | null;
  timezone: string;
  is_default: boolean;
  active: boolean;
}

export interface Professional {
  id: string;
  user_id: string | null;
  account_email: string | null;
  name: string;
  specialization: string | null;
  color: string;
  status: "active" | "inactive";
  public_booking: boolean;
}

export type ServiceMode = "in_person" | "online" | "both";

export interface Service {
  id: string;
  name: string;
  description: string | null;
  duration_minutes: number;
  preparation_minutes: number;
  price: string | null;
  color: string;
  mode: ServiceMode;
  public_visible: boolean;
  active: boolean;
  sort_order: number;
  professional_ids: string[];
}

export interface ProfilePreview {
  profile: string;
  label: string;
  services: { name: string; duration_minutes: number; preparation_minutes: number; mode: ServiceMode; already_present: boolean }[];
}

export interface Client {
  id: string;
  first_name: string;
  last_name: string;
  phone: string | null;
  email: string | null;
  birth_date: string | null;
  reference_professional_id: string | null;
  admin_notes: string | null;
  preferred_channel: "whatsapp" | "email" | "none" | null;
  whatsapp_consent: boolean;
  whatsapp_consent_at: string | null;
  email_consent: boolean;
  email_consent_at: string | null;
  marketing_consent: boolean;
  marketing_consent_at: string | null;
  status: "active" | "archived";
  created_at: string;
  updated_at: string;
  consent_history?: { channel: string; action: string; source: string; at: string }[];
}

export const MODE_LABELS: Record<ServiceMode, string> = {
  in_person: "In studio",
  online: "Online",
  both: "In studio o online",
};

/** Palette dei colori proposti (colori di sistema Apple). */
export const PALETTE = ["#0071e3", "#30b0c7", "#5856d6", "#34c759", "#ff9500", "#ff2d55", "#af52de", "#a2845e"];

export function formatPrice(price: string | null): string | null {
  if (price === null) return null;
  return new Intl.NumberFormat("it-IT", { style: "currency", currency: "EUR" }).format(Number(price));
}

export function formatDateTime(iso: string | null): string {
  if (!iso) return "";
  return new Intl.DateTimeFormat("it-IT", { dateStyle: "medium", timeStyle: "short" }).format(new Date(iso));
}

/** "+393331112222" → "+39 333 111 2222" (solo numeri italiani; gli altri restano come sono). */
export function formatPhone(e164: string | null): string | null {
  if (!e164) return null;
  const m = e164.match(/^\+39(\d{3})(\d{3})(\d{1,5})$/);
  return m ? `+39 ${m[1]} ${m[2]} ${m[3]}` : e164;
}
