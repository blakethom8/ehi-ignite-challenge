import type { RendererProps } from "../types";

export function TrialDetailRenderer({ canvas }: RendererProps) {
  const detail = canvas["trial.fetch_detail"] as { study?: Record<string, unknown> } | undefined;
  if (!detail?.study) {
    return (
      <div className="mx-auto max-w-[820px] px-8 py-10 text-[13.5px]" style={{ color: "var(--ink-3)" }}>
        No trial detail loaded. Click a candidate in the board to fetch.
      </div>
    );
  }
  return (
    <div className="mx-auto max-w-[820px] px-8 py-7 text-[13.5px]" style={{ color: "var(--ink-2)" }}>
      <pre
        className="overflow-auto rounded-md border p-4"
        style={{
          background: "var(--surface-1)",
          borderColor: "var(--line-1)",
          color: "var(--ink-1)",
          fontFamily: "var(--font-mono)",
          fontSize: 12,
        }}
      >
        {JSON.stringify(detail.study, null, 2)}
      </pre>
    </div>
  );
}
