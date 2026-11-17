"use client";

import { useState } from "react";
import { Segmented } from "@/components/Segmented";

export function SegmentedDemo() {
  const [view, setView] = useState<"giorno" | "settimana" | "mese">("settimana");
  return (
    <Segmented
      label="Vista agenda"
      value={view}
      onChange={setView}
      options={[
        ["giorno", "Giorno"],
        ["settimana", "Settimana"],
        ["mese", "Mese"],
      ]}
      className="w-72"
    />
  );
}
