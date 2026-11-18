import { PlatformApp } from "@/components/platform/PlatformApp";

// Area riservata al team CoreNexus: tutto si carica nel browser dopo la verifica della sessione.
export const instant = false;

export const metadata = { title: "Piattaforma CoreNexus", robots: { index: false, follow: false } };

export default function Page() {
  return <PlatformApp />;
}
