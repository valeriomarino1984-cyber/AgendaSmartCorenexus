import { Notifications } from "@/components/studio/Notifications";

// Area riservata: dati caricati nel browser dopo la verifica della sessione (vedi collaboratori/page.tsx).
export const instant = false;

export const metadata = { title: "Notifiche" };

export default function Page() {
  return <Notifications />;
}
