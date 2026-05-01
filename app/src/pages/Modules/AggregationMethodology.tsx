import {
  ArrowRight,
  BookMarked,
  BrainCircuit,
  CheckCircle2,
  DatabaseZap,
  FileSearch,
  Layers3,
  MessageSquareText,
  ShieldCheck,
} from "lucide-react";
import { Link, useSearchParams } from "react-router-dom";

const principles = [
  {
    title: "Source boundaries stay visible",
    body: "Every fact keeps its origin, extraction method, timestamp, and confidence. Patient-reported context is useful, but it does not overwrite system-derived chart evidence.",
  },
  {
    title: "Aggregation starts with patient workflow",
    body: "The platform should fit real record-gathering behavior: portals, PDFs, labs, pharmacies, payers, wearables, screenshots, and patient memory.",
  },
  {
    title: "The semantic layer is the product contract",
    body: "Downstream modules should consume normalized concepts such as medications, conditions, observations, encounters, sources, conflicts, and patient context rather than raw file formats.",
  },
  {
    title: "Agents clarify, they do not invent",
    body: "LLM agents can phrase questions, summarize answers, propose linkages, and draft context bundles, but deterministic services own gap detection and provenance boundaries.",
  },
];

const layers = [
  {
    label: "1",
    title: "Source inventory",
    body: "Track portals, files, labs, pharmacies, payers, wearables, and missing systems before normalization begins.",
  },
  {
    label: "2",
    title: "Format ingestion",
    body: "Accept FHIR, C-CDA, PDFs, CSVs, screenshots, device exports, and manual notes as source material with clear provenance.",
  },
  {
    label: "3",
    title: "Canonical facts",
    body: "Extract candidate facts into shared clinical concepts while preserving source references and uncertainty.",
  },
  {
    label: "4",
    title: "Reconciliation queue",
    body: "Deduplicate records, detect stale medications, identify date conflicts, and hold ambiguous facts for patient or reviewer confirmation.",
  },
  {
    label: "5",
    title: "Patient Context layer",
    body: "Capture qualitative history, goals, symptoms, care preferences, timeline clarifications, and source leads as patient-reported context.",
  },
  {
    label: "6",
    title: "Publishable chart packet",
    body: "Expose a chart-ready semantic layer plus portable Markdown context files for clinical review, future agents, and downstream modules.",
  },
];

const agentRoles = [
  ["Collection guide", "Helps the patient identify sources and complete the next collection step."],
  ["Context interviewer", "Walks through chart gaps and captures patient-reported clarifications one question at a time."],
  ["Reconciliation analyst", "Suggests likely duplicates, conflicts, and missing evidence while leaving final boundaries explicit."],
  ["Bundle drafter", "Creates portable Markdown context files and clinician-facing unresolved questions."],
];

const dataModes = [
  ["Synthetic showcase", "Safe public mode for demos, screenshots, and challenge review."],
  ["Selected patient", "FHIR-derived local patient records for realistic end-to-end product behavior."],
  ["Private proof-of-life", "Explicit local-only private data mode for proving the system can handle real patient exports without committing artifacts."],
];

