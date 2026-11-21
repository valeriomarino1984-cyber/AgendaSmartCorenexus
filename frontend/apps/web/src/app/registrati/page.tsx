import Link from "next/link";
import { AuthShell } from "@/components/AuthShell";
import { RegisterForm } from "@/components/auth/RegisterForm";
import { linkCls } from "@/components/ui";

export const metadata = { title: "Registra il tuo studio", robots: { index: false, follow: false } };

export default function Page() {
  return (
    <AuthShell
      kicker="Nuovo studio"
      title="Registra il tuo studio"
      subtitle="Diventi il titolare e poi inviti i tuoi collaboratori."
      footer={<>Hai già un account? <Link href="/accedi" className={linkCls}>Accedi ›</Link></>}
    >
      <RegisterForm />
    </AuthShell>
  );
}
