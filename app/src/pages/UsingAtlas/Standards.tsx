import { Link } from "react-router-dom";
import {
  ArrowRight,
  Ban,
  FileCode,
  FileText,
  Globe,
  Network,
  Smartphone,
} from "lucide-react";
import { PageHeader } from "./components/PageHeader";

// ─── Standards alignment row ─────────────────────────────────────────────────

interface StandardRowProps {
  icon: React.ComponentType<{ size?: number; className?: string }>;
  label: string;
  badge?: string;
  body: string;
}

function StandardRow({ icon: Icon, label, badge, body }: StandardRowProps) {
  return (
    <div className="flex gap-4 py-4 border-b border-[#f0f1f7] last:border-0">
      <div className="mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-[#eef1ff]">
        <Icon size={18} className="text-[#5b76fe]" />
      </div>
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <p className="text-[15px] font-semibold text-[#1d2433]">{label}</p>
          {badge && (
            <span className="rounded-full bg-[#eef1ff] px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-[#5b76fe]">
              {badge}
            </span>
          )}
        </div>
        <p className="mt-1.5 text-[14px] leading-[1.6] text-[#4a5168]">{body}</p>
      </div>
    </div>
  );
}

// ─── Ecosystem row ───────────────────────────────────────────────────────────

interface EcosystemRowProps {
  actor: string;
  role: string;
  atlasRelation: string;
}

function EcosystemRow({ actor, role, atlasRelation }: EcosystemRowProps) {
  return (
    <div className="grid grid-cols-[1fr_1.2fr_1.4fr] gap-4 py-3 border-b border-[#f0f1f7] last:border-0 text-[13px]">
      <p className="font-semibold text-[#1d2433]">{actor}</p>
      <p className="text-[#4a5168]">{role}</p>
      <p className="text-[#4a5168]">{atlasRelation}</p>
    </div>
  );
}

// ─── Not-list item ───────────────────────────────────────────────────────────

function NotItem({ children }: { children: React.ReactNode }) {
  return (
    <li className="flex items-start gap-3 py-2.5 border-b border-[#f0f1f7] last:border-0">
      <Ban size={14} className="mt-0.5 shrink-0 text-[#c5c9d9]" />
      <span className="text-[14px] leading-[1.6] text-[#4a5168]">{children}</span>
    </li>
  );
}

// ─── Section link row ─────────────────────────────────────────────────────────

interface SectionLinkProps {
  label: string;
  description: string;
  to: string;
  external?: boolean;
}

function SectionLink({ label, description, to, external }: SectionLinkProps) {
  const className =
    "group flex items-start gap-4 rounded-xl border border-[#e7eaf2] bg-white p-4 transition-colors hover:border-[#cfd7ff] hover:bg-[#fdfdff]";

  const inner = (
    <>
      <div className="min-w-0 flex-1">
        <p className="text-sm font-semibold text-[#1d2433]">{label}</p>
        <p className="mt-0.5 text-sm text-[#6b7390]">{description}</p>
      </div>
      <ArrowRight
        size={16}
        className="mt-0.5 shrink-0 text-[#9aa5c0] transition-transform group-hover:translate-x-0.5 group-hover:text-[#5b76fe]"
      />
    </>
  );

  if (external) {
    return (
      <a href={to} target="_blank" rel="noopener noreferrer" className={className}>
        {inner}
      </a>
    );
  }

  return (
    <Link to={to} className={className}>
      {inner}
    </Link>
  );
}

// ─── Standards data ───────────────────────────────────────────────────────────

const STANDARDS: StandardRowProps[] = [
  {
    icon: FileCode,
    label: "FHIR R4",
    badge: "canonical",
    body: "The internal canonical shape. Every typed clinical fact maps to a FHIR R4 resource — Observation, Condition, MedicationRequest, Encounter, DocumentReference, Provenance. Bundles can be exported as FHIR JSON, summary JSON, or Markdown.",
  },
  {
    icon: Globe,
    label: "US Core profiles",
    body: "Applied where applicable for clinical interoperability — US Core Patient, US Core MedicationRequest, US Core Condition, US Core Observation (lab results). Ensures the canonical record can interoperate with US Core-aligned tooling.",
  },
  {
    icon: FileText,
    label: "C-CDA / CDA",
    body: "Handled via Microsoft FHIR-Converter (subprocess wrapper, Liquid templates implementing the published CDA-on-FHIR IG). Test corpus: 747 sample C-CDAs from jmandel/sample_ccdas across approximately 12 vendors — Allscripts, Cerner, Greenway, Kareo, NextGen, Partners HealthCare, PracticeFusion, and others.",
  },
  {
    icon: FileText,
    label: "PDF, lab reports, portal exports",
    body: "Handled via the multi-pass extraction pipeline. Five architectures benchmarked: default, scout, bidi-scout, gold (Opus 4.7 + chain-of-thought), and gemma-tabular (local Gemma 4 31B via Ollama for tabular extraction). See the PDF Extraction page for methodology and precision/recall numbers.",
  },
  {
    icon: Smartphone,
    label: "SMART App Launch",
    badge: "Phase 2",
    body: "Readiness path planned for Phase 2 to enable direct patient-app integration with EHR FHIR endpoints. Phase 1 focuses on file-based ingest; SMART launch extends the intake surface to authenticated EHR connections.",
  },
];

