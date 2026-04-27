import { useQuery } from "@tanstack/react-query";
import { ArrowRight, BookOpenText, Database, FlaskConical, Route, ShieldCheck } from "lucide-react";
import { api } from "../../api/client";

function StatTile({ label, value, note }: { label: string; value: string; note: string }) {
  return (
    <article className="rounded-2xl bg-white p-5 shadow-[rgb(224_226_232)_0px_0px_0px_1px]">
      <p className="text-[11px] font-semibold uppercase tracking-wider text-[#55706c]">{label}</p>
      <p className="mt-1 text-3xl font-semibold text-[#0f172a]">{value}</p>
      <p className="mt-1 text-xs text-[#64748b]">{note}</p>
    </article>
  );
}

const LEARNING_OBJECTIVES = [
  "Understand exactly what is in each patient FHIR bundle before building inference features.",
  "Map clinical questions to specific resource fields and interpretability guardrails.",
  "Separate trustworthy signals from sparse fields using corpus-level coverage evidence.",
];

const PIPELINE_STEPS = [
  {
    name: "Ingest",
    detail: "Load raw FHIR R4 bundle and normalize to parser-backed PatientRecord models.",
    output: "Typed patient objects",
  },
  {
    name: "Structure",
    detail: "Group repeated events into episodes (medications, conditions, encounters) with temporal context.",
    output: "Longitudinal episodes",
  },
  {
    name: "Interpret",
    detail: "Apply deterministic risk logic (drug classes, active status, recency) before any LLM layer.",
    output: "Safety flags + ranked findings",
  },
  {
    name: "Explain",
    detail: "Produce clinician-readable narratives and evidence-backed answers tied to source records.",
    output: "Actionable briefing context",
  },
];

const QUESTION_MAP = [
  {
    question: "Is this patient safe for surgery this week?",
    resources: "MedicationRequest + Condition + Observation",
    method: "Drug-class risk flags + active condition acuity + critical lab checks",
  },
  {
    question: "What changed recently that I should care about?",
    resources: "Encounter + Observation + Procedure",
    method: "Recency windows (30d / 6mo) + trend deltas + event linking",
  },
  {
    question: "Which fields are dependable vs sparse?",
    resources: "Corpus field profiler",
    method: "Coverage tiers (Always / Usually / Sometimes / Rarely)",
  },
];

