import { Services } from "@/components/studio/Services";

// Area riservata: dati caricati nel browser dopo la verifica della sessione (vedi collaboratori/page.tsx).
export const instant = false;

export const metadata = { title: "Prestazioni" };

export default function Page() {
  return <Services />;
}
