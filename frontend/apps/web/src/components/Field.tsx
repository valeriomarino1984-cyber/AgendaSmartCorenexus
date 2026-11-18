"use client";

import { cloneElement, isValidElement, useId, type ReactElement, type ReactNode } from "react";

/**
 * Campo di un modulo: etichetta collegata al controllo (htmlFor) e suggerimento come descrizione
 * (aria-describedby), così i lettori di schermo annunciano "Password", non anche il suggerimento.
 */
export function Field({ label, children, hint }: { label: string; children: ReactNode; hint?: string }) {
  const autoId = useId();
  const child = isValidElement(children) ? (children as ReactElement<{ id?: string }>) : null;
  const id = child?.props.id ?? autoId;
  const hintId = `${id}-hint`;
  return (
    <div className="space-y-1.5">
      <label htmlFor={id} className="block px-1 t-footnote font-medium text-ink-3">
        {label}
      </label>
      {child ? cloneElement(child as ReactElement<Record<string, unknown>>, { id, "aria-describedby": hint ? hintId : undefined }) : children}
      {hint && (
        <span id={hintId} className="block px-1 t-caption text-ink-3">
          {hint}
        </span>
      )}
    </div>
  );
}
