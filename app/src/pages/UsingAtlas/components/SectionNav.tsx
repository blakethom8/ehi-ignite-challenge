import { Link, useLocation } from "react-router-dom";
import { BookOpen, GitBranch, FileText, GitMerge, ShieldCheck, Globe } from "lucide-react";

interface SectionPage {
  path: string;
  label: string;
  description: string;
  icon: React.ComponentType<{ size?: number; className?: string }>;
  available: boolean;
}

const SECTION_PAGES: SectionPage[] = [
  {
    path: "/using-atlas",
    label: "Get started",
    description: "What Atlas does, what's inside, and where to look first.",
    icon: BookOpen,
    available: true,
  },
  {
    path: "/using-atlas/pipeline",
    label: "The pipeline",
    description: "How data flows from EHI sources through to a usable record.",
    icon: GitBranch,
    available: true,
  },
  {
    path: "/using-atlas/pdf-extraction",
    label: "PDF extraction",
    description: "Five architectures benchmarked, with live F1 numbers.",
    icon: FileText,
    available: true,
  },
  {
    path: "/using-atlas/harmonization",
    label: "Harmonization",
    description: "Deduplication, conflict detection, and cross-source provenance.",
    icon: GitMerge,
    available: true,
  },
  {
    path: "/using-atlas/trustworthy-ai",
    label: "Trustworthy AI",
    description: "Evidence packets, bounded context, and missing-info disclosure.",
    icon: ShieldCheck,
    available: true,
  },
  {
    path: "/using-atlas/standards",
    label: "Standards & ecosystem",
    description: "FHIR R4, US Core, TEFCA, and where Atlas sits in the stack.",
    icon: Globe,
    available: true,
  },
];

export function SectionNav() {
  const location = useLocation();

  return (
    <nav className="w-56 shrink-0">
      <p className="mb-3 text-[11px] font-semibold uppercase tracking-[0.12em] text-[#9aa5c0]">
        Using Atlas
      </p>
      <ul className="space-y-0.5">
        {SECTION_PAGES.map((page) => {
          const Icon = page.icon;
          const isActive = location.pathname === page.path;

          if (!page.available) {
            return (
              <li key={page.path}>
                <div className="flex items-center gap-2.5 rounded-lg px-3 py-2 opacity-45">
                  <Icon size={14} className="shrink-0 text-[#9aa5c0]" />
                  <span className="text-sm text-[#6b7390]">{page.label}</span>
                  <span className="ml-auto rounded-full bg-[#f0f1f7] px-1.5 py-0.5 text-[9px] font-semibold uppercase tracking-wide text-[#9aa5c0]">
                    Soon
                  </span>
                </div>
              </li>
            );
          }

          return (
            <li key={page.path}>
              <Link
                to={page.path}
                className={`flex items-center gap-2.5 rounded-lg px-3 py-2 text-sm transition-colors ${
                  isActive
                    ? "bg-[#eef1ff] font-semibold text-[#5b76fe]"
                    : "text-[#4a5168] hover:bg-[#f5f6fb] hover:text-[#1d2433]"
                }`}
              >
                <Icon
                  size={14}
                  className={`shrink-0 ${isActive ? "text-[#5b76fe]" : "text-[#9aa5c0]"}`}
                />
                {page.label}
              </Link>
            </li>
          );
        })}
      </ul>

      <div className="mt-8 border-t border-[#e7eaf2] pt-5">
        <p className="mb-2 text-[11px] font-semibold uppercase tracking-[0.12em] text-[#9aa5c0]">
          Also
        </p>
        <ul className="space-y-0.5">
          <li>
            <Link
              to="/fhir-charts"
              className="flex items-center gap-2 rounded-lg px-3 py-2 text-sm text-[#4a5168] transition-colors hover:bg-[#f5f6fb] hover:text-[#1d2433]"
            >
              Open patient explorer
            </Link>
          </li>
          <li>
            <Link
              to="/learn"
              className="flex items-center gap-2 rounded-lg px-3 py-2 text-sm text-[#4a5168] transition-colors hover:bg-[#f5f6fb] hover:text-[#1d2433]"
            >
              Technical labs
            </Link>
          </li>
        </ul>
      </div>
    </nav>
  );
}

export { SECTION_PAGES };
