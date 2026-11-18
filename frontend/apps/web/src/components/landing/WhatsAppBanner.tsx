import { MessageCircle } from "lucide-react";
import QRCode from "qrcode";
import { PHONE_DISPLAY, WHATSAPP_URL } from "@/lib/contacts";

/** Riquadro "Scrivici su WhatsApp" con QR da inquadrare e pulsante (come in Presenze). Il QR si genera alla build. */
export async function WhatsAppBanner() {
  const svg = await QRCode.toString(WHATSAPP_URL, { type: "svg", margin: 0, color: { dark: "#000000", light: "#ffffff" } });
  return (
    <div className="mx-auto max-w-[880px] rounded-[28px] bg-card px-6 py-10 text-center shadow-card sm:px-10">
      <h2 className="text-[28px] leading-tight font-semibold tracking-tight sm:text-[32px]">Scrivici direttamente su WhatsApp</h2>
      <p className="mt-2 text-[17px] text-ink-2">Risponde una persona del nostro team, senza bot e senza centralino.</p>
      <div className="mt-8 flex flex-col items-center justify-center gap-8 md:flex-row md:gap-14">
        <div className="flex flex-col items-center gap-2">
          <a
            href={WHATSAPP_URL}
            target="_blank"
            rel="noopener noreferrer"
            aria-label="Apri la chat WhatsApp"
            className="block h-40 w-40 rounded-[20px] bg-white p-3 ring-1 ring-sys-green/30 transition hover:ring-sys-green/60"
            dangerouslySetInnerHTML={{ __html: svg.replace("<svg", '<svg width="100%" height="100%"') }}
          />
          <p className="t-footnote text-ink-3">Inquadra il QR con la fotocamera</p>
        </div>
        <div className="flex flex-col items-center gap-3">
          <a
            href={WHATSAPP_URL}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex h-14 items-center gap-3 rounded-full bg-[#25d366] px-8 text-[17px] font-semibold text-white shadow-[0_8px_24px_-8px_rgba(37,211,102,0.6)] transition hover:bg-[#1fbd5a] active:scale-[0.98]"
          >
            <MessageCircle className="h-6 w-6" />
            Scrivi su WhatsApp
          </a>
          <p className="num t-subhead text-ink-3">{PHONE_DISPLAY}</p>
        </div>
      </div>
    </div>
  );
}
