import { useEffect, useMemo, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { ModuleBar } from "./ModuleBar";
import { PlatformDrawer } from "./PlatformDrawer";
import { Titlebar, type Crumb } from "./Titlebar";
import type {
  ModuleId,
  PaneVisibility,
  User,
  WorkspaceId,
} from "./types";

const DEFAULT_USER: User = {
  initials: "RP",
  name: "R. Patel",
  org: "Mercy Medical Group · Clinician",
};

const MODULE_PATHS: { id: ModuleId; match: RegExp; href: string }[] = [
  { id: "patient-record", match: /^\/(patient-record|record|aggregate|records-pool|charts)/, href: "/patient-record" },
  { id: "fhir-charts", match: /^\/(fhir-charts|explorer)/, href: "/fhir-charts" },
  { id: "caspian", match: /^\/caspian/, href: "/caspian" },
  { id: "workspaces", match: /^\/(workspaces|marketplace|trials|skills|medication-access|payer-check|second-opinion|grants|research-opportunities|sharing|ai-workspace)/, href: "/workspaces" },
  { id: "learn", match: /^\/(learn|using-atlas|analysis|pipeline-lab|ccda-lab|ground-truth-review|architecture|guided-tour)/, href: "/learn" },
];

type AppShellProps = {
  children: React.ReactNode;
  /** Optional breadcrumb override; defaults to ["module / page"] */
  crumbs?: Crumb[];
  /** Show the dark titlebar above the content. Default true. */
  showTitlebar?: boolean;
  /** Pane visibility state (only the workspace shell consumes this). */
  panes?: PaneVisibility;
  onTogglePane?: (pane: keyof PaneVisibility) => void;
  /** Optional Run workflow callback; if absent the button is hidden. */
  onRunWorkflow?: () => void;
  showPaneToggles?: boolean;
  /** Adds a max-width container around children (false for full-bleed workspaces). */
  contained?: boolean;
};

export function deriveActiveModule(pathname: string): ModuleId {
  for (const m of MODULE_PATHS) {
    if (m.match.test(pathname)) return m.id;
  }
  if (pathname === "/" || pathname === "/platform") return "patient-record";
  return "patient-record";
}

const DEFAULT_PANES: PaneVisibility = {
  sessions: true,
  chat: true,
  workbench: true,
  files: true,
  inspector: true,
};

export function AppShell({
  children,
  crumbs,
  showTitlebar = true,
  panes,
  onTogglePane,
  onRunWorkflow,
  showPaneToggles = false,
  contained = true,
}: AppShellProps) {
  const navigate = useNavigate();
  const location = useLocation();
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [workspaceId, setWorkspaceId] = useState<WorkspaceId>(() => {
    // Migration: the slug "clinical-insights" was renamed to "caspian" in
    // Phase 6 of the Atlas IA refactor. If a user had the old slug stored,
    // promote it transparently.
    const stored = localStorage.getItem("atlas:workspaceId");
    if (stored === "clinical-insights") return "caspian";
    return (stored as WorkspaceId) || "caspian";
  });

  useEffect(() => {
    localStorage.setItem("atlas:workspaceId", workspaceId);
  }, [workspaceId]);

  const activeModule = useMemo(
    () => deriveActiveModule(location.pathname),
    [location.pathname],
  );

  const resolvedCrumbs: Crumb[] = useMemo(() => {
    if (crumbs && crumbs.length) return crumbs;
    const segs = location.pathname.split("/").filter(Boolean);
    if (!segs.length) return [{ label: "Home", active: true }];
    return segs.map((s, i) => ({
      label: humanize(s),
      active: i === segs.length - 1,
    }));
  }, [crumbs, location.pathname]);

  const handleSelectModule = (m: ModuleId) => {
    const target = MODULE_PATHS.find((p) => p.id === m);
    if (target) navigate(target.href);
  };

  const handleSwitchWorkspace = (w: WorkspaceId) => {
    setWorkspaceId(w);
    if (w === "caspian") navigate("/caspian");
    else navigate(`/workspaces/${w}`);
  };

  return (
    <div
      className="flex h-screen min-h-0 flex-col"
      style={{ background: "var(--bg-app)" }}
    >
      <ModuleBar
        activeModule={activeModule}
        onSelect={handleSelectModule}
        workspaceId={workspaceId}
        onSwitchWorkspace={handleSwitchWorkspace}
        onOpenDrawer={() => setDrawerOpen(true)}
        user={DEFAULT_USER}
      />
      {showTitlebar && (
        <Titlebar
          crumbs={resolvedCrumbs}
          panes={panes ?? DEFAULT_PANES}
          onTogglePane={onTogglePane ?? (() => undefined)}
          onRunWorkflow={onRunWorkflow}
          showRunWorkflow={Boolean(onRunWorkflow)}
          showPaneToggles={showPaneToggles}
        />
      )}
      <main
        className="flex min-h-0 flex-1 flex-col overflow-auto"
        style={{ background: "var(--bg-app)", color: "var(--ink-1)" }}
      >
        {contained ? (
          <div className="flex min-h-0 w-full flex-1 flex-col">{children}</div>
        ) : (
          children
        )}
      </main>
      <PlatformDrawer
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        user={DEFAULT_USER}
      />
    </div>
  );
}

function humanize(slug: string): string {
  if (/^[a-f0-9]{8}-/i.test(slug) || slug.length > 24) {
    return slug.slice(0, 8) + "…";
  }
  return slug
    .replace(/-/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
}
