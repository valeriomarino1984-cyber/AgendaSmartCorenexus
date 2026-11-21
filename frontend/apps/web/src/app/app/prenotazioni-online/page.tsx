import { OnlineBooking } from "@/components/studio/OnlineBooking";

// Area riservata: dati caricati nel browser dopo la verifica della sessione (vedi collaboratori/page.tsx).
export const instant = false;

export const metadata = { title: "Prenotazioni online" };

export default function Page() {
  return <OnlineBooking />;
}
