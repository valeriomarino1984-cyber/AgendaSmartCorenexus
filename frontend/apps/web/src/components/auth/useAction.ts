"use client";

import { useState } from "react";
import { ApiError } from "@/lib/api";

/** Stato di un invio: in corso, errore (messaggio + codice), esito positivo. */
export function useAction() {
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<{ message: string; code: string } | null>(null);

  async function run<T>(fn: () => Promise<T>): Promise<T | undefined> {
    setPending(true);
    setError(null);
    try {
      return await fn();
    } catch (e) {
      const err = e instanceof ApiError ? e : new ApiError(0, "errore", "Si è verificato un errore.");
      setError({ message: err.message, code: err.code });
      return undefined;
    } finally {
      setPending(false);
    }
  }

  return { pending, error, setError, run };
}

/** Accetta solo percorsi interni (niente redirect verso altri siti). */
export function safeNext(value: string | null): string {
  return value && value.startsWith("/") && !value.startsWith("//") ? value : "/app";
}
