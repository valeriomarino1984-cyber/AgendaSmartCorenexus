"use client";

/** Controllo segmentato in stile iOS: l'indicatore scorre sotto l'opzione scelta. */
export function Segmented<T extends string>({
  options,
  value,
  onChange,
  label,
  size = "md",
  className = "",
}: {
  options: readonly (readonly [T, string])[];
  value: T;
  onChange: (v: T) => void;
  label: string;
  size?: "sm" | "md";
  className?: string;
}) {
  const i = Math.max(0, options.findIndex(([id]) => id === value));
  const n = options.length;
  return (
    <div role="radiogroup" aria-label={label} className={`relative grid rounded-[9px] bg-paper-2 p-[2px] ${className}`} style={{ gridTemplateColumns: `repeat(${n}, minmax(0, 1fr))` }}>
      <span
        aria-hidden
        className="absolute top-[2px] bottom-[2px] left-[2px] rounded-[7px] bg-thumb shadow-[0_3px_8px_rgb(0_0_0/0.12),0_3px_1px_rgb(0_0_0/0.04)] transition-transform duration-300 ease-[cubic-bezier(0.3,0.9,0.3,1)]"
        style={{ width: `calc((100% - 4px) / ${n})`, transform: `translateX(${i * 100}%)` }}
      />
      {options.map(([id, text]) => (
        <button
          key={id}
          type="button"
          role="radio"
          aria-checked={value === id}
          onClick={() => onChange(id)}
          className={`relative z-10 truncate px-2 font-medium transition-colors ${size === "sm" ? "py-1 text-[13px]" : "py-1.5 text-[15px]"} ${
            value === id ? "text-ink" : "text-ink-2"
          }`}
        >
          {text}
        </button>
      ))}
    </div>
  );
}
