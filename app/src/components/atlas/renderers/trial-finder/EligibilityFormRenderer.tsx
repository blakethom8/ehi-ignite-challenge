import type { RendererProps } from "../types";

export function EligibilityFormRenderer({ canvas }: RendererProps) {
  const score = canvas["trial.score_fit"] as
    | { fit?: number; rationale?: Record<string, boolean>; nctId?: string }
    | undefined;
  if (!score) {
    return (
      <div className="mx-auto max-w-[820px] px-8 py-10 text-[13.5px]" style={{ color: "var(--ink-3)" }}>
        No eligibility check run yet. Run trial.score_fit on a candidate.
      </div>
    );
  }
  const checks = score.rationale ?? {};
  return (
    <div className="mx-auto max-w-[760px] px-8 py-7">
      <h2 className="text-[18px] font-semibold" style={{ color: "var(--ink-1)" }}>
        Eligibility — {score.nctId ?? "candidate"}
      </h2>
      <div className="mt-1 text-[12px]" style={{ color: "var(--ink-3)" }}>
        Computed fit: {(score.fit ?? 0).toFixed(2)}
      </div>
      <div className="mt-5 grid grid-cols-1 gap-2">
        {Object.entries(checks).map(([k, ok]) => (
          <div
            key={k}
            className="flex items-center justify-between rounded border px-3 py-2 text-[13px]"
            style={{
              background: "var(--surface-1)",
              borderColor: "var(--line-1)",
              color: "var(--ink-2)",
            }}
          >
            <span>{k}</span>
            <span style={{ color: ok ? "var(--ok)" : "var(--warn)" }}>
              {ok ? "✓ pass" : "✗ fail"}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
