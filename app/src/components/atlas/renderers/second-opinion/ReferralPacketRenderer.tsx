import { FileText, ShieldCheck } from "lucide-react";
import type { RendererProps } from "../types";

export function ReferralPacketRenderer({ canvas }: RendererProps) {
  const composed = canvas["referral.compose_packet"] as
    | { preview?: string; artifactId?: string }
    | undefined;
  const redactions = canvas["referral.apply_redactions"] as
    | { redactionPreset?: string; summary?: string; scope?: string[] }
    | undefined;
  if (!composed?.preview) {
    return (
      <div className="mx-auto max-w-[820px] px-8 py-10 text-[13.5px]" style={{ color: "var(--ink-3)" }}>
        No referral packet drafted yet. Run referral.compose_packet to build it.
      </div>
    );
  }
  return (
    <div className="mx-auto max-w-[820px] px-8 py-7">
      <div className="mb-3 flex items-center gap-2 text-[11px] font-semibold uppercase tracking-wider" style={{ color: "var(--ink-3)" }}>
        <FileText className="h-3.5 w-3.5" strokeWidth={1.5} />
        {composed.artifactId ?? "Referral packet"}
      </div>
      {redactions && (
        <div
          className="mb-3 flex items-center gap-2 rounded-md border px-3 py-2 text-[12px]"
          style={{
            background: "rgba(34,197,94,0.06)",
            borderColor: "var(--ok, #22c55e)",
            color: "var(--ink-2)",
          }}
        >
          <ShieldCheck className="h-3.5 w-3.5" strokeWidth={1.5} style={{ color: "var(--ok)" }} />
          {redactions.summary ?? `Redactions applied: ${redactions.redactionPreset}`}
        </div>
      )}
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
