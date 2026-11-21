import { ClientArea } from "@/components/clienti/ClientArea";

// Contenuto personale caricato nel browser dopo la verifica della sessione del cliente.
export const instant = false;

export const metadata = { title: "Area clienti", robots: { index: false, follow: false } };

export default function Page() {
  return <ClientArea />;
}
