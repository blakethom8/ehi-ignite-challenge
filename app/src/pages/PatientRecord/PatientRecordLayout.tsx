import { useMemo, useState } from "react";
import type { ReactNode } from "react";
import { Link, useLocation, useSearchParams } from "react-router-dom";
import {
  BookMarked,
  ChevronLeft,
  ChevronRight,
  Database,
  FileSearch,
  FolderKanban,
  Layers3,
  MessageSquareText,
  ShieldCheck,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";

type PatientRecordLayoutProps = {
  children: ReactNode;
};

type PatientNavItem = {
  label: string;
  description: string;
  to: string;
  icon: LucideIcon;
  match: (pathname: string) => boolean;
};

const SIDEBAR_STORAGE_KEY = "atlas:patient-record-nav-collapsed";

function withPatient(path: string, patientId: string | null): string {
  return patientId ? `${path}?patient=${encodeURIComponent(patientId)}` : path;
}

export function PatientRecordLayout({ children }: PatientRecordLayoutProps) {
  const location = useLocation();
  const [searchParams] = useSearchParams();
  const patientId = searchParams.get("patient");
  const [collapsed, setCollapsed] = useState<boolean>(() => {
    if (typeof window === "undefined") return false;
    return window.localStorage.getItem(SIDEBAR_STORAGE_KEY) === "true";
  });

  const items = useMemo<PatientNavItem[]>(
    () => [
      {
        label: "Prepared Chart",
        description: "Overview and chart posture",
        to: withPatient("/patient-record", patientId),
        icon: Database,
        match: (pathname) => pathname === "/patient-record",
      },
      {
        label: "Workspace Library",
        description: "Profiles and containers",
        to: withPatient("/patient-record/workspaces", patientId),
        icon: FolderKanban,
        match: (pathname) => pathname.startsWith("/patient-record/workspaces"),
      },
      {
        label: "Source Intake",
        description: "Collect source material",
        to: withPatient("/patient-record/sources", patientId),
        icon: FileSearch,
        match: (pathname) => pathname.startsWith("/patient-record/sources"),
      },
      {
        label: "Harmonized Record",
        description: "Resolve canonical facts",
        to: withPatient("/patient-record/harmonize", patientId),
        icon: Layers3,
        match: (pathname) =>
          pathname.startsWith("/patient-record/harmonize") ||
          pathname.startsWith("/patient-record/cleaning"),
      },
      {
        label: "Publish Chart",
        description: "Activate downstream snapshot",
        to: withPatient("/patient-record/publish", patientId),
        icon: ShieldCheck,
        match: (pathname) => pathname.startsWith("/patient-record/publish"),
      },
      {
        label: "Patient Context",
        description: "Capture missing story",
        to: withPatient("/patient-record/context", patientId),
        icon: MessageSquareText,
        match: (pathname) => pathname.startsWith("/patient-record/context"),
      },
      {
        label: "Methodology",
        description: "Pipeline and trust model",
        to: withPatient("/patient-record/methodology", patientId),
        icon: BookMarked,
        match: (pathname) => pathname.startsWith("/patient-record/methodology"),
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
        className={`hidden border-r border-[#dfe4ea] bg-white/86 backdrop-blur md:flex md:flex-col ${
          collapsed ? "w-[72px]" : "w-[268px]"
        }`}
      >
        <div className="border-b border-[#eef0f4] px-3 py-3">
          <div className="flex items-start justify-between gap-2">
            {!collapsed && (
              <div className="min-w-0">
                <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-[#5b76fe]">
                  Patient Workflow
                </p>
                <p className="mt-1 text-sm font-semibold text-[#1c1c1e]">
                  Patient Record pipeline
                </p>
                <p className="mt-1 text-xs leading-5 text-[#667085]">
                  Move from intake to publish with a consistent left-rail workflow.
                </p>
              </div>
            )}
            <button
              type="button"
              onClick={toggleCollapsed}
              className="inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border border-[#dfe4ea] bg-white text-[#667085] hover:border-[#5b76fe] hover:text-[#5b76fe]"
              aria-label={collapsed ? "Open patient workflow navigation" : "Collapse patient workflow navigation"}
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
                Current Step
              </p>
              <p className="mt-1 text-sm font-semibold text-[#1c1c1e]">
                {activeItem.label}
              </p>
              <p className="mt-1 text-xs leading-5 text-[#667085]">
                {activeItem.description}
              </p>
            </div>
          </div>
        )}
      </aside>

      <div className="min-h-0 min-w-0 flex-1 overflow-auto">{children}</div>
    </div>
  );
}
