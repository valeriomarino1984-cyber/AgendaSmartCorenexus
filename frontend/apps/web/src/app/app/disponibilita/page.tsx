import { Availability } from "@/components/studio/Availability";

// Area riservata: dati caricati nel browser dopo la verifica della sessione (vedi collaboratori/page.tsx).
export const instant = false;

export const metadata = { title: "Disponibilità" };

export default function Page() {
  return <Availability />;
}
