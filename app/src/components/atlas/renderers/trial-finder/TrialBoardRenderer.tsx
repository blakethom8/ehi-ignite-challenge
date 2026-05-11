import { Beaker, CheckCircle2, MapPin } from "lucide-react";
import type { RendererProps } from "../types";

type Study = {
  nctId: string;
  title: string;
  phase: string;
  site: string;
  distanceMi: number;
  fit: number;
  biomarkerMatch: boolean | null;
};

/** Renders the structured study list produced by trial.search. */
export function TrialBoardRenderer({ canvas }: RendererProps) {
  const search = (canvas["trial.search"] ?? canvas["candidate-board"]) as
    | { studies?: Study[] }
    | undefined;
  const studies = search?.studies ?? [];

  if (studies.length === 0) {
    return (
      <div className="mx-auto max-w-[820px] px-8 py-10 text-[13.5px]" style={{ color: "var(--ink-3)" }}>
        No candidate trials yet. Run the shortlist workflow to populate this board.
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-[920px] px-8 py-7">
      <div className="mb-4 flex items-center gap-2 text-[11px] font-semibold uppercase tracking-wider" style={{ color: "var(--ink-3)" }}>
        <Beaker className="h-3.5 w-3.5" strokeWidth={1.5} />
        Candidate board · {studies.length} trials
      </div>
      <div className="grid grid-cols-1 gap-3">
        {studies.map((s) => (
          <div
            key={s.nctId}
            className="rounded-md border p-4"
            style={{ background: "var(--surface-1)", borderColor: "var(--line-1)" }}
          >
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0">
                <div className="text-[14px] font-semibold" style={{ color: "var(--ink-1)" }}>
                  {s.nctId}
                </div>
                <div className="mt-0.5 text-[12.5px] leading-snug" style={{ color: "var(--ink-2)" }}>
                  {s.title}
                </div>
              </div>
              <FitMeter value={s.fit} />
            </div>
            <div className="mt-3 flex flex-wrap items-center gap-3 text-[11.5px]" style={{ color: "var(--ink-3)" }}>
              <span className="rounded-[3px] border px-1.5 py-0.5" style={{ borderColor: "var(--line-1)" }}>
                {s.phase}
              </span>
              <span className="inline-flex items-center gap-1">
                <MapPin className="h-3 w-3" strokeWidth={1.5} />
                {s.site} · {s.distanceMi} mi
              </span>
              {s.biomarkerMatch && (
                <span className="inline-flex items-center gap-1" style={{ color: "var(--ok)" }}>
                  <CheckCircle2 className="h-3 w-3" strokeWidth={1.5} />
                  Biomarker match
                </span>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function FitMeter({ value }: { value: number }) {
  const pct = Math.round(value * 100);
  const tone = value >= 0.85 ? "var(--ok)" : value >= 0.7 ? "var(--warn)" : "var(--ink-3)";
  return (
    <div className="text-right">
      <div className="text-[18px] font-semibold" style={{ color: tone, fontFamily: "var(--font-mono)" }}>
        {pct}
      </div>
      <div className="text-[10px] font-semibold uppercase tracking-wider" style={{ color: "var(--ink-3)" }}>
        fit
      </div>
    </div>
  );
}
