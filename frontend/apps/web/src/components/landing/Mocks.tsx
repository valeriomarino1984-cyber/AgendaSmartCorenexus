import type { CSSProperties } from "react";
import { Check, ChevronLeft, Video } from "lucide-react";
import { LogoMark } from "../Logo";
import { ServiceChip } from "../ui";

/*
 * Illustrazioni della home: NON sono dati reali. Mostrano l'aspetto dell'agenda e del promemoria WhatsApp (in arrivo).
 */

const DAYS = ["Lun 16", "Mar 17", "Mer 18", "Gio 19", "Ven 20"];
const BLOCKS: { day: number; top: number; h: number; color: string; time: string; title: string; sub: string }[] = [
  { day: 0, top: 4, h: 27, color: "#0071e3", time: "09:00", title: "Prima visita", sub: "Giulia F." },
  { day: 0, top: 44, h: 27, color: "#30b0c7", time: "11:30", title: "Controllo", sub: "Marco C." },
  { day: 1, top: 14, h: 27, color: "#5856d6", time: "09:45", title: "Seduta", sub: "Sara G." },
  { day: 2, top: 30, h: 27, color: "#0071e3", time: "10:30", title: "Prima visita", sub: "Luca M." },
  { day: 3, top: 6, h: 27, color: "#30b0c7", time: "09:00", title: "Controllo", sub: "Elena R." },
  { day: 3, top: 58, h: 27, color: "#ff9500", time: "12:00", title: "Consulenza", sub: "Paolo E." },
  { day: 4, top: 20, h: 27, color: "#5856d6", time: "10:00", title: "Seduta", sub: "Chiara L." },
];

export function LaptopMock() {
  return (
    <div className="relative mx-auto w-full max-w-[880px]">
      <div className="rounded-[22px] bg-[#1d1d1f] p-[10px] shadow-[0_40px_80px_-30px_rgb(0_0_0/0.45)]">
        <div className="overflow-hidden rounded-[13px] bg-paper">
          <div className="flex h-7 items-center gap-1.5 bg-paper-2 px-3">
            <span className="h-2.5 w-2.5 rounded-full bg-[#ff5f57]" />
            <span className="h-2.5 w-2.5 rounded-full bg-[#febc2e]" />
            <span className="h-2.5 w-2.5 rounded-full bg-[#28c840]" />
          </div>
          <div className="grid grid-cols-1 text-left sm:grid-cols-[150px_1fr]">
            <div className="vibrant hidden space-y-1 border-r border-ink/[0.08] p-3 sm:block">
              <div className="mb-3 flex items-center gap-1.5">
                <LogoMark className="h-5 w-5" />
                <span className="t-footnote font-semibold">Agenda</span>
              </div>
              {["Dashboard", "Agenda", "Clienti", "Prestazioni", "Disponibilità"].map((l) => (
                <div key={l} className={`rounded-[6px] px-2 py-1 t-caption ${l === "Agenda" ? "bg-accent text-white" : "text-ink"}`}>
                  {l}
                </div>
              ))}
            </div>
            <div className="p-3 sm:p-4">
              <p className="t-caption font-semibold text-ink-3">Novembre 2026</p>
              <p className="mb-3 t-title3">Settimana</p>
              <div className="grid grid-cols-5 gap-1.5">
                {DAYS.map((d, i) => (
                  <div key={d} className="min-w-0">
                    <p className={`mb-1 text-center t-caption font-semibold ${i === 1 ? "text-accent" : "text-ink-3"}`}>{d}</p>
                    <div className="relative h-[230px] rounded-[8px] bg-card shadow-card">
                      {BLOCKS.filter((b) => b.day === i).map((b) => (
                        <div key={b.time + b.title} className="absolute inset-x-1 overflow-hidden" style={{ top: `${b.top}%`, height: `${b.h}%` }}>
                          <ServiceChip color={b.color} time={b.time} title={b.title} subtitle={b.sub} />
                        </div>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      </div>
      <div className="mx-auto h-3 w-[104%] -translate-x-[2%] rounded-b-[14px] bg-gradient-to-b from-[#d2d2d7] to-[#a1a1a6] dark:from-[#48484a] dark:to-[#2c2c2e]" />
    </div>
  );
}

const delay = (s: string) => ({ "--bd": s }) as CSSProperties;

/** Telefono con il promemoria WhatsApp e i tre pulsanti del template. */
export function PhoneMock() {
  return (
    <div className="w-[230px] rounded-[38px] bg-[#1d1d1f] p-[8px] text-left shadow-[0_30px_60px_-20px_rgb(0_0_0/0.5)]">
      <div className="overflow-hidden rounded-[30px] bg-[#efeae2] dark:bg-[#0b141a]">
        <div className="flex items-center gap-2 bg-[#f6f6f6] px-3 pt-6 pb-2 text-[#1d1d1f] dark:bg-[#1f2c33] dark:text-[#e9edef]">
          <ChevronLeft className="h-4 w-4 text-[#0a84ff]" />
          <LogoMark className="h-7 w-7" />
          <div className="min-w-0 flex-1 leading-tight">
            <p className="truncate text-[12px] font-semibold">Studio Esempio</p>
            <p className="text-[9px] opacity-60">account aziendale</p>
          </div>
          <Video className="h-4 w-4 text-[#0a84ff]" />
        </div>
        <div className="space-y-2 px-2.5 pt-3 pb-5">
          <div className="bubble-in max-w-[92%] rounded-[10px] rounded-tl-[3px] bg-white p-2 text-[11px] leading-snug text-[#111b21] shadow-sm dark:bg-[#202c33] dark:text-[#e9edef]">
            Buongiorno Giulia, le ricordiamo che domani alle ore <b>09:00</b> ha un appuntamento presso Studio Esempio.
            <p className="mt-1 text-right text-[8.5px] opacity-50">10:02</p>
            <div className="-mx-2 mt-1.5 divide-y divide-black/10 border-t border-black/10 text-center text-[11px] font-medium text-[#027eb5] dark:divide-white/10 dark:border-white/10 dark:text-[#53bdeb]">
              <p className="py-1.5">Conferma</p>
              <p className="py-1.5">Sposta</p>
              <p className="py-1.5">Disdici</p>
            </div>
          </div>
          <div
            className="bubble-in ml-auto w-fit max-w-[60%] rounded-[10px] rounded-tr-[3px] bg-[#d9fdd3] px-2 py-1.5 text-[11px] text-[#111b21] dark:bg-[#005c4b] dark:text-[#e9edef]"
            style={delay("0.9s")}
          >
            Conferma
            <span className="ml-1.5 inline-flex items-center gap-0.5 text-[8.5px] opacity-60">
              10:03 <Check className="h-2.5 w-2.5" />
            </span>
          </div>
          <div
            className="bubble-in max-w-[85%] rounded-[10px] rounded-tl-[3px] bg-white p-2 text-[11px] text-[#111b21] shadow-sm dark:bg-[#202c33] dark:text-[#e9edef]"
            style={delay("1.6s")}
          >
            Grazie Giulia, il suo appuntamento è stato confermato.
          </div>
        </div>
      </div>
    </div>
  );
}
