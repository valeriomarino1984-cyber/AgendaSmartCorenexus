import { StudioSettings } from "@/components/studio/StudioSettings";

// L'area riservata si mostra solo dopo aver verificato la sessione nel browser: non è
// pre-renderizzabile sul server, quindi si esclude dalla validazione "instant navigation"
// (docs Next.js: instant-navigation → Opting out).
export const instant = false;

export const metadata = { title: "Impostazioni" };

export default function Page() {
  return <StudioSettings />;
}
