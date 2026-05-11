import { useMemo, useState } from "react";
import type { ReactNode } from "react";
import { Link, useLocation, useSearchParams } from "react-router-dom";
import {
  Activity,
  Bot,
  CalendarDays,
  ChevronLeft,
  ChevronRight,
  FileBarChart,
  Heart,
  Pill,
  ShieldAlert,
  Syringe,
  TestTube2,
  UserRound,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";

type FhirChartsLayoutProps = {
  children: ReactNode;
};

type FhirNavItem = {
  label: string;
  description: string;
  to: string;
  icon: LucideIcon;
  match: (pathname: string) => boolean;
};

const SIDEBAR_STORAGE_KEY = "atlas:fhir-charts-nav-collapsed";

function withPatient(path: string, patientId: string | null): string {
  return patientId ? `${path}?patient=${encodeURIComponent(patientId)}` : path;
}

export function FhirChartsLayout({ children }: FhirChartsLayoutProps) {
  const location = useLocation();
  const [searchParams] = useSearchParams();
  const patientId = searchParams.get("patient");
  const [collapsed, setCollapsed] = useState<boolean>(() => {
    if (typeof window === "undefined") return false;
    return window.localStorage.getItem(SIDEBAR_STORAGE_KEY) === "true";
  });

  const items = useMemo<FhirNavItem[]>(
    () => [
      {
        label: "Summary",
        description: "Prepared chart snapshot",
        to: withPatient("/fhir-charts", patientId),
        icon: UserRound,
        match: (pathname) => pathname === "/fhir-charts",
      },
      {
        label: "History",
        description: "Timeline and preview",
        to: withPatient("/fhir-charts/history", patientId),
        icon: CalendarDays,
        match: (pathname) => pathname.startsWith("/fhir-charts/history"),
      },
      {
        label: "Care Journey",
        description: "Episodes and chronology",
        to: withPatient("/fhir-charts/care-journey", patientId),
        icon: Heart,
        match: (pathname) =>
          pathname.startsWith("/fhir-charts/care-journey") ||
          pathname.startsWith("/fhir-charts/journey"),
      },
      {
        label: "Labs",
        description: "Key observations",
        to: withPatient("/fhir-charts/labs", patientId),
        icon: TestTube2,
        match: (pathname) => pathname.startsWith("/fhir-charts/labs"),
      },
      {
        label: "Safety",
        description: "Risk and alerts",
        to: withPatient("/fhir-charts/safety", patientId),
        icon: ShieldAlert,
        match: (pathname) => pathname.startsWith("/fhir-charts/safety"),
      },
      {
        label: "Interactions",
        description: "Medication interplay",
        to: withPatient("/fhir-charts/interactions", patientId),
        icon: Pill,
        match: (pathname) => pathname.startsWith("/fhir-charts/interactions"),
      },
      {
        label: "Immunizations",
        description: "Vaccine history",
        to: withPatient("/fhir-charts/immunizations", patientId),
        icon: Syringe,
        match: (pathname) => pathname.startsWith("/fhir-charts/immunizations"),
      },
      {
        label: "Patient Data",
        description: "Resource distribution",
        to: withPatient("/fhir-charts/patient-data", patientId),
        icon: FileBarChart,
        match: (pathname) => pathname.startsWith("/fhir-charts/patient-data"),
      },
      {
        label: "Assistant",
        description: "Chart-grounded Q&A",
        to: withPatient("/fhir-charts/assistant", patientId),
        icon: Bot,
        match: (pathname) => pathname.startsWith("/fhir-charts/assistant"),
      },
    ],
    [patientId],
  );

  const activeItem = items.find((item) => item.match(location.pathname)) ?? items[0];

  const toggleCollapsed = () => {
    setCollapsed((current) => {
      const next = !current;
      window.localStorage.setItem(SIDEBAR_STORAGE_KEY, String(next));
      return next;
    });
  };

  return (
    <div className="flex min-h-0 flex-1 overflow-hidden">
      <aside
        className={`hidden border-r border-[#dfe4ea] bg-white/88 backdrop-blur md:flex md:flex-col ${
          collapsed ? "w-[72px]" : "w-[268px]"
        }`}
      >
        <div className="border-b border-[#eef0f4] px-3 py-3">
          <div className="flex items-start justify-between gap-2">
            {!collapsed && (
              <div className="min-w-0">
                <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-[#5b76fe]">
                  Prepared Charts
                </p>
                <p className="mt-1 text-sm font-semibold text-[#1c1c1e]">
                  FHIR review workspace
                </p>
                <p className="mt-1 text-xs leading-5 text-[#667085]">
                  Summary first, then move into preview-heavy chart views.
                </p>
              </div>
            )}
            <button
              type="button"
              onClick={toggleCollapsed}
              className="inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border border-[#dfe4ea] bg-white text-[#667085] hover:border-[#5b76fe] hover:text-[#5b76fe]"
              aria-label={collapsed ? "Open FHIR charts navigation" : "Collapse FHIR charts navigation"}
              title={collapsed ? "Open navigation" : "Collapse navigation"}
            >
              {collapsed ? <ChevronRight size={16} /> : <ChevronLeft size={16} />}
            </button>
          </div>
        </div>

        <nav className="flex-1 space-y-1 overflow-auto px-2 py-3">
          {items.map((item, index) => {
            const active = item.match(location.pathname);
            const Icon = item.icon;
            return (
              <Link
                key={item.label}
                to={item.to}
                className={`group flex items-start gap-3 rounded-xl px-3 py-3 no-underline transition-colors ${
                  active
                    ? "bg-[#eef1ff] text-[#4157d8] shadow-[inset_0_0_0_1px_rgba(91,118,254,0.18)]"
                    : "text-[#5d6474] hover:bg-[#f6f8fc] hover:text-[#1c1c1e]"
                }`}
                title={collapsed ? item.label : undefined}
              >
                <div
                  className={`mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg ${
                    active
                      ? "bg-white text-[#5b76fe]"
                      : "bg-[#f4f6fa] text-[#7b8597] group-hover:bg-white"
                  }`}
                >
                  <Icon size={16} />
                </div>
                {!collapsed && (
                  <div className="min-w-0">
                    <div className="flex items-center gap-2">
                      <p className="text-sm font-semibold">{item.label}</p>
                      <span className="text-[11px] font-semibold text-[#9aa3b2]">
                        {index + 1}
                      </span>
                    </div>
                    <p className="mt-1 text-xs leading-5 text-[#7b8597]">
                      {item.description}
                    </p>
                  </div>
                )}
              </Link>
            );
          })}
        </nav>

        {!collapsed && (
          <div className="border-t border-[#eef0f4] px-3 py-3">
            <div className="rounded-xl bg-[#f7f9fc] px-3 py-3">
              <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-[#667085]">
                Default View
              </p>
              <p className="mt-1 text-sm font-semibold text-[#1c1c1e]">
                {activeItem.label}
              </p>
              <p className="mt-1 text-xs leading-5 text-[#667085]">
                {patientId
                  ? `${activeItem.description} for the selected prepared chart.`
                  : "Pick a sample chart or account workspace to open the prepared chart surfaces."}
              </p>
              {!patientId && (
                <div className="mt-3 flex items-center gap-2 rounded-lg bg-white px-2.5 py-2 text-xs text-[#5b76fe]">
                  <Activity size={14} />
                  Sample charts can launch directly into this workspace.
                </div>
              )}
            </div>
          </div>
        )}
      </aside>

      <div className="min-h-0 min-w-0 flex-1 overflow-auto">{children}</div>
    </div>
  );
}
