import { Suspense } from "react";
import { PlatformInvite } from "@/components/platform/PlatformInvite";
import { PlatformShell } from "@/components/platform/PlatformShell";

export const instant = false;

export const metadata = { title: "Configura l'accesso · Piattaforma", robots: { index: false, follow: false } };

export default function Page() {
  return (
    <PlatformShell>
      <Suspense fallback={null}>
        <PlatformInvite />
      </Suspense>
    </PlatformShell>
  );
}
