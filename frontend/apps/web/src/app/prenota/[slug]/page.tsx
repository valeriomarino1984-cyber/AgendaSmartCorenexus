import { Suspense } from "react";
import { BookingFlow } from "@/components/booking/BookingFlow";

// Pagina pubblica dello studio: orari e disponibilità cambiano di continuo, si caricano nel browser.
export const instant = false;

export const metadata = { title: "Prenota online" };

export default function Page() {
  return (
    <Suspense fallback={<div className="min-h-screen bg-paper" />}>
      <BookingFlow />
    </Suspense>
  );
}
