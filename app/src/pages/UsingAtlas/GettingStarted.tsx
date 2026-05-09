import { Link } from "react-router-dom";
import {
  ArrowRight,
  Blocks,
  BookOpen,
  Download,
  FileText,
  GitBranch,
  GitMerge,
  Globe,
  LineChart,
  Package,
  ShieldCheck,
  Sparkles,
} from "lucide-react";
import { PageHeader } from "./components/PageHeader";
import { PipelineDiagram } from "./components/PipelineDiagram";
import { SECTION_PAGES } from "./components/SectionNav";

// ─── Application surface card ────────────────────────────────────────────────

interface SurfaceCardProps {
  icon: React.ComponentType<{ size?: number; className?: string }>;
  label: string;
  role: string;
  body: string;
}

function SurfaceCard({ icon: Icon, label, role, body }: SurfaceCardProps) {
  return (
    <div className="flex flex-col rounded-xl border border-[#e7eaf2] bg-white p-5">
      <div className="mb-3 flex h-9 w-9 items-center justify-center rounded-lg bg-[#eef1ff]">
        <Icon size={18} className="text-[#5b76fe]" />
      </div>
      <p className="text-base font-semibold text-[#1d2433]">{label}</p>
      <p className="mt-0.5 text-[11px] font-semibold uppercase tracking-wide text-[#5b76fe]">{role}</p>
      <p className="mt-2.5 flex-1 text-sm leading-relaxed text-[#4a5168]">{body}</p>
    </div>
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

// ─── Page-list item (mirrors sidebar, visible in main content) ────────────────

interface PageListItemProps {
  num: string;
  label: string;
  description: string;
  available: boolean;
  icon: React.ComponentType<{ size?: number; className?: string }>;
  path: string;
}

function PageListItem({ num, label, description, available, icon: Icon, path }: PageListItemProps) {
  const inner = (
    <>
      <span className="text-[10px] font-semibold text-[#9aa5c0]">{num}</span>
      <Icon
        size={14}
        className={`shrink-0 ${available ? "text-[#5b76fe]" : "text-[#c5c9d9]"}`}
      />
      <div className="min-w-0 flex-1">
        <p className={`text-sm font-semibold ${available ? "text-[#1d2433]" : "text-[#9aa5c0]"}`}>
          {label}
          {!available && (
            <span className="ml-2 rounded-full bg-[#f0f1f7] px-1.5 py-0.5 text-[9px] font-semibold uppercase tracking-wide text-[#9aa5c0]">
              Coming soon
            </span>
          )}
        </p>
        <p className="text-sm text-[#6b7390]">{description}</p>
      </div>
    </>
  );

  if (available) {
    return (
      <Link
        to={path}
        className="group flex items-center gap-3 rounded-lg border border-[#e7eaf2] bg-white px-4 py-3 transition-colors hover:border-[#cfd7ff]"
      >
        {inner}
        <ArrowRight
          size={14}
          className="shrink-0 text-[#c5c9d9] transition-all group-hover:translate-x-0.5 group-hover:text-[#5b76fe]"
        />
      </Link>
    );
  }

  return (
    <div className="flex items-center gap-3 rounded-lg border border-[#f0f1f7] bg-[#fafbfc] px-4 py-3 opacity-60">
      {inner}
    </div>
  );
}

// ─── Application surfaces data ───────────────────────────────────────────────

const APPLICATION_SURFACES: SurfaceCardProps[] = [
  {
    icon: LineChart,
    label: "FHIR Charts",
    role: "Visualization layer",
    body: "Clinical charts and structured views built natively on FHIR — timelines, safety panels, medication histories. Familiar to anyone who's used a chart system, and portable across applications.",
  },
  {
    icon: Sparkles,
    label: "Clinical Insights",
    role: "Internal agent harness",
    body: "Atlas's own AI assistant: full bundle access, cited Q&A, and evidence packets assembled from validated facts. The reasoning layer Atlas builds in-house.",
  },
  {
    icon: Download,
    label: "Bundle Export",
    role: "Portable record",
    body: "Download the structured clinical bundle as a portable package. Take your record to a new specialist, plug it into another application, or use it with any agent or tool you choose.",
  },
  {
    icon: Blocks,
    label: "Marketplace",
    role: "Skills + modules",
    body: "A controlled-access space for skills and modules — modeled after open-skills patterns like Claude Skills and Codex. The bundle stays scoped; skills add web search, specialized analysis, or domain workflows without raw data exposure.",
  },
];

// ─── Page ────────────────────────────────────────────────────────────────────

export function GettingStarted() {
  const sectionPageIcons: Record<string, React.ComponentType<{ size?: number; className?: string }>> = {
    "/using-atlas": BookOpen,
    "/using-atlas/pipeline": GitBranch,
    "/using-atlas/pdf-extraction": FileText,
    "/using-atlas/harmonization": GitMerge,
    "/using-atlas/trustworthy-ai": ShieldCheck,
    "/using-atlas/standards": Globe,
  };

  return (
    <article>
      <PageHeader
        title="Get started"
        subtitle="What Atlas does, what's inside, and where to look first."
      />

      {/* ── What Atlas does ─────────────────────────────────────────────── */}
      <section className="mb-10">
        <h2 className="mb-3 text-[20px] font-semibold leading-snug text-[#1d2433]">
          What Atlas does
        </h2>
        <p className="text-[16px] leading-[1.6] text-[#1d2433]">
          <span className="font-semibold">We compile and integrate your health data, making it usable for AI.</span>{" "}
          <span className="text-[#4a5168]">
            Fragmented Single Patient EHI exports — FHIR bundles, C-CDAs, PDFs, portal downloads — become
            one source-backed clinical record where every fact knows where it came from.
          </span>
        </p>
        <p className="mt-4 text-[16px] leading-[1.6] text-[#1d2433]">
          <span className="font-semibold">Then we bundle it for portable, secure use across applications.</span>{" "}
          <span className="text-[#4a5168]">
            Atlas produces a structured clinical package with built-in access controls — deployable,
            storable, and ready to be consumed by AI agents, exports, or any application built on top.
            The pipeline produces; applications consume.
          </span>
        </p>
        <p className="mt-4 text-[14px] leading-[1.6] text-[#6b7390]">
          Atlas is open source — built to be inspected, extended, and run on your own data.
        </p>
        <blockquote className="mt-5 rounded-r-lg border-l-[3px] border-[#5b76fe] bg-[#eef1ff] py-3 pl-4 pr-5">
          <p className="text-[15px] font-semibold leading-snug text-[#1d2433]">
            Parse once. Structure once. Validate once. Cite forever.
          </p>
        </blockquote>
      </section>

      {/* ── Pipeline at a glance ────────────────────────────────────────── */}
      <section className="mb-10">
        <h2 className="mb-1.5 text-[20px] font-semibold leading-snug text-[#1d2433]">
          The pipeline at a glance
        </h2>
        <p className="mb-5 text-sm text-[#6b7390]">
          Four stages, from source files to a portable clinical bundle. Applications — Atlas's own
          and third-party — sit on top.
        </p>
        <PipelineDiagram />
        <p className="mt-4 text-sm leading-relaxed text-[#6b7390]">
          The full data-flow walkthrough — including source classification states, adapter
          architecture, and the provenance graph schema — is in{" "}
          <Link to="/using-atlas/pipeline" className="text-[#5b76fe] hover:underline">
            The pipeline
          </Link>
          .
        </p>
      </section>

      {/* ── Application overview ────────────────────────────────────────── */}
      <section className="mb-10">
        <h2 className="mb-1.5 text-[20px] font-semibold leading-snug text-[#1d2433]">
          Application overview
        </h2>
        <p className="mb-5 text-sm leading-relaxed text-[#6b7390]">
          Four surfaces sit on top of the bundle, each with a different access posture and use case.
          The pipeline produces; these consume.
        </p>
        <div className="relative grid gap-4 sm:grid-cols-2">
          {APPLICATION_SURFACES.map((surface) => (
            <SurfaceCard key={surface.label} {...surface} />
          ))}
          {/* Center connector — visually ties all four surfaces to the bundle */}
          <div
            className="pointer-events-none absolute left-1/2 top-1/2 hidden -translate-x-1/2 -translate-y-1/2 sm:flex"
            aria-hidden="true"
          >
            <div className="flex items-center gap-1.5 rounded-full border border-[#cfd7ff] bg-white px-3 py-1.5 shadow-[0_2px_10px_rgba(91,118,254,0.12)]">
              <Package size={13} className="text-[#5b76fe]" />
              <span className="text-[10px] font-bold uppercase tracking-[0.14em] text-[#5b76fe]">
                Bundle
              </span>
            </div>
          </div>
        </div>
      </section>

      {/* ── Where to look first ─────────────────────────────────────────── */}
      <section className="mb-10">
        <h2 className="mb-1.5 text-[20px] font-semibold leading-snug text-[#1d2433]">
          Where to look first
        </h2>
        <p className="mb-5 text-sm text-[#6b7390]">
          Three paths in, depending on what you want to evaluate.
        </p>
        <div className="flex flex-col gap-2.5">
          <SectionLink
            label="See data flow through the pipeline"
            description="End-to-end walkthrough of all four stages with live screen references."
            to="/using-atlas/pipeline"
          />
          <SectionLink
            label="Open the patient explorer"
            description="Working prototype across 1,180 synthetic patients — safety panel, medications, labs, timeline."
            to="/explorer"
          />
          <SectionLink
            label="Read the Phase 1 submission"
            description="The full design narrative: problem framing, architecture decisions, trustworthy-AI design."
            to="/analysis"
          />
        </div>
      </section>

      {/* ── What this section covers ─────────────────────────────────────── */}
      <section className="mb-2">
        <h2 className="mb-1.5 text-[20px] font-semibold leading-snug text-[#1d2433]">
          What this section covers
        </h2>
        <p className="mb-5 text-sm text-[#6b7390]">
          Six pages, ordered to read like an argument from "what is it" to "how does it fit in the
          ecosystem."
        </p>
        <div className="flex flex-col gap-2">
          {SECTION_PAGES.map((page, i) => {
            const Icon = sectionPageIcons[page.path] ?? BookOpen;
            return (
              <PageListItem
                key={page.path}
                num={String(i + 1).padStart(2, "0")}
                label={page.label}
                description={page.description}
                available={page.available}
                icon={Icon}
                path={page.path}
              />
            );
          })}
        </div>
      </section>
    </article>
  );
}
