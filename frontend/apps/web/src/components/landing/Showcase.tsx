import type { CSSProperties } from "react";
import { Mic, MonitorUp, MousePointer2, PhoneOff, Video } from "lucide-react";
import { LogoMark } from "../Logo";
import { ServiceChip } from "../ui";

/*
 * Illustrazioni animate della home. NON sono dati reali: mostrano come funzionano agenda,
 * orari liberi e visite online. Le animazioni sono solo CSS (globals.css, sezione "Vetrina")
 * e si fermano con "riduci movimento".
 */

const d = (s: string) => ({ "--d": s }) as CSSProperties;

/** Videochiamata: due riquadri, il link univoco che si "scrive" e i comandi. */
export function VideoCallMock() {
  return (
    <div className="relative mx-auto w-full max-w-[520px]">
      <div className="overflow-hidden rounded-[22px] bg-[#1c1c1e] p-3 shadow-[0_40px_80px_-30px_rgb(0_0_0/0.55)]">
        <div className="mb-3 flex items-center gap-2 px-1">
          <span className="h-2.5 w-2.5 rounded-full bg-[#ff5f57]" />
          <span className="h-2.5 w-2.5 rounded-full bg-[#febc2e]" />
          <span className="h-2.5 w-2.5 rounded-full bg-[#28c840]" />
          <span className="ml-2 flex min-w-0 flex-1 items-center gap-1.5 overflow-hidden rounded-full bg-white/10 px-3 py-1 text-[11px] text-white/70">
            <Video className="h-3 w-3 shrink-0" />
            <span className="type-link truncate font-mono">meet.jit.si/CN-q7XwP2mLr9ZtK4bVa8sNdY</span>
          </span>
        </div>
        <div className="grid grid-cols-2 gap-2.5">
          <div className="vc-tile relative aspect-[4/3] overflow-hidden rounded-[14px] bg-gradient-to-br from-[#5856d6] to-[#30b0c7]">
            <span className="vc-speaking absolute inset-0 rounded-[14px]" />
            <span className="absolute inset-0 grid place-items-center">
              <span className="grid h-16 w-16 place-items-center rounded-full bg-white/25 text-[22px] font-semibold text-white backdrop-blur">ER</span>
            </span>
            <span className="absolute bottom-2 left-2 rounded-full bg-black/40 px-2 py-0.5 text-[10px] text-white">Dott.ssa Rinaldi</span>
          </div>
          <div className="vc-tile relative aspect-[4/3] overflow-hidden rounded-[14px] bg-gradient-to-br from-[#ff9500] to-[#ff2d55]" style={d("0.25s")}>
            <span className="absolute inset-0 grid place-items-center">
              <span className="grid h-16 w-16 place-items-center rounded-full bg-white/25 text-[22px] font-semibold text-white backdrop-blur">GF</span>
            </span>
            <span className="absolute bottom-2 left-2 rounded-full bg-black/40 px-2 py-0.5 text-[10px] text-white">Giulia F.</span>
          </div>
        </div>
        <div className="mt-3 flex items-center justify-center gap-3">
          {[Mic, Video, MonitorUp].map((Icon, i) => (
            <span key={i} className="grid h-9 w-9 place-items-center rounded-full bg-white/12 text-white"><Icon className="h-4 w-4" /></span>
          ))}
          <span className="grid h-9 w-12 place-items-center rounded-full bg-[#ff3b30] text-white"><PhoneOff className="h-4 w-4" /></span>
        </div>
      </div>
      <div className="vc-badge absolute -top-4 right-2 flex items-center gap-2 rounded-full bg-card px-3 py-1.5 t-footnote font-semibold text-ink shadow-[0_10px_30px_-10px_rgb(0_0_0/0.35)] sm:-right-8">
        <span className="grid h-5 w-5 place-items-center rounded-full bg-go-fill text-[11px] text-white">✓</span>
        Link creato in automatico
      </div>
    </div>
  );
}

const COLS = ["Lun", "Mar", "Mer", "Gio", "Ven"];

