import { Agenda } from "@/components/agenda/Agenda";

// Area riservata: dati caricati nel browser dopo la verifica della sessione (vedi collaboratori/page.tsx).
export const instant = false;

export const metadata = { title: "Agenda" };

export default function Page() {
  return <Agenda />;
}
