import { useMemo, useState } from "react";
import { CheckCircle, ListChecks, Stethoscope, Target } from "lucide-react";
import type { RankedConditionItem } from "../../../../types";

interface BriefPanelProps {
  patientName: string;
  rankedActive: RankedConditionItem[];
  isStarting: boolean;
  onStart: (anchors: AnchorChoice[]) => void;
}

export interface AnchorChoice {
  resource_id: string;
  display: string;
  risk_category: string;
  clinical_status: string;
}

/**
 * Pre-run brief: shows the chart-derived anchors the agent will use, lets
 * the clinician toggle them, and starts the run. The "what the agent sees"
 * surface — see §3.1 Act 1 in SKILL-AGENT-WORKSPACE.md.
 */
export function BriefPanel({
  patientName,
  rankedActive,
  isStarting,
  onStart,
}: BriefPanelProps) {
  const eligible = useMemo(
    () =>
      rankedActive.filter(
        (c) => c.is_active && c.risk_category !== "OTHER"
      ),
    [rankedActive]
  );
  const [selected, setSelected] = useState<Set<string>>(
    () => new Set(eligible.slice(0, 3).map((c) => c.condition_id))
  );

  const toggle = (id: string) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const anchorPayload: AnchorChoice[] = Array.from(selected).flatMap((id) => {
    const c = rankedActive.find((x) => x.condition_id === id);
    if (!c) return [];
    return [
      {
        resource_id: c.condition_id,
        display: c.display,
        risk_category: c.risk_category,
        clinical_status: c.clinical_status,
      },
    ];
  });

  const start = () => {
    if (!anchorPayload.length || isStarting) return;
    onStart(anchorPayload);
  };

  return (
    <div className="space-y-4">
      <section className="rounded-2xl bg-[#eef1ff] p-5 shadow-[rgb(199_208_250)_0px_0px_0px_1px]">
        <div className="flex items-center gap-2">
          <p className="text-[10px] font-semibold uppercase tracking-wider text-[#5b76fe]">
            Trial finder
          </p>
        </div>
        <h1 className="mt-1 text-2xl font-semibold text-[#1c1c1e]">
          {patientName}
        </h1>
        <p className="mt-2 text-sm leading-6 text-[#3a4ca8]">
          The agent will read the anchors below, query ClinicalTrials.gov,
          parse inclusion criteria against the chart, and produce a citation-grounded
          shortlist. You can pause it at any escalation gate.
        </p>
      </section>

      <section className="rounded-2xl bg-white p-5 shadow-[rgb(224_226_232)_0px_0px_0px_1px]">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Stethoscope size={16} className="text-[#5b76fe]" />
            <h2 className="text-sm font-semibold text-[#1c1c1e]">
              Anchor conditions
            </h2>
          </div>
          <span className="text-[11px] text-[#a5a8b5]">
            {eligible.length} eligible · {selected.size} selected
          </span>
        </div>
        <p className="mt-2 text-xs leading-5 text-[#555a6a]">
          Active conditions with a known body system. The agent uses each
          selected anchor to seed a CT.gov search; deselect any you don't want
          searched.
        </p>

        {eligible.length === 0 ? (
          <div className="mt-3 rounded-xl border border-dashed border-[#e9eaef] p-4 text-xs text-[#a5a8b5]">
            No anchor conditions found. The agent will escalate immediately —
            you can confirm or supply a target condition.
          </div>
        ) : (
          <ul className="mt-3 space-y-2">
            {eligible.map((c) => {
              const checked = selected.has(c.condition_id);
              return (
                <li
                  key={c.condition_id}
                  className={`rounded-xl border p-3 ${
                    checked
                      ? "border-[#5b76fe] bg-[#eef1ff]"
                      : "border-[#e9eaef] bg-white"
                  }`}
                >
                  <label className="flex items-start gap-3">
                    <input
                      type="checkbox"
                      checked={checked}
                      onChange={() => toggle(c.condition_id)}
                      className="mt-1"
                    />
                    <div className="min-w-0 flex-1">
                      <p className="text-sm font-semibold text-[#1c1c1e]">
                        {c.display}
                      </p>
                      <p className="mt-0.5 flex items-center gap-2 text-[11px] text-[#555a6a]">
                        <span className="rounded bg-white px-1.5 py-0.5 font-mono">
                          {c.risk_category}
                        </span>
                        <span>{c.risk_label}</span>
                        <span>·</span>
                        <span>{c.clinical_status}</span>
                      </p>
                    </div>
                  </label>
                </li>
              );
            })}
          </ul>
        )}
      </section>

      <section className="rounded-2xl bg-white p-5 shadow-[rgb(224_226_232)_0px_0px_0px_1px]">
        <div className="flex items-center gap-2">
          <ListChecks size={16} className="text-[#5b76fe]" />
          <h2 className="text-sm font-semibold text-[#1c1c1e]">
            Trust contract
          </h2>
        </div>
        <ul className="mt-3 space-y-2 text-xs leading-5 text-[#555a6a]">
          <li className="flex items-start gap-2">
            <CheckCircle size={13} className="mt-0.5 shrink-0 text-[#00b473]" />
            Every fact in the artifact carries a citation chip back to the
            chart resource or external source.
          </li>
          <li className="flex items-start gap-2">
            <CheckCircle size={13} className="mt-0.5 shrink-0 text-[#00b473]" />
            The agent will pause at declared approval gates — no
            unresolved-low-confidence outputs ship into the artifact.
          </li>
          <li className="flex items-start gap-2">
            <CheckCircle size={13} className="mt-0.5 shrink-0 text-[#00b473]" />
            No outreach is sent. The packet is produced for you to review,
            edit, and dispatch.
          </li>
        </ul>
      </section>

      <button
        type="button"
        onClick={start}
        disabled={!anchorPayload.length || isStarting}
        className="inline-flex w-full items-center justify-center gap-2 rounded-xl bg-[#5b76fe] px-4 py-3 text-sm font-semibold text-white shadow-sm transition disabled:cursor-not-allowed disabled:opacity-60"
        style={{ letterSpacing: 0.175 }}
      >
        <Target size={16} />
        {isStarting ? "Starting run…" : "Run trial finder"}
      </button>
    </div>
  );
}
