"use client";

import { Check } from "lucide-react";
import { PALETTE } from "@/lib/catalog";

/** Scelta del colore tra quelli di sistema (radiogroup accessibile da tastiera). */
export function ColorPicker({ value, onChange, label = "Colore" }: { value: string; onChange: (v: string) => void; label?: string }) {
  return (
    <div className="space-y-1.5">
      <p className="px-1 t-footnote font-medium text-ink-3">{label}</p>
      <div role="radiogroup" aria-label={label} className="flex flex-wrap gap-2">
        {PALETTE.map((c) => (
          <button
            key={c}
            type="button"
            role="radio"
            aria-checked={value === c}
            aria-label={c}
            onClick={() => onChange(c)}
            className="grid h-8 w-8 place-items-center rounded-full ring-offset-2 ring-offset-card transition focus-visible:ring-2 focus-visible:ring-accent"
            style={{ background: c }}
          >
            {value === c && <Check className="h-4 w-4 text-white" strokeWidth={3} />}
          </button>
        ))}
      </div>
    </div>
  );
}
