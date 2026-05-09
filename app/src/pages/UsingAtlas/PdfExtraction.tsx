import { Link } from "react-router-dom";
import {
  ArrowRight,
  AlertTriangle,
  CheckCircle2,
  FileText,
  FlaskConical,
  GitBranch,
  Info,
  Layers,
} from "lucide-react";
import { PageHeader } from "./components/PageHeader";

// ─── Architecture card ────────────────────────────────────────────────────────

interface ArchCardProps {
  name: string;
  tag: string;
  description: string;
  status: "default" | "best" | "tripwire" | "gold" | "candidate";
}

const STATUS_LABELS: Record<ArchCardProps["status"], string> = {
  default: "Default",
  best: "Strongest",
  tripwire: "Tripwire",
  gold: "Gold standard",
  candidate: "Cost candidate",
};

const STATUS_COLORS: Record<ArchCardProps["status"], string> = {
  default: "bg-[#eef1ff] text-[#5b76fe]",
  best: "bg-[#d1fae5] text-[#10864c]",
  tripwire: "bg-[#fff7ed] text-[#b86e00]",
  gold: "bg-[#f3e8ff] text-[#7c3aed]",
  candidate: "bg-[#f0f1f7] text-[#6b7390]",
};

function ArchCard({ name, tag, description, status }: ArchCardProps) {
  return (
    <div className="flex flex-col rounded-xl border border-[#e7eaf2] bg-white p-5">
      <div className="mb-3 flex items-start justify-between gap-3">
        <code className="rounded bg-[#f4f5fa] border border-[#e7eaf2] px-2 py-0.5 text-[12px] font-mono text-[#2d3650]">
          {name}
        </code>
        <span className={`shrink-0 rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide ${STATUS_COLORS[status]}`}>
          {STATUS_LABELS[status]}
        </span>
      </div>
      <p className="mb-1.5 text-[13px] font-semibold text-[#1d2433]">{tag}</p>
      <p className="flex-1 text-[13px] leading-relaxed text-[#4a5168]">{description}</p>
    </div>
  );
}

// ─── Section link ─────────────────────────────────────────────────────────────

interface SectionLinkProps {
  label: string;
  description: string;
  to: string;
}

function SectionLink({ label, description, to }: SectionLinkProps) {
  return (
    <Link
      to={to}
      className="group flex items-start gap-4 rounded-xl border border-[#e7eaf2] bg-white p-4 transition-colors hover:border-[#cfd7ff] hover:bg-[#fdfdff]"
    >
      <div className="min-w-0 flex-1">
        <p className="text-sm font-semibold text-[#1d2433]">{label}</p>
        <p className="mt-0.5 text-sm text-[#6b7390]">{description}</p>
      </div>
      <ArrowRight
        size={16}
        className="mt-0.5 shrink-0 text-[#9aa5c0] transition-transform group-hover:translate-x-0.5 group-hover:text-[#5b76fe]"
      />
    </Link>
  );
}

// ─── Pipeline architectures data ─────────────────────────────────────────────

