import { Professionals } from "@/components/studio/Professionals";

// Area riservata: dati caricati nel browser dopo la verifica della sessione (vedi collaboratori/page.tsx).
export const instant = false;

export const metadata = { title: "Professionisti" };

export default function Page() {
  return <Professionals />;
}
