import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, NavLink, useLocation, useNavigate, useSearchParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
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
  FileUp,
  Code2,
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
import type { AggregationCreateProfilePayload, PatientListItem, PatientRiskSummary } from "../types";

interface LayoutProps {
  children: React.ReactNode;
}

type FilterMode = "all" | "high_risk" | "needs_review";
type AppEnvironment = "platform" | "record" | "aggregator" | "clinical" | "marketplace" | "trials" | "medication" | "sharing" | "analysis";
type TopArea = "platform" | "record" | "aggregator" | "clinical" | "marketplace" | "internal" | "using-atlas";

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
  { to: "/explorer/labs", label: "Labs", icon: TestTubeDiagonal, description: "Lab history" },
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
      { to: "/aggregate", label: "Overview", icon: DatabaseZap, description: "Aggregation guide" },
      { to: "/aggregate/workspaces", label: "Workspace Library", icon: Archive, description: "Create and manage workspaces" },
      { to: "/aggregate/sources", label: "Source Intake", icon: FileJson2, description: "Upload and source checklist" },
      { to: "/aggregate/harmonize", label: "Harmonized Record", icon: Layers3, description: "Merge, review, provenance" },
      { to: "/aggregate/context", label: "Patient Context", icon: MessageSquareText, description: "Guided patient intake" },
      { to: "/aggregate/publish", label: "Publish Chart", icon: ClipboardCheck, description: "Activate chart snapshots" },
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
  { to: "/analysis", label: "Module Overview", icon: BookMarked, description: "Internal tools overview" },
  { to: "/ai-workspace/trial-finder", label: "AI Workspace", icon: MessageSquareText, description: "Clean agent workspace shell" },
  { to: "/pipeline-lab", label: "Pipeline Lab", icon: DatabaseZap, description: "PDF parser experiment leaderboard" },
  { to: "/analysis/qa-eval-lab", label: "Q&A Eval Lab", icon: MessageSquareText, description: "Clinical question test development" },
  { to: "/analysis/ccda-testing-lab", label: "C-CDA Testing Lab", icon: FileJson2, description: "C-CDA and PDF to FHIR playground" },
  { to: "/ground-truth-review", label: "Reference Review", icon: ClipboardCheck, description: "Human-reviewed benchmark bundles" },
  ...ANALYSIS_NAV_LINKS.filter((item) => item.to !== "/analysis"),
];

function withPatientQuery(path: string, patientId: string | null): string {
  if (!patientId) return path;
  return `${path}?patient=${patientId}`;
}

