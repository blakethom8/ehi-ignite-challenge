import { CheckCircle2, Layers3, TimerReset, TriangleAlert } from "lucide-react";

const PRINCIPLES = [
  {
    title: "Lead with safety-critical signal",
    detail:
      "Anticoagulants, antiplatelets, immunosuppressants, active high-risk conditions, and adverse lab trends are always surfaced first.",
  },
  {
    title: "Time is the primary lens",
    detail:
      "Every derived row keeps first_seen, last_seen, duration, and recency. The UI favors NOW and RECENT windows before historical detail.",
  },
  {
    title: "Compress without losing auditability",
    detail:
      "Multiple MedicationRequest records become episodes, but each episode retains references needed for evidence retrieval.",
  },
  {
    title: "Declare absences explicitly",
    detail:
      "No active anticoagulants, no major interaction pairs, and no recent warning labs are rendered as explicit states.",
  },
];

const LAYERS = [
  {
    layer: "Layer 0",
    name: "Hard Filters",
    summary: "Remove billing and non-clinical administrative noise before enrichment.",
    output: "Reduced token footprint with clinical relevance preserved",
  },
  {
    layer: "Layer 1",
    name: "Episode Compression",
    summary: "Group repeated records into medication, condition, and encounter episodes with temporal metadata.",
    output: "Longitudinal structures usable by both UI and LLM layers",
  },
  {
    layer: "Layer 2",
    name: "Deterministic Interpretation",
    summary: "Apply rule-based risk logic (drug classes, active status, encounter links, lab thresholds).",
    output: "Reproducible safety flags and ranked findings",
  },
  {
    layer: "Layer 3",
    name: "Batch Enrichment (planned)",
    summary: "Add compact clinical narratives and relevance scoring as a cacheable offline step.",
    output: "Context-ready rows for NL reasoning",
  },
  {
    layer: "Layer 4",
    name: "Context Assembly",
    summary: "Build persona-specific briefings with strict token budgets and citation hooks.",
    output: "Actionable briefing in seconds",
  },
];

const QUALITY_CHECKS = [
  "Every derived risk flag must map to an explicit source record set.",
  "Rows with low-coverage fields are tagged for caution in downstream interpretation.",
  "Temporal contradictions (future dates, reversed periods) are flagged as parse warnings.",
  "The methodology layer is deterministic first; probabilistic enrichment is additive.",
];

export function AnalysisMethodology() {
  return (
    <div className="mx-auto max-w-7xl px-6 py-8 lg:px-10">
      <section className="rounded-3xl border border-[#c4e6dc] bg-[linear-gradient(140deg,#f6fffc_0%,#edfcf6_45%,#f9fffd_100%)] p-6 lg:p-8">
        <p className="inline-flex items-center gap-2 rounded-full bg-[#d8f5ee] px-3 py-1 text-xs font-semibold uppercase tracking-wider text-[#0f766e]">
          <Layers3 size={13} />
          Methodology
        </p>
        <h1 className="mt-3 text-3xl font-semibold tracking-tight text-[#0f172a] lg:text-4xl">
          How We Interpret FHIR for Clinical Use Cases
        </h1>
        <p className="mt-3 max-w-4xl text-sm leading-6 text-[#35524d] lg:text-base">
          Our strategy is rules-first interpretability. We compress and organize FHIR records into temporal episodes,
          apply deterministic clinical logic, and only then layer on narrative generation. This keeps output auditable
          while still supporting advanced reasoning workflows.
        </p>
      </section>

      <section className="mt-6 grid gap-4 md:grid-cols-2">
        {PRINCIPLES.map((item) => (
          <article
            key={item.title}
            className="rounded-2xl bg-white p-5 shadow-[rgb(224_226_232)_0px_0px_0px_1px]"
          >
            <p className="flex items-center gap-2 text-sm font-semibold text-[#0f172a]">
              <CheckCircle2 size={15} className="text-[#0f766e]" />
              {item.title}
            </p>
            <p className="mt-2 text-sm leading-6 text-[#35524d]">{item.detail}</p>
          </article>
        ))}
      </section>

      <section className="mt-7 rounded-2xl bg-white p-5 shadow-[rgb(224_226_232)_0px_0px_0px_1px]">
        <p className="flex items-center gap-2 text-sm font-semibold text-[#0f172a]">
          <TimerReset size={16} className="text-[#0f766e]" />
          Pipeline Layers
        </p>
        <div className="mt-4 grid gap-3 lg:grid-cols-5">
          {LAYERS.map((layer) => (
            <article key={layer.layer} className="rounded-xl border border-[#e3f2ee] bg-[#f8fffd] p-3.5">
              <p className="text-xs font-semibold uppercase tracking-wider text-[#0f766e]">{layer.layer}</p>
              <h2 className="mt-1 text-sm font-semibold text-[#0f172a]">{layer.name}</h2>
              <p className="mt-2 text-xs leading-5 text-[#35524d]">{layer.summary}</p>
              <p className="mt-2 text-[11px] text-[#55706c]">
                Output: <span className="font-semibold text-[#0f766e]">{layer.output}</span>
              </p>
            </article>
          ))}
        </div>
      </section>

      <section className="mt-7 rounded-2xl border border-[#f5d9bf] bg-[#fff9f2] p-5">
        <p className="flex items-center gap-2 text-sm font-semibold text-[#92400e]">
          <TriangleAlert size={16} />
          Quality and Interpretability Gates
        </p>
        <ul className="mt-3 space-y-2 text-sm text-[#7c4a1f]">
          {QUALITY_CHECKS.map((item) => (
            <li key={item} className="flex items-start gap-2">
              <span className="mt-1 h-1.5 w-1.5 rounded-full bg-[#d97706]" />
              <span>{item}</span>
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}
