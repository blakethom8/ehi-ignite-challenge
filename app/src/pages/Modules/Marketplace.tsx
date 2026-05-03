import { useMemo, useState } from "react";
import { Link, useLocation, useSearchParams } from "react-router-dom";
import {
  ArrowRight,
  BookMarked,
  CheckCircle2,
  DollarSign,
  FileSearch,
  LayoutGrid,
  MessageSquareText,
  Pill,
  Search,
  ShieldCheck,
  SlidersHorizontal,
  Star,
  Store,
  Table2,
  TestTubeDiagonal,
  Upload,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";

function withPatient(path: string, patientId: string | null): string {
  return patientId ? `${path}?patient=${patientId}` : path;
}

type Tone = "blue" | "green" | "orange" | "rose" | "slate";
type MarketStatus = "Preview" | "Concept";
type MarketplaceViewMode = "cards" | "table";

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

const FAVORITES_STORAGE_KEY = "ehi-marketplace-favorite-modules";
const PINNED_STORAGE_KEY = "ehi-marketplace-pinned-modules";
const defaultFavoriteIds = ["trials", "medication-access", "payer-check", "second-opinion", "grants", "research-opportunities", "caregiver-sharing"];
const defaultPinnedIds = ["trials", "medication-access", "payer-check", "second-opinion"];
const categories = ["All", ...Array.from(new Set(marketplaceModules.map((module) => module.category)))];

function loadModuleIds(storageKey: string, fallback: string[]): Set<string> {
  try {
    const raw = localStorage.getItem(storageKey);
    if (!raw) return new Set(fallback);
    const parsed = JSON.parse(raw) as unknown;
    if (Array.isArray(parsed)) return new Set(parsed.filter((id): id is string => typeof id === "string"));
    return new Set(fallback);
  } catch {
    return new Set(fallback);
  }
}

function saveModuleIds(storageKey: string, ids: Set<string>): void {
  try {
    localStorage.setItem(storageKey, JSON.stringify(Array.from(ids)));
    window.dispatchEvent(new Event("ehi-marketplace-workspace-updated"));
  } catch {
    // Local storage is progressive enhancement for the prototype workspace.
  }
}

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
          {selected ? "In favorites" : "Add favorite"}
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

function ViewModeToggle({
  viewMode,
  onChange,
}: {
  viewMode: MarketplaceViewMode;
  onChange: (mode: MarketplaceViewMode) => void;
}) {
  return (
    <div className="inline-flex rounded-xl bg-white p-1 shadow-[rgb(224_226_232)_0px_0px_0px_1px]">
      {[
        { mode: "cards" as const, label: "Cards", icon: LayoutGrid },
        { mode: "table" as const, label: "Table", icon: Table2 },
      ].map(({ mode, label, icon: Icon }) => (
        <button
          key={mode}
          type="button"
          onClick={() => onChange(mode)}
          className={`inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-sm font-semibold transition-colors ${
            viewMode === mode ? "bg-[#1c1c1e] text-white" : "text-[#667085] hover:bg-[#eef1ff] hover:text-[#5b76fe]"
          }`}
          aria-pressed={viewMode === mode}
        >
          <Icon size={14} />
          {label}
        </button>
      ))}
    </div>
  );
}

function MarketplaceTable({
  modules,
  patientId,
  favoriteIds,
  pinnedIds,
  onToggle,
  onTogglePin,
}: {
  modules: MarketplaceModule[];
  patientId: string | null;
  favoriteIds: Set<string>;
  pinnedIds: Set<string>;
  onToggle: (moduleId: string) => void;
  onTogglePin: (moduleId: string) => void;
}) {
  return (
    <div className="mt-5 overflow-x-auto rounded-2xl bg-white shadow-[rgb(224_226_232)_0px_0px_0px_1px]">
      <table className="w-full min-w-[1080px] border-collapse text-[12px]">
        <thead>
          <tr className="bg-[#fafafa] text-left text-[10px] font-semibold uppercase tracking-wider text-[#8d92a3]">
            <th className="border-b border-[#eef0f5] px-3 py-2">Module</th>
            <th className="border-b border-[#eef0f5] px-3 py-2">Status</th>
            <th className="border-b border-[#eef0f5] px-3 py-2">Category</th>
            <th className="border-b border-[#eef0f5] px-3 py-2">Requires</th>
            <th className="border-b border-[#eef0f5] px-3 py-2">Produces</th>
            <th className="border-b border-[#eef0f5] px-3 py-2">Boundary</th>
            <th className="border-b border-[#eef0f5] px-3 py-2">Favorite</th>
            <th className="border-b border-[#eef0f5] px-3 py-2">Pinned</th>
            <th className="border-b border-[#eef0f5] px-3 py-2" />
          </tr>
        </thead>
        <tbody>
          {modules.map((module) => {
            const isFavorite = favoriteIds.has(module.id);
            const isPinned = pinnedIds.has(module.id);
            return (
              <tr key={module.id} className="hover:bg-[#fafbff]">
                <td className="border-b border-[#f2f4f8] px-3 py-2">
                  <Link to={withPatient(module.route, patientId)} className="font-semibold text-[#1c1c1e] no-underline hover:text-[#5b76fe]">
                    {module.title}
                  </Link>
                  {module.recommended ? <span className="ml-2 text-[10px] font-semibold uppercase text-[#5b76fe]">Recommended</span> : null}
                </td>
                <td className="border-b border-[#f2f4f8] px-3 py-2 text-[#555a6a]">{module.status}</td>
                <td className="border-b border-[#f2f4f8] px-3 py-2 text-[#555a6a]">{module.category}</td>
                <td className="border-b border-[#f2f4f8] px-3 py-2 text-[#555a6a]">{module.inputs.join(", ")}</td>
                <td className="border-b border-[#f2f4f8] px-3 py-2 text-[#555a6a]">{module.outputs.join(", ")}</td>
                <td className="border-b border-[#f2f4f8] px-3 py-2 text-[#667085]">{module.boundary}</td>
                <td className="border-b border-[#f2f4f8] px-3 py-2">
                  <button
                    type="button"
                    onClick={() => onToggle(module.id)}
                    className={`rounded-md px-2 py-1 text-[11px] font-semibold transition-colors ${
                      isFavorite ? "bg-[#1c1c1e] text-white" : "bg-white text-[#5b76fe] shadow-[rgb(224_226_232)_0px_0px_0px_1px] hover:bg-[#eef1ff]"
                    }`}
                  >
                    {isFavorite ? "Yes" : "Add"}
                  </button>
                </td>
                <td className="border-b border-[#f2f4f8] px-3 py-2">
                  <button
                    type="button"
                    onClick={() => onTogglePin(module.id)}
                    className={`rounded-md px-2 py-1 text-[11px] font-semibold transition-colors ${
                      isPinned ? "bg-[#eef1ff] text-[#5b76fe]" : "bg-white text-[#667085] shadow-[rgb(224_226_232)_0px_0px_0px_1px] hover:bg-[#eef1ff]"
                    }`}
                  >
                    {isPinned ? "Top" : "Pin"}
                  </button>
                </td>
                <td className="border-b border-[#f2f4f8] px-3 py-2 text-right">
                  <Link to={withPatient(module.route, patientId)} className="font-semibold text-[#5b76fe] no-underline">{module.action}</Link>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function WorkspaceFavorites({
  modules,
  patientId,
  favoriteIds,
  pinnedIds,
  onToggleFavorite,
  onTogglePin,
}: {
  modules: MarketplaceModule[];
  patientId: string | null;
  favoriteIds: Set<string>;
  pinnedIds: Set<string>;
  onToggleFavorite: (moduleId: string) => void;
  onTogglePin: (moduleId: string) => void;
}) {
  const favoriteModules = modules.filter((module) => favoriteIds.has(module.id));
  const sortedFavoriteModules = [
    ...favoriteModules.filter((module) => pinnedIds.has(module.id)),
    ...favoriteModules.filter((module) => !pinnedIds.has(module.id)),
  ];

  return (
    <main className="mx-auto max-w-7xl space-y-4 p-4 lg:p-5">
      <section className="rounded-2xl bg-white p-5 shadow-[rgb(224_226_232)_0px_0px_0px_1px]">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
          <div className="max-w-3xl">
            <p className="inline-flex items-center gap-2 rounded-full bg-[#eef1ff] px-3 py-1 text-xs font-semibold uppercase tracking-wider text-[#5b76fe]">
              <Star size={13} />
              Workspace favorites
            </p>
            <h1 className="mt-3 text-2xl font-semibold tracking-tight text-[#1c1c1e] lg:text-3xl">
              Favorite modules
            </h1>
            <p className="mt-2 text-sm leading-6 text-[#667085]">
              Manage the modules saved to this workspace and choose which ones stay pinned in the top navigation.
            </p>
          </div>
          <div className="grid min-w-[220px] grid-cols-2 gap-2">
            <div className="rounded-xl bg-[#fafbff] px-4 py-3 shadow-[rgb(224_226_232)_0px_0px_0px_1px]">
              <p className="text-xs font-semibold uppercase tracking-wider text-[#667085]">Favorites</p>
              <p className="mt-1 text-2xl font-semibold text-[#1c1c1e]">{favoriteModules.length}</p>
            </div>
            <div className="rounded-xl bg-[#fafbff] px-4 py-3 shadow-[rgb(224_226_232)_0px_0px_0px_1px]">
              <p className="text-xs font-semibold uppercase tracking-wider text-[#667085]">Pinned</p>
              <p className="mt-1 text-2xl font-semibold text-[#1c1c1e]">{favoriteModules.filter((module) => pinnedIds.has(module.id)).length}</p>
            </div>
          </div>
        </div>
      </section>

      <section className="rounded-2xl bg-white p-5 shadow-[rgb(224_226_232)_0px_0px_0px_1px]">
        <div className="flex flex-col gap-2 md:flex-row md:items-end md:justify-between">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wider text-[#5b76fe]">Favorite modules</p>
            <h2 className="mt-1 text-xl font-semibold text-[#1c1c1e]">Extended workspace list</h2>
          </div>
          <p className="max-w-xl text-sm leading-6 text-[#667085]">
            Favorites can be used often without taking over the main navigation. Pin only the few modules that should be
            one click away.
          </p>
        </div>

        <div className="mt-5 overflow-x-auto rounded-xl border border-[#e9eaef]">
          <table className="w-full min-w-[920px] border-collapse text-[12px]">
            <thead>
              <tr className="bg-[#fafafa] text-left text-[10px] font-semibold uppercase tracking-wider text-[#8d92a3]">
                <th className="border-b border-[#eef0f5] px-3 py-2">Module</th>
                <th className="border-b border-[#eef0f5] px-3 py-2">Category</th>
                <th className="border-b border-[#eef0f5] px-3 py-2">Produces</th>
                <th className="border-b border-[#eef0f5] px-3 py-2">Top nav</th>
                <th className="border-b border-[#eef0f5] px-3 py-2" />
              </tr>
            </thead>
            <tbody>
              {sortedFavoriteModules.map((module) => {
                const isPinned = pinnedIds.has(module.id);
                return (
                  <tr key={module.id} className="hover:bg-[#fafbff]">
                    <td className="border-b border-[#f2f4f8] px-3 py-2">
                      <Link to={withPatient(module.route, patientId)} className="font-semibold text-[#1c1c1e] no-underline hover:text-[#5b76fe]">
                        {module.title}
                      </Link>
                    </td>
                    <td className="border-b border-[#f2f4f8] px-3 py-2 text-[#555a6a]">{module.category}</td>
                    <td className="border-b border-[#f2f4f8] px-3 py-2 text-[#555a6a]">{module.outputs.join(", ")}</td>
                    <td className="border-b border-[#f2f4f8] px-3 py-2">
                      <button
                        type="button"
                        onClick={() => onTogglePin(module.id)}
                        className={`rounded-md px-2 py-1 text-[11px] font-semibold transition-colors ${
                          isPinned ? "bg-[#eef1ff] text-[#5b76fe]" : "bg-white text-[#667085] shadow-[rgb(224_226_232)_0px_0px_0px_1px] hover:bg-[#eef1ff]"
                        }`}
                      >
                        {isPinned ? "Pinned" : "Pin"}
                      </button>
                    </td>
                    <td className="border-b border-[#f2f4f8] px-3 py-2 text-right">
                      <button
                        type="button"
                        onClick={() => onToggleFavorite(module.id)}
                        className="text-[11px] font-semibold text-[#667085] hover:text-[#1c1c1e]"
                      >
                        Remove
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </section>

      <section className="grid gap-4 md:grid-cols-2">
        {[
          { title: "Explore Modules", body: "Browse the full marketplace and add modules into this workspace.", icon: Store, to: "/marketplace" },
          { title: "Create Module", body: "Draft a new workflow, declare required chart inputs, and define the output contract.", icon: SlidersHorizontal, to: "/marketplace/publish" },
        ].map((item) => {
          const Icon = item.icon;
          return (
            <Link key={item.title} to={withPatient(item.to, patientId)} className="rounded-2xl bg-white p-5 no-underline shadow-[rgb(224_226_232)_0px_0px_0px_1px] hover:bg-[#fafbff]">
              <div className="flex items-center gap-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-[#eef1ff] text-[#5b76fe]">
                  <Icon size={18} />
                </div>
                <div>
                  <p className="text-base font-semibold text-[#1c1c1e]">{item.title}</p>
                  <p className="mt-1 text-sm leading-6 text-[#667085]">{item.body}</p>
                </div>
              </div>
            </Link>
          );
        })}
      </section>
    </main>
  );
}

function MarketplaceOverview({ patientId }: { patientId: string | null }) {
  return (
    <main className="mx-auto max-w-7xl space-y-4 p-4 lg:p-5">
      <section className="rounded-2xl bg-white p-5 shadow-[rgb(224_226_232)_0px_0px_0px_1px]">
        <div className="flex flex-col gap-5 lg:flex-row lg:items-center lg:justify-between">
          <div className="max-w-3xl">
            <p className="inline-flex items-center gap-2 rounded-full bg-[#eef1ff] px-3 py-1 text-xs font-semibold uppercase tracking-wider text-[#5b76fe]">
              <Store size={13} />
              Marketplace overview
            </p>
            <h1 className="mt-3 text-2xl font-semibold tracking-tight text-[#1c1c1e] lg:text-3xl">
              Use your health record with trusted modules
            </h1>
            <p className="mt-2 text-sm leading-6 text-[#667085]">
              Marketplace modules can review your patient-owned chart, help complete focused workflows, and prepare
              packets for outside people or services. Any module that acts outside the private record workspace should
              make the requested data, destination, and saved output clear before anything is shared.
            </p>
          </div>
          <div className="rounded-xl bg-[#fafbff] p-4 shadow-[rgb(224_226_232)_0px_0px_0px_1px] lg:max-w-[360px]">
            <div className="flex items-center gap-2">
              <ShieldCheck size={16} className="text-[#00b473]" />
              <p className="text-sm font-semibold text-[#1c1c1e]">Patient-controlled exchange</p>
            </div>
            <p className="mt-2 text-xs leading-5 text-[#667085]">
              This is the bridge between private clinical data and the outside world: trials, second opinions, payer
              packets, affordability programs, research, and caregiver support.
            </p>
          </div>
        </div>
      </section>

      <section className="grid gap-4 md:grid-cols-3">
        {[
          {
            icon: FileSearch,
            title: "Review your data",
            body: "Modules read scoped chart facts, source notes, and patient context to produce a focused review.",
          },
          {
            icon: CheckCircle2,
            title: "Act on your behalf",
            body: "A module may prepare searches, packets, checklists, or outreach steps for a specific real-world workflow.",
          },
          {
            icon: Upload,
            title: "Share only with consent",
            body: "Before data leaves the workspace, the patient should see what is shared, who receives it, and what is saved.",
          },
        ].map((item) => {
          const Icon = item.icon;
          return (
            <article key={item.title} className="rounded-2xl bg-white p-5 shadow-[rgb(224_226_232)_0px_0px_0px_1px]">
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-[#eef1ff] text-[#5b76fe]">
                <Icon size={18} />
              </div>
              <h2 className="mt-4 text-base font-semibold text-[#1c1c1e]">{item.title}</h2>
              <p className="mt-2 text-sm leading-6 text-[#667085]">{item.body}</p>
            </article>
          );
        })}
      </section>

      <section className="rounded-2xl bg-white p-5 shadow-[rgb(224_226_232)_0px_0px_0px_1px]">
        <div className="grid gap-5 lg:grid-cols-[0.9fr_1.1fr]">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wider text-[#5b76fe]">Transparency contract</p>
            <h2 className="mt-1 text-xl font-semibold text-[#1c1c1e]">Every module should declare its data behavior</h2>
            <p className="mt-2 text-sm leading-6 text-[#667085]">
              The module contract is the product promise: patients and care teams should know what the module needs,
              whether it contacts an outside party, and what artifact comes back into the record workspace.
            </p>
          </div>
          <div className="overflow-hidden rounded-xl border border-[#e9eaef]">
            <table className="w-full border-collapse text-sm">
              <tbody>
                {[
                  ["Data requested", "Chart facts, uploaded files, patient context, or generated summaries."],
                  ["Destination", "Private workspace only, patient download, clinician packet, or external service."],
                  ["Saved output", "A review, checklist, packet, match list, or activity log with evidence attached."],
                  ["Patient control", "Consent, expiration, revocation, and audit trail should be visible."],
                ].map(([label, body]) => (
                  <tr key={label} className="border-b border-[#f2f4f8] last:border-b-0">
                    <td className="w-44 bg-[#fafafa] px-3 py-3 text-xs font-semibold uppercase tracking-wider text-[#667085]">
                      {label}
                    </td>
                    <td className="px-3 py-3 text-[#555a6a]">{body}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </section>

      <section className="grid gap-4 md:grid-cols-2">
        {[
          { title: "Explore modules", body: "Browse available modules and choose which ones belong in your workspace.", to: "/marketplace", icon: Store },
          { title: "Configure sharing", body: "Review access, packet scope, and sharing controls for module workflows.", to: "/marketplace/settings", icon: SlidersHorizontal },
        ].map((item) => {
          const Icon = item.icon;
          return (
            <Link key={item.title} to={withPatient(item.to, patientId)} className="rounded-2xl bg-white p-5 no-underline shadow-[rgb(224_226_232)_0px_0px_0px_1px] hover:bg-[#fafbff]">
              <div className="flex items-center gap-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-[#eef1ff] text-[#5b76fe]">
                  <Icon size={18} />
                </div>
                <div>
                  <p className="text-base font-semibold text-[#1c1c1e]">{item.title}</p>
                  <p className="mt-1 text-sm leading-6 text-[#667085]">{item.body}</p>
                </div>
              </div>
            </Link>
          );
        })}
      </section>
    </main>
  );
}

export function Marketplace() {
  const location = useLocation();
  const [searchParams] = useSearchParams();
  const patientId = searchParams.get("patient");
  const [query, setQuery] = useState("");
  const [category, setCategory] = useState("All");
  const [favoriteIds, setFavoriteIds] = useState(() => loadModuleIds(FAVORITES_STORAGE_KEY, defaultFavoriteIds));
  const [pinnedIds, setPinnedIds] = useState(() => loadModuleIds(PINNED_STORAGE_KEY, defaultPinnedIds));
  const [viewMode, setViewMode] = useState<MarketplaceViewMode>("table");

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

  const favoriteModules = useMemo(() => marketplaceModules.filter((module) => favoriteIds.has(module.id)), [favoriteIds]);

  function toggleModule(moduleId: string) {
    setFavoriteIds((current) => {
      const next = new Set(current);
      if (next.has(moduleId)) {
        next.delete(moduleId);
        setPinnedIds((currentPinned) => {
          const nextPinned = new Set(currentPinned);
          nextPinned.delete(moduleId);
          saveModuleIds(PINNED_STORAGE_KEY, nextPinned);
          return nextPinned;
        });
      } else {
        next.add(moduleId);
      }
      saveModuleIds(FAVORITES_STORAGE_KEY, next);
      return next;
    });
  }

  function togglePinned(moduleId: string) {
    setPinnedIds((current) => {
      const next = new Set(current);
      if (next.has(moduleId)) {
        next.delete(moduleId);
      } else {
        next.add(moduleId);
        setFavoriteIds((currentFavorites) => {
          const nextFavorites = new Set(currentFavorites);
          nextFavorites.add(moduleId);
          saveModuleIds(FAVORITES_STORAGE_KEY, nextFavorites);
          return nextFavorites;
        });
      }
      saveModuleIds(PINNED_STORAGE_KEY, next);
      return next;
    });
  }

  if (location.pathname.startsWith("/marketplace/overview")) {
    return <MarketplaceOverview patientId={patientId} />;
  }

  if (location.pathname.startsWith("/marketplace/workspace")) {
    return (
      <WorkspaceFavorites
        modules={marketplaceModules}
        patientId={patientId}
        favoriteIds={favoriteIds}
        pinnedIds={pinnedIds}
        onToggleFavorite={toggleModule}
        onTogglePin={togglePinned}
      />
    );
  }

  return (
    <main className="mx-auto max-w-7xl space-y-4 p-4 lg:p-5">
      <section className="rounded-2xl bg-white p-5 shadow-[rgb(224_226_232)_0px_0px_0px_1px]">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
          <div className="max-w-3xl">
            <p className="inline-flex items-center gap-2 rounded-full bg-[#eef1ff] px-3 py-1 text-xs font-semibold uppercase tracking-wider text-[#5b76fe]">
              <Store size={13} />
              Marketplace inventory
            </p>
            <h1 className="mt-3 text-2xl font-semibold tracking-tight text-[#1c1c1e] lg:text-3xl">
              Explore modules that can use the patient-owned FHIR Chart
            </h1>
            <p className="mt-2 text-sm leading-6 text-[#667085]">
              Marketplace modules help patients act outside the care record: trials, medication access, payer coverage,
              grants, research programs, second opinions, and scoped caregiver support.
            </p>
          </div>
          <div className="rounded-xl bg-[#fafbff] p-3 shadow-[rgb(224_226_232)_0px_0px_0px_1px] lg:max-w-[360px]">
            <div className="flex items-center gap-2">
              <ShieldCheck size={16} className="text-[#00b473]" />
              <p className="text-sm font-semibold text-[#1c1c1e]">Module contract</p>
            </div>
            <p className="mt-1.5 text-xs leading-5 text-[#667085]">
              Every module declares whether it leaves the private record workspace, what data it needs, and what evidence
              must stay attached to its output.
            </p>
          </div>
        </div>
      </section>

      <section className="rounded-[24px] border border-[#dfe4ff] bg-[#f7f8ff] p-5">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wider text-[#5b76fe]">Search marketplace</p>
            <h2 className="mt-1 text-xl font-semibold text-[#1c1c1e]">Available patient action modules</h2>
          </div>
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
            <label className="flex min-w-[280px] items-center gap-2 rounded-xl bg-white px-3 py-2 shadow-[rgb(224_226_232)_0px_0px_0px_1px]">
              <Search size={16} className="text-[#a5a8b5]" />
              <input
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="Search by goal, record input, or output"
                className="w-full bg-transparent text-sm text-[#1c1c1e] outline-none placeholder:text-[#a5a8b5]"
              />
            </label>
            <ViewModeToggle viewMode={viewMode} onChange={setViewMode} />
          </div>
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
            {favoriteModules.length} favorites in workspace
          </span>
        </div>

        {viewMode === "cards" ? (
          <div className="mt-5 grid gap-4 md:grid-cols-2 xl:grid-cols-3">
            {filteredModules.map((module) => (
              <MarketplaceCard
                key={module.id}
                module={module}
                patientId={patientId}
                selected={favoriteIds.has(module.id)}
                onToggle={toggleModule}
              />
            ))}
          </div>
        ) : (
          <MarketplaceTable
            modules={filteredModules}
            patientId={patientId}
            favoriteIds={favoriteIds}
            pinnedIds={pinnedIds}
            onToggle={toggleModule}
            onTogglePin={togglePinned}
          />
        )}
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