const ARCHITECTURES: ArchCardProps[] = [
  {
    name: "multipass-fhir",
    tag: "Vision-LLM, 13 specialist passes in parallel",
    description:
      "The production default. Each pass targets a specific FHIR resource type (Condition, Medication, Observation, Practitioner, etc.) using a vision model on the raw PDF pages. ~$0.40/PDF, 134s.",
    status: "default",
  },
  {
    name: "multipass-fhir-scout",
    tag: "Single Pass-0 manifest scout, then specialists",
    description:
      "A Pass-0 scout first identifies which resource types are present in the document, then dispatches only the relevant specialist passes. Visible failure mode by design: if the scout's manifest is empty, no specialists run and the bundle comes back empty. Currently 0% F1 — used as a tripwire to surface prompt drift in the scout pass.",
    status: "tripwire",
  },
  {
    name: "multipass-fhir-bidi-scout",
    tag: "Two scouts (events + tables) with reconciliation",
    description:
      "Two scout passes — one oriented to narrative events, one to tabular data — with a reconciliation step before specialist dispatch. After the May 2026 perf pass, this is the strongest pipeline: 97% F1 on the cedars-myhealth eval at comparable cost to default.",
    status: "best",
  },
  {
    name: "multipass-fhir-gold",
    tag: "Opus 4.7 + extended thinking + self-consistency intersect + reviewer agent",
    description:
      "Reserved for ground-truth generation, not production use. Runs twice independently with extended thinking, intersects only entries that appear in both runs, then applies a reviewer agent (also Opus) as a critique pass. Expensive; used to produce the GT v1 set of 186 entries.",
    status: "gold",
  },
  {
    name: "multipass-fhir-gemma-tabular",
    tag: "Claude for narrative passes, Gemma 4 31B for tabular passes",
    description:
      "Cost-reduction candidate. Claude handles narrative-heavy passes (Condition, Practitioner); Gemma 4 31B (local, via Ollama) handles tabular passes (labs, vitals). Currently 0.55 F1 — a chunking artifact, not a model quality deficit. Under active investigation.",
    status: "candidate",
  },
];

// ─── F1 table rows ────────────────────────────────────────────────────────────

interface F1Row {
  pipeline: string;
  f1: string;
  f1Color: string;
  cost: string;
  latency: string;
  entries: string;
}

const F1_ROWS: F1Row[] = [
  {
    pipeline: "multipass-fhir (default)",
    f1: "92%",
    f1Color: "text-[#1d2433]",
    cost: "$0.39",
    latency: "134s",
    entries: "198",
  },
  {
    pipeline: "multipass-fhir-scout",
    f1: "0% (visible failure)",
    f1Color: "text-[#b3261e] font-semibold",
    cost: "$0.006",
    latency: "1.1s",
    entries: "0",
  },
  {
    pipeline: "multipass-fhir-bidi-scout",
    f1: "97%",
    f1Color: "text-[#10864c] font-semibold",
    cost: "$0.40",
    latency: "121s",
    entries: "195",
  },
];

// ─── Page ────────────────────────────────────────────────────────────────────

