import { Suspense } from "react";
import { AuthShell, FormSkeleton } from "@/components/AuthShell";
import { VerifyEmail } from "@/components/auth/TokenForms";

export const metadata = { title: "Conferma email" };

export default function Page() {
  return (
    <AuthShell kicker="Quasi fatto" title="Conferma email" subtitle="Stiamo attivando il tuo account.">
      <Suspense fallback={<FormSkeleton />}>
        <VerifyEmail />
      </Suspense>
    </AuthShell>
  );
}
