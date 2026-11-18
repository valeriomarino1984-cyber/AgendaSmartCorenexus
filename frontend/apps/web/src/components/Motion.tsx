"use client";

import { useEffect } from "react";

/**
 * Comparsa allo scorrimento (dalla home di Presenze): titoli e blocchi entrano in dissolvenza dal basso,
 * i figli dei contenitori con data-stagger uno dopo l'altro; data-spot attiva l'alone che segue il puntatore.
 * Parte dopo l'idratazione di React (gli attributi aggiunti non creano differenze con l'HTML del server).
 * Se manca IntersectionObserver o è attivo "riduci movimento" non nasconde nulla.
 */
export function Motion() {
  useEffect(() => {
    const mq = window.matchMedia?.("(prefers-reduced-motion: reduce)");
    if (!("IntersectionObserver" in window) || mq?.matches) return;
    const root = document.querySelector("main");
    if (!root) return;
    const targets: [HTMLElement, number][] = [];
    root.querySelectorAll<HTMLElement>("main > section:not(:first-child)").forEach((s) =>
      s.querySelectorAll<HTMLElement>("h2, h2 + p").forEach((el) => targets.push([el, 0])),
    );
    root.querySelectorAll<HTMLElement>("[data-reveal]").forEach((el) => targets.push([el, 0]));
    root.querySelectorAll<HTMLElement>("[data-stagger]").forEach((c) =>
      Array.from(c.children).forEach((el, i) => targets.push([el as HTMLElement, Math.min(i, 8) * 90])),
    );
    const viewportBottom = window.innerHeight;
    const io = new IntersectionObserver(
      (entries) =>
        entries.forEach((e) => {
          if (e.isIntersecting) {
            e.target.setAttribute("data-in", "");
            io.unobserve(e.target);
          }
        }),
      { rootMargin: "0px 0px -8% 0px", threshold: 0.12 },
    );
    for (const [el, delay] of targets) {
      if (el.hasAttribute("data-in")) continue;
      if (!el.hasAttribute("data-r")) {
        // Ciò che è già visibile all'apertura non si nasconde (niente lampeggio).
        if (el.getBoundingClientRect().top < viewportBottom) continue;
        el.setAttribute("data-r", "");
        if (delay) el.style.setProperty("--rd", `${delay}ms`);
      }
      // Anche se l'effetto riparte (sviluppo, navigazione) gli elementi ancora nascosti si osservano di nuovo.
      io.observe(el);
    }
    document.documentElement.setAttribute("data-motion", "");
    const spots = Array.from(root.querySelectorAll<HTMLElement>("[data-spot]"));
    const onMove = (ev: PointerEvent) => {
      const el = ev.currentTarget as HTMLElement;
      const r = el.getBoundingClientRect();
      el.style.setProperty("--mx", `${ev.clientX - r.left}px`);
      el.style.setProperty("--my", `${ev.clientY - r.top}px`);
    };
    spots.forEach((el) => el.addEventListener("pointermove", onMove));
    const fallback = setTimeout(() => targets.forEach(([el]) => el.setAttribute("data-in", "")), 12000);
    return () => {
      io.disconnect();
      clearTimeout(fallback);
      spots.forEach((el) => el.removeEventListener("pointermove", onMove));
    };
  }, []);
  return null;
}
