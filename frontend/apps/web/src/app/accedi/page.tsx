import { Suspense } from "react";
import { AuthShell, FormSkeleton } from "@/components/AuthShell";
import { AreaSwitch } from "@/components/auth/AreaSwitch";
import { LoginForm } from "@/components/auth/LoginForm";

export const metadata = { title: "Login professionisti", robots: { index: false, follow: false } };

export default function Page() {
  return (
    <AuthShell kicker="Area professionisti" title="Login professionisti" subtitle="Agenda, clienti e collaboratori del tuo studio.">
      <AreaSwitch current="professionisti" />
      <Suspense fallback={<FormSkeleton />}>
        <LoginForm />
      </Suspense>
    </AuthShell>
  );
}
