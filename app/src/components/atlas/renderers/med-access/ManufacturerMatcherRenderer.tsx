import { Pill } from "lucide-react";
import type { RendererProps } from "../types";

type Program = {
  id: string;
  manufacturer: string;
  drug: string;
  incomeBandMax: number;
  diagnosisFilter: string[];
};

export function ManufacturerMatcherRenderer({ canvas }: RendererProps) {
  const match = canvas["pap.match"] as { matches?: Program[] } | undefined;
  const matches = match?.matches ?? [];
  if (matches.length === 0) {
    return (
      <div className="mx-auto max-w-[820px] px-8 py-10 text-[13.5px]" style={{ color: "var(--ink-3)" }}>
        No manufacturer programs matched yet. Run pap.match to surface options.
      </div>
    );
  }
  return (
    <div className="mx-auto max-w-[820px] px-8 py-7">
      <h2 className="mb-3 text-[16.5px] font-semibold" style={{ color: "var(--ink-1)" }}>
        Manufacturer programs
      </h2>
      <div className="grid grid-cols-1 gap-2">
        {matches.map((p) => (
          <div
            key={p.id}
            className="flex items-center gap-3 rounded-md border p-3"
            style={{ background: "var(--surface-1)", borderColor: "var(--line-1)" }}
          >
            <Pill className="h-4 w-4" strokeWidth={1.5} style={{ color: "var(--mod-meds, #0f766e)" }} />
            <div className="flex-1 min-w-0">
              <div className="text-[13.5px] font-semibold" style={{ color: "var(--ink-1)" }}>
                {p.manufacturer} · {p.drug}
              </div>
              <div className="text-[12px]" style={{ color: "var(--ink-3)" }}>
                Income band ≤ ${p.incomeBandMax}k · Eligible Dx: {p.diagnosisFilter.join(", ")}
              </div>
            </div>
            <code className="text-[11px]" style={{ color: "var(--ink-3)", fontFamily: "var(--font-mono)" }}>
              {p.id}
            </code>
          </div>
        ))}
      </div>
    </div>
  );
}
