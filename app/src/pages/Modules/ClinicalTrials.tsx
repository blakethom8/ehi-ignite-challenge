import { useMemo } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { ArrowRight, ClipboardCheck, FileText, Search, Share2, Target, UserRound } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { api } from "../../api/client";
import { EmptyState } from "../../components/EmptyState";

function formatDate(value: string | null): string {
  if (!value) return "Unknown";
  return new Date(value).toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" });
}

function TrialWorkflowCard({
  icon: Icon,
  label,
  body,
}: {
  icon: LucideIcon;
  label: string;
  body: string;
}) {
  return (
    <div className="rounded-2xl bg-white p-5 shadow-[rgb(224_226_232)_0px_0px_0px_1px]">
      <div className="mb-4 flex h-10 w-10 items-center justify-center rounded-xl bg-[#eef1ff] text-[#5b76fe]">
        <Icon size={18} />
      </div>
      <h3 className="text-sm font-semibold text-[#1c1c1e]">{label}</h3>
      <p className="mt-2 text-sm leading-6 text-[#667085]">{body}</p>
    </div>
  );
}

export function ClinicalTrials() {
  const [searchParams] = useSearchParams();
  const patientId = searchParams.get("patient");

  const overviewQ = useQuery({
    queryKey: ["overview", patientId],
    queryFn: () => api.getOverview(patientId!),
    enabled: !!patientId,
  });
  const conditionsQ = useQuery({
    queryKey: ["conditionAcuity", patientId],
    queryFn: () => api.getConditionAcuity(patientId!),
    enabled: !!patientId,
  });

  const overview = overviewQ.data;
  const conditions = conditionsQ.data;
  const activeConditions = useMemo(
    () => (conditions?.ranked_active ?? []).filter((condition) => condition.risk_category !== "OTHER").slice(0, 6),
    [conditions]
  );

  if (!patientId) {
    return (
      <EmptyState
        icon={UserRound}
        title="Choose a patient to begin"
        bullets={[
          "Preview eligibility signals from the longitudinal chart",
          "Build a search packet for trial matching",
          "Keep the patient record available while researching options",
        ]}
        stat="Clinical trials module"
      />
    );
  }

  if (overviewQ.isLoading || conditionsQ.isLoading) {
    return (
      <div className="mx-auto max-w-7xl space-y-5 p-6">
        <div className="h-56 animate-pulse rounded-3xl bg-[#e9eaef]" />
        <div className="grid gap-4 md:grid-cols-3">
          <div className="h-44 animate-pulse rounded-2xl bg-[#e9eaef]" />
          <div className="h-44 animate-pulse rounded-2xl bg-[#e9eaef]" />
          <div className="h-44 animate-pulse rounded-2xl bg-[#e9eaef]" />
        </div>
      </div>
    );
  }

  if (overviewQ.isError || conditionsQ.isError || !overview || !conditions) {
    return (
      <div className="p-8">
        <p className="text-sm text-[#991b1b]">Failed to load clinical trials workspace.</p>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-7xl space-y-5 p-4 lg:p-6">
      <section className="rounded-3xl bg-white p-6 shadow-[rgb(224_226_232)_0px_0px_0px_1px] lg:p-8">
        <div className="flex flex-col gap-6 lg:flex-row lg:items-start lg:justify-between">
          <div className="max-w-3xl">
            <p className="inline-flex items-center gap-2 rounded-full bg-[#eef1ff] px-3 py-1 text-xs font-semibold uppercase tracking-wider text-[#5b76fe]">
              <Target size={13} />
              Clinical trials module
            </p>
            <h1 className="mt-5 text-3xl font-semibold tracking-tight text-[#1c1c1e] lg:text-4xl">
              Trial matching brief for {overview.name}
            </h1>
            <p className="mt-3 text-base leading-7 text-[#667085]">
              This workspace turns the patient record into a research packet: relevant diagnoses, history span, medication context,
              and a structured plan for screening trials before sharing opportunities with a clinician or patient.
            </p>
          </div>

          <div className="grid min-w-[260px] gap-3 rounded-2xl bg-[#fafbff] p-4 shadow-[rgb(224_226_232)_0px_0px_0px_1px]">
            <div>
              <p className="text-[10px] font-semibold uppercase tracking-wider text-[#a5a8b5]">Patient</p>
              <p className="mt-1 text-sm font-semibold text-[#1c1c1e]">
                {Math.floor(overview.age_years)} years · {overview.gender}
              </p>
            </div>
            <div>
              <p className="text-[10px] font-semibold uppercase tracking-wider text-[#a5a8b5]">Record span</p>
              <p className="mt-1 text-sm font-semibold text-[#1c1c1e]">
                {formatDate(overview.earliest_encounter_dt)} to {formatDate(overview.latest_encounter_dt)}
              </p>
            </div>
            <div>
              <p className="text-[10px] font-semibold uppercase tracking-wider text-[#a5a8b5]">Active conditions</p>
              <p className="mt-1 text-sm font-semibold text-[#1c1c1e]">{overview.active_condition_count}</p>
            </div>
          </div>
        </div>
      </section>

      <div className="grid gap-4 lg:grid-cols-3">
        <TrialWorkflowCard
          icon={Search}
          label="Search strategy"
          body="Use diagnosis, age, geography, and timeline context to generate targeted trial queries instead of broad keyword searches."
        />
        <TrialWorkflowCard
          icon={ClipboardCheck}
          label="Eligibility screen"
          body="Compare inclusion and exclusion criteria against known conditions, medication context, and available labs before escalating."
        />
        <TrialWorkflowCard
          icon={Share2}
          label="Share packet"
          body="Package the patient-level evidence and candidate trial rationale into a clinician-ready review artifact."
        />
      </div>

      <div className="grid gap-5 lg:grid-cols-[1.05fr_0.95fr]">
        <section className="rounded-2xl bg-white p-5 shadow-[rgb(224_226_232)_0px_0px_0px_1px]">
          <div className="flex items-center justify-between gap-3">
            <div>
              <h2 className="text-lg font-semibold text-[#1c1c1e]">Signals to Match</h2>
              <p className="mt-1 text-sm text-[#667085]">Condition context that should shape the first-pass trial search.</p>
            </div>
            <Link
              to={`/explorer/conditions?patient=${patientId}`}
              className="inline-flex items-center gap-1 rounded-lg px-3 py-2 text-sm font-semibold text-[#5b76fe] hover:bg-[#eef1ff]"
            >
              Conditions
              <ArrowRight size={14} />
            </Link>
          </div>

          <div className="mt-5 space-y-3">
            {activeConditions.length > 0 ? (
              activeConditions.map((condition) => (
                <div key={condition.condition_id} className="rounded-xl border border-[#e9eaef] p-4">
                  <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
                    <div>
                      <p className="font-semibold text-[#1c1c1e]">{condition.display}</p>
                      <p className="mt-1 text-sm text-[#667085]">
                        Onset {formatDate(condition.onset_dt)} · {condition.clinical_status}
                      </p>
                    </div>
                    <span className="w-fit rounded-full bg-[#eef1ff] px-2.5 py-1 text-xs font-semibold text-[#5b76fe]">
                      {condition.risk_label}
                    </span>
                  </div>
                </div>
              ))
            ) : (
              <div className="rounded-xl border border-dashed border-[#d5d9e5] p-6 text-sm text-[#667085]">
                No high-signal active conditions were detected for trial matching.
              </div>
            )}
          </div>
        </section>

        <section className="rounded-2xl bg-white p-5 shadow-[rgb(224_226_232)_0px_0px_0px_1px]">
          <div className="flex items-center gap-2">
            <FileText size={18} className="text-[#5b76fe]" />
            <h2 className="text-lg font-semibold text-[#1c1c1e]">Prototype Workflow</h2>
          </div>
          <div className="mt-5 space-y-4">
            {[
              ["1", "Extract patient traits", `${overview.active_condition_count} active conditions, ${overview.active_med_count} active meds, ${overview.years_of_history.toFixed(1)} years of history.`],
              ["2", "Find candidate trials", "Search public registries and sponsor pages with patient-specific inclusion terms."],
              ["3", "Screen and cite", "Return candidate trials with matching rationale, exclusions to verify, and source links."],
            ].map(([step, label, body]) => (
              <div key={step} className="flex gap-3">
                <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-[#eef1ff] text-xs font-semibold text-[#5b76fe]">
                  {step}
                </div>
                <div>
                  <p className="text-sm font-semibold text-[#1c1c1e]">{label}</p>
                  <p className="mt-1 text-sm leading-6 text-[#667085]">{body}</p>
                </div>
              </div>
            ))}
          </div>
        </section>
      </div>
    </div>
  );
}