export function AggregationMethodology() {
  const [params] = useSearchParams();
  const patientId = params.get("patient");
  const contextHref = patientId ? `/aggregate/context?patient=${patientId}` : "/aggregate/context";
  const chartHref = patientId ? `/charts?patient=${patientId}` : "/charts";

  return (
    <main className="mx-auto max-w-7xl space-y-5 p-4 lg:p-6">
      <section className="rounded-2xl bg-white p-6 shadow-[rgb(224_226_232)_0px_0px_0px_1px] lg:p-8">
        <div className="flex flex-col gap-6 lg:flex-row lg:items-start lg:justify-between">
          <div className="max-w-3xl">
            <p className="inline-flex items-center gap-2 rounded-full bg-[#eef1ff] px-3 py-1 text-xs font-semibold uppercase tracking-wider text-[#5b76fe]">
              <BookMarked size={13} />
              Aggregation Methodology
            </p>
            <h1 className="mt-5 text-3xl font-semibold tracking-tight text-[#1c1c1e] lg:text-4xl">
              A patient-first method for turning scattered health data into usable context
            </h1>
            <p className="mt-3 max-w-4xl text-base leading-7 text-[#667085]">
              The Data Aggregator is not just an ingestion pipeline. It is a guided process for collecting fragmented EHI,
              reconciling it into a common semantic layer, and capturing the patient context that structured records almost
              always miss.
            </p>
          </div>
          <div className="min-w-[280px] rounded-2xl bg-[#f7f8ff] p-4 shadow-[rgb(224_226_232)_0px_0px_0px_1px]">
            <div className="flex items-center gap-2">
              <ShieldCheck size={18} className="text-[#5b76fe]" />
              <p className="text-sm font-semibold text-[#1c1c1e]">Operating boundary</p>
            </div>
            <p className="mt-2 text-sm leading-6 text-[#667085]">
              We separate verified chart evidence, extracted candidate facts, and patient-reported context. That boundary is
              the trust model.
            </p>
          </div>
        </div>
      </section>

      <section className="grid gap-4 lg:grid-cols-[0.95fr_1.05fr]">
        <div className="rounded-2xl bg-[#f7f8ff] p-5 shadow-[rgb(224_226_232)_0px_0px_0px_1px]">
          <div className="flex items-center gap-2">
            <DatabaseZap size={18} className="text-[#5b76fe]" />
            <h2 className="text-lg font-semibold text-[#1c1c1e]">What we are building</h2>
          </div>
          <p className="mt-3 text-sm leading-6 text-[#667085]">
            We are building a data-source agnostic aggregation layer that can accept whatever a patient can realistically
            obtain, then convert that material into a clinical semantic layer with provenance, uncertainty, and patient
            context attached.
          </p>
          <div className="mt-4 grid gap-3">
            {[
              "A patient-facing collection and context workflow.",
              "A deterministic normalization and reconciliation backbone.",
              "An agent-guided interview that fills gaps without pretending patient memory is verified chart truth.",
              "Portable context artifacts that can move with the patient and support future agents.",
            ].map((item) => (
              <div key={item} className="flex gap-3 rounded-xl bg-white p-3">
                <CheckCircle2 size={17} className="mt-0.5 shrink-0 text-[#0f766e]" />
                <p className="text-sm leading-6 text-[#35524d]">{item}</p>
              </div>
            ))}
          </div>
        </div>

        <div className="rounded-2xl bg-white p-5 shadow-[rgb(224_226_232)_0px_0px_0px_1px]">
          <div className="flex items-center gap-2">
            <Layers3 size={18} className="text-[#5b76fe]" />
            <h2 className="text-lg font-semibold text-[#1c1c1e]">Core principles</h2>
          </div>
          <div className="mt-4 grid gap-3">
            {principles.map((principle) => (
              <div key={principle.title} className="rounded-xl border border-[#e9eaef] p-4">
                <p className="text-sm font-semibold text-[#1c1c1e]">{principle.title}</p>
                <p className="mt-1 text-sm leading-6 text-[#667085]">{principle.body}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="rounded-2xl bg-white p-5 shadow-[rgb(224_226_232)_0px_0px_0px_1px]">
        <div className="flex flex-col gap-2 md:flex-row md:items-end md:justify-between">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wider text-[#5b76fe]">Semantic architecture</p>
            <h2 className="mt-1 text-xl font-semibold text-[#1c1c1e]">Six-layer aggregation model</h2>
          </div>
          <p className="max-w-xl text-sm leading-6 text-[#667085]">
            Each layer preserves the evidence boundary needed for clinician trust and downstream agent use.
          </p>
        </div>

        <div className="mt-5 grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {layers.map((layer) => (
            <div key={layer.title} className="rounded-2xl border border-[#e9eaef] bg-[#fafbff] p-5">
              <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-[#5b76fe] text-sm font-semibold text-white">
                {layer.label}
              </div>
              <h3 className="mt-4 text-base font-semibold text-[#1c1c1e]">{layer.title}</h3>
              <p className="mt-2 text-sm leading-6 text-[#667085]">{layer.body}</p>
            </div>
          ))}
        </div>
      </section>

      <section className="grid gap-4 lg:grid-cols-[1.05fr_0.95fr]">
        <div className="rounded-2xl bg-white p-5 shadow-[rgb(224_226_232)_0px_0px_0px_1px]">
          <div className="flex items-center gap-2">
            <BrainCircuit size={18} className="text-[#5b76fe]" />
            <h2 className="text-lg font-semibold text-[#1c1c1e]">Where agents fit</h2>
          </div>
          <p className="mt-2 text-sm leading-6 text-[#667085]">
            The agent experience is the bridge between incomplete records and useful context. The system should be adaptive
            and personal, but the agent should operate inside strict boundaries: no diagnosis, no fabrication, no silent
            merging of patient statements into chart truth.
          </p>
          <div className="mt-4 grid gap-3 sm:grid-cols-2">
            {agentRoles.map(([title, body]) => (
              <div key={title} className="rounded-xl border border-[#e9eaef] p-4">
                <p className="text-sm font-semibold text-[#1c1c1e]">{title}</p>
                <p className="mt-1 text-sm leading-6 text-[#667085]">{body}</p>
              </div>
            ))}
          </div>
        </div>

        <div className="rounded-2xl bg-[#f7fffc] p-5 shadow-[rgb(224_226_232)_0px_0px_0px_1px]">
          <div className="flex items-center gap-2">
            <MessageSquareText size={18} className="text-[#0f766e]" />
            <h2 className="text-lg font-semibold text-[#0f172a]">Patient Context is the first thin slice</h2>
          </div>
          <p className="mt-2 text-sm leading-6 text-[#35524d]">
            The guided context workflow proves the platform stance: use structured chart data where it exists, ask the
            patient where the record is silent, and export the resulting context in a portable format that follows the
            patient.
          </p>
          <Link to={contextHref} className="mt-5 inline-flex items-center gap-1 text-sm font-semibold text-[#0f766e]">
            Open Patient Context
            <ArrowRight size={14} />
          </Link>
        </div>
      </section>

      <section className="grid gap-4 lg:grid-cols-[0.9fr_1.1fr]">
        <div className="rounded-2xl bg-white p-5 shadow-[rgb(224_226_232)_0px_0px_0px_1px]">
          <div className="flex items-center gap-2">
            <FileSearch size={18} className="text-[#5b76fe]" />
            <h2 className="text-lg font-semibold text-[#1c1c1e]">Review modes</h2>
          </div>
          <div className="mt-4 grid gap-3">
            {dataModes.map(([title, body]) => (
              <div key={title} className="rounded-xl border border-[#e9eaef] p-4">
                <p className="text-sm font-semibold text-[#1c1c1e]">{title}</p>
                <p className="mt-1 text-sm leading-6 text-[#667085]">{body}</p>
              </div>
            ))}
          </div>
        </div>

        <div className="rounded-2xl bg-[#111827] p-5 text-white shadow-[rgb(224_226_232)_0px_0px_0px_1px]">
          <p className="text-xs font-semibold uppercase tracking-wider text-[#a5b4fc]">Decision record</p>
          <h2 className="mt-2 text-xl font-semibold">The chart is not the whole patient story</h2>
          <p className="mt-3 text-sm leading-6 text-[#d1d5db]">
            Our aggregation strategy should not chase a perfect automated merge as the first product promise. The practical
            path is to aggregate records, preserve uncertainty, ask better questions, and produce a trusted packet that helps
            clinicians find the right facts quickly.
          </p>
          <Link to={chartHref} className="mt-5 inline-flex items-center gap-1 text-sm font-semibold text-white">
            View the resulting chart surface
            <ArrowRight size={14} />
          </Link>
        </div>
      </section>
    </main>
  );
}
