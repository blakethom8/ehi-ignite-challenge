import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, NavLink, useLocation, useNavigate, useSearchParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import {
  Activity,
  Archive,
  BookMarked,
  CalendarDays,
  ChevronDown,
  ChevronRight,
  ChevronsLeft,
  ChevronsRight,
  ClipboardCheck,
  Database,
  DatabaseZap,
  FileJson2,
  FileSearch,
  GraduationCap,
  Heart,
  Layers3,
  MessageSquareText,
  Pill,
  Search,
  Share2,
  ShieldAlert,
  SlidersHorizontal,
  Star,
  Store,
  Stethoscope,
  TestTubeDiagonal,
  UserRound,
  X,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { api } from "../api/client";
import { useFavorites } from "../hooks/useFavorites";
import { CommandPalette } from "./CommandPalette";
import type { PatientListItem, PatientRiskSummary } from "../types";

interface LayoutProps {
  children: React.ReactNode;
}

type FilterMode = "all" | "high_risk" | "needs_review";
type AppEnvironment = "platform" | "record" | "aggregator" | "clinical" | "marketplace" | "trials" | "medication" | "sharing" | "analysis" | "catalog";
type TopArea = "platform" | "record" | "aggregator" | "clinical" | "marketplace" | "internal";

interface NavItem {
  to: string;
  label: string;
  icon: LucideIcon;
  description: string;
  children?: NavItem[];
}

interface NavGroup {
  label: string;
  items: NavItem[];
  advanced?: boolean;
}

interface ModuleMapItem {
  label: string;
  description: string;
  hash: string;
  path?: string;
}

interface ModuleMapSection {
  id: string;
  label: string;
  description: string;
  icon: LucideIcon;
  items: ModuleMapItem[];
}

interface ModuleWorkspaceMap {
  basePath: string;
  title: string;
  subtitle: string;
  icon: LucideIcon;
  sections: ModuleMapSection[];
}

const MARKETPLACE_PINNED_STORAGE_KEY = "ehi-marketplace-pinned-modules";
const DEFAULT_MARKETPLACE_PINNED_IDS = ["trials", "medication-access", "payer-check", "second-opinion"];
const MARKETPLACE_PINNED_LINK_OPTIONS = [
  { id: "trials", key: "trialMatch", label: "Trial Match", path: "/trials" },
  { id: "medication-access", key: "medAccess", label: "Med Access", path: "/medication-access" },
  { id: "payer-check", key: "payerCheck", label: "Payer Check", path: "/payer-check" },
  { id: "second-opinion", key: "secondOpinion", label: "Second Opinion", path: "/second-opinion" },
  { id: "grants", key: "grants", label: "Grants", path: "/grants" },
  { id: "research-opportunities", key: "research", label: "Research", path: "/research-opportunities" },
  { id: "caregiver-sharing", key: "sharing", label: "Caregiver Packet", path: "/sharing" },
];

function loadMarketplacePinnedIds(): string[] {
  try {
    const raw = localStorage.getItem(MARKETPLACE_PINNED_STORAGE_KEY);
    if (!raw) return DEFAULT_MARKETPLACE_PINNED_IDS;
    const parsed = JSON.parse(raw) as unknown;
    if (Array.isArray(parsed)) return parsed.filter((id): id is string => typeof id === "string");
    return DEFAULT_MARKETPLACE_PINNED_IDS;
  } catch {
    return DEFAULT_MARKETPLACE_PINNED_IDS;
  }
}

const MODULE_WORKSPACE_MAPS: ModuleWorkspaceMap[] = [
  {
    basePath: "/preop",
    title: "Pre-Op Support",
    subtitle: "Surgical readiness, medication holds, clearance, and handoff review",
    icon: Stethoscope,
    sections: [
      {
        id: "preop-review",
        label: "Review",
        description: "Understand readiness before surgery",
        icon: ClipboardCheck,
        items: [
          { label: "Overview", description: "Module summary", hash: "overview", path: "/preop" },
          { label: "Surgical brief", description: "30-second readiness view", hash: "surgical-brief" },
          { label: "Review boundary", description: "What the chart supports", hash: "review-boundary" },
        ],
      },
      {
        id: "preop-data",
        label: "Workflow Sections",
        description: "Focused pre-op review areas",
        icon: FileJson2,
        items: [
          { label: "Clearance", description: "Readiness check", hash: "clearance", path: "/preop/clearance" },
          { label: "Medication Holds", description: "Medication safety review", hash: "medication-holds", path: "/preop/medication-holds" },
          { label: "Anesthesia Handoff", description: "Perioperative handoff", hash: "anesthesia-handoff", path: "/preop/anesthesia-handoff" },
        ],
      },
      {
        id: "preop-packet",
        label: "Handoff",
        description: "Prepare clinical output",
        icon: Share2,
        items: [
          { label: "Anesthesia handoff", description: "Perioperative summary", hash: "anesthesia-handoff", path: "/preop/anesthesia-handoff" },
          { label: "Future agent", description: "Dedicated surgical review agent", hash: "future-agent" },
        ],
      },
    ],
  },
  {
    basePath: "/trials",
    title: "Trial Match",
    subtitle: "Eligibility research and outreach packet",
    icon: Search,
    sections: [
      {
        id: "trial-review",
        label: "Review",
        description: "Understand fit before outreach",
        icon: ClipboardCheck,
        items: [
          { label: "Overview", description: "Workspace summary", hash: "overview" },
          { label: "Candidate trials", description: "Matched opportunities", hash: "candidate-trials" },
          { label: "Eligibility review", description: "Inclusion and exclusion logic", hash: "eligibility-review" },
        ],
      },
      {
        id: "trial-data",
        label: "Data Needs",
        description: "Resolve gaps before sharing",
        icon: FileJson2,
        items: [
          { label: "Missing data", description: "Labs, staging, dates, and medications", hash: "missing-data" },
          { label: "Patient questions", description: "Context the chart cannot answer", hash: "patient-questions" },
        ],
      },
      {
        id: "trial-packet",
        label: "Packet",
        description: "Prepare patient-controlled outreach",
        icon: Share2,
        items: [
          { label: "Share packet", description: "Scoped evidence bundle", hash: "share-packet" },
          { label: "Activity", description: "Outreach and review history", hash: "activity" },
        ],
      },
    ],
  },
  {
    basePath: "/medication-access",
    title: "Medication Access",
    subtitle: "Programs, coverage, and fulfillment tasks",
    icon: Pill,
    sections: [
      {
        id: "access-workflow",
        label: "Workflow",
        description: "Organize access options",
        icon: ClipboardCheck,
        items: [
          { label: "Overview", description: "Access summary", hash: "overview" },
          { label: "Programs", description: "Manufacturer and foundation options", hash: "programs" },
          { label: "Cost and coverage", description: "Benefit and price context", hash: "cost-coverage" },
        ],
      },
      {
        id: "access-tasks",
        label: "Tasks",
        description: "Move from recommendation to action",
        icon: SlidersHorizontal,
        items: [
          { label: "Applications", description: "Forms and eligibility needs", hash: "applications" },
          { label: "Pharmacy tasks", description: "Fill, coupon, and prior-auth steps", hash: "pharmacy-tasks" },
        ],
      },
    ],
  },
  {
    basePath: "/payer-check",
    title: "Payer Check",
    subtitle: "Coverage rules and evidence packets",
    icon: ShieldAlert,
    sections: [
      {
        id: "payer-review",
        label: "Review",
        description: "Understand the coverage path",
        icon: ClipboardCheck,
        items: [
          { label: "Overview", description: "Coverage summary", hash: "overview" },
          { label: "Coverage rules", description: "Policy and criteria", hash: "coverage-rules" },
          { label: "Evidence packet", description: "Chart facts supporting request", hash: "evidence-packet" },
        ],
      },
      {
        id: "payer-actions",
        label: "Actions",
        description: "Prepare payer-facing artifacts",
        icon: Share2,
        items: [
          { label: "Prior auth", description: "Submission readiness", hash: "prior-auth" },
          { label: "Appeal support", description: "Denial response materials", hash: "appeal-support" },
        ],
      },
    ],
  },
  {
    basePath: "/second-opinion",
    title: "Second Opinion",
    subtitle: "Specialist review packet and questions",
    icon: MessageSquareText,
    sections: [
      {
        id: "opinion-packet",
        label: "Packet",
        description: "Control what reviewers receive",
        icon: FileSearch,
        items: [
          { label: "Overview", description: "Review workspace summary", hash: "overview" },
          { label: "Clinical question", description: "What the patient wants answered", hash: "clinical-question" },
          { label: "Evidence packet", description: "Scoped chart materials", hash: "evidence-packet" },
        ],
      },
      {
        id: "opinion-network",
        label: "Review",
        description: "Manage specialist workflow",
        icon: Share2,
        items: [
          { label: "Specialists", description: "Reviewer options", hash: "specialists" },
          { label: "Activity", description: "Requests and responses", hash: "activity" },
        ],
      },
    ],
  },
];

const CLINICAL_INSIGHTS_NAV_GROUPS: NavGroup[] = [
  {
    label: "LLM Review",
    items: [
      { to: "/explorer/assistant", label: "Chat", icon: MessageSquareText, description: "Chart-grounded agent review" },
      { to: "/clinical-insights/context-library", label: "Context Library", icon: Layers3, description: "Packages and published scripts" },
    ],
  },
  {
    label: "Clinical Modules",
    items: [
      { to: "/clinical-insights/favorites", label: "Favorites", icon: Star, description: "Saved clinical modules" },
      { to: "/clinical-insights", label: "Explore Modules", icon: Activity, description: "Browse review workflows" },
      { to: "/clinical-insights/create", label: "Create a Module", icon: ClipboardCheck, description: "Build a review workflow" },
    ],
  },
];

const PATIENT_RECORD_NAV_ITEMS: NavItem[] = [
  { to: "/charts", label: "Module Overview", icon: Database, description: "Record intelligence" },
  { to: "/explorer", label: "Clinical Snapshot", icon: UserRound, description: "Patient summary" },
  { to: "/explorer/history", label: "History", icon: CalendarDays, description: "Tables and timelines" },
  { to: "/explorer/care-journey", label: "Care Journey", icon: Heart, description: "Visual care timeline" },
  { to: "/explorer/patient-data", label: "FHIR Sources", icon: FileJson2, description: "Bundle metrics" },
];

const PATIENT_RECORD_NAV_GROUPS: NavGroup[] = [
  {
    label: "FHIR Charts",
    items: PATIENT_RECORD_NAV_ITEMS,
  },
];

const DATA_AGGREGATOR_NAV_GROUPS: NavGroup[] = [
  {
    label: "Data Aggregator",
    items: [
      { to: "/aggregate", label: "Module Overview", icon: DatabaseZap, description: "Patient collection guide" },
      { to: "/aggregate/sources", label: "Source Inventory", icon: FileJson2, description: "Portal and file checklist" },
      { to: "/aggregate/cleaning", label: "Cleaning Queue", icon: SlidersHorizontal, description: "Normalization workbench" },
      { to: "/aggregate/context", label: "Patient Context", icon: MessageSquareText, description: "Guided patient intake" },
      { to: "/aggregate/publish", label: "Publish Readiness", icon: ClipboardCheck, description: "Chart activation gates" },
    ],
  },
];

const TRIALS_NAV_GROUPS: NavGroup[] = [
  {
    label: "Clinical Trials",
    items: [
      { to: "/trials", label: "Overview", icon: Search, description: "Trial matching guide" },
    ],
  },
];

const MEDICATION_ACCESS_NAV_GROUPS: NavGroup[] = [
  {
    label: "Medication Access",
    items: [
      { to: "/medication-access", label: "Overview", icon: Pill, description: "Affordability guide" },
    ],
  },
];

const MARKETPLACE_NAV_GROUPS: NavGroup[] = [
  {
    label: "Workspace",
    items: [
      { to: "/marketplace/workspace", label: "Favorites", icon: Star, description: "Saved modules" },
      { to: "/marketplace/settings", label: "Configuration", icon: SlidersHorizontal, description: "Access and sharing scope" },
    ],
  },
  {
    label: "Marketplace",
    items: [
      { to: "/marketplace", label: "Explore Modules", icon: Store, description: "Browse and select modules" },
      { to: "/marketplace/publish", label: "Create Module", icon: Share2, description: "Submit a workflow" },
    ],
  },
];

const SHARING_NAV_GROUPS: NavGroup[] = [
  {
    label: "Sharing",
    items: [
      { to: "/sharing", label: "Packet Builder", icon: Share2, description: "Scope and recipients" },
      { to: "/second-opinion", label: "Second Opinion", icon: MessageSquareText, description: "Specialist review packet" },
      { to: "/charts", label: "FHIR Chart", icon: Database, description: "Source patient chart" },
    ],
  },
];

const ANALYSIS_NAV_LINKS: NavItem[] = [
  { to: "/analysis", label: "Overview", icon: BookMarked, description: "Orientation and goals" },
  {
    to: "/analysis/fhir-primer",
    label: "FHIR Primer",
    icon: FileJson2,
    description: "Data format deep dive",
  },
  {
    to: "/analysis/flight-school",
    label: "Flight School",
    icon: GraduationCap,
    description: "Guided learning missions",
  },
  {
    to: "/analysis/methodology",
    label: "Methodology",
    icon: Layers3,
    description: "Interpretability strategy",
  },
  {
    to: "/analysis/definitions",
    label: "Definitions",
    icon: Database,
    description: "Canonical data contracts",
  },
  {
    to: "/analysis/coverage",
    label: "Coverage",
    icon: TestTubeDiagonal,
    description: "Field quality and reliability",
  },
];

const INTERNAL_NAV_LINKS: NavItem[] = [
  { to: "/analysis", label: "Module Overview", icon: BookMarked, description: "FHIR education and methodology" },
  { to: "/catalog", label: "Data Catalog", icon: Archive, description: "Platform contracts and schemas" },
  ...ANALYSIS_NAV_LINKS.filter((item) => item.to !== "/analysis"),
];

function withPatientQuery(path: string, patientId: string | null): string {
  if (!patientId) return path;
  return `${path}?patient=${patientId}`;
}

function getEnvironment(pathname: string): AppEnvironment {
  if (pathname.startsWith("/platform")) return "platform";
  if (pathname.startsWith("/catalog")) return "catalog";
  if (pathname.startsWith("/analysis")) return "analysis";
  if (pathname.startsWith("/aggregate")) return "aggregator";
  if (pathname.startsWith("/clinical-insights")) return "clinical";
  if (
    pathname.startsWith("/marketplace") ||
    pathname.startsWith("/sharing") ||
    pathname.startsWith("/second-opinion") ||
    pathname.startsWith("/trials") ||
    pathname.startsWith("/medication-access") ||
    pathname.startsWith("/grants") ||
    pathname.startsWith("/research-opportunities") ||
    pathname.startsWith("/payer-check")
  ) {
    return "marketplace";
  }
  if (pathname.startsWith("/preop")) return "clinical";
  if (pathname === "/journey") return "clinical";
  if (pathname.startsWith("/explorer/safety")) return "clinical";
  if (pathname.startsWith("/explorer/clearance")) return "clinical";
  if (pathname.startsWith("/explorer/anesthesia")) return "clinical";
  if (pathname.startsWith("/explorer/assistant")) return "clinical";
  if (pathname.startsWith("/charts") || pathname.startsWith("/record") || pathname.startsWith("/explorer")) return "record";
  return "clinical";
}

function getClinicalNavGroups(environment: AppEnvironment): NavGroup[] {
  if (environment === "record") return PATIENT_RECORD_NAV_GROUPS;
  if (environment === "aggregator") return DATA_AGGREGATOR_NAV_GROUPS;
  if (environment === "clinical") return CLINICAL_INSIGHTS_NAV_GROUPS;
  if (environment === "marketplace") return MARKETPLACE_NAV_GROUPS;
  if (environment === "sharing") return SHARING_NAV_GROUPS;
  if (environment === "trials") return TRIALS_NAV_GROUPS;
  if (environment === "medication") return MEDICATION_ACCESS_NAV_GROUPS;
  return CLINICAL_INSIGHTS_NAV_GROUPS;
}

function shouldMatchSidebarLinkExactly(path: string): boolean {
  return [
    "/aggregate",
    "/charts",
    "/clinical-insights",
    "/marketplace",
    "/analysis",
    "/explorer",
  ].includes(path);
}

function getWorkspaceCopy(environment: AppEnvironment): { title: string; sidebarTitle: string; subtitle: string; icon: LucideIcon } {
  if (environment === "platform") {
    return {
      title: "Platform",
      sidebarTitle: "Platform",
      subtitle: "Select a patient context before opening a workspace",
      icon: UserRound,
    };
  }
  if (environment === "record") {
    return {
      title: "FHIR Charts",
      sidebarTitle: "FHIR Charts",
      subtitle: "Patient-owned chart intelligence and source evidence",
      icon: Database,
    };
  }
  if (environment === "marketplace") {
    return {
      title: "Module Marketplace",
      sidebarTitle: "Marketplace",
      subtitle: "External modules built on the FHIR Chart",
      icon: Store,
    };
  }
  if (environment === "aggregator") {
    return {
      title: "Data Aggregator",
      sidebarTitle: "Data Aggregator",
      subtitle: "Guided collection, cleaning, and chart publishing",
      icon: DatabaseZap,
    };
  }
  if (environment === "clinical") {
    return {
      title: "Clinical Insights",
      sidebarTitle: "Clinical Insights",
      subtitle: "Private chart-review modules and clinical agents",
      icon: Activity,
    };
  }
  if (environment === "trials") {
    return {
      title: "Clinical Trials Workspace",
      sidebarTitle: "Clinical Trials",
      subtitle: "Eligibility research and shareable patient packet",
      icon: Search,
    };
  }
  if (environment === "medication") {
    return {
      title: "Medication Access Workspace",
      sidebarTitle: "Medication Access",
      subtitle: "Cost, assistance, and affordability research",
      icon: Pill,
    };
  }
  if (environment === "analysis") {
    return {
      title: "Data Analysis & Methodology Environment",
      sidebarTitle: "Data Lab",
      subtitle: "Definitions, methodology, and reliability evidence",
      icon: BookMarked,
    };
  }
  if (environment === "catalog") {
    return {
      title: "Internal Data Catalog",
      sidebarTitle: "Data Catalog",
      subtitle: "Platform contracts, schemas, and module inputs",
      icon: Archive,
    };
  }
  if (environment === "sharing") {
    return {
      title: "Data Sharing Workspace",
      sidebarTitle: "Data Sharing",
      subtitle: "Evidence packets, recipients, and second opinions",
      icon: Share2,
    };
  }
  return {
    title: "Clinical Insights",
    sidebarTitle: "Clinical Insights",
    subtitle: "Private chart-review modules and clinical agents",
    icon: Activity,
  };
}

function getTopArea(environment: AppEnvironment): TopArea {
  if (environment === "platform") return "platform";
  if (environment === "record") return "record";
  if (environment === "aggregator") return "aggregator";
  if (environment === "analysis" || environment === "catalog") return "internal";
  if (environment === "marketplace" || environment === "trials" || environment === "medication" || environment === "sharing") {
    return "marketplace";
  }
  return "clinical";
}

function getActiveModuleMap(pathname: string): ModuleWorkspaceMap | null {
  return MODULE_WORKSPACE_MAPS.find((moduleMap) => pathname.startsWith(moduleMap.basePath)) ?? null;
}

function isModuleMapItemActive(moduleMap: ModuleWorkspaceMap, item: ModuleMapItem, pathname: string, hash: string): boolean {
  if (item.path) return pathname === item.path;
  return pathname === moduleMap.basePath && hash === `#${item.hash}`;
}

function getActiveModuleMapSectionIds(moduleMap: ModuleWorkspaceMap, pathname: string, hash: string): string[] {
  return moduleMap.sections
    .filter((section) => section.items.some((item) => isModuleMapItemActive(moduleMap, item, pathname, hash)))
    .map((section) => section.id);
}

function StatusDot({ risk }: { risk: PatientRiskSummary | undefined }) {
  if (!risk) return null;
  if (risk.has_critical_flag) {
    return <span className="h-1.5 w-1.5 shrink-0 rounded-full bg-[#ef4444]" />;
  }
  if (risk.complexity_tier === "complex" || risk.complexity_tier === "highly_complex") {
    return <span className="h-1.5 w-1.5 shrink-0 rounded-full bg-[#f59e0b]" />;
  }
  return null;
}

function PatientPickerModal({
  open,
  selectedId,
  onSelect,
  onClose,
}: {
  open: boolean;
  selectedId: string | null;
  onSelect: (id: string) => void;
  onClose: () => void;
}) {
  const [filter, setFilter] = useState<FilterMode>("all");
  const [search, setSearch] = useState("");
  const [previewId, setPreviewId] = useState<string | null>(selectedId);

  const { data: patients = [], isLoading: patientsLoading } = useQuery({
    queryKey: ["patients"],
    queryFn: api.listPatients,
    staleTime: Infinity,
    enabled: open,
  });

  const { data: riskSummary = [], isLoading: riskQueryLoading } = useQuery({
    queryKey: ["risk-summary"],
    queryFn: api.getRiskSummary,
    staleTime: 5 * 60 * 1000,
    enabled: open,
  });

  const riskMap = useMemo(
    () => new Map<string, PatientRiskSummary>(riskSummary.map((item) => [item.id, item])),
    [riskSummary]
  );

  const { isFavorite, toggleFavorite } = useFavorites();

  const riskLoading = filter !== "all" && riskQueryLoading;

  let visiblePatients = patients.filter((patient) => {
    const q = search.trim().toLowerCase();
    if (!q) return true;
    return patient.name.toLowerCase().includes(q);
  });

  if (!riskLoading && filter === "high_risk") {
    visiblePatients = visiblePatients.filter((patient) => {
      const risk = riskMap.get(patient.id);
      return risk?.complexity_tier === "complex" || risk?.complexity_tier === "highly_complex";
    });
  }

  if (!riskLoading && filter === "needs_review") {
    visiblePatients = visiblePatients.filter((patient) => riskMap.get(patient.id)?.has_critical_flag === true);
  }

  const favorites = visiblePatients.filter((patient) => isFavorite(patient.id));
  const others = visiblePatients.filter((patient) => !isFavorite(patient.id));
  const selectedPatient = patients.find((patient) => patient.id === selectedId);
  const previewPatient = patients.find((patient) => patient.id === previewId) ?? selectedPatient ?? visiblePatients[0];
  const previewRisk = previewPatient ? riskMap.get(previewPatient.id) : undefined;
  const complexCount = patients.filter((patient) => (
    patient.complexity_tier === "complex" || patient.complexity_tier === "highly_complex"
  )).length;
  const criticalCount = riskSummary.filter((patient) => patient.has_critical_flag).length;

  function renderRow(patient: PatientListItem) {
    const active = patient.id === selectedId;
    const previewing = patient.id === previewPatient?.id;
    const favorited = isFavorite(patient.id);
    const risk = riskMap.get(patient.id);

    return (
      <div
        key={patient.id}
        className={`group flex items-center gap-1 rounded-lg pr-1 transition-colors ${
          previewing ? "bg-[#eef1ff] shadow-[inset_3px_0_0_#5b76fe]" : "hover:bg-[#f5f6f8]"
        }`}
      >
        <button
          onClick={() => setPreviewId(patient.id)}
          className={`flex flex-1 items-center gap-2 truncate px-3 py-2 text-left text-sm ${
            previewing ? "font-medium text-[#5b76fe]" : "text-[#1c1c1e]"
          }`}
        >
          <StatusDot risk={risk} />
          <div className="min-w-0 flex-1">
            <span className="block truncate">{patient.name}</span>
            <span className="block truncate text-[10px] leading-tight text-[#a5a8b5]">
              {patient.total_resources} resources · {patient.active_condition_count} conditions · {patient.active_med_count} meds
            </span>
          </div>
        </button>

        {active && (
          <span className="shrink-0 rounded-full bg-white px-1.5 py-0.5 text-[10px] font-semibold text-[#5b76fe] shadow-[rgb(224_226_232)_0px_0px_0px_1px]">
            Current
          </span>
        )}

        <button
          onClick={(event) => {
            event.stopPropagation();
            toggleFavorite(patient.id);
          }}
          title={favorited ? "Remove from favorites" : "Add to favorites"}
          className={`shrink-0 rounded p-1 transition-colors ${
            favorited
              ? "text-[#5b76fe]"
              : "text-transparent group-hover:text-[#c7cad5] hover:!text-[#5b76fe]"
          }`}
        >
          <Star size={13} fill={favorited ? "currentColor" : "none"} strokeWidth={favorited ? 0 : 1.5} />
        </button>
      </div>
    );
  }

  const FILTER_OPTIONS: { key: FilterMode; label: string }[] = [
    { key: "all", label: "All" },
    { key: "high_risk", label: "High Risk" },
    { key: "needs_review", label: "Needs Review" },
  ];

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-[80] flex items-center justify-center bg-[#0f172a]/25 px-4 py-6">
      <div className="flex max-h-[88vh] w-full max-w-5xl flex-col overflow-hidden rounded-2xl bg-white shadow-2xl">
        <div className="flex shrink-0 items-start justify-between gap-4 border-b border-[#e9eaef] px-5 py-4">
          <div>
            <p className="inline-flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-[#5b76fe]">
              <SlidersHorizontal size={13} />
              Patient context setting
            </p>
            <h2 className="mt-1 text-xl font-semibold tracking-tight text-[#1c1c1e]">Advanced patient selection</h2>
            <p className="mt-1 text-sm text-[#667085]">
              Switch the single-patient context used across the clinical workspace.
            </p>
          </div>
          <button
            onClick={onClose}
            className="rounded-lg p-2 text-[#667085] transition-colors hover:bg-[#f5f6f8] hover:text-[#1c1c1e]"
            title="Close"
          >
            <X size={18} />
          </button>
        </div>

        <div className="grid min-h-0 flex-1 gap-0 lg:grid-cols-[340px_1fr]">
          <aside className="border-b border-[#e9eaef] bg-[#fafbff] p-4 lg:border-b-0 lg:border-r">
            <div className="rounded-xl bg-white p-4 shadow-[rgb(224_226_232)_0px_0px_0px_1px]">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <p className="text-xs font-semibold uppercase tracking-wider text-[#a5a8b5]">Preview patient</p>
                  <p className="mt-2 text-base font-semibold text-[#1c1c1e]">
                    {previewPatient ? previewPatient.name : "No patient selected"}
                  </p>
                </div>
                {previewPatient?.id === selectedId && (
                  <span className="rounded-full bg-[#eef1ff] px-2 py-1 text-[10px] font-semibold uppercase tracking-wider text-[#5b76fe]">
                    Current
                  </span>
                )}
              </div>

              {previewPatient && (
                <>
                <p className="mt-1 text-sm text-[#667085]">
                  {previewPatient.gender} · {Math.floor(previewPatient.age_years)} years · {previewPatient.complexity_score.toFixed(0)}/100 complexity
                </p>
                <div className="mt-3 grid grid-cols-2 gap-2 text-sm">
                  <div className="rounded-lg bg-[#f5f6f8] p-2">
                    <p className="text-[10px] uppercase tracking-wider text-[#a5a8b5]">Resources</p>
                    <p className="font-semibold text-[#1c1c1e]">{previewPatient.total_resources.toLocaleString()}</p>
                  </div>
                  <div className="rounded-lg bg-[#f5f6f8] p-2">
                    <p className="text-[10px] uppercase tracking-wider text-[#a5a8b5]">Tier</p>
                    <p className="capitalize font-semibold text-[#1c1c1e]">{previewPatient.complexity_tier.replace("_", " ")}</p>
                  </div>
                  <div className="rounded-lg bg-[#f5f6f8] p-2">
                    <p className="text-[10px] uppercase tracking-wider text-[#a5a8b5]">Conditions</p>
                    <p className="font-semibold text-[#1c1c1e]">{previewPatient.active_condition_count}</p>
                  </div>
                  <div className="rounded-lg bg-[#f5f6f8] p-2">
                    <p className="text-[10px] uppercase tracking-wider text-[#a5a8b5]">Meds</p>
                    <p className="font-semibold text-[#1c1c1e]">{previewPatient.active_med_count}</p>
                  </div>
                  <div className="rounded-lg bg-[#f5f6f8] p-2">
                    <p className="text-[10px] uppercase tracking-wider text-[#a5a8b5]">Encounters</p>
                    <p className="font-semibold text-[#1c1c1e]">{previewPatient.encounter_count}</p>
                  </div>
                  <div className="rounded-lg bg-[#f5f6f8] p-2">
                    <p className="text-[10px] uppercase tracking-wider text-[#a5a8b5]">Safety</p>
                    <p className={`font-semibold ${previewRisk?.has_critical_flag ? "text-[#ef4444]" : "text-[#16a34a]"}`}>
                      {previewRisk?.has_critical_flag ? "Flagged" : "No critical flag"}
                    </p>
                  </div>
                </div>
                <button
                  onClick={() => onSelect(previewPatient.id)}
                  disabled={previewPatient.id === selectedId}
                  className={`mt-4 w-full rounded-lg px-3 py-2 text-sm font-semibold transition-colors ${
                    previewPatient.id === selectedId
                      ? "cursor-default bg-[#f5f6f8] text-[#a5a8b5]"
                      : "bg-[#5b76fe] text-white hover:bg-[#4f68e8]"
                  }`}
                >
                  {previewPatient.id === selectedId ? "Using this patient" : "Use this patient"}
                </button>
                </>
              )}
            </div>

            <div className="mt-4 grid grid-cols-2 gap-2">
              <div className="rounded-xl bg-white p-3 shadow-[rgb(224_226_232)_0px_0px_0px_1px]">
                <p className="text-[10px] uppercase tracking-wider text-[#a5a8b5]">Patients</p>
                <p className="text-xl font-semibold text-[#1c1c1e]">{patients.length.toLocaleString()}</p>
              </div>
              <div className="rounded-xl bg-white p-3 shadow-[rgb(224_226_232)_0px_0px_0px_1px]">
                <p className="text-[10px] uppercase tracking-wider text-[#a5a8b5]">Complex</p>
                <p className="text-xl font-semibold text-[#1c1c1e]">{complexCount.toLocaleString()}</p>
              </div>
              <div className="rounded-xl bg-white p-3 shadow-[rgb(224_226_232)_0px_0px_0px_1px]">
                <p className="text-[10px] uppercase tracking-wider text-[#a5a8b5]">Critical</p>
                <p className="text-xl font-semibold text-[#ef4444]">{riskQueryLoading ? "..." : criticalCount.toLocaleString()}</p>
              </div>
              <div className="rounded-xl bg-white p-3 shadow-[rgb(224_226_232)_0px_0px_0px_1px]">
                <p className="text-[10px] uppercase tracking-wider text-[#a5a8b5]">Shown</p>
                <p className="text-xl font-semibold text-[#5b76fe]">{visiblePatients.length.toLocaleString()}</p>
              </div>
            </div>
          </aside>

          <div className="flex min-h-0 flex-col">
            <div className="shrink-0 border-b border-[#e9eaef] p-4">
              <div className="flex flex-col gap-3 lg:flex-row lg:items-center">
                <div className="flex min-w-0 flex-1 items-center gap-2 rounded-lg border border-[#e9eaef] bg-[#f5f6f8] px-3 py-2">
                  <Search size={14} className="shrink-0 text-[#a5a8b5]" />
                  <input
                    value={search}
                    onChange={(event) => setSearch(event.target.value)}
                    placeholder="Search by patient name..."
                    className="min-w-0 flex-1 bg-transparent text-sm text-[#1c1c1e] outline-none placeholder:text-[#a5a8b5]"
                  />
                </div>
                <div className="flex gap-1 rounded-xl bg-[#f5f6f8] p-1">
                  {FILTER_OPTIONS.map(({ key, label }) => (
                    <button
                      key={key}
                      onClick={() => setFilter(key)}
                      className={`rounded-lg px-3 py-1.5 text-xs font-medium transition-colors ${
                        filter === key ? "bg-white text-[#5b76fe] shadow-sm" : "text-[#667085] hover:text-[#1c1c1e]"
                      }`}
                    >
                      {label}
                    </button>
                  ))}
                </div>
              </div>
            </div>

            <div className="min-h-0 flex-1 overflow-y-auto p-3">
              {(patientsLoading || riskLoading) && (
                <div className="space-y-2">
                  {[1, 2, 3, 4, 5].map((item) => (
                    <div key={item} className="h-12 animate-pulse rounded-lg bg-[#f5f6f8]" />
                  ))}
                </div>
              )}

              {!patientsLoading && !riskLoading && (
                <>
                  {favorites.length > 0 && (
                    <>
                      <p className="mb-1 px-2 text-[10px] font-semibold uppercase tracking-wider text-[#a5a8b5]">
                        Favorites
                      </p>
                      <div className="mb-3 space-y-0.5">{favorites.map(renderRow)}</div>
                      <div className="mb-3 border-t border-[#e9eaef]" />
                    </>
                  )}

                  <p className="mb-1 px-2 text-[10px] font-semibold uppercase tracking-wider text-[#a5a8b5]">
                    {filter === "all" ? "All Patients" : filter === "high_risk" ? "High Risk" : "Needs Review"}
                  </p>
                  <div className="space-y-0.5">{others.map(renderRow)}</div>

                  {visiblePatients.length === 0 && (
                    <p className="px-3 py-8 text-center text-sm text-[#a5a8b5]">
                      {filter === "all" ? "No patients available" : "No patients match this filter"}
                    </p>
                  )}
                </>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

// ─── Patient Selector Dropdown ────────────────────────────────────────────────
function PatientSelector({
  patientId,
  onSelect,
  onAdvancedOpen,
}: {
  patientId: string | null;
  onSelect: (id: string) => void;
  onAdvancedOpen: () => void;
}) {
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState("");
  const ref = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const { data: patients = [], isLoading } = useQuery({
    queryKey: ["patients"],
    queryFn: api.listPatients,
    staleTime: Infinity,
  });

  const current = patients.find((p) => p.id === patientId);

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return patients;
    return patients.filter((p) => p.name.toLowerCase().includes(q));
  }, [patients, search]);

  // Close on outside click
  useEffect(() => {
    if (!open) return;
    function handler(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
        setSearch("");
      }
    }
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [open]);

  // Focus input when opened
  useEffect(() => {
    if (open) setTimeout(() => inputRef.current?.focus(), 50);
  }, [open]);

  return (
    <div ref={ref} className="relative">
      <button
        onClick={() => setOpen((o) => !o)}
        className={`flex items-center gap-2 rounded-lg border px-3 py-1.5 text-sm transition-colors ${
          open
            ? "border-[#5b76fe] bg-[#eef1ff] text-[#5b76fe]"
            : "border-[#e9eaef] bg-white text-[#555a6a] hover:border-[#5b76fe] hover:text-[#5b76fe]"
        }`}
        title="Switch patient"
      >
        <UserRound size={14} className="shrink-0" />
        <span className="max-w-[180px] truncate font-medium">
          {isLoading ? "Loading…" : current ? current.name : "Select patient"}
        </span>
        <ChevronDown size={13} className={`shrink-0 transition-transform ${open ? "rotate-180" : ""}`} />
      </button>

      {open && (
        <div className="absolute left-0 top-full z-50 mt-1 w-72 rounded-xl border border-[#e9eaef] bg-white shadow-lg">
          {/* Search input */}
          <div className="flex items-center gap-2 border-b border-[#e9eaef] px-3 py-2">
            <Search size={13} className="shrink-0 text-[#a5a8b5]" />
            <input
              ref={inputRef}
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search patients…"
              className="flex-1 bg-transparent text-sm text-[#1c1c1e] outline-none placeholder:text-[#a5a8b5]"
            />
          </div>
          {/* List */}
          <div className="max-h-64 overflow-y-auto py-1">
            {filtered.length === 0 && (
              <p className="px-4 py-3 text-sm text-[#a5a8b5]">No patients match</p>
            )}
            {filtered.slice(0, 100).map((p) => (
              <button
                key={p.id}
                onClick={() => {
                  onSelect(p.id);
                  setOpen(false);
                  setSearch("");
                }}
                className={`flex w-full items-start gap-2 px-3 py-2 text-left transition-colors hover:bg-[#f5f6f8] ${
                  p.id === patientId ? "bg-[#eef1ff]" : ""
                }`}
              >
                <div className="min-w-0 flex-1">
                  <p className={`truncate text-sm font-medium ${
                    p.id === patientId ? "text-[#5b76fe]" : "text-[#1c1c1e]"
                  }`}>
                    {p.name}
                  </p>
                  <p className="truncate text-[11px] text-[#a5a8b5]">
                    {p.gender} · {Math.floor(p.age_years)}y · {p.complexity_tier}
                  </p>
                </div>
                {p.id === patientId && (
                  <span className="mt-0.5 shrink-0 text-[#5b76fe]">✓</span>
                )}
              </button>
            ))}
            {filtered.length > 100 && (
              <p className="px-4 py-2 text-center text-[11px] text-[#a5a8b5]">
                {filtered.length - 100} more — type to narrow
              </p>
            )}
          </div>
          <div className="border-t border-[#e9eaef] p-2">
            <button
              onClick={() => {
                setOpen(false);
                setSearch("");
                onAdvancedOpen();
              }}
              className="flex w-full items-center justify-between rounded-lg px-3 py-2 text-left text-sm font-medium text-[#5b76fe] transition-colors hover:bg-[#eef1ff]"
            >
              <span className="inline-flex items-center gap-2">
                <SlidersHorizontal size={14} />
                Advanced selection
              </span>
              <ChevronRight size={14} />
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
// ───────────────────────────────────────────────────────────────────────────────

export function Layout({ children }: LayoutProps) {
  const location = useLocation();
  const [searchParams] = useSearchParams();
  const patientId = searchParams.get("patient");

  const [paletteOpen, setPaletteOpen] = useState(false);
  const [patientPickerOpen, setPatientPickerOpen] = useState(false);
  const [marketplacePinnedIds, setMarketplacePinnedIds] = useState<string[]>(loadMarketplacePinnedIds);
  const [moduleMapOpen, setModuleMapOpen] = useState(true);
  const [openModuleMapSections, setOpenModuleMapSections] = useState<Set<string>>(() => new Set(["trial-review"]));

  const [sidebarCollapsed, setSidebarCollapsed] = useState<boolean>(() => {
    try { return localStorage.getItem("ehi-sidebar-collapsed") === "true"; } catch { return false; }
  });
  const [advancedOpen, setAdvancedOpen] = useState<boolean>(false);
  const [preOpOpen, setPreOpOpen] = useState<boolean>(true);
  const toggleSidebar = useCallback(() => {
    setSidebarCollapsed((prev) => {
      const next = !prev;
      try { localStorage.setItem("ehi-sidebar-collapsed", String(next)); } catch { /* noop */ }
      return next;
    });
  }, []);

  const environment: AppEnvironment = getEnvironment(location.pathname);
  const isPlatform = environment === "platform";
  const isAnalysis = environment === "analysis";
  const isInternal = environment === "analysis" || environment === "catalog";
  const clinicalNavGroups = getClinicalNavGroups(environment);
  const workspace = getWorkspaceCopy(environment);
  const WorkspaceIcon = workspace.icon;
  const topArea = getTopArea(environment);
  const activeModuleMap = getActiveModuleMap(location.pathname);
  const ActiveModuleMapIcon = activeModuleMap?.icon;
  const headerHeight = isPlatform ? 76 : 126;
  const sidebarTone =
    topArea === "clinical"
      ? {
          icon: "text-[#9a5a16]",
          active: "bg-[#fff1df] font-medium text-[#9a5a16]",
          activeCollapsed: "bg-[#fff1df] text-[#9a5a16]",
          group: "text-[#9a5a16]",
          hover: "hover:bg-[#fff8f1] hover:text-[#1c1c1e]",
        }
      : topArea === "record"
        ? {
            icon: "text-[#0f766e]",
            active: "bg-[#e7fbf7] font-medium text-[#0f766e]",
            activeCollapsed: "bg-[#e7fbf7] text-[#0f766e]",
            group: "text-[#0f766e]",
            hover: "hover:bg-[#f4fffc] hover:text-[#1c1c1e]",
          }
        : {
            icon: "text-[#5b76fe]",
            active: "bg-[#eef1ff] font-medium text-[#5b76fe]",
            activeCollapsed: "bg-[#eef1ff] text-[#5b76fe]",
            group: "text-[#5b76fe]",
            hover: "hover:bg-[#f5f6f8] hover:text-[#1c1c1e]",
          };

  const { data: corpusStats } = useQuery({
    queryKey: ["corpus-stats"],
    queryFn: api.getCorpusStats,
    staleTime: Infinity,
    enabled: isInternal,
  });

  const topLinks: { key: TopArea; label: string; to: string }[] = [
    { key: "aggregator", label: "Data Aggregator", to: withPatientQuery("/aggregate", patientId) },
    { key: "record", label: "FHIR Charts", to: withPatientQuery("/charts", patientId) },
    { key: "clinical", label: "Clinical Insights", to: withPatientQuery("/clinical-insights", patientId) },
    { key: "marketplace", label: "Marketplace", to: withPatientQuery("/marketplace", patientId) },
    { key: "internal", label: "Internal Tools", to: "/analysis" },
  ];

  useEffect(() => {
    const refreshMarketplacePinnedIds = () => setMarketplacePinnedIds(loadMarketplacePinnedIds());
    window.addEventListener("storage", refreshMarketplacePinnedIds);
    window.addEventListener("ehi-marketplace-workspace-updated", refreshMarketplacePinnedIds);
    return () => {
      window.removeEventListener("storage", refreshMarketplacePinnedIds);
      window.removeEventListener("ehi-marketplace-workspace-updated", refreshMarketplacePinnedIds);
    };
  }, []);

  useEffect(() => {
    if (!activeModuleMap) return;
    const activeSectionIds = getActiveModuleMapSectionIds(activeModuleMap, location.pathname, location.hash);
    setModuleMapOpen(true);
    setOpenModuleMapSections(new Set((activeSectionIds.length ? activeSectionIds : [activeModuleMap.sections[0]?.id]).filter(Boolean) as string[]));
    setSidebarCollapsed(true);
  }, [activeModuleMap, location.pathname, location.hash]);

  const toggleModuleMapSection = useCallback((sectionId: string) => {
    setOpenModuleMapSections((current) => {
      const next = new Set(current);
      if (next.has(sectionId)) {
        next.delete(sectionId);
      } else {
        next.add(sectionId);
      }
      return next;
    });
  }, []);

  const marketplaceLinks: {
    key: AppEnvironment | "trialMatch" | "medAccess" | "payerCheck" | "secondOpinion" | "grants" | "research";
    label: string;
    to: string;
  }[] = [
    ...MARKETPLACE_PINNED_LINK_OPTIONS.filter((link) => marketplacePinnedIds.includes(link.id)).map((link) => ({
      key: link.key as "trialMatch" | "medAccess" | "payerCheck" | "secondOpinion" | "grants" | "research" | "sharing",
      label: link.label,
      to: withPatientQuery(link.path, patientId),
    })),
  ];

  const chartLinks: { key: string; label: string; to: string }[] = [
    { key: "chartHome", label: "Module Overview", to: withPatientQuery("/charts", patientId) },
    { key: "snapshot", label: "Clinical Snapshot", to: withPatientQuery("/explorer", patientId) },
    { key: "history", label: "History", to: withPatientQuery("/explorer/history", patientId) },
    { key: "journey", label: "Care Journey", to: withPatientQuery("/explorer/care-journey", patientId) },
    { key: "sources", label: "FHIR Sources", to: withPatientQuery("/explorer/patient-data", patientId) },
  ];

  const aggregatorLinks: { key: string; label: string; to: string }[] = [
    { key: "walkthrough", label: "Module Overview", to: withPatientQuery("/aggregate", patientId) },
    { key: "sourceInventory", label: "Source Inventory", to: withPatientQuery("/aggregate/sources", patientId) },
    { key: "cleaningQueue", label: "Cleaning Queue", to: withPatientQuery("/aggregate/cleaning", patientId) },
    { key: "patientContext", label: "Patient Context", to: withPatientQuery("/aggregate/context", patientId) },
    { key: "publishReadiness", label: "Publish Readiness", to: withPatientQuery("/aggregate/publish", patientId) },
  ];

  const clinicalInsightLinks: { key: string; label: string; to: string }[] = [
    { key: "preop", label: "Pre-Op Support", to: withPatientQuery("/preop", patientId) },
  ];

  const internalToolLinks: { key: string; label: string; to: string }[] = [
    { key: "dataLab", label: "Module Overview", to: "/analysis" },
    { key: "catalog", label: "Data Catalog", to: "/catalog" },
    { key: "primer", label: "FHIR Primer", to: "/analysis/fhir-primer" },
    { key: "methodology", label: "Methodology", to: "/analysis/methodology" },
    { key: "coverage", label: "Coverage", to: "/analysis/coverage" },
  ];

  const subnav =
    topArea === "platform"
      ? null
      : topArea === "aggregator"
      ? {
          label: "Data aggregation",
          links: aggregatorLinks,
          tone: "blue",
        }
      : topArea === "record"
        ? {
            label: "FHIR chart views",
            links: chartLinks,
            tone: "teal",
          }
        : topArea === "clinical"
          ? {
              label: "Pinned clinical modules",
              links: clinicalInsightLinks,
              tone: "amber",
            }
          : topArea === "internal"
            ? {
                label: "Internal tools",
                links: internalToolLinks,
                tone: "green",
              }
            : {
                label: "Pinned modules",
                links: marketplaceLinks,
                tone: "blue",
              };

  const subnavTone =
    subnav?.tone === "amber"
      ? {
          wrap: "border-[#f6dfc9] bg-[#fff8f1]",
          label: "text-[#9a5a16]",
          active: "bg-white text-[#9a5a16] shadow-sm",
        }
      : subnav?.tone === "teal" || subnav?.tone === "green"
        ? {
            wrap: "border-[#cdeee9] bg-[#f4fffc]",
            label: "text-[#0f766e]",
            active: "bg-white text-[#0f766e] shadow-sm",
          }
        : {
            wrap: "border-[#dfe4ff] bg-[#f7f8ff]",
            label: "text-[#5b76fe]",
            active: "bg-white text-[#5b76fe] shadow-sm",
          };

  const isSubnavActive = (key: string): boolean => {
    if (key === "workspace") {
      return location.pathname.startsWith("/marketplace/workspace");
    }
    if (key === "marketplace") return location.pathname === "/marketplace";
    if (key === "mySettings") return location.pathname.startsWith("/marketplace/settings") || location.pathname.startsWith("/sharing");
    if (key === "trialMatch") return location.pathname.startsWith("/trials");
    if (key === "medAccess") return location.pathname.startsWith("/medication-access");
    if (key === "payerCheck") return location.pathname.startsWith("/payer-check");
    if (key === "trials") return location.pathname.startsWith("/trials");
    if (key === "medication") return location.pathname.startsWith("/medication-access");
    if (key === "payer") return location.pathname.startsWith("/payer-check");
    if (key === "grants") return location.pathname.startsWith("/grants");
    if (key === "research") return location.pathname.startsWith("/research-opportunities");
    if (key === "sharing") return location.pathname.startsWith("/sharing");
    if (key === "secondOpinion") return location.pathname.startsWith("/second-opinion");
    if (key === "chartHome") return location.pathname.startsWith("/charts") || location.pathname.startsWith("/record");
    if (key === "snapshot") return location.pathname === "/explorer";
    if (key === "history") return location.pathname.startsWith("/explorer/history");
    if (key === "journey") return location.pathname.startsWith("/explorer/care-journey");
    if (key === "sources") return location.pathname.startsWith("/explorer/patient-data");
    if (key === "walkthrough") return location.pathname === "/aggregate" || location.pathname.startsWith("/aggregate/methodology");
    if (key === "sourceInventory") return location.pathname.startsWith("/aggregate/sources");
    if (key === "cleaningQueue") return location.pathname.startsWith("/aggregate/cleaning");
    if (key === "patientContext") return location.pathname.startsWith("/aggregate/context");
    if (key === "publishReadiness") return location.pathname.startsWith("/aggregate/publish");
    if (key === "preop") {
      return (
        location.pathname.startsWith("/preop") ||
        location.pathname === "/journey"
      );
    }
    if (key === "medSafety") return location.pathname.startsWith("/explorer/safety");
    if (key === "clearance") return location.pathname.startsWith("/explorer/clearance");
    if (key === "anesthesia") return location.pathname.startsWith("/explorer/anesthesia");
    if (key === "qa") return location.pathname.startsWith("/explorer/assistant");
    if (key === "dataLab") return location.pathname === "/analysis";
    if (key === "catalog") return location.pathname.startsWith("/catalog");
    if (key === "primer") return location.pathname.startsWith("/analysis/fhir-primer");
    if (key === "methodology") return location.pathname.startsWith("/analysis/methodology");
    if (key === "coverage") return location.pathname.startsWith("/analysis/coverage");
    return false;
  };

  const isPathActive = (path: string): boolean => {
    if (path === "/explorer") return location.pathname === "/explorer";
    if (path === "/journey") return location.pathname === "/journey";
    return location.pathname.startsWith(path);
  };

  const isPreOpModulePath =
    location.pathname.startsWith("/preop") ||
    location.pathname === "/journey" ||
    location.pathname.startsWith("/explorer/clearance") ||
    location.pathname.startsWith("/explorer/safety") ||
    location.pathname.startsWith("/explorer/anesthesia");

  const navigate = useNavigate();

  const handleSelectPatient = (id: string) => {
    // Use navigate (like landing page cards) to ensure reliable routing
    const base =
      location.pathname.startsWith("/explorer") ||
      location.pathname.startsWith("/record") ||
      location.pathname.startsWith("/charts") ||
      location.pathname.startsWith("/aggregate") ||
      location.pathname.startsWith("/clinical-insights") ||
      location.pathname.startsWith("/preop") ||
      location.pathname.startsWith("/journey") ||
      location.pathname.startsWith("/trials") ||
      location.pathname.startsWith("/medication-access") ||
      location.pathname.startsWith("/marketplace") ||
      location.pathname.startsWith("/sharing") ||
      location.pathname.startsWith("/second-opinion") ||
      location.pathname.startsWith("/grants") ||
      location.pathname.startsWith("/research-opportunities") ||
      location.pathname.startsWith("/payer-check")
        ? location.pathname
        : location.pathname.startsWith("/platform")
          ? "/explorer"
        : "/charts";
    navigate(`${base}?patient=${id}`);
  };

  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      if ((event.metaKey || event.ctrlKey) && event.key === "k") {
        event.preventDefault();
        setPaletteOpen((open) => !open);
      }
    }

    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, []);

  const showSubnav = subnav !== null;
  const showSidebar = !isPlatform;

  return (
    <>
      <CommandPalette open={paletteOpen} onClose={() => setPaletteOpen(false)} />
      <PatientPickerModal
        key={patientId ?? "no-patient"}
        open={patientPickerOpen}
        selectedId={patientId}
        onSelect={(id) => {
          handleSelectPatient(id);
          setPatientPickerOpen(false);
        }}
        onClose={() => setPatientPickerOpen(false)}
      />

      <div className={`h-screen overflow-hidden ${isInternal ? "bg-[#edf7f5]" : "bg-[#f5f6f8]"}`}>
        <header
          className={`border-b border-[#e9eaef] ${isInternal ? "bg-[#f7fffc]" : "bg-white"}`}
          style={{ height: headerHeight }}
        >
          <div className="flex h-full flex-col justify-center gap-2 px-4 lg:px-6">
            <div className="flex items-center justify-between gap-4">
              <Link to="/" className="min-w-0 group cursor-pointer no-underline">
                <div className="flex items-center gap-2">
                  <p className="text-xs font-semibold uppercase tracking-wider text-[#a5a8b5] group-hover:text-[#5b76fe] transition-colors">EHI Exchange Platform</p>
                  <span className="rounded px-1.5 py-0.5 text-[10px] font-medium leading-none text-[#555a6a] bg-[#f5f6f8] border border-[#e9eaef]">
                    Aggregate once · Activate anywhere
                  </span>
                </div>
                <p className="truncate text-sm font-semibold text-[#1c1c1e] group-hover:text-[#5b76fe] transition-colors">
                  {workspace.title}
                </p>
              </Link>

              <div className="flex min-w-0 flex-1 items-center justify-end gap-2">
                {!isInternal && (
                  <PatientSelector
                    patientId={patientId}
                    onSelect={handleSelectPatient}
                    onAdvancedOpen={() => setPatientPickerOpen(true)}
                  />
                )}

                <nav className="flex min-w-0 max-w-[820px] items-center gap-1 overflow-x-auto rounded-xl border border-[#e9eaef] bg-white p-1">
                  {topLinks.map((link) => {
                    const active = topArea === link.key;
                    const activeClass = link.key === "internal" ? "bg-[#dff6ef] text-[#0f766e]" : "bg-[#eef1ff] text-[#5b76fe]";
                    return (
                      <Link
                        key={link.key}
                        to={link.to}
                        className={`shrink-0 rounded-lg px-3 py-1.5 text-xs font-semibold transition-colors lg:text-sm ${
                          active ? activeClass : "text-[#667085] hover:text-[#1f2937]"
                        }`}
                      >
                        {link.label}
                      </Link>
                    );
                  })}
                </nav>
              </div>
            </div>

            {showSubnav && (
              <div className={`flex min-w-0 items-center gap-2 rounded-xl border px-2 py-1.5 ${subnavTone.wrap}`}>
                <span className={`hidden shrink-0 px-2 text-[10px] font-semibold uppercase tracking-wider md:inline ${subnavTone.label}`}>
                  {subnav.label}
                </span>
                <nav className="flex min-w-0 flex-1 items-center gap-1 overflow-x-auto">
                  {subnav.links.map((link) => {
                    const active = isSubnavActive(String(link.key));
                    return (
                      <Link
                        key={link.key}
                        to={link.to}
                        className={`shrink-0 rounded-lg px-3 py-1.5 text-xs font-semibold transition-colors ${
                          active ? subnavTone.active : "text-[#667085] hover:bg-white/70 hover:text-[#1f2937]"
                        }`}
                      >
                        {link.label}
                      </Link>
                    );
                  })}
                </nav>
              </div>
            )}
          </div>
        </header>

        <div className="flex flex-col overflow-hidden lg:flex-row" style={{ height: `calc(100vh - ${headerHeight}px)` }}>
          {showSidebar && (
            <aside
              className={`relative flex max-h-[50vh] w-full shrink-0 flex-col overflow-hidden border-b border-r border-[#e9eaef] transition-all duration-200 lg:max-h-full lg:border-b-0 ${
              sidebarCollapsed ? "lg:w-14" : "lg:w-72"
            } ${isInternal ? "bg-[#f7fffc]" : "bg-white"}`}
            >
            {!isInternal && (
              <>
                {/* Workspace header + collapse toggle */}
                <div className="shrink-0 border-b border-[#e9eaef] px-2 pb-3 pt-4 lg:px-3">
                  {environment === "marketplace" ? (
                    <div className="flex items-start justify-between gap-2">
                      <Link
                        to={withPatientQuery("/marketplace/overview", patientId)}
                        title={sidebarCollapsed ? "Marketplace overview" : undefined}
                        className={`flex min-w-0 flex-1 items-start gap-2 rounded-lg no-underline transition-colors hover:bg-[#f5f6f8] ${
                          sidebarCollapsed ? "justify-center p-2" : "-ml-1 px-1 py-1.5"
                        }`}
                      >
                        <WorkspaceIcon size={18} className={`mt-0.5 shrink-0 ${sidebarTone.icon}`} />
                        {!sidebarCollapsed && (
                          <span className="min-w-0">
                            <span className="block text-sm font-semibold tracking-tight text-[#1c1c1e]">{workspace.sidebarTitle}</span>
                            <span className="mt-1 block text-xs leading-5 text-[#a5a8b5]">{workspace.subtitle}</span>
                          </span>
                        )}
                      </Link>
                      <button
                        onClick={toggleSidebar}
                        className={`hidden lg:flex shrink-0 items-center justify-center w-6 h-6 rounded hover:bg-[#f5f6f8] text-[#a5a8b5] hover:text-[#555a6a] transition-colors ${sidebarCollapsed ? "absolute right-1 top-4" : ""}`}
                        title={sidebarCollapsed ? "Expand sidebar" : "Collapse sidebar"}
                      >
                        {sidebarCollapsed ? <ChevronsRight size={14} /> : <ChevronsLeft size={14} />}
                      </button>
                    </div>
                  ) : (
                    <>
                      <div className="flex items-center justify-between">
                        <div className={`flex items-center gap-2 ${sidebarCollapsed ? "justify-center w-full" : ""}`}>
                          <WorkspaceIcon size={18} className={`shrink-0 ${sidebarTone.icon}`} />
                          {!sidebarCollapsed && (
                            <span className="text-sm font-semibold tracking-tight text-[#1c1c1e]">{workspace.sidebarTitle}</span>
                          )}
                        </div>
                        <button
                          onClick={toggleSidebar}
                          className={`hidden lg:flex shrink-0 items-center justify-center w-6 h-6 rounded hover:bg-[#f5f6f8] text-[#a5a8b5] hover:text-[#555a6a] transition-colors ${sidebarCollapsed ? "absolute right-1 top-4" : ""}`}
                          title={sidebarCollapsed ? "Expand sidebar" : "Collapse sidebar"}
                        >
                          {sidebarCollapsed ? <ChevronsRight size={14} /> : <ChevronsLeft size={14} />}
                        </button>
                      </div>
                      {!sidebarCollapsed && (
                        <p className="mt-1 text-xs text-[#a5a8b5]">{workspace.subtitle}</p>
                      )}
                    </>
                  )}
                </div>

                {/* Nav links — always scrollable, takes remaining space */}
                <nav className={`flex-1 overflow-y-auto ${sidebarCollapsed ? "px-1 py-2" : "px-3 py-4"}`}>
                  {clinicalNavGroups.map((group, groupIndex) => {
                    const isAdvanced = group.advanced === true;
                    const isOpen = !isAdvanced || advancedOpen;
                    return (
                      <div key={group.label} className={groupIndex > 0 && !sidebarCollapsed ? "mt-3" : ""}>
                        {!sidebarCollapsed && (
                          isAdvanced ? (
                            <button
                              onClick={() => setAdvancedOpen((prev) => !prev)}
                              className="mb-2 flex w-full items-center justify-between px-2 text-[10px] font-semibold uppercase tracking-wider text-[#a5a8b5] hover:text-[#555a6a] transition-colors"
                            >
                              <span>{group.label}</span>
                              {advancedOpen ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
                            </button>
                          ) : (
                            <p className={`mb-2 px-2 text-[10px] font-semibold uppercase tracking-wider ${sidebarTone.group}`}>
                              {group.label}
                            </p>
                          )
                        )}
                        {isOpen && (
                          <div className="space-y-0.5">
                            {group.items.map(({ to, label, icon: Icon, description, children }) => {
                              const hasChildren = Boolean(children?.length);
                              const childActive = children?.some((child) => isPathActive(child.to)) ?? false;
                              const expanded = hasChildren && !sidebarCollapsed && (preOpOpen || childActive || (to === "/preop" && isPreOpModulePath));

                              return (
                                <div key={to}>
                                  <div className="flex items-stretch gap-1">
                                    <NavLink
                                      to={withPatientQuery(to, patientId)}
                                      end={shouldMatchSidebarLinkExactly(to)}
                                      title={sidebarCollapsed ? label : undefined}
                                      className={({ isActive }) =>
                                        `flex min-w-0 flex-1 items-center rounded-lg transition-colors ${
                                          sidebarCollapsed
                                            ? `justify-center p-2.5 ${isActive || childActive ? sidebarTone.activeCollapsed : `text-[#555a6a] ${sidebarTone.hover}`}`
                                            : `gap-3 px-3 py-2.5 text-sm ${isActive || childActive ? sidebarTone.active : `text-[#555a6a] ${sidebarTone.hover}`}`
                                        }`
                                      }
                                    >
                                      <Icon size={sidebarCollapsed ? 18 : 16} className="shrink-0" />
                                      {!sidebarCollapsed && (
                                        <div className="min-w-0 flex-1">
                                          <div className="truncate">{label}</div>
                                          <div className="truncate text-xs font-normal opacity-60">{description}</div>
                                        </div>
                                      )}
                                    </NavLink>
                                    {hasChildren && !sidebarCollapsed && (
                                      <button
                                        onClick={() => setPreOpOpen((prev) => !prev)}
                                        className={`flex w-8 shrink-0 items-center justify-center rounded-lg transition-colors ${
                                          childActive ? sidebarTone.active : `text-[#a5a8b5] ${sidebarTone.hover}`
                                        }`}
                                        title={expanded ? "Collapse Pre-Op Support modules" : "Expand Pre-Op Support modules"}
                                      >
                                        {expanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
                                      </button>
                                    )}
                                  </div>

                                  {expanded && (
                                    <div className="ml-5 mt-1 space-y-0.5 border-l border-[#f0d7bf] pl-2">
                                      {children?.map(({ to: childTo, label: childLabel, icon: ChildIcon, description: childDescription }) => (
                                        <NavLink
                                          key={childTo}
                                          to={withPatientQuery(childTo, patientId)}
                                          end={childTo === "/journey"}
                                          className={({ isActive }) =>
                                            `flex items-center gap-2 rounded-lg px-2.5 py-2 text-xs transition-colors ${
                                              isActive
                                                ? "bg-white font-medium text-[#9a5a16] shadow-[rgb(246_223_201)_0px_0px_0px_1px]"
                                                : "text-[#667085] hover:bg-[#fff8f1] hover:text-[#1c1c1e]"
                                            }`
                                          }
                                        >
                                          <ChildIcon size={13} className="shrink-0" />
                                          <div className="min-w-0">
                                            <div className="truncate">{childLabel}</div>
                                            <div className="truncate text-[11px] font-normal opacity-60">{childDescription}</div>
                                          </div>
                                        </NavLink>
                                      ))}
                                    </div>
                                  )}
                                </div>
                              );
                            })}
                          </div>
                        )}
                      </div>
                    );
                  })}
                </nav>
              </>
            )}

            {isInternal && (
              <>
                <div className="shrink-0 border-b border-[#d5ebe5] px-2 pb-3 pt-4 lg:px-3">
                  <div className="flex items-center justify-between">
                    <div className={`flex items-center gap-2 ${sidebarCollapsed ? "justify-center w-full" : ""}`}>
                      <WorkspaceIcon size={18} className="shrink-0 text-[#0f766e]" />
                      {!sidebarCollapsed && (
                        <span className="text-sm font-semibold tracking-tight text-[#0f172a]">{workspace.sidebarTitle}</span>
                      )}
                    </div>
                    <button
                      onClick={toggleSidebar}
                      className={`hidden lg:flex shrink-0 items-center justify-center w-6 h-6 rounded hover:bg-[#edf9f5] text-[#55706c] hover:text-[#0f172a] transition-colors ${sidebarCollapsed ? "absolute right-1 top-4" : ""}`}
                      title={sidebarCollapsed ? "Expand sidebar" : "Collapse sidebar"}
                    >
                      {sidebarCollapsed ? <ChevronsRight size={14} /> : <ChevronsLeft size={14} />}
                    </button>
                  </div>
                  {!sidebarCollapsed && (
                    <p className="mt-1 text-xs text-[#55706c]">{workspace.subtitle}</p>
                  )}
                </div>

                {!sidebarCollapsed && (
                  <div className="shrink-0 border-b border-[#d5ebe5] px-4 py-3">
                    <p className="text-[11px] font-semibold uppercase tracking-wider text-[#55706c]">Corpus Snapshot</p>
                    <div className="mt-2 grid grid-cols-2 gap-2">
                      <div className="rounded-lg bg-white px-2.5 py-2 shadow-[rgb(213_235_229)_0px_0px_0px_1px]">
                        <p className="text-[10px] uppercase tracking-wider text-[#55706c]">Patients</p>
                        <p className="text-sm font-semibold text-[#0f172a]">
                          {corpusStats ? corpusStats.total_patients.toLocaleString() : "..."}
                        </p>
                      </div>
                      <div className="rounded-lg bg-white px-2.5 py-2 shadow-[rgb(213_235_229)_0px_0px_0px_1px]">
                        <p className="text-[10px] uppercase tracking-wider text-[#55706c]">Resources</p>
                        <p className="text-sm font-semibold text-[#0f172a]">
                          {corpusStats ? corpusStats.total_resources.toLocaleString() : "..."}
                        </p>
                      </div>
                    </div>
                  </div>
                )}

                <nav className={`space-y-0.5 border-t border-[#d5ebe5] ${sidebarCollapsed ? "px-1 py-2" : "px-3 py-4"}`}>
                  {!sidebarCollapsed && (
                    <p className="mb-2 px-2 text-xs font-medium uppercase tracking-wider text-[#55706c]">Data Views</p>
                  )}
                  {INTERNAL_NAV_LINKS.map(({ to, label, icon: Icon, description }) => (
                    <NavLink
                      key={to}
                      to={to}
                      end={to === "/analysis"}
                      title={sidebarCollapsed ? label : undefined}
                      className={({ isActive }) =>
                        `flex items-center rounded-lg transition-colors ${
                          sidebarCollapsed
                            ? `justify-center p-2.5 ${isActive ? "bg-[#dff6ef] text-[#0f766e]" : "text-[#35524d] hover:bg-[#edf9f5] hover:text-[#0f172a]"}`
                            : `gap-3 px-3 py-2.5 text-sm ${isActive ? "bg-[#dff6ef] font-medium text-[#0f766e]" : "text-[#35524d] hover:bg-[#edf9f5] hover:text-[#0f172a]"}`
                        }`
                      }
                    >
                      <Icon size={sidebarCollapsed ? 18 : 16} />
                      {!sidebarCollapsed && (
                        <div>
                          <div>{label}</div>
                          <div className="text-xs font-normal opacity-70">{description}</div>
                        </div>
                      )}
                    </NavLink>
                  ))}
                </nav>
              </>
            )}

            {!sidebarCollapsed && (
              <div className={`shrink-0 border-t px-4 py-3 ${isAnalysis ? "border-[#d5ebe5]" : "border-[#e9eaef]"}`}>
                <p className={`text-xs ${isAnalysis ? "text-[#55706c]" : "text-[#a5a8b5]"}`}>
                  EHI Ignite Challenge · Phase 1
                </p>
              </div>
            )}
            </aside>
          )}

          {activeModuleMap && ActiveModuleMapIcon && (
            <aside
              className={`relative flex max-h-[50vh] w-full shrink-0 flex-col overflow-hidden border-b border-r border-[#dfe4ff] bg-[#fbfcff] transition-all duration-200 lg:max-h-full lg:border-b-0 ${
                moduleMapOpen ? "lg:w-72" : "lg:w-14"
              }`}
            >
              <div className={`shrink-0 border-b border-[#dfe4ff] ${moduleMapOpen ? "px-3 py-4" : "px-1 py-3"}`}>
                <div className={`flex items-center ${moduleMapOpen ? "justify-between gap-3" : "justify-center"}`}>
                  <div className={`flex min-w-0 items-center gap-2 ${moduleMapOpen ? "" : "justify-center"}`}>
                    <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-[#eef1ff] text-[#5b76fe]">
                      <ActiveModuleMapIcon size={17} />
                    </span>
                    {moduleMapOpen && (
                      <div className="min-w-0">
                        <p className="truncate text-[10px] font-semibold uppercase tracking-wider text-[#5b76fe]">Module Map</p>
                        <p className="truncate text-sm font-semibold text-[#1c1c1e]">{activeModuleMap.title}</p>
                      </div>
                    )}
                  </div>
                  <button
                    type="button"
                    onClick={() => setModuleMapOpen((open) => !open)}
                    className={`hidden h-6 w-6 shrink-0 items-center justify-center rounded text-[#8d92a3] transition-colors hover:bg-[#eef1ff] hover:text-[#5b76fe] lg:flex ${
                      moduleMapOpen ? "" : "absolute right-1 top-4"
                    }`}
                    title={moduleMapOpen ? `Collapse ${activeModuleMap.title} map` : `Expand ${activeModuleMap.title} map`}
                  >
                    {moduleMapOpen ? <ChevronsLeft size={14} /> : <ChevronsRight size={14} />}
                  </button>
                </div>
                {moduleMapOpen && <p className="mt-2 text-xs leading-5 text-[#8d92a3]">{activeModuleMap.subtitle}</p>}
              </div>

              {moduleMapOpen ? (
                <nav className="flex-1 overflow-y-auto px-3 py-4">
                  <div className="space-y-2">
                    {activeModuleMap.sections.map((section) => {
                      const SectionIcon = section.icon;
                      const sectionOpen = openModuleMapSections.has(section.id);
                      return (
                        <div key={section.id} className="border-b border-[#edf0ff] pb-2 last:border-b-0">
                          <button
                            type="button"
                            onClick={() => toggleModuleMapSection(section.id)}
                            className="flex w-full items-center justify-between gap-2 rounded-lg px-2.5 py-2 text-left transition-colors hover:bg-[#f3f5ff]"
                          >
                            <span className="flex min-w-0 items-center gap-2">
                              <SectionIcon size={14} className="shrink-0 text-[#5b76fe]" />
                              <span className="min-w-0">
                                <span className="block truncate text-sm font-semibold text-[#1c1c1e]">{section.label}</span>
                                <span className="block truncate text-[11px] text-[#8d92a3]">{section.description}</span>
                              </span>
                            </span>
                            <span className="shrink-0 text-[#a5a8b5]">
                              {sectionOpen ? <ChevronDown size={13} /> : <ChevronRight size={13} />}
                            </span>
                          </button>

                          {sectionOpen && (
                            <div className="ml-4 mt-1 space-y-0.5 border-l border-[#dfe4ff] pl-2">
                              {section.items.map((item) => {
                                const itemPath = item.path ?? `${activeModuleMap.basePath}#${item.hash}`;
                                const active = isModuleMapItemActive(activeModuleMap, item, location.pathname, location.hash);
                                return (
                                  <Link
                                    key={item.hash}
                                    to={item.path ? withPatientQuery(itemPath, patientId) : `${withPatientQuery(activeModuleMap.basePath, patientId)}#${item.hash}`}
                                    className={`block rounded-md px-2.5 py-2 no-underline transition-colors ${
                                      active ? "bg-[#eef1ff] text-[#5b76fe]" : "text-[#555a6a] hover:bg-[#f3f5ff] hover:text-[#1c1c1e]"
                                    }`}
                                  >
                                    <span className="block text-xs font-medium">{item.label}</span>
                                    <span className="block truncate text-[11px] opacity-65">{item.description}</span>
                                  </Link>
                                );
                              })}
                            </div>
                          )}
                        </div>
                      );
                    })}
                  </div>
                </nav>
              ) : (
                <nav className="flex-1 space-y-1 px-1 py-2">
                  {activeModuleMap.sections.map((section) => {
                    const SectionIcon = section.icon;
                    return (
                      <button
                        key={section.id}
                        type="button"
                        onClick={() => {
                          setModuleMapOpen(true);
                          toggleModuleMapSection(section.id);
                        }}
                        className="flex w-full justify-center rounded-lg p-2.5 text-[#667085] transition-colors hover:bg-[#eef1ff] hover:text-[#5b76fe]"
                        title={section.label}
                      >
                        <SectionIcon size={17} />
                      </button>
                    );
                  })}
                </nav>
              )}
            </aside>
          )}

          <main className={`flex-1 overflow-y-auto px-4 py-3 ${isInternal ? "bg-[#edf7f5]" : "bg-[#f5f6f8]"}`}>
            {children}
          </main>
        </div>
      </div>
    </>
  );
}
