import { Link } from "react-router-dom";
import { ArrowRight, FileText, GitMerge } from "lucide-react";
import { PageHeader } from "./components/PageHeader";
import { PipelineDiagram } from "./components/PipelineDiagram";

// ─── Stage section ────────────────────────────────────────────────────────────

interface StageSectionProps {
  num: string;
  label: string;
  summary: string;
  details: React.ReactNode;
  status: string;
}

function StageSection({ num, label, summary, details, status }: StageSectionProps) {
  return (
    <section className="mb-9">
      {/* Header row */}
      <div className="mb-3 flex items-center gap-3">
        <span
          className="inline-flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-[#5b76fe] text-[10px] font-bold text-white"
          aria-hidden="true"
        >
          {num}
        </span>
        <h2 className="text-[20px] font-semibold leading-snug text-[#1d2433]">
          {num} — {label}
        </h2>
      </div>

      {/* Summary */}
      <p className="mb-4 text-[16px] leading-[1.6] text-[#4a5168]">{summary}</p>

      {/* Details block */}
      <div className="rounded-xl border border-[#e7eaf2] bg-white p-5">
        {details}
      </div>

      {/* Status note */}
      <p className="mt-3 text-[13px] leading-relaxed text-[#9aa5c0]">
        <span className="font-semibold text-[#6b7390]">Phase status —</span> {status}
      </p>
    </section>
  );
}

// ─── Bullet list helper ───────────────────────────────────────────────────────

function DetailList({ items }: { items: { label: string; body: string }[] }) {
  return (
    <ul className="space-y-3">
      {items.map(({ label, body }) => (
        <li key={label} className="flex gap-3">
          <span
            className="mt-[3px] h-2 w-2 shrink-0 rounded-full bg-[#cfd7ff]"
            aria-hidden="true"
          />
          <p className="text-[15px] leading-[1.65] text-[#4a5168]">
            <span className="font-semibold text-[#1d2433]">{label}.</span>{" "}
            {body}
          </p>
        </li>
      ))}
    </ul>
  );
}

// ─── Section link card ────────────────────────────────────────────────────────

interface SectionLinkProps {
  label: string;
  description: string;
  to: string;
  icon: React.ComponentType<{ size?: number; className?: string }>;
}

