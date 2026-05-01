import { useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import {
  ArrowRight,
  BookMarked,
  DollarSign,
  FileSearch,
  MessageSquareText,
  Pill,
  Search,
  ShieldCheck,
  Store,
  TestTubeDiagonal,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";

function withPatient(path: string, patientId: string | null): string {
  return patientId ? `${path}?patient=${patientId}` : path;
}

type Tone = "blue" | "green" | "orange" | "rose" | "slate";
type MarketStatus = "Preview" | "Concept";

interface MarketplaceModule {
  id: string;
  icon: LucideIcon;
  title: string;
  status: MarketStatus;
  category: string;
  audience: string;
  route: string;
  inputs: string[];
  outputs: string[];
  body: string;
  boundary: string;
  action: string;
  tone: Tone;
  recommended?: boolean;
}

const toneClasses: Record<Tone, string> = {
  blue: "bg-[#eef1ff] text-[#5b76fe]",
  green: "bg-[#c3faf5] text-[#187574]",
  orange: "bg-[#ffe6cd] text-[#744000]",
  rose: "bg-[#ffd8f4] text-[#7a285f]",
  slate: "bg-[#f5f6f8] text-[#555a6a]",
};

const marketplaceModules: MarketplaceModule[] = [
  {
    id: "trials",
    icon: Search,
    title: "Clinical Trial Match",
    status: "Preview",
    category: "Research",
    audience: "External opportunity",
    route: "/trials",
    inputs: ["Problems", "Labs", "Age", "Meds"],
    outputs: ["Eligibility signals", "Exclusions", "Share packet"],
    body: "Screens record facts against candidate eligibility criteria and highlights what needs verification.",
    boundary: "External search; patient consent required before sharing packet.",
    action: "Find trials",
    tone: "rose",
    recommended: true,
  },
  {
    id: "medication-access",
    icon: Pill,
    title: "Medication Access",
    status: "Preview",
    category: "Treatment access",
    audience: "External affordability",
    route: "/medication-access",
    inputs: ["Active therapies", "Rx fills", "Coverage context"],
    outputs: ["Affordability brief", "Program checklist", "Fulfillment plan"],
    body: "Uses medication context to organize price, assistance, and payer-friction workflows.",
    boundary: "May use pharmacy, coupon, manufacturer, or benefit data outside the private chart.",
    action: "Find access paths",
    tone: "green",
    recommended: true,
  },
  {
    id: "payer-check",
    icon: ShieldCheck,
    title: "Payer Coverage Check",
    status: "Concept",
    category: "Payer",
    audience: "Payer impact",
    route: "/payer-check",
    inputs: ["Diagnosis", "Meds", "Procedures", "Claims/EOBs"],
    outputs: ["Coverage brief", "Prior-auth checklist", "Appeal packet"],
    body: "Uses chart evidence to prepare benefits checks, prior authorization packets, and medical-necessity narratives.",
    boundary: "Outbound only after the patient reviews exactly which evidence supports the packet.",
    action: "Preview payer workflow",
    tone: "green",
    recommended: true,
  },
  {
    id: "grants",
    icon: DollarSign,
    title: "Grant Finder",
    status: "Concept",
    category: "Financial support",
    audience: "External support",
    route: "/grants",
    inputs: ["Diagnosis", "Meds", "Financial context"],
    outputs: ["Grant matches", "Document checklist", "Application path"],
    body: "Identifies disease foundations, assistance programs, and grant opportunities that fit the patient context.",
    boundary: "Requires explicit patient-supplied financial context; FHIR alone is not enough.",
    action: "Preview concept",
    tone: "orange",
  },
  {
    id: "research-opportunities",
    icon: BookMarked,
    title: "Research Opportunities",
    status: "Concept",
    category: "Research",
    audience: "External research",
    route: "/research-opportunities",
    inputs: ["Conditions", "Procedures", "Care timeline"],
    outputs: ["Study leads", "Recruitment packet", "Questions"],
    body: "Surfaces registries, studies, and patient communities where the record can support next-step research.",
    boundary: "Research outreach should stay patient-initiated and auditable.",
    action: "Preview concept",
    tone: "blue",
  },
  {
    id: "second-opinion",
    icon: MessageSquareText,
    title: "Second Opinion",
    status: "Concept",
    category: "Specialist review",
    audience: "Specialist marketplace",
    route: "/second-opinion",
    inputs: ["Chart summary", "Imaging/procedure history", "Questions"],
    outputs: ["Review packet", "Specialist questions", "Evidence appendix"],
    body: "Packages the FHIR Chart into a time-limited specialist review workspace with scoped facts and source evidence.",
    boundary: "Share packet must show exactly what the specialist can see and for how long.",
    action: "Build review packet",
    tone: "rose",
    recommended: true,
  },
  {
    id: "caregiver-sharing",
    icon: FileSearch,
    title: "Caregiver Packet",
    status: "Concept",
    category: "Sharing",
    audience: "Trusted helper",
    route: "/sharing",
    inputs: ["Summary", "Meds", "Questions", "Access limits"],
    outputs: ["Scoped packet", "Access terms", "Question guide"],
    body: "Creates a bounded chart view for family members, caregivers, or advocates who help the patient act on care tasks.",
    boundary: "Consent, duration, and revocation controls must be first-class.",
    action: "Scope sharing",
    tone: "slate",
  },
];

const defaultSelected = new Set(["trials", "medication-access", "payer-check", "second-opinion"]);
const categories = ["All", ...Array.from(new Set(marketplaceModules.map((module) => module.category)))];

function StatusBadge({ status }: { status: MarketStatus }) {
  const classes = status === "Preview" ? "bg-[#eef1ff] text-[#5b76fe]" : "bg-[#f5f6f8] text-[#667085]";
  return <span className={`rounded-full px-2.5 py-1 text-xs font-semibold ${classes}`}>{status}</span>;
}

function MarketplaceCard({
  module,
  patientId,
  selected,
  onToggle,
}: {
  module: MarketplaceModule;
  patientId: string | null;
  selected: boolean;
  onToggle: (moduleId: string) => void;
}) {
  const Icon = module.icon;

  return (
    <article
      className={`flex min-h-[380px] flex-col rounded-2xl bg-white p-5 shadow-[rgb(224_226_232)_0px_0px_0px_1px] ${
        selected ? "ring-2 ring-[#aab7ff]" : ""
      }`}
    >
      <div className="flex items-start justify-between gap-4">
        <div className={`flex h-11 w-11 items-center justify-center rounded-xl ${toneClasses[module.tone]}`}>
          <Icon size={20} />
        </div>
        <StatusBadge status={module.status} />
      </div>

      <div className="mt-5">
        <div className="flex flex-wrap items-center gap-2">
          <p className="text-[10px] font-semibold uppercase tracking-wider text-[#5b76fe]">{module.category}</p>
          {module.recommended ? (
            <span className="rounded-full bg-[#eef1ff] px-2 py-0.5 text-[10px] font-semibold text-[#5b76fe]">
              Recommended
            </span>
          ) : null}
        </div>
        <p className="mt-2 text-[10px] font-semibold uppercase tracking-wider text-[#a5a8b5]">{module.audience}</p>
        <h2 className="mt-1 text-lg font-semibold text-[#1c1c1e]">{module.title}</h2>
        <p className="mt-2 text-sm leading-6 text-[#667085]">{module.body}</p>
      </div>

      <div className="mt-5 grid gap-3">
        <div>
          <p className="text-[10px] font-semibold uppercase tracking-wider text-[#a5a8b5]">Requires</p>
          <div className="mt-2 flex flex-wrap gap-1.5">
            {module.inputs.map((input) => (
              <span key={input} className="rounded-full bg-[#f5f6f8] px-2 py-1 text-[11px] font-medium text-[#555a6a]">
                {input}
              </span>
            ))}
          </div>
        </div>
        <div>
          <p className="text-[10px] font-semibold uppercase tracking-wider text-[#a5a8b5]">Produces</p>
          <div className="mt-2 flex flex-wrap gap-1.5">
            {module.outputs.map((output) => (
              <span key={output} className="rounded-full bg-[#eef1ff] px-2 py-1 text-[11px] font-semibold text-[#5b76fe]">
                {output}
              </span>
            ))}
          </div>
        </div>
      </div>

      <p className="mt-4 rounded-xl bg-[#fafbff] px-3 py-2 text-xs leading-5 text-[#555a6a]">{module.boundary}</p>

      <div className="mt-auto flex items-center justify-between gap-3 pt-5">
        <button
          type="button"
          onClick={() => onToggle(module.id)}
          className={`rounded-full px-3 py-2 text-sm font-semibold transition-colors ${
            selected ? "bg-[#1c1c1e] text-white" : "bg-[#eef1ff] text-[#5b76fe] hover:bg-[#dfe4ff]"
          }`}
        >
          {selected ? "Shown in marketplace" : "Add to marketplace"}
        </button>
        <Link
          to={withPatient(module.route, patientId)}
          className="inline-flex items-center gap-1 text-sm font-semibold text-[#5b76fe] no-underline"
        >
          {module.action}
          <ArrowRight size={14} />
        </Link>
      </div>
    </article>
  );
}

function SelectedMarketplace({
  modules,
  patientId,
}: {
  modules: MarketplaceModule[];
  patientId: string | null;
}) {
  return (
    <section className="rounded-2xl bg-white p-5 shadow-[rgb(224_226_232)_0px_0px_0px_1px]">
      <div className="flex flex-col gap-2 md:flex-row md:items-end md:justify-between">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wider text-[#5b76fe]">Patient-selected marketplace</p>
          <h2 className="mt-1 text-xl font-semibold text-[#1c1c1e]">External modules visible on the main marketplace page</h2>
        </div>
        <p className="max-w-xl text-sm leading-6 text-[#667085]">
          This previews a configurable marketplace shelf. The key product point is that the patient chooses which outbound
          workflows are available and what chart evidence each can request.
        </p>
      </div>

      <div className="mt-5 grid gap-3 md:grid-cols-2 xl:grid-cols-4">
        {modules.map((module) => {
          const Icon = module.icon;
          return (
            <Link
              key={module.id}
              to={withPatient(module.route, patientId)}
              className="rounded-xl border border-[#dfe4ff] bg-[#fafbff] p-4 no-underline transition-colors hover:bg-[#f2f5ff]"
            >
              <div className="flex items-center justify-between gap-3">
                <div className={`flex h-9 w-9 items-center justify-center rounded-lg ${toneClasses[module.tone]}`}>
                  <Icon size={17} />
                </div>
                <StatusBadge status={module.status} />
              </div>
              <p className="mt-3 text-sm font-semibold text-[#1c1c1e]">{module.title}</p>
              <p className="mt-1 text-xs leading-5 text-[#667085]">{module.outputs[0]}</p>
            </Link>
          );
        })}
      </div>
    </section>
  );
}

export function Marketplace() {
  const [searchParams] = useSearchParams();
  const patientId = searchParams.get("patient");
  const [query, setQuery] = useState("");
  const [category, setCategory] = useState("All");
  const [selected, setSelected] = useState(defaultSelected);

  const filteredModules = useMemo(() => {
    const normalizedQuery = query.trim().toLowerCase();
    return marketplaceModules.filter((module) => {
      const matchesCategory = category === "All" || module.category === category;
      const searchableText = [
        module.title,
        module.category,
        module.audience,
        module.body,
        module.boundary,
        ...module.inputs,
        ...module.outputs,
      ]
        .join(" ")
        .toLowerCase();
      return matchesCategory && (!normalizedQuery || searchableText.includes(normalizedQuery));
    });
  }, [category, query]);

  const selectedModules = useMemo(() => marketplaceModules.filter((module) => selected.has(module.id)), [selected]);

  function toggleModule(moduleId: string) {
    setSelected((current) => {
      const next = new Set(current);
      if (next.has(moduleId)) {
        next.delete(moduleId);
      } else {
        next.add(moduleId);
      }
      return next;
    });
  }

  return (
    <main className="mx-auto max-w-7xl space-y-5 p-4 lg:p-6">
      <section className="rounded-3xl bg-white p-6 shadow-[rgb(224_226_232)_0px_0px_0px_1px] lg:p-8">
        <div className="flex flex-col gap-6 lg:flex-row lg:items-start lg:justify-between">
          <div className="max-w-3xl">
            <p className="inline-flex items-center gap-2 rounded-full bg-[#eef1ff] px-3 py-1 text-xs font-semibold uppercase tracking-wider text-[#5b76fe]">
              <Store size={13} />
              Marketplace inventory
            </p>
            <h1 className="mt-5 text-3xl font-semibold tracking-tight text-[#1c1c1e] lg:text-4xl">
              Choose external modules that can use the patient-owned FHIR Chart
            </h1>
            <p className="mt-3 text-base leading-7 text-[#667085]">
              Marketplace modules help patients act outside the care record: trials, medication access, payer coverage,
              grants, research programs, second opinions, and scoped caregiver support.
            </p>
          </div>
          <div className="rounded-2xl bg-[#fafbff] p-4 shadow-[rgb(224_226_232)_0px_0px_0px_1px] lg:min-w-[280px]">
            <div className="flex items-center gap-2">
              <ShieldCheck size={18} className="text-[#00b473]" />
              <p className="text-sm font-semibold text-[#1c1c1e]">Module contract</p>
            </div>
            <p className="mt-2 text-sm leading-6 text-[#667085]">
              Every module declares whether it leaves the private record workspace, what data it needs, and what evidence
              must stay attached to its output.
            </p>
          </div>
        </div>
      </section>

      <SelectedMarketplace modules={selectedModules} patientId={patientId} />

      <section className="rounded-[24px] border border-[#dfe4ff] bg-[#f7f8ff] p-5">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wider text-[#5b76fe]">Search marketplace</p>
            <h2 className="mt-1 text-xl font-semibold text-[#1c1c1e]">Available patient action modules</h2>
          </div>
          <label className="flex min-w-[280px] items-center gap-2 rounded-xl bg-white px-3 py-2 shadow-[rgb(224_226_232)_0px_0px_0px_1px]">
            <Search size={16} className="text-[#a5a8b5]" />
            <input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Search by goal, record input, or output"
              className="w-full bg-transparent text-sm text-[#1c1c1e] outline-none placeholder:text-[#a5a8b5]"
            />
          </label>
        </div>

        <div className="mt-4 flex flex-wrap gap-2">
          {categories.map((item) => (
            <button
              key={item}
              type="button"
              onClick={() => setCategory(item)}
              className={`rounded-full px-3 py-1.5 text-sm font-semibold transition-colors ${
                category === item ? "bg-[#1c1c1e] text-white" : "bg-white text-[#667085] hover:bg-[#eef1ff] hover:text-[#5b76fe]"
              }`}
            >
              {item}
            </button>
          ))}
        </div>

        <div className="mt-5 flex flex-wrap gap-1.5">
          <span className="rounded-full bg-white px-3 py-1.5 text-xs font-semibold text-[#667085]">
            {filteredModules.length} modules shown
          </span>
          <span className="rounded-full bg-white px-3 py-1.5 text-xs font-semibold text-[#667085]">
            {selectedModules.length} selected for marketplace
          </span>
        </div>

        <div className="mt-5 grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {filteredModules.map((module) => (
            <MarketplaceCard
              key={module.id}
              module={module}
              patientId={patientId}
              selected={selected.has(module.id)}
              onToggle={toggleModule}
            />
          ))}
        </div>
      </section>

      <section className="rounded-2xl bg-white p-5 shadow-[rgb(224_226_232)_0px_0px_0px_1px]">
        <div className="flex items-center gap-2">
          <FileSearch size={18} className="text-[#5b76fe]" />
          <h2 className="text-lg font-semibold text-[#1c1c1e]">Exploratory product thesis</h2>
        </div>
        <div className="mt-5 grid gap-3 md:grid-cols-3">
          {[
            ["Patient impact", "Find external help from a chart the patient already owns: trials, support programs, second opinions, and medication access paths."],
            ["Payer impact", "Turn source-backed FHIR facts into coverage packets that reduce prior-auth rework, appeal friction, and missing documentation."],
            ["Competition story", "Show that FHIR is not just a data format. It is a launch layer for focused, consent-aware workflows."],
          ].map(([title, body]) => (
            <div key={title} className="rounded-xl border border-[#e9eaef] p-4">
              <p className="text-sm font-semibold text-[#1c1c1e]">{title}</p>
              <p className="mt-2 text-sm leading-6 text-[#667085]">{body}</p>
            </div>
          ))}
        </div>
      </section>

      <section className="rounded-2xl bg-[#f7fffc] p-5 shadow-[rgb(224_226_232)_0px_0px_0px_1px]">
        <div className="flex items-center gap-2">
          <TestTubeDiagonal size={18} className="text-[#0f766e]" />
          <h2 className="text-lg font-semibold text-[#0f172a]">Phase 1 implementation posture</h2>
        </div>
        <p className="mt-2 max-w-4xl text-sm leading-6 text-[#35524d]">
          This inventory is intentionally a product scaffold. The cards route to existing working pages or concept
          workspaces while the long-term system adds module manifests, consent controls, external search, and publishing.
        </p>
      </section>
    </main>
  );
}