export function AnalysisOverview() {
  const { data: stats, isLoading } = useQuery({
    queryKey: ["corpus-stats"],
    queryFn: api.getCorpusStats,
    staleTime: Infinity,
  });

  return (
    <div className="mx-auto max-w-7xl px-6 py-8 lg:px-10">
      <section className="rounded-3xl border border-[#b7e6dc] bg-[linear-gradient(135deg,#f5fffc_0%,#e9fbf6_55%,#f0fff9_100%)] p-6 lg:p-8">
        <div>
          <p className="inline-flex items-center gap-2 rounded-full bg-[#d8f5ee] px-3 py-1 text-xs font-semibold uppercase tracking-wider text-[#0f766e]">
            <BookOpenText size={13} />
            Data Review Environment
          </p>
          <h1 className="mt-3 max-w-4xl text-3xl font-semibold tracking-tight text-[#0f172a] lg:text-4xl">
            FHIR Data Definitions and Methodology
          </h1>
          <p className="mt-3 max-w-5xl text-sm leading-6 text-[#35524d] lg:text-base">
            This module is the public-facing tutorial surface for understanding what we ingest from FHIR,
            how we interpret it, and which signals are safe to operationalize in clinical workflows.
          </p>

          <div className="mt-5 border-t border-[#b7e6dc]/70 pt-4">
            <p className="text-xs font-semibold uppercase tracking-wider text-[#0f766e]">Learning goals</p>
            <ul className="mt-3 grid gap-3 text-sm text-[#35524d] lg:grid-cols-3">
              {LEARNING_OBJECTIVES.map((item) => (
                <li key={item} className="flex items-start gap-2 rounded-xl bg-white/55 px-3 py-2 shadow-[rgb(183_230_220)_0px_0px_0px_1px]">
                  <span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-[#0f766e]" />
                  <span>{item}</span>
                </li>
              ))}
            </ul>
          </div>
        </div>
      </section>

      <section className="mt-6">
        <div className="mb-3 flex items-baseline justify-between gap-3">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wider text-[#0f766e]">
              Synthea R4 Corpus Snapshot
            </p>
            <p className="mt-1 text-sm text-[#55706c]">
              Metrics below summarize the 1,180 synthetic patient bundles loaded for this submission.
            </p>
          </div>
        </div>

        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        {isLoading &&
          Array.from({ length: 4 }).map((_, idx) => (
            <div key={idx} className="h-[122px] animate-pulse rounded-2xl bg-white shadow-[rgb(224_226_232)_0px_0px_0px_1px]" />
          ))}

        {!isLoading && stats && (
          <>
            <StatTile
              label="Corpus Size"
              value={stats.total_patients.toLocaleString()}
              note="Individual patient bundles available"
            />
            <StatTile
              label="Total Encounters"
              value={stats.total_encounters.toLocaleString()}
              note="Visit-level events for longitudinal reasoning"
            />
            <StatTile
              label="Total Resources"
              value={stats.total_resources.toLocaleString()}
              note="Clinical + administrative FHIR resources"
            />
            <StatTile
              label="Avg Active Meds"
              value={stats.avg_active_med_count.toFixed(1)}
              note="Useful baseline for safety panel complexity"
            />
          </>
        )}
        </div>
      </section>

      <section className="mt-7 grid gap-5 lg:grid-cols-[1.05fr_1fr]">
        <article className="rounded-2xl bg-white p-5 shadow-[rgb(224_226_232)_0px_0px_0px_1px]">
          <p className="inline-flex items-center gap-2 text-sm font-semibold text-[#0f766e]">
            <Route size={16} />
            Data-to-Insight Pipeline
          </p>
          <div className="mt-4 space-y-3">
            {PIPELINE_STEPS.map((step, idx) => (
              <div key={step.name} className="rounded-xl border border-[#e5f4ef] bg-[#f7fffc] p-3.5">
                <div className="flex items-center gap-2">
                  <span className="inline-flex h-5 w-5 items-center justify-center rounded-full bg-[#0f766e] text-xs font-semibold text-white">
                    {idx + 1}
                  </span>
                  <h2 className="text-sm font-semibold text-[#0f172a]">{step.name}</h2>
                </div>
                <p className="mt-2 text-sm text-[#35524d]">{step.detail}</p>
                <p className="mt-1 text-xs text-[#55706c]">
                  Output: <span className="font-semibold text-[#0f766e]">{step.output}</span>
                </p>
              </div>
            ))}
          </div>
        </article>

        <article className="rounded-2xl bg-white p-5 shadow-[rgb(224_226_232)_0px_0px_0px_1px]">
          <p className="inline-flex items-center gap-2 text-sm font-semibold text-[#0f766e]">
            <ShieldCheck size={16} />
            Clinical Question Mapping
          </p>
          <div className="mt-4 space-y-3">
            {QUESTION_MAP.map((item) => (
              <div key={item.question} className="rounded-xl border border-[#edf0f7] p-3.5">
                <p className="text-sm font-semibold text-[#0f172a]">{item.question}</p>
                <p className="mt-1 text-xs text-[#64748b]">FHIR scope: {item.resources}</p>
                <div className="mt-2 flex items-start gap-2 text-sm text-[#35524d]">
                  <ArrowRight size={14} className="mt-0.5 shrink-0 text-[#0f766e]" />
                  <span>{item.method}</span>
                </div>
              </div>
            ))}
          </div>
        </article>
      </section>

      <section className="mt-7 grid gap-4 md:grid-cols-3">
        <article className="rounded-2xl border border-[#dbece7] bg-white p-4">
          <p className="flex items-center gap-2 text-sm font-semibold text-[#0f172a]">
            <Database size={16} className="text-[#0f766e]" />
            What this section covers
          </p>
          <p className="mt-2 text-sm leading-6 text-[#35524d]">
            Canonical data definitions for Patient, Encounter, Condition, Medication, Observation, Procedure,
            Immunization, and Allergy resources as they exist in this project.
          </p>
        </article>

        <article className="rounded-2xl border border-[#dbece7] bg-white p-4">
          <p className="flex items-center gap-2 text-sm font-semibold text-[#0f172a]">
            <FlaskConical size={16} className="text-[#0f766e]" />
            Why it matters
          </p>
          <p className="mt-2 text-sm leading-6 text-[#35524d]">
            The fastest way to ship safer clinical features is to make interpretability explicit before adding model
            complexity. Every derived insight should map back to typed source fields.
          </p>
        </article>

        <article className="rounded-2xl border border-[#dbece7] bg-white p-4">
          <p className="flex items-center gap-2 text-sm font-semibold text-[#0f172a]">
            <ShieldCheck size={16} className="text-[#0f766e]" />
            Guardrails
          </p>
          <p className="mt-2 text-sm leading-6 text-[#35524d]">
            We treat absence as a first-class signal: no active anticoagulants, no high-criticality allergies, and no
            recent adverse trends must be represented explicitly, not implied.
          </p>
        </article>
      </section>
    </div>
  );
}