/** Settimana con un appuntamento che viene trascinato da un giorno all'altro, in dissolvenza continua. */
export function DragAgendaMock() {
  return (
    <div className="relative mx-auto w-full max-w-[560px] rounded-[20px] bg-card p-4 shadow-card">
      <div className="mb-3 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <LogoMark className="h-6 w-6" />
          <span className="t-subhead font-semibold">Settimana</span>
        </div>
        <span className="rounded-full bg-paper-2 p-0.5 t-caption">
          {["Giorno", "Settimana", "Mese"].map((v) => (
            <span key={v} className={`inline-block rounded-full px-2.5 py-0.5 ${v === "Settimana" ? "bg-card font-semibold shadow-sm" : "text-ink-3"}`}>{v}</span>
          ))}
        </span>
      </div>
      <div className="grid grid-cols-5 gap-1.5">
        {COLS.map((c, i) => (
          <div key={c} className="min-w-0">
            <p className={`mb-1 text-center t-caption font-semibold ${i === 1 ? "text-accent" : "text-ink-3"}`}>{c}</p>
            <div className="relative h-[210px] rounded-[8px] bg-paper/70">
              <span className="absolute inset-x-0 top-[38%] border-t border-dashed border-rule" />
              {i === 0 && (
                <div className="absolute inset-x-1 top-[8%] h-[24%]"><ServiceChip color="#30b0c7" time="09:00" title="Controllo" subtitle="Marco C." /></div>
              )}
              {i === 2 && (
                <div className="absolute inset-x-1 top-[52%] h-[24%]"><ServiceChip color="#ff9500" time="11:30" title="Prima visita" subtitle="Sara G." /></div>
              )}
              {i === 4 && (
                <div className="absolute inset-x-1 top-[14%] h-[24%]"><ServiceChip color="#0071e3" time="09:30" title="Colloquio" subtitle="Luca M." /></div>
              )}
              {i === 1 && (
                // Trascinato verso giovedì: due colonne più in là (2 × larghezza + spazi) e un po' più in basso.
                <div className="drag-chip absolute inset-x-1 top-[22%] z-20 h-[24%]">
                  <ServiceChip color="#5856d6" time="10:00" title="Seduta" subtitle="Giulia F." />
                  <MousePointer2 className="absolute -right-2 -bottom-3 h-5 w-5 fill-ink text-white drop-shadow" />
                </div>
              )}
              {i === 3 && <div className="drop-target absolute inset-x-1 top-[40%] h-[24%] rounded-[8px] border-2 border-dashed border-accent/60" />}
            </div>
          </div>
        ))}
      </div>
      <p className="drag-toast absolute -bottom-4 left-1/2 -translate-x-1/2 whitespace-nowrap rounded-full bg-ink px-3 py-1.5 t-footnote font-medium text-canvas shadow-lg">
        Spostato a gio alle 11:00
      </p>
    </div>
  );
}

const SLOTS = ["09:00", "09:15", "09:30", "10:30", "10:45", "11:00", "11:15", "12:00", "12:15"];

/** Orari liberi proposti che compaiono uno dopo l'altro; quello scelto si accende. */
export function SlotsMock() {
  return (
    <div className="mx-auto w-full max-w-[360px] rounded-[20px] bg-card p-5 shadow-card">
      <p className="t-footnote font-medium text-ink-3">Orari liberi · lunedì 23 novembre</p>
      <div className="mt-3 flex flex-wrap gap-1.5">
        {SLOTS.map((t, i) => (
          <span key={t} data-r-child className={`slot-pop num rounded-full px-3 py-1 t-footnote font-medium ${t === "10:30" ? "slot-pick" : "bg-paper-2 text-ink"}`} style={d(`${i * 70}ms`)}>
            {t}
          </span>
        ))}
      </div>
      <div className="mt-4 rounded-[12px] bg-accent/10 p-3 t-footnote text-accent">
        <b>Seduta di fisioterapia</b> · 45 min + 10 min di preparazione. Gli orari già occupati non compaiono.
      </div>
    </div>
  );
}
