import { FileText } from "lucide-react";
import type { RendererProps } from "../types";

export function PaFormRenderer({ canvas }: RendererProps) {
  const composed = canvas["pa.compose"] as { preview?: string; artifactId?: string } | undefined;
  if (!composed?.preview) {
    return (
      <div className="mx-auto max-w-[820px] px-8 py-10 text-[13.5px]" style={{ color: "var(--ink-3)" }}>
        No PA composed yet. Run pa.compose to draft the clinical justification.
      </div>
    );
  }
  return (
    <div className="mx-auto max-w-[820px] px-8 py-7">
      <div className="mb-3 flex items-center gap-2 text-[11px] font-semibold uppercase tracking-wider" style={{ color: "var(--ink-3)" }}>
        <FileText className="h-3.5 w-3.5" strokeWidth={1.5} />
        {composed.artifactId ?? "PA packet"}
      </div>
      <pre
        className="overflow-auto whitespace-pre-wrap rounded-md border p-4 text-[13px] leading-[1.55]"
        style={{
          background: "var(--surface-1)",
          borderColor: "var(--line-1)",
          color: "var(--ink-1)",
          fontFamily: "var(--font-sans)",
        }}
      >
        {composed.preview}
      </pre>
    </div>
  );
}
