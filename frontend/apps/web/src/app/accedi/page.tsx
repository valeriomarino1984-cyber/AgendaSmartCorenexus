import { Suspense } from "react";
import { AuthShell, FormSkeleton } from "@/components/AuthShell";
import { LoginForm, SignupLink } from "@/components/auth/LoginForm";

export const metadata = { title: "Accedi" };

export default function Page() {
  return (
    <AuthShell kicker="Area studio" title="Accedi" subtitle="Agenda, clienti e collaboratori del tuo studio." footer={<SignupLink />}>
      <Suspense fallback={<FormSkeleton />}>
        <LoginForm />
      </Suspense>
    </AuthShell>
  );
}
