import { Clients } from "@/components/studio/Clients";

// Area riservata: dati caricati nel browser dopo la verifica della sessione (vedi collaboratori/page.tsx).
export const instant = false;

export const metadata = { title: "Clienti" };

export default function Page() {
  return <Clients />;
}
