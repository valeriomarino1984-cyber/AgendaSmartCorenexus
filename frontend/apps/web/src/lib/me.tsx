"use client";

import { createContext, useContext } from "react";
import type { Me } from "./api";

export const MeContext = createContext<{ me: Me; refresh: () => Promise<void> } | null>(null);

export function useMe() {
  const value = useContext(MeContext);
  if (!value) throw new Error("useMe va usato dentro l'area riservata");
  return value;
}
