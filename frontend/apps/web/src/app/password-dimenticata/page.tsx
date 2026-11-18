import Link from "next/link";
import { AuthShell } from "@/components/AuthShell";
import { ForgotPassword } from "@/components/auth/TokenForms";
import { linkCls } from "@/components/ui";

export const metadata = { title: "Password dimenticata" };

export default function Page() {
  return (
    <AuthShell
      title="Password dimenticata"
      subtitle="Ti inviamo un link per sceglierne una nuova."
      footer={<Link href="/accedi" className={linkCls}>Torna all&apos;accesso ›</Link>}
    >
      <ForgotPassword />
    </AuthShell>
  );
}
