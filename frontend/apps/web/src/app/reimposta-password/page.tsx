import { Suspense } from "react";
import { AuthShell, FormSkeleton } from "@/components/AuthShell";
import { ResetPassword } from "@/components/auth/TokenForms";

export const metadata = { title: "Nuova password", robots: { index: false, follow: false } };

export default function Page() {
  return (
    <AuthShell title="Nuova password" subtitle="Scegli la password per il tuo account.">
      <Suspense fallback={<FormSkeleton />}>
        <ResetPassword />
      </Suspense>
    </AuthShell>
  );
}
