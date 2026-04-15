import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, NavLink, useLocation, useSearchParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import {
  Activity,
  BarChart2,
  BarChart3,
  BookMarked,
  CalendarDays,
  ChevronsLeft,
  ChevronsRight,
  ClipboardCheck,
  Database,
  FileJson2,
  GraduationCap,
  Heart,
  Layers3,
  MessageSquareText,
  Scissors,
  ShieldAlert,
  Star,
  Stethoscope,
  Syringe,
  TestTubeDiagonal,
  Zap,
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
type AppEnvironment = "clinical" | "analysis";

interface NavItem {
  to: string;
  label: string;
  icon: LucideIcon;
  description: string;
}

const CLINICAL_NAV_LINKS: NavItem[] = [
  { to: "/explorer", label: "Overview", icon: Database, description: "Patient summary" },
  { to: "/explorer/timeline", label: "Timeline", icon: CalendarDays, description: "Encounter history" },
  { to: "/explorer/care-journey", label: "Care Journey", icon: Heart, description: "Visual care timeline" },
  { to: "/explorer/safety", label: "Safety", icon: ShieldAlert, description: "Pre-op risk flags" },
  { to: "/explorer/interactions", label: "Interactions", icon: Zap, description: "Drug-drug interactions" },
  { to: "/explorer/conditions", label: "Conditions", icon: Activity, description: "Surgical risk ranking" },
  { to: "/explorer/procedures", label: "Procedures", icon: Scissors, description: "Procedure history" },
  { to: "/explorer/immunizations", label: "Immunizations", icon: Syringe, description: "Vaccination history" },
  { to: "/explorer/clearance", label: "Clearance", icon: ClipboardCheck, description: "Pre-op readiness check" },
  { to: "/explorer/anesthesia", label: "Anesthesia", icon: Stethoscope, description: "Anesthesia handoff card" },
  { to: "/explorer/assistant", label: "Assistant", icon: MessageSquareText, description: "Provider chart Q&A" },
  { to: "/explorer/corpus", label: "Corpus", icon: BarChart3, description: "Population statistics" },
  { to: "/explorer/distributions", label: "Distributions", icon: BarChart2, description: "Lab value distributions" },
  { to: "/journey", label: "Patient Journey", icon: Activity, description: "Clinical briefing" },
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

function withPatientQuery(path: string, patientId: string | null): string {
  if (!patientId) return path;
  return `${path}?patient=${patientId}`;
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

function PatientList({
  selectedId,
  onSelect,
}: {
  selectedId: string | null;
  onSelect: (id: string) => void;
}) {
  const [filter, setFilter] = useState<FilterMode>("all");

  const { data: patients = [], isLoading: patientsLoading } = useQuery({
    queryKey: ["patients"],
    queryFn: api.listPatients,
    staleTime: Infinity,
  });

  const { data: riskSummary = [], isLoading: riskQueryLoading } = useQuery({
    queryKey: ["risk-summary"],
    queryFn: api.getRiskSummary,
    staleTime: 5 * 60 * 1000,
  });

  const riskMap = useMemo(
    () => new Map<string, PatientRiskSummary>(riskSummary.map((item) => [item.id, item])),
    [riskSummary]
  );

  const { isFavorite, toggleFavorite } = useFavorites();

  const riskLoading = filter !== "all" && riskQueryLoading;

  let visiblePatients = patients;
  if (!riskLoading && filter === "high_risk") {
    visiblePatients = patients.filter((patient) => {
      const risk = riskMap.get(patient.id);
      return risk?.complexity_tier === "complex" || risk?.complexity_tier === "highly_complex";
    });
  }

  if (!riskLoading && filter === "needs_review") {
    visiblePatients = patients.filter((patient) => riskMap.get(patient.id)?.has_critical_flag === true);
  }

  const favorites = visiblePatients.filter((patient) => isFavorite(patient.id));
  const others = visiblePatients.filter((patient) => !isFavorite(patient.id));

  function renderRow(patient: PatientListItem) {
    const active = patient.id === selectedId;
    const favorited = isFavorite(patient.id);
    const risk = riskMap.get(patient.id);

    return (
      <div
        key={patient.id}
        className={`group flex items-center gap-1 rounded-lg pr-1 transition-colors ${
          active ? "bg-[#eef1ff]" : "hover:bg-[#f5f6f8]"
        }`}
      >
        <button
          onClick={() => onSelect(patient.id)}
          className={`flex flex-1 items-center gap-2 truncate px-3 py-2 text-left text-sm ${
            active ? "font-medium text-[#5b76fe]" : "text-[#1c1c1e]"
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

  if (patientsLoading) {
    return (
      <div className="space-y-1 px-1">
        {[1, 2, 3, 4].map((item) => (
          <div key={item} className="h-8 animate-pulse rounded-lg bg-[#f5f6f8]" />
        ))}
      </div>
    );
  }

  return (
    <div className="flex flex-1 flex-col overflow-hidden">
      <div className="shrink-0 px-3 pb-1 pt-2">
        <div className="flex gap-1">
          {FILTER_OPTIONS.map(({ key, label }) => (
            <button
              key={key}
              onClick={() => setFilter(key)}
              className={`flex-1 rounded-full px-2 py-1 text-xs transition-colors ${
                filter === key ? "bg-[#eef1ff] font-medium text-[#5b76fe]" : "text-[#a5a8b5] hover:text-[#555a6a]"
              }`}
            >
              {label}
            </button>
          ))}
        </div>
      </div>

      <div className="flex-1 overflow-y-auto px-2 py-2">
        {riskLoading && (
          <div className="space-y-1">
            {[1, 2, 3].map((item) => (
              <div key={item} className="h-8 animate-pulse rounded-lg bg-[#f5f6f8]" />
            ))}
          </div>
        )}

        {!riskLoading && (
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
              <p className="px-3 py-4 text-center text-sm text-[#a5a8b5]">
                {filter === "all" ? "No patients available" : "No patients match this filter"}
              </p>
            )}
          </>
        )}
      </div>
    </div>
  );
}

export function Layout({ children }: LayoutProps) {
  const location = useLocation();
  const [searchParams, setSearchParams] = useSearchParams();
  const patientId = searchParams.get("patient");

  const [paletteOpen, setPaletteOpen] = useState(false);

  const [sidebarCollapsed, setSidebarCollapsed] = useState<boolean>(() => {
    try { return localStorage.getItem("ehi-sidebar-collapsed") === "true"; } catch { return false; }
  });
  const toggleSidebar = useCallback(() => {
    setSidebarCollapsed((prev) => {
      const next = !prev;
      try { localStorage.setItem("ehi-sidebar-collapsed", String(next)); } catch { /* noop */ }
      return next;
    });
  }, []);

  const environment: AppEnvironment = location.pathname.startsWith("/analysis") ? "analysis" : "clinical";
  const isAnalysis = environment === "analysis";

  const { data: corpusStats } = useQuery({
    queryKey: ["corpus-stats"],
    queryFn: api.getCorpusStats,
    staleTime: Infinity,
    enabled: isAnalysis,
  });

  const clinicalLanding = withPatientQuery("/explorer", patientId);

  const handleSelectPatient = (id: string) => {
    const next = new URLSearchParams(searchParams);
    next.set("patient", id);
    setSearchParams(next);
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

  return (
    <>
      <CommandPalette open={paletteOpen} onClose={() => setPaletteOpen(false)} />

      <div className={`h-screen overflow-hidden ${isAnalysis ? "bg-[#edf7f5]" : "bg-[#f5f6f8]"}`}>
        <header
          className={`border-b border-[#e9eaef] ${isAnalysis ? "bg-[#f7fffc]" : "bg-white"}`}
          style={{ height: 72 }}
        >
          <div className="flex h-full flex-col justify-center gap-2 px-4 lg:px-6">
            <div className="flex items-center justify-between gap-4">
              <div className="min-w-0">
                <p className="text-xs font-semibold uppercase tracking-wider text-[#a5a8b5]">EHI Ignite</p>
                <p className="truncate text-sm font-semibold text-[#1c1c1e]">
                  {isAnalysis ? "Data Analysis & Methodology Environment" : "Clinical Intelligence Workspace"}
                </p>
              </div>

              <nav className="flex min-w-0 items-center gap-1 rounded-xl border border-[#e9eaef] bg-white p-1">
                <Link
                  to={clinicalLanding}
                  className={`rounded-lg px-3 py-1.5 text-xs font-semibold transition-colors lg:text-sm ${
                    !isAnalysis ? "bg-[#eef1ff] text-[#5b76fe]" : "text-[#667085] hover:text-[#1f2937]"
                  }`}
                >
                  Clinical
                </Link>
                <Link
                  to="/analysis"
                  className={`rounded-lg px-3 py-1.5 text-xs font-semibold transition-colors lg:text-sm ${
                    isAnalysis ? "bg-[#dff6ef] text-[#0f766e]" : "text-[#667085] hover:text-[#1f2937]"
                  }`}
                >
                  Data Lab
                </Link>
              </nav>
            </div>
          </div>
        </header>

        <div className="flex h-[calc(100vh-72px)] flex-col overflow-hidden lg:flex-row">
          <aside
            className={`relative flex max-h-[50vh] w-full shrink-0 flex-col overflow-hidden border-b border-r border-[#e9eaef] transition-all duration-200 lg:max-h-none lg:border-b-0 ${
              sidebarCollapsed ? "lg:w-14" : "lg:w-72"
            } ${isAnalysis ? "bg-[#f7fffc]" : "bg-white"}`}
          >
            {!isAnalysis && (
              <>
                {/* Workspace header + collapse toggle */}
                <div className="shrink-0 border-b border-[#e9eaef] px-2 pb-3 pt-4 lg:px-3">
                  <div className="flex items-center justify-between">
                    <div className={`flex items-center gap-2 ${sidebarCollapsed ? "justify-center w-full" : ""}`}>
                      <Activity size={18} className="shrink-0 text-[#5b76fe]" />
                      {!sidebarCollapsed && (
                        <span className="text-sm font-semibold tracking-tight text-[#1c1c1e]">Clinical Workspace</span>
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
                    <p className="mt-1 text-xs text-[#a5a8b5]">Patient-level safety and chart review</p>
                  )}
                </div>

                {/* Search + patient list (hidden when collapsed) */}
                {!sidebarCollapsed && (
                  <div className="flex min-h-0 flex-1 flex-col overflow-hidden">
                    <div className="shrink-0 border-b border-[#e9eaef] px-4 py-3">
                      <button
                        onClick={() => setPaletteOpen(true)}
                        className="flex w-full items-center gap-2 rounded-lg border border-[#e9eaef] bg-[#f5f6f8] px-3 py-2 text-sm text-[#a5a8b5] transition-colors hover:border-[#5b76fe] hover:text-[#555a6a]"
                      >
                        <span className="flex-1 text-left">Search patients…</span>
                        <kbd className="shrink-0 rounded border border-[#e9eaef] bg-white px-1 py-0.5 font-mono text-[10px]">
                          ⌘K
                        </kbd>
                      </button>
                    </div>

                    <PatientList selectedId={patientId} onSelect={handleSelectPatient} />
                  </div>
                )}

                {/* Nav links */}
                <nav className={`shrink-0 space-y-0.5 overflow-y-auto border-t border-[#e9eaef] ${sidebarCollapsed ? "px-1 py-2" : "px-3 py-4"}`}>
                  {!sidebarCollapsed && (
                    <p className="mb-2 px-2 text-xs font-medium uppercase tracking-wider text-[#a5a8b5]">Views</p>
                  )}
                  {CLINICAL_NAV_LINKS.map(({ to, label, icon: Icon, description }) => (
                    <NavLink
                      key={to}
                      to={withPatientQuery(to, patientId)}
                      title={sidebarCollapsed ? label : undefined}
                      className={({ isActive }) =>
                        `flex items-center rounded-lg transition-colors ${
                          sidebarCollapsed
                            ? `justify-center p-2.5 ${isActive ? "bg-[#eef1ff] text-[#5b76fe]" : "text-[#555a6a] hover:bg-[#f5f6f8] hover:text-[#1c1c1e]"}`
                            : `gap-3 px-3 py-2.5 text-sm ${isActive ? "bg-[#eef1ff] font-medium text-[#5b76fe]" : "text-[#555a6a] hover:bg-[#f5f6f8] hover:text-[#1c1c1e]"}`
                        }`
                      }
                    >
                      <Icon size={sidebarCollapsed ? 18 : 16} />
                      {!sidebarCollapsed && (
                        <div>
                          <div>{label}</div>
                          <div className="text-xs font-normal opacity-60">{description}</div>
                        </div>
                      )}
                    </NavLink>
                  ))}
                </nav>
              </>
            )}

            {isAnalysis && (
              <>
                <div className="shrink-0 border-b border-[#d5ebe5] px-2 pb-3 pt-4 lg:px-3">
                  <div className="flex items-center justify-between">
                    <div className={`flex items-center gap-2 ${sidebarCollapsed ? "justify-center w-full" : ""}`}>
                      <BookMarked size={18} className="shrink-0 text-[#0f766e]" />
                      {!sidebarCollapsed && (
                        <span className="text-sm font-semibold tracking-tight text-[#0f172a]">Data Lab</span>
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
                    <p className="mt-1 text-xs text-[#55706c]">Definitions, methodology, and reliability evidence</p>
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
                  {ANALYSIS_NAV_LINKS.map(({ to, label, icon: Icon, description }) => (
                    <NavLink
                      key={to}
                      to={to}
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

          <main className={`flex-1 overflow-y-auto px-4 py-3 ${isAnalysis ? "bg-[#edf7f5]" : "bg-[#f5f6f8]"}`}>
            {children}
          </main>
        </div>
      </div>
    </>
  );
}