export function PdfExtraction() {
  return (
    <article>
      <PageHeader
        title="PDF extraction"
        subtitle="Five architectures benchmarked against ground truth. Why this is the hardest single ingestion path — and how Atlas measures honesty."
      />

      {/* ── Why PDFs are the hardest ─────────────────────────────────────── */}
      <section className="mb-10">
        <h2 className="mb-3 text-[20px] font-semibold leading-snug text-[#1d2433]">
          Why PDFs are the hardest ingestion path
        </h2>
        <p className="text-[15px] leading-[1.65] text-[#4a5168]">
          PDFs are the dominant clinical-export format for the long tail of records that don't
          flow through TEFCA or direct EHR connections: consult notes, lab reports, imaging
          summaries, and anything that crossed a fax or a portal download. They're visually rich,
          layout-variable, and resist naive OCR — the same glucose result may appear in a
          color-coded table, a dense narrative paragraph, or stamped into a page header, depending
          on which system produced the report.
        </p>
        <p className="mt-3 text-[15px] leading-[1.65] text-[#4a5168]">
          Atlas treats PDF extraction as the headline technical challenge in the Adapt stage.
          Rather than committing to a single architecture, we benchmarked five approaches against
          a shared ground-truth set, so the choice is backed by numbers rather than intuition.
        </p>
        <div className="mt-5 flex items-start gap-3 rounded-r-lg border-l-[3px] border-[#5b76fe] bg-[#eef1ff] py-3 pl-4 pr-5">
          <FileText size={16} className="mt-0.5 shrink-0 text-[#5b76fe]" />
          <p className="text-[14px] leading-[1.6] text-[#1d2433]">
            PDF extraction is part of pipeline stage 2 (Adapt). Every extracted fact flows
            downstream as a FHIR resource with provenance pointing to the source page and
            extraction method — so downstream deduplication and conflict detection can trace
            exactly where each value came from.
          </p>
        </div>
      </section>

      {/* ── Five architectures ───────────────────────────────────────────── */}
      <section className="mb-10">
        <h2 className="mb-1.5 text-[20px] font-semibold leading-snug text-[#1d2433]">
          Five architectures benchmarked
        </h2>
        <p className="mb-5 text-sm text-[#6b7390]">
          Each implements the same{" "}
          <code className="rounded bg-[#f4f5fa] border border-[#e7eaf2] px-1.5 py-px text-[11px] font-mono text-[#2d3650]">
            ExtractionPipeline
          </code>{" "}
          protocol and emits FHIR — comparable by design, evaluable against the same ground truth.
        </p>
        <div className="grid gap-4 sm:grid-cols-2">
          {ARCHITECTURES.map((arch) => (
            <ArchCard key={arch.name} {...arch} />
          ))}
        </div>
      </section>

      {/* ── Live F1 numbers ──────────────────────────────────────────────── */}
      <section className="mb-10">
        <div className="mb-1.5 flex items-center gap-2.5">
          <h2 className="text-[20px] font-semibold leading-snug text-[#1d2433]">
            Live F1 numbers
          </h2>
          <span className="rounded-full bg-[#eef1ff] px-2.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-[#5b76fe]">
            cedars-myhealth eval
          </span>
        </div>
        <p className="mb-4 text-sm text-[#6b7390]">
          Fresh extraction on PDF SHA{" "}
          <code className="rounded bg-[#f4f5fa] border border-[#e7eaf2] px-1.5 py-px text-[11px] font-mono text-[#2d3650]">
            511b7036
          </code>
          , scored against ground-truth v1 (186 entries) via a two-stage matcher: code-first
          resolution, then Jaccard fuzzy fallback.
        </p>

        <div className="overflow-hidden rounded-xl border border-[#e7eaf2] bg-white">
          <table className="w-full text-[13px]">
            <thead>
              <tr className="border-b border-[#e7eaf2] bg-[#f7f8fc]">
                <th className="px-4 py-3 text-left text-[11px] font-semibold uppercase tracking-wide text-[#6b7390]">
                  Pipeline
                </th>
                <th className="px-4 py-3 text-right text-[11px] font-semibold uppercase tracking-wide text-[#6b7390]">
                  F1
                </th>
                <th className="px-4 py-3 text-right text-[11px] font-semibold uppercase tracking-wide text-[#6b7390]">
                  Cost
                </th>
                <th className="px-4 py-3 text-right text-[11px] font-semibold uppercase tracking-wide text-[#6b7390]">
                  Latency
                </th>
                <th className="px-4 py-3 text-right text-[11px] font-semibold uppercase tracking-wide text-[#6b7390]">
                  Entries
                </th>
              </tr>
            </thead>
            <tbody>
              {F1_ROWS.map((row, i) => (
                <tr
                  key={row.pipeline}
                  className={i < F1_ROWS.length - 1 ? "border-b border-[#e7eaf2]" : ""}
                >
                  <td className="px-4 py-3 font-mono text-[12px] text-[#2d3650]">
                    {row.pipeline}
                  </td>
                  <td className={`px-4 py-3 text-right tabular-nums ${row.f1Color}`}>
                    {row.f1}
                  </td>
                  <td className="px-4 py-3 text-right tabular-nums text-[#4a5168]">
                    {row.cost}
                  </td>
                  <td className="px-4 py-3 text-right tabular-nums text-[#4a5168]">
                    {row.latency}
                  </td>
                  <td className="px-4 py-3 text-right tabular-nums text-[#4a5168]">
                    {row.entries}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <p className="mt-3 text-[13px] leading-relaxed text-[#6b7390]">
          After the May 2026 perf pass: bidi-scout beats default by 5 points at comparable cost.
          Scout deliberately fails loud when its Pass-0 manifest is empty — cost $0.006, 1.1s,
          zero entries, WARN log fires. That's the designed behavior: visible failure is preferable
          to silent $0.40 extraction of nothing.
        </p>

        <div className="mt-4 flex items-start gap-3 rounded-xl border border-[#fde8d5] bg-[#fff8f0] p-4">
          <AlertTriangle size={15} className="mt-0.5 shrink-0 text-[#b86e00]" />
          <div>
            <p className="text-[13px] font-semibold text-[#1d2433]">
              Pre-PERF scout numbers were an artifact
            </p>
            <p className="mt-1 text-[13px] leading-relaxed text-[#4a5168]">
              Before the perf pass, scout reported 98% F1 — because it was silently falling back
              to running all specialist passes when its manifest was empty, effectively becoming
              the default pipeline under a different name. The fix removed the fallback, exposing
              the failure mode the scout was masking.
            </p>
          </div>
        </div>
      </section>

      {/* ── Gold-standard methodology ─────────────────────────────────────── */}
      <section className="mb-10">
        <h2 className="mb-3 text-[20px] font-semibold leading-snug text-[#1d2433]">
          The gold-standard methodology — and its limits
        </h2>
        <p className="text-[15px] leading-[1.65] text-[#4a5168]">
          Ground truth v1 was generated by running Claude Opus 4.7 with adaptive extended thinking
          twice, independently, on the same PDF — then intersecting. Only entries that appear in{" "}
          <em>both</em> runs are retained. A reviewer agent (also Opus) critiques the
          intersection. Final output: 186 declared ground-truth entries.
        </p>
        <p className="mt-3 text-[15px] leading-[1.65] text-[#4a5168]">
          The intent is sound: self-consistency specifically targets hallucinations. If the most
          capable available model, with thinking enabled, agrees with itself across two independent
          runs, that's a strong signal. Invented entries drop out at the intersect.
        </p>

        {/* What it catches / doesn't catch */}
        <div className="mt-5 grid gap-4 sm:grid-cols-2">
          <div className="rounded-xl border border-[#d1fae5] bg-[#f0fdf4] p-5">
            <div className="mb-2 flex items-center gap-2">
              <CheckCircle2 size={15} className="text-[#10864c]" />
              <p className="text-[13px] font-semibold text-[#10864c]">What self-consistency catches</p>
            </div>
            <p className="text-[13px] leading-relaxed text-[#374151]">
              Hallucinations — entries invented in one run but not reproducible in a second
              independent run. These drop out at the intersect step and don't reach the GT.
            </p>
          </div>
          <div className="rounded-xl border border-[#fde8d5] bg-[#fff8f0] p-5">
            <div className="mb-2 flex items-center gap-2">
              <AlertTriangle size={15} className="text-[#b86e00]" />
              <p className="text-[13px] font-semibold text-[#b86e00]">What self-consistency misses</p>
            </div>
            <p className="text-[13px] leading-relaxed text-[#374151]">
              Consistent misses — if Opus has a systematic blind spot (e.g., underweighting
              "Authorizing Provider" stamps), both runs share the omission, the intersection
              inherits it, and the reviewer (also Opus) likely agrees. The GT encodes the model's
              systematic errors as ground truth.
            </p>
          </div>
        </div>

        <div className="mt-4 rounded-r-lg border-l-[3px] border-[#5b76fe] bg-[#eef1ff] py-3 pl-4 pr-5">
          <p className="text-[14px] font-semibold text-[#1d2433]">
            Pipeline rankings are valid. Absolute scores are not.
          </p>
          <p className="mt-1.5 text-[13px] leading-relaxed text-[#4a5168]">
            A measurement system where GT is generated by the same model class being tested is
            biased toward agreement with that model. When we report 97% F1, we mean "97%
            agreement with what Opus-with-thinking produces, intersected with itself" — not
            "97% of all extractable clinical facts." Relative comparisons between pipelines are
            reliable; absolute claims are not.
          </p>
        </div>

        {/* Phase 2 path */}
        <div className="mt-5">
          <p className="mb-3 text-[13px] font-semibold text-[#1d2433]">
            Phase 2 path to hardened ground truth
          </p>
          <div className="flex flex-col gap-2">
            <div className="flex items-start gap-3 rounded-lg border border-[#e7eaf2] bg-white px-4 py-3">
              <Layers size={14} className="mt-0.5 shrink-0 text-[#5b76fe]" />
              <div>
                <p className="text-[13px] font-semibold text-[#1d2433]">Synthea round-trip</p>
                <p className="mt-0.5 text-[12px] text-[#6b7390]">
                  Render a Synthea FHIR bundle to PDF, run the pipeline, score against the
                  original bundle. The GT is constructive — no LLM in the loop. Lower bound on
                  a clean-PDF scenario; 1,180 free test cases.
                </p>
              </div>
            </div>
            <div className="flex items-start gap-3 rounded-lg border border-[#e7eaf2] bg-white px-4 py-3">
              <FlaskConical size={14} className="mt-0.5 shrink-0 text-[#5b76fe]" />
              <div>
                <p className="text-[13px] font-semibold text-[#1d2433]">Cross-model gold</p>
                <p className="mt-0.5 text-[12px] text-[#6b7390]">
                  Add a third extractor from a different model family (Gemini 2.5 Pro or GPT-5)
                  and require 3-of-3 agreement. Cross-family mismatches are more diagnostic than
                  within-family mismatches.
                </p>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ── Where this fits ───────────────────────────────────────────────── */}
      <section className="mb-10">
        <h2 className="mb-3 text-[20px] font-semibold leading-snug text-[#1d2433]">
          Where this fits in the pipeline
        </h2>
        <div className="flex items-start gap-3 rounded-xl border border-[#e7eaf2] bg-white p-5">
          <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-[#eef1ff]">
            <GitBranch size={18} className="text-[#5b76fe]" />
          </div>
          <div>
            <p className="text-[13px] font-semibold text-[#1d2433]">Stage 2 — Adapt</p>
            <p className="mt-1.5 text-[13px] leading-relaxed text-[#4a5168]">
              PDF extraction is one adapter within the Adapt stage, alongside the FHIR bundle
              parser and the C-CDA converter. The output of every PDF run is a per-source FHIR
              bundle — typed objects that flow into stage 3 (Harmonize). Each extracted fact
              carries a provenance edge pointing back to the originating PDF page, the extraction
              pass, and the pipeline variant. Downstream deduplication and conflict detection can
              therefore distinguish "same Glucose from two sources" from "two different Glucose
              readings" — and surface disagreements rather than silently resolving them.
            </p>
          </div>
        </div>
        <div className="mt-3 flex items-start gap-2.5 rounded-lg border border-[#e7eaf2] bg-[#f7f9ff] px-4 py-3">
          <Info size={13} className="mt-0.5 shrink-0 text-[#9aa5c0]" />
          <p className="text-[12px] leading-relaxed text-[#6b7390]">
            The pipeline produces; applications consume. Extraction produces a FHIR bundle — the
            reasoning, clinical briefing, and safety panels that applications build on top are a
            separate layer. The bundle is the durable, portable artifact.
          </p>
        </div>
      </section>

      {/* ── Where to next ────────────────────────────────────────────────── */}
      <section>
        <h2 className="mb-4 text-[20px] font-semibold leading-snug text-[#1d2433]">
          Where to next
        </h2>
        <div className="flex flex-col gap-2.5">
          <SectionLink
            label="Harmonization →"
            description="Stage 3 deep dive: dedup, conflict detection, provenance graph, and TEFCA complementarity."
            to="/using-atlas/harmonization"
          />
          <SectionLink
            label="The pipeline →"
            description="Full four-stage walkthrough — Ingest, Adapt, Harmonize, Bundle — with data-flow details."
            to="/using-atlas/pipeline"
          />
        </div>
      </section>
    </article>
  );
}
