import { Link } from "react-router-dom";
import {
  ArrowRight,
  CheckCircle2,
  Clock,
  Copy,
  GitMerge,
  Globe,
  Info,
  Link2,
  ShieldAlert,
} from "lucide-react";
import { PageHeader } from "./components/PageHeader";

// ─── Feature card ─────────────────────────────────────────────────────────────

interface FeatureCardProps {
  icon: React.ComponentType<{ size?: number; className?: string }>;
  label: string;
  body: string;
  example?: string;
}

function FeatureCard({ icon: Icon, label, body, example }: FeatureCardProps) {
  return (
    <div className="flex flex-col rounded-xl border border-[#e7eaf2] bg-white p-5">
      <div className="mb-3 flex h-9 w-9 items-center justify-center rounded-lg bg-[#eef1ff]">
        <Icon size={18} className="text-[#5b76fe]" />
      </div>
      <p className="text-base font-semibold text-[#1d2433]">{label}</p>
      <p className="mt-2 flex-1 text-[13px] leading-relaxed text-[#4a5168]">{body}</p>
      {example && (
        <p className="mt-3 rounded-lg bg-[#f7f8fc] px-3 py-2.5 text-[12px] leading-relaxed text-[#6b7390] italic">
          {example}
        </p>
      )}
    </div>
  );
}

// ─── Status item ──────────────────────────────────────────────────────────────

interface StatusItemProps {
  label: string;
  detail: string;
  shipped: boolean;
}