function SectionLink({ label, description, to, icon: Icon }: SectionLinkProps) {
  return (
    <Link
      to={to}
      className="group flex items-start gap-4 rounded-xl border border-[#e7eaf2] bg-white p-4 transition-colors hover:border-[#cfd7ff] hover:bg-[#fdfdff]"
    >
      <div className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-[#eef1ff]">
        <Icon size={15} className="text-[#5b76fe]" />
      </div>
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

// ─── Page ─────────────────────────────────────────────────────────────────────

export function ThePipeline() {
  return (
    <article>
      <PageHeader
        eyebrow="Using Atlas"
        title="The pipeline"
        subtitle="How data flows from EHI sources through to a portable clinical bundle."
      />

      {/* ── Intro + diagram ─────────────────────────────────────────────── */}
      <section className="mb-10">
        <p className="mb-2 text-[16px] leading-[1.6] text-[#1d2433]">
          <span className="font-semibold">
            Atlas's pipeline has four stages, each with a defined input, transformation, and output.
          </span>{" "}
          <span className="text-[#4a5168]">
            The output of stage 4 is the bundle — a structured clinical package that applications consume.
            Every stage preserves provenance: each fact in the bundle can be traced back to its source
            document, adapter, and reconciliation decision.
          </span>
        </p>
        <p className="mb-6 text-[15px] leading-[1.65] text-[#4a5168]">
          The pipeline produces. Applications — FHIR Charts, Caspian, Bundle Export,
          Marketplace skills — consume the bundle. That separation is the interoperability boundary.
        </p>
        <PipelineDiagram />
      </section>

      {/* ── 01 Ingest ───────────────────────────────────────────────────── */}
      <StageSection
        num="01"
        label="Ingest"
        summary="Sources arrive, are classified by format, validated for structural readiness, and assigned a provenance trail before any extraction begins. Nothing downstream runs until a source has cleared this gate."
        details={
          <DetailList
            items={[
              {
                label: "Source classification",
                body: "Incoming files are assigned one of four types: FHIR R4 bundle, C-CDA document, PDF (clinical or lab report), or structured portal export. Classification is deterministic — based on file signature and schema sniffing, not filename.",
              },
              {
                label: "Readiness validation",
                body: "FHIR bundles are checked for valid resourceType and a non-empty entry list. PDFs are checked for extractable content (text layer or vision-readable pages). Files that fail readiness are quarantined with a diagnostic code; they never reach the adapt stage.",
              },
              {
                label: "Provenance trail",
                body: "Each admitted source is assigned a stable SHA-keyed identifier, an ingest timestamp, and a source_type tag. This identifier threads through every downstream record — adapter output, harmonization decision, and bundle entry — so the chain of custody is never broken.",
              },
              {
                label: "Deduplication gate",
                body: "Sources are checked against previously ingested content by SHA hash. Re-submitting the same file is a no-op; the existing provenance record is returned without re-running the adapter.",
              },
            ]}
          />
        }
        status="FHIR and PDF classification are fully wired and tested across 1,180 synthetic patients. C-CDA classification is scaffolded and wired; the adapter (stage 2) is the Phase 2 priority. Portal export handling is designed but not yet in the active path."
      />

      {/* ── 02 Adapt ────────────────────────────────────────────────────── */}
      <StageSection
        num="02"
        label="Adapt"
        summary="Per-source adapters convert raw inputs into typed FHIR-shaped objects. Each adapter family is independent — a FHIR bundle needs no extraction; a PDF goes through a multi-pass vision pipeline. The output of every adapter is the same typed record shape, ready for harmonization."
        details={
          <div className="space-y-5">
            <div>
              <p className="mb-2.5 text-[13px] font-semibold uppercase tracking-wide text-[#9aa5c0]">
                Adapter families
              </p>
              <DetailList
                items={[
                  {
                    label: "FHIR parser",
                    body: "lib/fhir_parser/ handles FHIR R4 bundles directly. It produces typed dataclass objects — PatientRecord, Condition, Medication, Observation, Encounter, AllergyRecord — without any LLM call. This is the fastest and most reliable adapter path.",
                  },
                  {
                    label: "PDF → FHIR (multipass)",
                    body: "PDFs go through the multipass_fhir pipeline. Pass 0 extracts document context (patient, date, facility, provider) once per file. Subsequent passes target individual FHIR resource types in parallel — Conditions, Medications, AllergyIntolerance, Immunizations, Lab Observations. Cheap models handle tabular passes; stronger models handle narrative ones. Five architectures were benchmarked: bidi-scout, scout, default, gold, and Gemma 4 31B.",
                  },
                  {
                    label: "C-CDA via FHIR-Converter",
                    body: "C-CDA documents are converted through Microsoft's open-source FHIR-Converter, which produces a FHIR bundle. That bundle then runs through the same FHIR parser path. The adapter is scaffolded but not yet in the active extraction path.",
                  },
                ]}
              />
            </div>
            <div className="rounded-lg bg-[#f7f9ff] px-4 py-3">
              <p className="text-[13px] leading-[1.6] text-[#4a5168]">
                The PDF extraction architecture — including bake-off F1 numbers across all five
                architectures and the prompt-tuning log — is covered in depth on the{" "}
                <Link to="/using-atlas/pdf-extraction" className="font-semibold text-[#5b76fe] hover:underline">
                  PDF extraction
                </Link>{" "}
                page.
              </p>
            </div>
          </div>
        }
        status="The FHIR parser is stable and is the primary adapter used across the patient explorer. The PDF pipeline is the most-tested path: five architectures benchmarked, caching layer stable, parallel dispatch wired. The CCDA adapter is scaffolded; full integration is the Phase 2 build priority."
      />

      {/* ── 03 Harmonize ────────────────────────────────────────────────── */}
      <StageSection
        num="03"
        label="Harmonize"
        summary="Typed records from multiple sources are compared and reconciled. Duplicate facts are merged; conflicting facts are surfaced, not silently resolved. Every surviving fact retains a citation edge to the source that contributed it."
        details={
          <div className="space-y-5">
            <DetailList
              items={[
                {
                  label: "Deduplication via SQL-on-FHIR",
                  body: "The SQL-on-FHIR engine materializes typed records into a SQLite warehouse (sof.db). Dedup runs as a query-layer operation: medication episodes are grouped by normalized drug name into the medication_episode derived table; observation_latest keeps only the most-recent value per LOINC code per patient. No Python-level loop needed.",
                },
                {
                  label: "Conflict detection",
                  body: "When two sources report the same fact with differing values — for example, two medication lists with different dosages for the same drug — the harmonizer classifies each fact as shared (both sources agree), unique (only one source has it), or conflict (both have it, values differ). Conflicts are recorded in the provenance graph, not resolved by silent fallback.",
                },
                {
                  label: "Citation edges",
                  body: "Every fact in the harmonized record carries a citation edge: source document SHA, adapter name, and pass name (for PDF extractions). The provenance graph is first-class data — queryable, not just a log.",
                },
                {
                  label: "Enrichment columns",
                  body: "Additional clinical columns — drug_class on medication_request — are spliced onto rows at ingest time using the enrichment layer (enrich.py). These are clinically derived, not FHIRPath-expressible, and are carried through to the bundle without breaking the provenance chain.",
                },
              ]}
            />
            <div className="rounded-lg bg-[#f7f9ff] px-4 py-3">
              <p className="text-[13px] leading-[1.6] text-[#4a5168]">
                The full deduplication logic, conflict-detection schema, and provenance graph design
                are covered on the{" "}
                <Link to="/using-atlas/harmonization" className="font-semibold text-[#5b76fe] hover:underline">
                  Harmonization
                </Link>{" "}
                page.
              </p>
            </div>
          </div>
        }
        status="Deduplication and enrichment are fully wired for FHIR sources across the active patient explorer. Conflict detection is implemented in the harmonize service layer. Cross-source merge across PDF + FHIR + CCDA — the case where the same patient has records from three different formats — is the Phase 2 priority."
      />

      {/* ── 04 Bundle ───────────────────────────────────────────────────── */}
      <StageSection
        num="04"
        label="Bundle"
        summary="The pipeline's output: a structured clinical package containing typed resources, the full provenance graph, and access metadata. The bundle is deployable, storable, and portable. It is what applications consume — Atlas's own and third-party alike."
        details={
          <DetailList
            items={[
              {
                label: "What's inside",
                body: "Typed clinical resources (Patient, Condition, Medication, Observation, Encounter, AllergyIntolerance, Immunization, Procedure), the provenance graph recording every source-to-fact citation edge, and access metadata (scoping principals, bundle version, generation timestamp).",
              },
              {
                label: "Access controls",
                body: "The bundle carries RBAC scoping: a principal list defines which identities can read which resource types. Audit log targets are registered at bundle creation so every downstream read is traceable. This is the access boundary that Marketplace skills and external applications operate within — they receive a scoped bundle view, not the raw source files.",
              },
              {
                label: "Portability",
                body: "The bundle is storage-agnostic: it can be written to disk, a cloud object store, or an EHR system that accepts FHIR R4 Bundle input. The Bundle Export application surface produces a downloadable package. Format is FHIR R4 Bundle with Atlas-namespaced extension elements for provenance and access metadata.",
              },
              {
                label: "Application boundary",
                body: "No application gets direct access to source files or the intermediate adapter output. The bundle is the only interface. This is intentional: it decouples source-format concerns from application logic, and it lets the provenance layer enforce citation requirements uniformly.",
              },
            ]}
          />
        }
        status="Scoped chart-snapshot export is wired and used by the patient explorer. The full RBAC and audit-log production deployment is designed and documented; implementation is Phase 2. Bundle portability (download, FHIR R4 export) is in the active build path."
      />

      {/* ── What this enables ───────────────────────────────────────────── */}
      <section className="mb-10">
        <h2 className="mb-3 text-[20px] font-semibold leading-snug text-[#1d2433]">
          What this enables
        </h2>
        <p className="mb-4 text-[15px] leading-[1.65] text-[#4a5168]">
          Once the bundle exists, any application can consume it. The pipeline produces a single
          durable artifact; every application built on top of Atlas reads from that artifact, not
          from the source files directly.
        </p>
        <div className="rounded-xl border border-[#e7eaf2] bg-white p-5">
          <ul className="space-y-3">
            {[
              {
                label: "FHIR Charts",
                body: "Visualizes the bundle as clinical charts — timelines, safety panels, medication histories. Familiar to anyone who has used a chart system.",
              },
              {
                label: "Caspian",
                body: "Atlas's internal agent harness. Full bundle access, cited Q&A, and evidence packets assembled from validated facts. Reasoning over the bundle, not over raw source text.",
              },
              {
                label: "Bundle Export",
                body: "Downloads the structured bundle as a portable package. Take the record to a new specialist, plug it into another application, or use it with any agent or tool that accepts FHIR R4.",
              },
              {
                label: "Marketplace skills",
                body: "A controlled-access space for skills and modules. Skills receive a scoped bundle view — web search, specialized analysis, domain workflows — without raw source file exposure.",
              },
            ].map(({ label, body }) => (
              <li key={label} className="flex gap-3">
                <span
                  className="mt-[3px] h-2 w-2 shrink-0 rounded-full bg-[#cfd7ff]"
                  aria-hidden="true"
                />
                <p className="text-[15px] leading-[1.65] text-[#4a5168]">
                  <span className="font-semibold text-[#1d2433]">{label}.</span>{" "}
                  {body}
                </p>
              </li>
            ))}
          </ul>
        </div>
        <p className="mt-3 text-[13px] text-[#9aa5c0]">
          All four surfaces are described on the{" "}
          <Link to="/using-atlas" className="text-[#5b76fe] hover:underline">
            Get started
          </Link>{" "}
          page under Application overview.
        </p>
      </section>

      {/* ── Where to next ───────────────────────────────────────────────── */}
      <section className="mb-2">
        <h2 className="mb-3 text-[20px] font-semibold leading-snug text-[#1d2433]">
          Where to next
        </h2>
        <p className="mb-4 text-sm text-[#6b7390]">
          The two deepest parts of the pipeline each have their own page.
        </p>
        <div className="flex flex-col gap-2.5">
          <SectionLink
            label="PDF extraction"
            description="Five architectures benchmarked — bidi-scout, scout, default, gold, Gemma 4 31B — with F1 numbers and the bake-off methodology."
            to="/using-atlas/pdf-extraction"
            icon={FileText}
          />
          <SectionLink
            label="Harmonization"
            description="Deduplication logic, conflict detection schema, and the provenance graph design — the mechanics of stage 3 in depth."
            to="/using-atlas/harmonization"
            icon={GitMerge}
          />
        </div>
      </section>
    </article>
  );
}
