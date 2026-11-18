"use client";

import { useEffect, useRef, useState } from "react";

/**
 * Parole che scorrono come un contatore: la vecchia esce verso l'alto, la nuova entra dal basso
 * in dissolvenza. La larghezza segue la parola corrente (niente buchi tra "Per" e la parola).
 * Con "riduci movimento" resta ferma sulla prima parola.
 */
export function RotatingWords({ words, interval = 2200, label }: { words: string[]; interval?: number; label: string }) {
  const [index, setIndex] = useState(0);
  const [widths, setWidths] = useState<number[]>([]);
  const refs = useRef<(HTMLSpanElement | null)[]>([]);

  useEffect(() => {
    if (window.matchMedia?.("(prefers-reduced-motion: reduce)").matches) return;
    // Parte dopo l'apertura della pagina (logo iniziale e comparsa del titolo).
    let timer: ReturnType<typeof setInterval> | undefined;
    const start = setTimeout(() => {
      timer = setInterval(() => setIndex((i) => (i + 1) % words.length), interval);
    }, 1800);
    return () => {
      clearTimeout(start);
      if (timer) clearInterval(timer);
    };
  }, [words.length, interval]);

  useEffect(() => {
    const measure = () => setWidths(refs.current.map((el) => el?.offsetWidth ?? 0));
    const ro = new ResizeObserver(measure);
    refs.current.forEach((el) => el && ro.observe(el));
    return () => ro.disconnect();
  }, [words]);

  const width = widths[index];
  return (
    <span className="rotating-words" aria-label={label} style={width ? { width } : undefined}>
      {/* Segnaposto invisibile: dà la larghezza giusta prima della prima misura. */}
      {!width && <span className="invisible whitespace-nowrap">{words[0]}</span>}
      {words.map((w, i) => {
        const offset = (i - index + words.length) % words.length;
        const state = offset === 0 ? "now" : offset === words.length - 1 ? "past" : "next";
        return (
          <span key={w} ref={(el) => { refs.current[i] = el; }} aria-hidden data-state={state} className="rotating-word">
            {w}
          </span>
        );
      })}
    </span>
  );
}