function StatusItem({ label, detail, shipped }: StatusItemProps) {
  return (
    <div className="flex items-start gap-3 rounded-lg border border-[#e7eaf2] bg-white px-4 py-3">
      <CheckCircle2
        size={15}
        className={`mt-0.5 shrink-0 ${shipped ? "text-[#10864c]" : "text-[#c5c9d9]"}`}
      />
      <div>
        <p className={`text-[13px] font-semibold ${shipped ? "text-[#1d2433]" : "text-[#9aa5c0]"}`}>
          {label}
          {!shipped && (
            <span className="ml-2 rounded-full bg-[#f0f1f7] px-1.5 py-0.5 text-[9px] font-semibold uppercase tracking-wide text-[#9aa5c0]">
              Phase 2
            </span>
          )}
        </p>
        <p className="mt-0.5 text-[12px] text-[#6b7390]">{detail}</p>
      </div>
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

// ─── Feature cards data ───────────────────────────────────────────────────────

const FEATURE_CARDS: FeatureCardProps[] = [
  {
    icon: Copy,
    label: "Deduplication",
    body: "The same clinical fact appearing in two sources collapses to one record, with a list of contributing sources attached. Not two separate Observations — one Observation that knows it was corroborated.",
    example: "Glucose 98 mg/dL from Kaiser portal + same result in a Cedars PDF → one Observation, two provenance edges.",
  },
  {
    icon: ShieldAlert,
    label: "Conflict detection",
    body: "When sources disagree — different value, different unit, different date for the same nominal fact — the conflict is surfaced for review rather than silently resolved. Resolution is a decision, not an assumption.",
    example: "Metformin 500mg from portal vs 1000mg from discharge summary → flagged as conflict, both values preserved pending review.",
  },
  {
    icon: Link2,
    label: "Provenance graph",
    body: "Every harmonized fact retains an edge back to each contributing source: document identity, page number, extraction method, and pipeline variant. The graph is queryable — you can always trace any value to its origin.",
    example: "HbA1c 7.2% → extracted from page 3 of PDF 511b7036 via bidi-scout pipeline, corroborated by FHIR portal export.",
  },
  {
    icon: Clock,
    label: "Active vs. historical",
    body: "Temporal logic distinguishes a medication that is currently active from one that was prescribed in 2018 and discontinued. The same molecule appearing as both a current prescription and a historical entry is not treated as a duplicate.",
    example: "Metformin 500mg active (2024) and Metformin 500mg discontinued (2018) → two distinct records, not deduped.",
  },
];

// ─── Status items ─────────────────────────────────────────────────────────────

const SHIPPED_ITEMS: StatusItemProps[] = [
  {
    label: "Dedup on FHIR sources via SQL-on-FHIR engine",
    detail: "Patient, Condition, Medication, Observation, Encounter — deduplication across per-source views at ingest time.",
    shipped: true,
  },
  {
    label: "Per-fact provenance edges",
    detail: "Every fact carries source document and extraction metadata. Queryable via the SQL-on-FHIR warehouse.",
    shipped: true,
  },
  {
    label: "Conflict surfacing on the Harmonized Record view",
    detail: "Disagreements between sources are surfaced in the React app's harmonization review panel, not silently merged.",
    shipped: true,
  },
];

const PHASE2_ITEMS: StatusItemProps[] = [
  {
    label: "Cross-source merge at scale",
    detail: "PDF-extracted facts + FHIR portal exports + CCDA-converted records merged in a unified pass. Currently handled per-source; cross-source merge is Phase 2.",
    shipped: false,
  },
  {
    label: "Fan-out provenance",
    detail: "A single condition with five contributing sources — each edge independently preserved, queryable, and displayable. Current implementation handles up to two sources per fact cleanly.",
    shipped: false,
  },
  {
    label: "Synthea round-trip evaluation harness for harmonization F1",
    detail: "Render Synthea bundles, introduce deliberate conflicts, run harmonization, score against the known ground truth. The evaluation harness that makes the dedup logic measurable.",
    shipped: false,
  },
];

// ─── Page ────────────────────────────────────────────────────────────────────

export function Harmonization() {
  return (
    <article>
      <PageHeader
        title="Harmonization"
        subtitle="Deduplicating, reconciling, and tracking provenance across heterogeneous sources — the wedge."
      />

      {/* ── The problem ──────────────────────────────────────────────────── */}
      <section className="mb-10">
        <h2 className="mb-3 text-[20px] font-semibold leading-snug text-[#1d2433]">
          The problem
        </h2>
        <p className="text-[15px] leading-[1.65] text-[#4a5168]">
          Records arrive from many sources: FHIR portal exports, C-CDAs, PDFs, lab reports,
          payer claims. The same clinical fact routinely appears in multiple sources — the same
          glucose result in both a hospital discharge summary and a lab portal download; the same
          medication in both a CCDA and a handwritten prescription PDF.
        </p>
        <p className="mt-3 text-[15px] leading-[1.65] text-[#4a5168]">
          Naively concatenating produces duplicates that inflate the apparent record. Naively
          merging collapses provenance — you lose the ability to trace where each value came from
          and to surface disagreements between sources. Harmonization is the stage where Atlas
          earns its differentiation: making a single coherent record while preserving every source
          relationship.
        </p>
      </section>

      {/* ── What harmonization does ──────────────────────────────────────── */}
      <section className="mb-10">
        <h2 className="mb-1.5 text-[20px] font-semibold leading-snug text-[#1d2433]">
          What harmonization does
        </h2>
        <p className="mb-5 text-sm text-[#6b7390]">
          Four operations, each independently necessary.
        </p>
        <div className="grid gap-4 sm:grid-cols-2">
          {FEATURE_CARDS.map((card) => (
            <FeatureCard key={card.label} {...card} />
          ))}
        </div>
      </section>

      {/* ── TEFCA complementarity ────────────────────────────────────────── */}
      <section className="mb-10">
        <h2 className="mb-3 text-[20px] font-semibold leading-snug text-[#1d2433]">
          Where Atlas sits relative to TEFCA and health information exchanges
        </h2>
        <div className="rounded-r-lg border-l-[3px] border-[#5b76fe] bg-[#eef1ff] py-4 pl-5 pr-6">
          <p className="text-[15px] leading-[1.7] text-[#1d2433]">
            TEFCA, Carequality, and CommonWell move records between providers and increasingly do
            this well. They don't, by design, organize what they move. Atlas focuses on the next
            layer: when records arrive — whether from a TEFCA pull, a portal export, or a paper
            scan — Atlas turns the pile into one structured clinical record where every fact
            knows where it came from.
          </p>
        </div>
        <p className="mt-4 text-[15px] leading-[1.65] text-[#4a5168]">
          This is a complementary position, not a competitive one. TEFCA handles transport and
          trust; Atlas handles structure and provenance. A health system that already uses
          Carequality for record exchange still needs to answer "which Metformin entry in this
          consolidated record is the current one, and does it agree across the three sources that
          reported it?" That question is not answered by the exchange network — it's answered by
          the harmonization layer.
        </p>
        <div className="mt-4 flex items-start gap-3 rounded-xl border border-[#e7eaf2] bg-white p-5">
          <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-[#eef1ff]">
            <Globe size={18} className="text-[#5b76fe]" />
          </div>
          <div>
            <p className="text-[13px] font-semibold text-[#1d2433]">What Atlas is not</p>
            <p className="mt-1.5 text-[13px] leading-relaxed text-[#4a5168]">
              Atlas is not a QHIN, a clinical data repository, or a record-exchange service. It
              doesn't move records between providers or operate as a health information exchange.
              It operates on records that have already arrived — from any source — and organizes
              them into a provenance-backed structure that downstream applications can consume.
            </p>
          </div>
        </div>
      </section>

      {/* ── What's shipped vs Phase 2 ────────────────────────────────────── */}
      <section className="mb-10">
        <h2 className="mb-1.5 text-[20px] font-semibold leading-snug text-[#1d2433]">
          What's shipped vs. Phase 2
        </h2>
        <p className="mb-4 text-sm text-[#6b7390]">
          Honest status: what works today, what's on the Phase 2 roadmap.
        </p>

        <div className="mb-3 flex items-center gap-2">
          <CheckCircle2 size={13} className="text-[#10864c]" />
          <p className="text-[12px] font-semibold uppercase tracking-wide text-[#10864c]">
            Shipped
          </p>
        </div>
        <div className="mb-5 flex flex-col gap-2">
          {SHIPPED_ITEMS.map((item) => (
            <StatusItem key={item.label} {...item} />
          ))}
        </div>

        <div className="mb-3 flex items-center gap-2">
          <Info size={13} className="text-[#9aa5c0]" />
          <p className="text-[12px] font-semibold uppercase tracking-wide text-[#9aa5c0]">
            Phase 2
          </p>
        </div>
        <div className="flex flex-col gap-2">
          {PHASE2_ITEMS.map((item) => (
            <StatusItem key={item.label} {...item} />
          ))}
        </div>
      </section>

      {/* ── Where this fits in the pipeline ─────────────────────────────── */}
      <section className="mb-10">
        <h2 className="mb-3 text-[20px] font-semibold leading-snug text-[#1d2433]">
          Where this fits in the pipeline
        </h2>
        <div className="flex items-start gap-3 rounded-xl border border-[#e7eaf2] bg-white p-5">
          <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-[#eef1ff]">
            <GitMerge size={18} className="text-[#5b76fe]" />
          </div>
          <div>
            <p className="text-[13px] font-semibold text-[#1d2433]">Stage 3 — Harmonize</p>
            <p className="mt-1.5 text-[13px] leading-relaxed text-[#4a5168]">
              Input: per-source typed FHIR objects from stage 2 (Adapt) — one set per source
              document, each carrying its own provenance metadata. Output: a harmonized clinical
              record with deduplication applied, conflicts surfaced, and every remaining fact
              retaining a provenance edge to its contributing source or sources. This record
              flows into stage 4 (Bundle), where the access-controlled, portable package is
              produced.
            </p>
            <p className="mt-2.5 text-[13px] leading-relaxed text-[#4a5168]">
              The pipeline produces; applications consume. The harmonized bundle is the durable
              artifact — the clinical briefing, safety panel, and Q&amp;A surfaces that clinicians
              interact with are built on top of it, not within it.
            </p>
          </div>
        </div>

        {/* Pipeline position indicator */}
        <div className="mt-4 flex items-center gap-2 overflow-x-auto rounded-lg border border-[#e7eaf2] bg-[#f7f9ff] px-4 py-3">
          {["Ingest", "Adapt", "Harmonize", "Bundle"].map((stage, i) => (
            <div key={stage} className="flex shrink-0 items-center gap-2">
              {i > 0 && (
                <ArrowRight size={12} className="shrink-0 text-[#c5c9d9]" />
              )}
              <span
                className={`rounded-full px-3 py-1 text-[11px] font-semibold ${
                  stage === "Harmonize"
                    ? "bg-[#5b76fe] text-white"
                    : "bg-[#f0f1f7] text-[#6b7390]"
                }`}
              >
                {stage}
              </span>
            </div>
          ))}
        </div>
      </section>

      {/* ── Where to next ────────────────────────────────────────────────── */}
      <section>
        <h2 className="mb-4 text-[20px] font-semibold leading-snug text-[#1d2433]">
          Where to next
        </h2>
        <div className="flex flex-col gap-2.5">
          <SectionLink
            label="PDF extraction →"
            description="Stage 2 deep dive: five extraction architectures, live F1 numbers, gold-standard methodology and its limits."
            to="/using-atlas/pdf-extraction"
          />
          <SectionLink
            label="Standards & ecosystem →"
            description="FHIR R4, US Core, TEFCA, and where Atlas sits relative to existing health information exchanges."
            to="/using-atlas/standards"
          />
        </div>
      </section>
    </article>
  );
}
