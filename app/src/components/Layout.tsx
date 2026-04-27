import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, NavLink, useLocation, useNavigate, useSearchParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import {
  Activity,
  BarChart2,
  BarChart3,
  BookMarked,
  CalendarDays,
  ChevronDown,
  ChevronRight,
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
  Search,
  ShieldAlert,
  SlidersHorizontal,
  Star,
  Stethoscope,
  Syringe,
  TestTubeDiagonal,
  UserRound,
  X,
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

interface NavGroup {
  label: string;
  items: NavItem[];
  advanced?: boolean;
}

const CLINICAL_NAV_GROUPS: NavGroup[] = [
  {
    label: "Pre-op Essentials",
    items: [
      { to: "/explorer", label: "Overview", icon: Database, description: "Patient summary" },
      { to: "/explorer/safety", label: "Safety", icon: ShieldAlert, description: "Pre-op risk flags" },
      { to: "/explorer/clearance", label: "Clearance", icon: ClipboardCheck, description: "Pre-op readiness check" },
      { to: "/explorer/anesthesia", label: "Anesthesia", icon: Stethoscope, description: "Anesthesia handoff card" },
      { to: "/explorer/interactions", label: "Interactions", icon: Zap, description: "Drug-drug interactions" },
    ],
  },
  {
    label: "Longitudinal",
    items: [
      { to: "/explorer/timeline", label: "Timeline", icon: CalendarDays, description: "Encounter history" },
      { to: "/explorer/care-journey", label: "Care Journey", icon: Heart, description: "Visual care timeline" },
      { to: "/explorer/conditions", label: "Conditions", icon: Activity, description: "Surgical risk ranking" },
      { to: "/explorer/procedures", label: "Procedures", icon: Scissors, description: "Procedure history" },
      { to: "/explorer/immunizations", label: "Immunizations", icon: Syringe, description: "Vaccination history" },
    ],
  },
  {
    label: "Context & Data",
    items: [
      { to: "/explorer/assistant", label: "Assistant", icon: MessageSquareText, description: "AI chart Q&A" },
      { to: "/explorer/patient-data", label: "FHIR Data", icon: FileJson2, description: "Patient bundle metrics" },
      { to: "/explorer/corpus", label: "Corpus", icon: BarChart3, description: "Population statistics" },
      { to: "/explorer/distributions", label: "Distributions", icon: BarChart2, description: "Lab value distributions" },
    ],
  },
  {
    label: "Advanced",
    advanced: true,
    items: [
      { to: "/journey", label: "Patient Journey", icon: Activity, description: "Clinical briefing" },
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

  const [sidebarCollapsed, setSidebarCollapsed] = useState<boolean>(() => {
    try { return localStorage.getItem("ehi-sidebar-collapsed") === "true"; } catch { return false; }
  });
  const [advancedOpen, setAdvancedOpen] = useState<boolean>(false);
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

  const navigate = useNavigate();

  const handleSelectPatient = (id: string) => {
    // Use navigate (like landing page cards) to ensure reliable routing
    const base =
      location.pathname.startsWith("/explorer") || location.pathname.startsWith("/journey")
        ? location.pathname
        : "/explorer";
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

      <div className={`h-screen overflow-hidden ${isAnalysis ? "bg-[#edf7f5]" : "bg-[#f5f6f8]"}`}>
        <header
          className={`border-b border-[#e9eaef] ${isAnalysis ? "bg-[#f7fffc]" : "bg-white"}`}
          style={{ height: 72 }}
        >
          <div className="flex h-full flex-col justify-center gap-2 px-4 lg:px-6">
            <div className="flex items-center justify-between gap-4">
              <Link to="/" className="min-w-0 group cursor-pointer no-underline">
                <div className="flex items-center gap-2">
                  <p className="text-xs font-semibold uppercase tracking-wider text-[#a5a8b5] group-hover:text-[#5b76fe] transition-colors">EHI Ignite</p>
                  <span className="rounded px-1.5 py-0.5 text-[10px] font-medium leading-none text-[#555a6a] bg-[#f5f6f8] border border-[#e9eaef]">
                    Synthetic data · Synthea R4
                  </span>
                </div>
                <p className="truncate text-sm font-semibold text-[#1c1c1e] group-hover:text-[#5b76fe] transition-colors">
                  {isAnalysis ? "Data Analysis & Methodology Environment" : "Clinical Intelligence Workspace"}
                </p>
              </Link>

              <div className="flex items-center gap-2">
                {!isAnalysis && (
                  <PatientSelector
                    patientId={patientId}
                    onSelect={handleSelectPatient}
                    onAdvancedOpen={() => setPatientPickerOpen(true)}
                  />
                )}

                <nav className="flex items-center gap-1 rounded-xl border border-[#e9eaef] bg-white p-1">
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
          </div>
        </header>

        <div className="flex h-[calc(100vh-72px)] flex-col overflow-hidden lg:flex-row">
          <aside
            className={`relative flex max-h-[50vh] w-full shrink-0 flex-col overflow-hidden border-b border-r border-[#e9eaef] transition-all duration-200 lg:max-h-full lg:border-b-0 ${
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

                {/* Nav links — always scrollable, takes remaining space */}
                <nav className={`flex-1 overflow-y-auto ${sidebarCollapsed ? "px-1 py-2" : "px-3 py-4"}`}>
                  {CLINICAL_NAV_GROUPS.map((group, groupIndex) => {
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
                            <p className="mb-2 px-2 text-[10px] font-semibold uppercase tracking-wider text-[#a5a8b5]">
                              {group.label}
                            </p>
                          )
                        )}
                        {isOpen && (
                          <div className="space-y-0.5">
                            {group.items.map(({ to, label, icon: Icon, description }) => (
                              <NavLink
                                key={to}
                                to={withPatientQuery(to, patientId)}
                                end={to === "/explorer"}
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
                          </div>
                        )}
                      </div>
                    );
                  })}
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

          <main className={`flex-1 overflow-y-auto px-4 py-3 ${isAnalysis ? "bg-[#edf7f5]" : "bg-[#f5f6f8]"}`}>
            {children}
          </main>
        </div>
      </div>
    </>
  );
}
