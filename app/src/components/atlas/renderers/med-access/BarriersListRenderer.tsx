import { AlertTriangle } from "lucide-react";
import type { RendererProps } from "../types";

type Barrier = { drug: string; type: string; remedy: string; supportingDx: string[] };

export function BarriersListRenderer({ canvas }: RendererProps) {
  const out = canvas["med.identify_barriers"] as { barriers?: Barrier[] } | undefined;
  const barriers = out?.barriers ?? [];
  if (barriers.length === 0) {
    return (
      <div className="mx-auto max-w-[820px] px-8 py-10 text-[13.5px]" style={{ color: "var(--ink-3)" }}>
        No barriers identified yet. Run med.identify_barriers to populate.
      </div>
    );
  }
  return (
    <div className="mx-auto max-w-[820px] px-8 py-7">
      <h2 className="mb-3 text-[16.5px] font-semibold" style={{ color: "var(--ink-1)" }}>
        Access barriers
      </h2>
      <div className="grid grid-cols-1 gap-2">
        {barriers.map((b, i) => (
          <div
            key={i}
            className="rounded-md border p-3"
            style={{ background: "var(--surface-1)", borderColor: "var(--line-1)" }}
          >
            <div className="flex items-center gap-2 text-[13.5px] font-semibold" style={{ color: "var(--ink-1)" }}>
              <AlertTriangle className="h-3.5 w-3.5" strokeWidth={1.5} style={{ color: "var(--warn)" }} />
              {b.drug}
            </div>
            <div className="mt-1 text-[12.5px]" style={{ color: "var(--ink-2)" }}>
              <strong>Type:</strong> {b.type}
            </div>
            <div className="mt-0.5 text-[12.5px]" style={{ color: "var(--ink-2)" }}>
              <strong>Remedy:</strong> {b.remedy}
            </div>
            {b.supportingDx.length > 0 && (
              <div className="mt-0.5 text-[12.5px]" style={{ color: "var(--ink-3)" }}>
                Supporting Dx: {b.supportingDx.join(", ")}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
