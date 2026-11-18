/** Tipi dell'area piattaforma (API /platform). */
export interface StaffMe { id: string; email: string; full_name: string }

export interface PlatformTenant {
  id: string;
  name: string;
  slug: string;
  business_type: string;
  status: "trial" | "active" | "suspended" | "cancelled";
  trial_ends_at: string | null;
  created_at: string;
  owner_name: string;
  owner_email: string;
  owner_invitation_pending: boolean;
  professionals: number;
  clients: number;
  upcoming_appointments: number;
  services?: number;
  contact_email?: string | null;
  contact_phone?: string | null;
}

export interface PlatformStaff {
  id: string;
  email: string;
  full_name: string;
  status: "invited" | "active" | "disabled";
  last_login_at: string | null;
  is_me: boolean;
}

export interface PlatformActivity { at: string; action: string; staff: string | null; tenant: string | null; ip: string | null }

export const TENANT_STATUS: Record<PlatformTenant["status"], [string, "warn" | "go" | "stamp" | "neutral"]> = {
  trial: ["In prova", "warn"],
  active: ["Attivo", "go"],
  suspended: ["Sospeso", "stamp"],
  cancelled: ["Chiuso", "neutral"],
};

export const ACTION_LABELS: Record<string, string> = {
  setup_requested: "Prima configurazione richiesta",
  invite_accepted: "Invito accettato",
  login: "Accesso",
  login_failed: "Accesso non riuscito",
  mfa_failed: "Codice errato",
  logout: "Uscita",
  staff_invited: "Persona invitata",
  staff_disabled: "Persona disattivata",
  staff_enabled: "Persona riattivata",
  tenant_created: "Studio creato",
  tenant_updated: "Studio modificato",
  tenant_profile_loaded: "Prestazioni consigliate aggiunte",
  tenant_invite_resent: "Invito al titolare inviato di nuovo",
};

export function daysLeft(iso: string | null): number | null {
  if (!iso) return null;
  return Math.ceil((new Date(iso).getTime() - Date.now()) / 86_400_000);
}