function getEnvironment(pathname: string): AppEnvironment {
  if (pathname.startsWith("/platform")) return "platform";
  if (pathname.startsWith("/ai-workspace")) return "analysis";
  if (pathname.startsWith("/pipeline-lab")) return "analysis";
  if (pathname.startsWith("/ground-truth-review")) return "analysis";
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
      subtitle: "Guided intake, harmonization, and chart publishing",
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
      title: "Internal Tools",
      sidebarTitle: "Data Lab",
      subtitle: "Evaluation, conversion, and benchmark tooling",
      icon: BookMarked,
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
  if (environment === "analysis") return "internal";
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
  onCreateWorkspace,
  onClose,
}: {
  open: boolean;
  selectedId: string | null;
  onSelect: (id: string) => void;
  onCreateWorkspace: () => void;
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
  const uploadWorkspaces = visiblePatients.filter((patient) => (
    (patient.workspace_type === "upload" || patient.workspace_type === "profile") && !isFavorite(patient.id)
  ));
  const syntheaPatients = visiblePatients.filter((patient) => (
    patient.workspace_type !== "upload" && patient.workspace_type !== "profile" && !isFavorite(patient.id)
  ));
  const selectedPatient = patients.find((patient) => patient.id === selectedId);
  const previewPatient = patients.find((patient) => patient.id === previewId) ?? selectedPatient ?? visiblePatients[0];
  const previewRisk = previewPatient ? riskMap.get(previewPatient.id) : undefined;
  const previewIsWorkspace = previewPatient?.workspace_type === "upload" || previewPatient?.workspace_type === "profile";
  const complexCount = patients.filter((patient) => (
    patient.complexity_tier === "complex" || patient.complexity_tier === "highly_complex"
  )).length;
  const criticalCount = riskSummary.filter((patient) => patient.has_critical_flag).length;

  function renderRow(patient: PatientListItem) {
    const active = patient.id === selectedId;
    const previewing = patient.id === previewPatient?.id;
    const favorited = isFavorite(patient.id);
    const risk = riskMap.get(patient.id);
    const isUploadWorkspace = patient.workspace_type === "upload" || patient.workspace_type === "profile";

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
              {isUploadWorkspace
                ? `${patient.source_count ?? patient.total_resources} sources · ${patient.prepared_source_count ?? 0} prepared`
                : `${patient.total_resources} resources · ${patient.active_condition_count} conditions · ${patient.active_med_count} meds`}
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
              Switch the patient workspace used by Source Intake, Harmonized Record, charts, and clinical modules.
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
                  {previewIsWorkspace
                    ? `${previewPatient.source_count ?? previewPatient.total_resources} sources · ${previewPatient.prepared_source_count ?? 0} prepared · server-local profile`
                    : `${previewPatient.gender} · ${Math.floor(previewPatient.age_years)} years · ${previewPatient.complexity_score.toFixed(0)}/100 complexity`}
                </p>
                <div className="mt-3 grid grid-cols-2 gap-2 text-sm">
                  <div className="rounded-lg bg-[#f5f6f8] p-2">
                    <p className="text-[10px] uppercase tracking-wider text-[#a5a8b5]">{previewIsWorkspace ? "Sources" : "Resources"}</p>
                    <p className="font-semibold text-[#1c1c1e]">
                      {(previewIsWorkspace ? previewPatient.source_count ?? 0 : previewPatient.total_resources).toLocaleString()}
                    </p>
                  </div>
                  <div className="rounded-lg bg-[#f5f6f8] p-2">
                    <p className="text-[10px] uppercase tracking-wider text-[#a5a8b5]">Tier</p>
                    <p className="capitalize font-semibold text-[#1c1c1e]">
                      {previewIsWorkspace ? "Demo profile" : previewPatient.complexity_tier.replace("_", " ")}
                    </p>
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

            <button
              type="button"
              onClick={onCreateWorkspace}
              className="mt-3 flex w-full items-center justify-between rounded-xl border border-[#dfe4ea] bg-white px-3 py-2.5 text-left text-sm font-semibold text-[#5b76fe] transition-colors hover:border-[#5b76fe] hover:bg-[#f8faff]"
            >
              <span className="inline-flex items-center gap-2">
                <FileUp size={15} />
                New patient workspace
              </span>
              <ChevronRight size={14} />
            </button>
            <p className="mt-2 rounded-lg border border-[#f0d7bf] bg-[#fff8f1] px-3 py-2 text-xs leading-5 text-[#8a5a24]">
              Demo storage: profiles and uploads are stored on this application server for the prototype.
            </p>

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

                  {uploadWorkspaces.length > 0 && (
                    <>
                      <p className="mb-1 px-2 text-[10px] font-semibold uppercase tracking-wider text-[#a5a8b5]">
                        Uploaded workspaces and profiles
                      </p>
                      <div className="mb-3 space-y-0.5">{uploadWorkspaces.map(renderRow)}</div>
                      <div className="mb-3 border-t border-[#e9eaef]" />
                    </>
                  )}

                  <p className="mb-1 px-2 text-[10px] font-semibold uppercase tracking-wider text-[#a5a8b5]">
                    {filter === "all" ? "Synthea patients" : filter === "high_risk" ? "High Risk" : "Needs Review"}
                  </p>
                  <div className="space-y-0.5">{syntheaPatients.map(renderRow)}</div>

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
  onCreateWorkspace,
  onAdvancedOpen,
}: {
  patientId: string | null;
  onSelect: (id: string) => void;
  onCreateWorkspace: () => void;
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
  const currentLabel = current
    ? current.name
    : patientId
      ? patientId.startsWith("workspace-")
        ? "New patient workspace"
        : patientId
      : "Select patient";

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return patients;
    return patients.filter((p) => p.name.toLowerCase().includes(q));
  }, [patients, search]);
  const uploadWorkspaces = filtered.filter((patient) => patient.workspace_type === "upload" || patient.workspace_type === "profile");
  const syntheaPatients = filtered.filter((patient) => patient.workspace_type !== "upload" && patient.workspace_type !== "profile");

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
        title="Switch patient workspace"
      >
        <UserRound size={14} className="shrink-0" />
        <span className="max-w-[180px] truncate font-medium">
          {isLoading ? "Loading…" : currentLabel}
        </span>
        <ChevronDown size={13} className={`shrink-0 transition-transform ${open ? "rotate-180" : ""}`} />
      </button>

      {open && (
        <div className="absolute left-0 top-full z-50 mt-1 w-72 rounded-xl border border-[#e9eaef] bg-white shadow-lg">
          <div className="border-b border-[#e9eaef] px-3 py-2.5">
            <p className="text-xs font-semibold uppercase tracking-wider text-[#5b76fe]">Patient workspace</p>
            <p className="mt-1 text-xs leading-5 text-[#667085]">
              Development selector for uploaded sessions, curated profiles, and Synthea patients.
            </p>
          </div>
          <button
            type="button"
            onClick={() => {
              setOpen(false);
              setSearch("");
              onCreateWorkspace();
            }}
            className="flex w-full items-center justify-between border-b border-[#e9eaef] px-3 py-2 text-left text-sm font-semibold text-[#5b76fe] transition-colors hover:bg-[#eef1ff]"
          >
            <span className="inline-flex items-center gap-2">
              <FileUp size={14} />
              New patient workspace
            </span>
            <ChevronRight size={14} />
          </button>
          <p className="border-b border-[#e9eaef] px-3 py-2 text-[11px] leading-5 text-[#8d92a3]">
            Demo storage: profiles and uploads are stored on this application server for the prototype.
          </p>
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
            {uploadWorkspaces.length > 0 && (
              <p className="px-3 pb-1 pt-2 text-[10px] font-semibold uppercase tracking-wider text-[#a5a8b5]">
                Uploaded workspaces and profiles
              </p>
            )}
            {uploadWorkspaces.slice(0, 20).map((p) => (
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
                    {(p.source_count ?? p.total_resources).toLocaleString()} sources · {(p.prepared_source_count ?? 0).toLocaleString()} prepared
                  </p>
                </div>
                {p.id === patientId && (
                  <span className="mt-0.5 shrink-0 text-[#5b76fe]">✓</span>
                )}
              </button>
            ))}
            <p className="px-3 pb-1 pt-2 text-[10px] font-semibold uppercase tracking-wider text-[#a5a8b5]">
              Synthea patients
            </p>
            {syntheaPatients.slice(0, 100).map((p) => (
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
            {syntheaPatients.length > 100 && (
              <p className="px-4 py-2 text-center text-[11px] text-[#a5a8b5]">
                {syntheaPatients.length - 100} more — type to narrow
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

function CreateWorkspaceModal({
  form,
  isPending,
  error,
  onChange,
  onClose,
  onSubmit,
}: {
  form: Required<AggregationCreateProfilePayload>;
  isPending: boolean;
  error: Error | null;
  onChange: (form: Required<AggregationCreateProfilePayload>) => void;
  onClose: () => void;
  onSubmit: () => void;
}) {
  return (
    <div className="fixed inset-0 z-[70] flex items-start justify-center overflow-y-auto bg-[#101828]/35 px-4 py-10 backdrop-blur-[2px]">
      <section className="w-full max-w-xl overflow-hidden rounded-xl border border-[#dfe4ea] bg-white shadow-2xl">
        <header className="flex items-start justify-between gap-4 border-b border-[#eef0f5] px-5 py-4">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wider text-[#5b76fe]">New patient workspace</p>
            <h2 className="mt-1 text-lg font-semibold text-[#1c1c1e]">Name the workspace before adding files</h2>
            <p className="mt-1 text-sm leading-6 text-[#667085]">
              This creates a saved demo profile. Uploaded records will stay attached to this name in the patient selector, Source Intake, FHIR Charts, and Clinical Insights.
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-[#dfe4ea] text-[#667085] hover:border-[#5b76fe] hover:text-[#5b76fe]"
            aria-label="Close new patient workspace"
          >
            <X size={16} />
          </button>
        </header>
        <div className="space-y-4 px-5 py-4">
          <label className="block text-sm font-semibold text-[#1c1c1e]">
            Patient or workspace name
            <input
              value={form.display_name}
              onChange={(event) => onChange({ ...form, display_name: event.target.value })}
              placeholder="Example: Blake test upload, Aaron demo packet"
              className="mt-2 w-full rounded-lg border border-[#dfe4ea] px-3 py-2 text-sm outline-none focus:border-[#5b76fe]"
            />
          </label>
          <label className="block text-sm font-semibold text-[#1c1c1e]">
            Notes
            <textarea
              value={form.notes}
              onChange={(event) => onChange({ ...form, notes: event.target.value })}
              placeholder="Optional context for this demo workspace."
              className="mt-2 min-h-[88px] w-full resize-y rounded-lg border border-[#dfe4ea] px-3 py-2 text-sm outline-none focus:border-[#5b76fe]"
            />
          </label>
          <div className="rounded-lg border border-[#f0d7bf] bg-[#fff8f1] px-3 py-2 text-xs leading-5 text-[#8a5a24]">
            Demo storage: the profile and uploaded files are saved on this application server. Use synthetic or test records unless you intentionally want to test the hosted demo environment.
          </div>
          {error && (
            <p className="rounded-lg border border-red-100 bg-red-50 px-3 py-2 text-sm text-red-700">
              {error.message}
            </p>
          )}
        </div>
        <footer className="flex justify-end gap-2 border-t border-[#eef0f5] bg-[#f8faff] px-5 py-4">
          <button type="button" onClick={onClose} className="rounded-lg border border-[#dfe4ea] bg-white px-3 py-2 text-sm font-semibold text-[#555a6a]">
            Cancel
          </button>
          <button
            type="button"
            onClick={onSubmit}
            disabled={isPending || !form.display_name.trim()}
            className="rounded-lg bg-[#5b76fe] px-4 py-2 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:opacity-60"
          >
            {isPending ? "Creating..." : "Create workspace"}
          </button>
        </footer>
      </section>
    </div>
  );
}
// ───────────────────────────────────────────────────────────────────────────────

export function Layout({ children }: LayoutProps) {
  const location = useLocation();
  const [searchParams] = useSearchParams();
  const patientId = searchParams.get("patient");
  const queryClient = useQueryClient();

  const [paletteOpen, setPaletteOpen] = useState(false);
  const [patientPickerOpen, setPatientPickerOpen] = useState(false);
  const [moduleMapOpen, setModuleMapOpen] = useState(true);
  const [openModuleMapSections, setOpenModuleMapSections] = useState<Set<string>>(() => new Set(["trial-review"]));
  const [createWorkspaceOpen, setCreateWorkspaceOpen] = useState(false);
  const [createWorkspaceForm, setCreateWorkspaceForm] = useState<Required<AggregationCreateProfilePayload>>({
    display_name: "",
    notes: "",
  });

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
  const isInternal = environment === "analysis";
  const clinicalNavGroups = getClinicalNavGroups(environment);
  const workspace = getWorkspaceCopy(environment);
  const WorkspaceIcon = workspace.icon;
  const sidebarOverviewPath =
    environment === "marketplace"
      ? "/marketplace/overview"
      : environment === "clinical"
        ? "/clinical-insights/overview"
        : null;
  const topArea: TopArea = location.pathname.startsWith("/using-atlas")
    ? "using-atlas"
    : getTopArea(environment);
  const activeModuleMap = getActiveModuleMap(location.pathname);
  const ActiveModuleMapIcon = activeModuleMap?.icon;
  const headerHeight = 72;
  const sidebarTone =
    topArea === "clinical"
      ? {
          icon: "text-[#8f5f2e]",
          active: "border-[#8f5f2e] bg-[#f3eee7] font-medium text-[#171717]",
          activeCollapsed: "bg-[#f3eee7] text-[#171717]",
          group: "text-[#8f5f2e]",
          hover: "hover:bg-[#f3eee7] hover:text-[#171717]",
        }
      : topArea === "record"
        ? {
            icon: "text-[#2f6f68]",
            active: "border-[#2f6f68] bg-[#edf5f2] font-medium text-[#171717]",
            activeCollapsed: "bg-[#edf5f2] text-[#171717]",
            group: "text-[#2f6f68]",
            hover: "hover:bg-[#edf5f2] hover:text-[#171717]",
          }
        : {
            icon: "text-[#3f5edb]",
            active: "border-[#3f5edb] bg-[#eef1ff] font-medium text-[#171717]",
            activeCollapsed: "bg-[#eef1ff] text-[#171717]",
            group: "text-[#3f5edb]",
            hover: "hover:bg-[#f0f1ed] hover:text-[#171717]",
          };

  const { data: corpusStats } = useQuery({
    queryKey: ["corpus-stats"],
    queryFn: api.getCorpusStats,
    staleTime: Infinity,
    enabled: isInternal,
  });

  const topLinks: { key: TopArea; label: string; to: string }[] = [
    { key: "using-atlas", label: "Using Atlas", to: "/using-atlas" },
    { key: "aggregator", label: "Data Aggregator", to: withPatientQuery("/aggregate", patientId) },
    { key: "record", label: "FHIR Charts", to: withPatientQuery("/charts", patientId) },
    { key: "clinical", label: "Clinical Insights", to: withPatientQuery("/clinical-insights", patientId) },
    { key: "marketplace", label: "Marketplace", to: withPatientQuery("/marketplace", patientId) },
    { key: "internal", label: "Internal Tools", to: "/analysis" },
  ];

  useEffect(() => {
    if (!activeModuleMap) return;
    const activeSectionIds = getActiveModuleMapSectionIds(activeModuleMap, location.pathname, location.hash);
    let cancelled = false;
    queueMicrotask(() => {
      if (cancelled) return;
      setModuleMapOpen(true);
      setOpenModuleMapSections(new Set((activeSectionIds.length ? activeSectionIds : [activeModuleMap.sections[0]?.id]).filter(Boolean) as string[]));
      setSidebarCollapsed(true);
    });
    return () => {
      cancelled = true;
    };
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

  const createProfileMutation = useMutation({
    mutationFn: (payload: AggregationCreateProfilePayload) => api.createAggregationProfile(payload),
    onSuccess: async (response) => {
      await queryClient.invalidateQueries({ queryKey: ["patients"] });
      navigate(`/aggregate/sources?patient=${response.profile.id}`);
      setPatientPickerOpen(false);
      setCreateWorkspaceOpen(false);
      setCreateWorkspaceForm({ display_name: "", notes: "" });
    },
  });

  const handleCreatePatientWorkspace = () => {
    createProfileMutation.reset();
    setCreateWorkspaceForm({ display_name: "", notes: "" });
    setCreateWorkspaceOpen(true);
  };

  const submitCreatePatientWorkspace = () => {
    if (createProfileMutation.isPending || !createWorkspaceForm.display_name.trim()) return;
    createProfileMutation.mutate({
      display_name: createWorkspaceForm.display_name.trim(),
      notes: createWorkspaceForm.notes.trim(),
    });
  };

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
        onCreateWorkspace={handleCreatePatientWorkspace}
        onClose={() => setPatientPickerOpen(false)}
      />
      {createWorkspaceOpen && (
        <CreateWorkspaceModal
          form={createWorkspaceForm}
          isPending={createProfileMutation.isPending}
          error={createProfileMutation.error as Error | null}
          onChange={setCreateWorkspaceForm}
          onClose={() => setCreateWorkspaceOpen(false)}
          onSubmit={submitCreatePatientWorkspace}
        />
      )}

      <div className="h-screen overflow-hidden bg-[#f7f5f0]">
        <header
          className="border-b border-[#e5ded2]/80 bg-[#fbfaf7]/95 backdrop-blur"
          style={{ height: headerHeight }}
        >
          <div className="flex h-full items-center gap-4 px-4 lg:px-6">
            <div className="flex items-center justify-between gap-4">
              <Link to="/" className="group flex min-w-0 items-center gap-3 no-underline">
                <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-[#171717] text-[11px] font-semibold text-[#fbfaf7]">
                  AT
                </span>
                <span className="min-w-0">
                  <span className="block truncate text-sm font-semibold tracking-tight text-[#171717] transition-colors group-hover:text-[#3f5edb]">
                    Atlas
                  </span>
                  <span className="hidden truncate text-xs text-[#6f6a60] sm:block">
                    {workspace.title}
                  </span>
                </span>
              </Link>
            </div>

            <nav className="flex min-w-0 flex-1 items-center justify-start gap-1 overflow-x-auto px-2 lg:justify-center">
              {topLinks.map((link) => {
                const active = topArea === link.key;
                return (
                  <Link
                    key={link.key}
                    to={link.to}
                    className={`shrink-0 rounded-full px-3 py-2 text-sm transition-colors ${
                      active
                        ? "bg-[#e9e4da] font-semibold text-[#171717]"
                        : "font-medium text-[#6f6a60] hover:bg-[#efebe3] hover:text-[#171717]"
                    }`}
                  >
                    {link.label}
                  </Link>
                );
              })}
            </nav>

            <div className="flex shrink-0 items-center justify-end gap-2">
              {!isInternal && (
                <div className="hidden md:block">
                <PatientSelector
                  patientId={patientId}
                  onSelect={handleSelectPatient}
                  onCreateWorkspace={handleCreatePatientWorkspace}
                  onAdvancedOpen={() => setPatientPickerOpen(true)}
                />
                </div>
              )}
              <a
                href="https://github.com/blakethom8/ehi-ignite-challenge"
                target="_blank"
                rel="noopener noreferrer"
                aria-label="View source on GitHub"
                title="View source on GitHub"
                className="hidden h-9 w-9 shrink-0 items-center justify-center rounded-full text-[#6f6a60] transition-colors hover:bg-[#efebe3] hover:text-[#171717] sm:flex"
              >
                <Code2 size={16} />
              </a>
            </div>
          </div>
        </header>

        <div className="flex flex-col overflow-hidden md:flex-row" style={{ height: `calc(100vh - ${headerHeight}px)` }}>
          {showSidebar && (
            <aside
              className={`relative flex max-h-[50vh] w-full shrink-0 flex-col overflow-hidden border-b border-r border-[#e5ded2] bg-[#fbfaf7] transition-all duration-200 md:max-h-full md:border-b-0 ${
              sidebarCollapsed ? "md:w-14" : "md:w-72"
            }`}
            >
            {!isInternal && (
              <>
                {/* Workspace header + collapse toggle */}
                <div className="shrink-0 border-b border-[#e5ded2] px-2 pb-3 pt-4 lg:px-3">
                  {sidebarOverviewPath ? (
                    <div className="flex items-start justify-between gap-2">
                      <Link
                        to={withPatientQuery(sidebarOverviewPath, patientId)}
                        title={sidebarCollapsed ? `${workspace.sidebarTitle} overview` : undefined}
                        className={`flex min-w-0 flex-1 items-start gap-2 rounded-xl no-underline transition-colors hover:bg-[#efebe3] ${
                          sidebarCollapsed ? "justify-center p-2" : "-ml-1 px-1 py-1.5"
                        }`}
                      >
                        <WorkspaceIcon size={18} className={`mt-0.5 shrink-0 ${sidebarTone.icon}`} />
                        {!sidebarCollapsed && (
                          <span className="min-w-0">
                            <span className="block text-sm font-semibold tracking-tight text-[#171717]">{workspace.sidebarTitle}</span>
                            <span className="mt-1 block text-xs leading-5 text-[#6f6a60]">{workspace.subtitle}</span>
                          </span>
                        )}
                      </Link>
                      <button
                        onClick={toggleSidebar}
                        className={`hidden md:flex shrink-0 items-center justify-center w-6 h-6 rounded-full hover:bg-[#efebe3] text-[#8a8174] hover:text-[#171717] transition-colors ${sidebarCollapsed ? "absolute right-1 top-4" : ""}`}
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
                            <span className="text-sm font-semibold tracking-tight text-[#171717]">{workspace.sidebarTitle}</span>
                          )}
                        </div>
                        <button
                          onClick={toggleSidebar}
                          className={`hidden md:flex shrink-0 items-center justify-center w-6 h-6 rounded-full hover:bg-[#efebe3] text-[#8a8174] hover:text-[#171717] transition-colors ${sidebarCollapsed ? "absolute right-1 top-4" : ""}`}
                          title={sidebarCollapsed ? "Expand sidebar" : "Collapse sidebar"}
                        >
                          {sidebarCollapsed ? <ChevronsRight size={14} /> : <ChevronsLeft size={14} />}
                        </button>
                      </div>
                      {!sidebarCollapsed && (
                        <p className="mt-1 text-xs text-[#6f6a60]">{workspace.subtitle}</p>
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
                              className="mb-2 flex w-full items-center justify-between px-2 text-[10px] font-semibold uppercase tracking-wider text-[#8a8174] hover:text-[#171717] transition-colors"
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
                                            : `gap-3 border-l-2 px-3 py-2.5 text-sm ${isActive || childActive ? sidebarTone.active : `border-transparent text-[#504a42] ${sidebarTone.hover}`}`
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
                                          childActive ? sidebarTone.active : `text-[#8a8174] ${sidebarTone.hover}`
                                        }`}
                                        title={expanded ? "Collapse Pre-Op Support modules" : "Expand Pre-Op Support modules"}
                                      >
                                        {expanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
                                      </button>
                                    )}
                                  </div>

                                  {expanded && (
                                    <div className="ml-5 mt-1 space-y-0.5 border-l border-[#ded6ca] pl-2">
                                      {children?.map(({ to: childTo, label: childLabel, icon: ChildIcon, description: childDescription }) => (
                                        <NavLink
                                          key={childTo}
                                          to={withPatientQuery(childTo, patientId)}
                                          end={childTo === "/journey"}
                                          className={({ isActive }) =>
                                            `flex items-center gap-2 rounded-lg px-2.5 py-2 text-xs transition-colors ${
                                              isActive
                                                ? "bg-[#f3eee7] font-medium text-[#171717]"
                                                : "text-[#6f6a60] hover:bg-[#efebe3] hover:text-[#171717]"
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
                <div className="shrink-0 border-b border-[#e5ded2] px-2 pb-3 pt-4 lg:px-3">
                  <div className="flex items-center justify-between">
                    <div className={`flex items-center gap-2 ${sidebarCollapsed ? "justify-center w-full" : ""}`}>
                      <WorkspaceIcon size={18} className="shrink-0 text-[#2f6f68]" />
                      {!sidebarCollapsed && (
                        <span className="text-sm font-semibold tracking-tight text-[#171717]">{workspace.sidebarTitle}</span>
                      )}
                    </div>
                    <button
                      onClick={toggleSidebar}
                      className={`hidden md:flex shrink-0 items-center justify-center w-6 h-6 rounded-full hover:bg-[#efebe3] text-[#8a8174] hover:text-[#171717] transition-colors ${sidebarCollapsed ? "absolute right-1 top-4" : ""}`}
                      title={sidebarCollapsed ? "Expand sidebar" : "Collapse sidebar"}
                    >
                      {sidebarCollapsed ? <ChevronsRight size={14} /> : <ChevronsLeft size={14} />}
                    </button>
                  </div>
                  {!sidebarCollapsed && (
                    <p className="mt-1 text-xs text-[#6f6a60]">{workspace.subtitle}</p>
                  )}
                </div>

                {!sidebarCollapsed && (
                  <div className="shrink-0 border-b border-[#e5ded2] px-4 py-3">
                    <p className="text-[11px] font-semibold uppercase tracking-wider text-[#6f6a60]">Corpus Snapshot</p>
                    <div className="mt-2 grid grid-cols-2 gap-2">
                      <div className="rounded-lg bg-[#f3eee7] px-2.5 py-2">
                        <p className="text-[10px] uppercase tracking-wider text-[#6f6a60]">Patients</p>
                        <p className="text-sm font-semibold text-[#171717]">
                          {corpusStats ? corpusStats.total_patients.toLocaleString() : "..."}
                        </p>
                      </div>
                      <div className="rounded-lg bg-[#f3eee7] px-2.5 py-2">
                        <p className="text-[10px] uppercase tracking-wider text-[#6f6a60]">Resources</p>
                        <p className="text-sm font-semibold text-[#171717]">
                          {corpusStats ? corpusStats.total_resources.toLocaleString() : "..."}
                        </p>
                      </div>
                    </div>
                  </div>
                )}

                <nav className={`space-y-0.5 ${sidebarCollapsed ? "px-1 py-2" : "px-3 py-4"}`}>
                  {!sidebarCollapsed && (
                    <p className="mb-2 px-2 text-[10px] font-semibold uppercase tracking-wider text-[#6f6a60]">Data Views</p>
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
                            ? `justify-center p-2.5 ${isActive ? "bg-[#edf5f2] text-[#171717]" : "text-[#504a42] hover:bg-[#efebe3] hover:text-[#171717]"}`
                            : `gap-3 border-l-2 px-3 py-2.5 text-sm ${isActive ? "border-[#2f6f68] bg-[#edf5f2] font-medium text-[#171717]" : "border-transparent text-[#504a42] hover:bg-[#efebe3] hover:text-[#171717]"}`
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
              <div className="shrink-0 border-t border-[#e5ded2] px-4 py-3">
                <p className="text-xs text-[#8a8174]">
                  EHI Ignite Challenge · Phase 1
                </p>
              </div>
            )}
            </aside>
          )}

          {activeModuleMap && ActiveModuleMapIcon && (
            <aside
              className={`relative flex max-h-[50vh] w-full shrink-0 flex-col overflow-hidden border-b border-r border-[#dfe4ff] bg-[#fbfcff] transition-all duration-200 md:max-h-full md:border-b-0 ${
                moduleMapOpen ? "md:w-72" : "md:w-14"
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
                    className={`hidden h-6 w-6 shrink-0 items-center justify-center rounded text-[#8d92a3] transition-colors hover:bg-[#eef1ff] hover:text-[#5b76fe] md:flex ${
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

          <main className="flex-1 overflow-y-auto bg-[#f7f5f0] px-4 py-3">
            {children}
          </main>
        </div>
      </div>
    </>
  );
}
