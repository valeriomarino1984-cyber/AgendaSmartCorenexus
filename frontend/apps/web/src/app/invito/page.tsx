import { Suspense } from "react";
import { AuthShell, FormSkeleton } from "@/components/AuthShell";
import { AcceptInvitation } from "@/components/auth/TokenForms";

export const metadata = { title: "Invito", robots: { index: false, follow: false } };

export default function Page() {
  return (
    <AuthShell kicker="Invito" title="Entra nello studio" subtitle="Ti hanno invitato a usare l'agenda dello studio.">
      <Suspense fallback={<FormSkeleton />}>
        <AcceptInvitation />
      </Suspense>
    </AuthShell>
  );
}