// ─── Ecosystem actors ─────────────────────────────────────────────────────────

const ECOSYSTEM_ACTORS: EcosystemRowProps[] = [
  {
    actor: "TEFCA / QHINs",
    role: "Provider-to-provider record movement via participating QHINs (Epic Nexus, eHealth Exchange, Health Gorilla, etc.)",
    atlasRelation: "Atlas ingests records that don't flow through TEFCA; synthesizes records that do",
  },
  {
    actor: "Carequality / CommonWell",
    role: "Record exchange networks between EHR systems and labs; growing provider coverage",
    atlasRelation: "Same role as QHINs — Atlas sits downstream, organizing what arrives",
  },
  {
    actor: "Apple Health Records",
    role: "Patient-held FHIR copies pulled from authenticated EHR endpoints; read-only",
    atlasRelation: "A valid Atlas source input. Apple Health exports can flow into the Atlas pipeline as FHIR bundles.",
  },
  {
    actor: "CommonHealth / SMART Health Cards",
    role: "Patient-mediated portable records; verifiable credentials",
    atlasRelation: "Source inputs. The Atlas adapter classifies and ingests these like any other FHIR bundle.",
  },
];

// ─── Page ────────────────────────────────────────────────────────────────────

export function Standards() {
  return (
    <article>
      <PageHeader
        title="Standards and ecosystem"
        subtitle="FHIR, C-CDA, and where Atlas sits in the landscape of TEFCA, QHINs, and patient apps."
      />

      {/* ── What Atlas speaks ──────────────────────────────────────────────── */}
      <section className="mb-10">
        <h2 className="mb-3 text-[20px] font-semibold leading-snug text-[#1d2433]">
          What Atlas speaks
        </h2>
        <p className="text-[15px] leading-[1.65] text-[#4a5168]">
          Atlas is FHIR-native at the core, with adapters for the other formats real-world
          clinical data arrives in. The internal canonical shape is FHIR R4 with US Core
          profiles where applicable. C-CDA and CDA documents are converted via Microsoft's
          open-source FHIR-Converter before entering the harmonization layer. PDFs and
          portal exports enter through the multi-pass extraction pipeline. Bundles can be
          exported in FHIR JSON, summary JSON, or plain Markdown.
        </p>
        <p className="mt-3 text-[14px] leading-[1.6] text-[#6b7390]">
          The principle: source-specific at the edge, standards-aligned at the core. Input
          format diversity is handled by adapters; the harmonized record stays FHIR-shaped
          regardless of where the data originated.
        </p>
      </section>

      {/* ── Standards alignment ────────────────────────────────────────────── */}
      <section className="mb-10">
        <h2 className="mb-1.5 text-[20px] font-semibold leading-snug text-[#1d2433]">
          Standards alignment
        </h2>
        <p className="mb-4 text-[14px] leading-relaxed text-[#6b7390]">
          Each input format has a defined adapter path into the canonical FHIR-shaped record.
        </p>
        <div className="rounded-xl border border-[#e7eaf2] bg-white px-5 pb-1 pt-2">
          {STANDARDS.map((s) => (
            <StandardRow key={s.label} {...s} />
          ))}
        </div>
      </section>

      {/* ── Where Atlas sits in the ecosystem ─────────────────────────────── */}
      <section className="mb-10">
        <h2 className="mb-3 text-[20px] font-semibold leading-snug text-[#1d2433]">
          Where Atlas sits in the ecosystem
        </h2>
        <p className="text-[15px] leading-[1.65] text-[#4a5168]">
          TEFCA, QHINs, Carequality, and CommonWell are increasingly making record movement
          work. Provider-to-provider exchange via participating networks is real and growing.
          What these networks don't do is organize or synthesize what moves. A Carequality
          record dump can arrive as dozens of encounter documents, multiple medication lists
          with conflicting active/inactive states, and duplicate lab results across sources.
          The records moved; the usability problem remains.
        </p>
        <p className="mt-4 text-[15px] leading-[1.65] text-[#4a5168]">
          Apple Health Records and CommonHealth consume FHIR from authenticated EHR
          endpoints. These are patient-mediated copies, not writable targets. They are valid
          Atlas source inputs, not substitutes for the harmonization layer.
        </p>
        <blockquote className="mt-5 rounded-r-lg border-l-[3px] border-[#5b76fe] bg-[#eef1ff] py-3 pl-4 pr-5">
          <p className="text-[15px] font-semibold leading-snug text-[#1d2433]">
            TEFCA moves records. Atlas organizes them — wherever they came from.
          </p>
        </blockquote>

        <div className="mt-6">
          <p className="mb-3 text-[13px] font-semibold uppercase tracking-wide text-[#9aa5c0]">
            Atlas's role in the exchange landscape
          </p>
          <ul className="ml-0 space-y-1.5 text-[14px] leading-[1.6] text-[#4a5168]">
            <li className="flex gap-3">
              <span className="mt-[7px] h-1.5 w-1.5 shrink-0 rounded-full bg-[#5b76fe]" />
              Ingest records that don't flow through TEFCA: paper, faxes, off-network
              providers, dental, mental health, foreign records, direct lab services
            </li>
            <li className="flex gap-3">
              <span className="mt-[7px] h-1.5 w-1.5 shrink-0 rounded-full bg-[#5b76fe]" />
              Synthesize records that do flow through TEFCA — turning a network record dump
              into a usable briefing with deduplicated facts, ranked by clinical relevance
            </li>
            <li className="flex gap-3">
              <span className="mt-[7px] h-1.5 w-1.5 shrink-0 rounded-full bg-[#5b76fe]" />
              Produce a portable clinical bundle that can travel to any application — not
              locked to Atlas's own surfaces
            </li>
          </ul>
        </div>

        {/* Actor comparison table */}
        <div className="mt-6 rounded-xl border border-[#e7eaf2] bg-white px-5 pb-1 pt-4">
          <div className="grid grid-cols-[1fr_1.2fr_1.4fr] gap-4 pb-2 border-b border-[#e7eaf2] text-[11px] font-semibold uppercase tracking-wide text-[#9aa5c0]">
            <span>Exchange actor</span>
            <span>What it does</span>
            <span>Atlas relationship</span>
          </div>
          {ECOSYSTEM_ACTORS.map((row) => (
            <EcosystemRow key={row.actor} {...row} />
          ))}
        </div>
      </section>

      {/* ── Open source ───────────────────────────────────────────────────── */}
      <section className="mb-10">
        <div className="flex gap-4 rounded-xl border border-[#e7eaf2] bg-white p-5">
          <div className="mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-[#eef1ff]">
            <Network size={18} className="text-[#5b76fe]" />
          </div>
          <div>
            <p className="text-[15px] font-semibold text-[#1d2433]">Open source</p>
            <p className="mt-2 text-[14px] leading-[1.6] text-[#4a5168]">
              Atlas is open source — the pipeline, adapters, agent tools, and evaluation
              harness all live in the repository. Built to be inspected, extended, and run
              on your own data. The FHIR-Converter integration, the C-CDA adapter, and the
              PDF extraction pipelines are all reviewable code, not black-box services.
            </p>
            <a
              href="https://github.com/blakethom8/ehi-ignite-challenge"
              target="_blank"
              rel="noopener noreferrer"
              className="mt-2.5 inline-flex items-center gap-1.5 text-[13px] font-semibold text-[#5b76fe] hover:underline"
            >
              github.com/blakethom8/ehi-ignite-challenge
              <ArrowRight size={13} />
            </a>
          </div>
        </div>
      </section>

      {/* ── What Atlas is not ─────────────────────────────────────────────── */}
      <section className="mb-10">
        <h2 className="mb-1.5 text-[20px] font-semibold leading-snug text-[#1d2433]">
          What Atlas explicitly is not
        </h2>
        <p className="mb-4 text-[14px] leading-relaxed text-[#6b7390]">
          Honest framing matters more than scope inflation.
        </p>
        <div className="rounded-xl border border-[#e7eaf2] bg-white px-5 pb-1 pt-2">
          <ul className="divide-y divide-[#f0f1f7]">
            <NotItem>
              <span className="font-semibold text-[#1d2433]">Not a TEFCA participant or QHIN.</span>{" "}
              Atlas is not a record-movement network and does not participate in exchange
              infrastructure.
            </NotItem>
            <NotItem>
              <span className="font-semibold text-[#1d2433]">Not an EHR.</span>{" "}
              No clinical workflow, order entry, scheduling, or prescribing. Atlas reads and
              organizes records; it does not generate them.
            </NotItem>
            <NotItem>
              <span className="font-semibold text-[#1d2433]">Not a HIE.</span>{" "}
              Atlas reads what health information exchanges produce. It doesn't replace them
              or compete with their network function.
            </NotItem>
            <NotItem>
              <span className="font-semibold text-[#1d2433]">Not a clinical decision support tool.</span>{" "}
              The assistant is a synthesis layer — it organizes and cites; it does not
              recommend diagnoses or treatments. Clinical judgment remains with the clinician.
            </NotItem>
          </ul>
        </div>
      </section>

      {/* ── Where to next ─────────────────────────────────────────────────── */}
      <section className="mb-2">
        <h2 className="mb-3 text-[20px] font-semibold leading-snug text-[#1d2433]">
          Where to next
        </h2>
        <div className="flex flex-col gap-2.5">
          <SectionLink
            label="Trustworthy AI"
            description="How the bundle architecture enforces trust properties across all applications."
            to="/using-atlas/trustworthy-ai"
          />
          <SectionLink
            label="Application overview"
            description="The four application surfaces and how each consumes the portable bundle."
            to="/using-atlas"
          />
          <SectionLink
            label="How records are harmonized"
            description="Deduplication, conflict detection, provenance edges, and cross-source validation."
            to="/using-atlas/harmonization"
          />
        </div>
      </section>
    </article>
  );
}
