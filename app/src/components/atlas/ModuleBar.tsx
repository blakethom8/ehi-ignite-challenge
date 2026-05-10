import { useEffect, useRef, useState } from "react";
import {
  ChevronDown,
  Compass,
  HelpCircle,
  Menu,
  Pill,
  Play,
  Search,
  Send,
  Telescope,
} from "lucide-react";
import type { Crumb } from "./Titlebar";
import type {
  ModuleId,
  PaneVisibility,
  RecentWorkspace,
  User,
  WorkspaceId,
} from "./types";

const RECENT: RecentWorkspace[] = [
  { id: "trial-finder", label: "Trial Finder", vendor: "Helix Clinical", icon: "Telescope" },
  { id: "med-access", label: "Medication Access", vendor: "RxBridge", icon: "Pill" },
  { id: "site-coord", label: "Site Coordination", vendor: "TrialOps", icon: "Send" },
];

const RECENT_ICONS: Record<string, typeof Telescope> = {
  Telescope,
  Pill,
  Send,
};

const MODULES: { id: ModuleId; label: string; hasMenu?: boolean }[] = [
  { id: "patient-record", label: "Patient Record" },
  { id: "fhir-charts", label: "FHIR Charts" },
  { id: "caspian", label: "Caspian" },
  { id: "workspaces", label: "Workspaces", hasMenu: true },
  { id: "learn", label: "Learn" },
];

type ModuleBarProps = {
  activeModule: ModuleId;
  onSelect: (module: ModuleId) => void;
  workspaceId: WorkspaceId;
  onSwitchWorkspace: (workspaceId: WorkspaceId) => void;
  onOpenDrawer: () => void;
  user: User;
  crumbs?: Crumb[];
  panes?: PaneVisibility;
  onTogglePane?: (pane: keyof PaneVisibility) => void;
  onRunWorkflow?: () => void;
  showPaneToggles?: boolean;
};

const PANE_LABELS: Record<keyof PaneVisibility, string> = {
  sessions: "S",
  chat: "C",
  workbench: "P",
  files: "F",
  inspector: "I",
};

const PANE_TITLES: Record<keyof PaneVisibility, string> = {
  sessions: "Sessions (Alt+S)",
  chat: "Chat (Alt+C)",
  workbench: "Workbench (Alt+P)",
  files: "Files (Alt+F)",
  inspector: "Inspector (Alt+I)",
};

export function ModuleBar({
  activeModule,
  onSelect,
  workspaceId,
  onSwitchWorkspace,
  onOpenDrawer,
  user,
  crumbs,
  panes,
  onTogglePane,
  onRunWorkflow,
  showPaneToggles = false,
}: ModuleBarProps) {
  const [wsOpen, setWsOpen] = useState(false);
  const wsRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const onClick = (e: MouseEvent) => {
      if (wsRef.current && !wsRef.current.contains(e.target as Node)) {
        setWsOpen(false);
      }
    };
    document.addEventListener("mousedown", onClick);
    return () => document.removeEventListener("mousedown", onClick);
  }, []);

  return (
    <div
      className="grid-cols-full flex h-9 items-center px-3 text-[12px]"
      style={{
        background: "var(--chrome-modulebar)",
        color: "var(--chrome-text)",
        borderBottom: "1px solid #000",
      }}
    >
      <button
        onClick={onOpenDrawer}
        title="Open menu"
        className="mr-1 grid h-7 w-7 place-items-center rounded-[5px] text-white/75 hover:bg-white/8 hover:text-white"
      >
        <Menu className="h-3.5 w-3.5" strokeWidth={1.5} />
      </button>
      <div className="flex items-center gap-2 border-r border-white/10 pr-3.5">
        <div
          className="grid h-[22px] w-[22px] place-items-center rounded-[5px] text-[10px] font-bold tracking-wide text-white"
          style={{
            background:
              "linear-gradient(135deg, var(--action) 0%, var(--action-press) 100%)",
          }}
        >
          EI
        </div>
        <span className="whitespace-nowrap text-[12.5px] font-semibold tracking-tight text-white">
          EHI Ignite
        </span>
      </div>
      {crumbs?.length ? (
        <div className="ml-3 flex min-w-0 items-center gap-2 border-r border-white/10 pr-3.5">
          {crumbs.map((crumb, index) => (
            <div key={`${crumb.label}-${index}`} className="flex min-w-0 items-center gap-2">
              {index > 0 && (
                <span style={{ color: "rgba(255,255,255,0.35)" }}>/</span>
              )}
              <span
                className={`truncate text-[12px] ${
                  crumb.active ? "font-medium text-white" : ""
                }`}
                style={{
                  color: crumb.active
                    ? "#ffffff"
                    : "rgba(255,255,255,0.68)",
                }}
              >
                {crumb.label}
              </span>
            </div>
          ))}
        </div>
      ) : null}
      <div className="ml-2 flex min-w-0 flex-[0_1_auto] gap-px overflow-hidden">
        {MODULES.map((m) => {
          const active = m.id === activeModule;
          if (m.hasMenu) {
            return (
              <div key={m.id} ref={wsRef} className="relative">
                <div className="relative flex flex-[0_0_auto] items-center">
                  <button
                    onClick={() => {
                      setWsOpen(false);
                      onSelect("workspaces");
                    }}
                    className={`relative flex cursor-pointer items-center whitespace-nowrap rounded-l px-3 py-2 text-[12px] font-medium leading-none transition-colors ${
                      active
                        ? "bg-white/8 text-white"
                        : "text-[rgba(229,233,240,0.62)] hover:bg-white/5 hover:text-white"
                    }`}
                  >
                    {m.label}
                    {active && (
                      <span
                        className="absolute -bottom-2 left-2 right-0 h-0.5 rounded-t"
                        style={{ background: "var(--action)" }}
                      />
                    )}
                  </button>
                  <button
                    onClick={() => {
                      setWsOpen((o) => !o);
                    }}
                    aria-label="Open workspaces menu"
                    className={`relative flex cursor-pointer items-center rounded-r px-1.5 py-2 text-[12px] font-medium leading-none transition-colors ${
                      active
                        ? "bg-white/8 text-white"
                        : "text-[rgba(229,233,240,0.62)] hover:bg-white/5 hover:text-white"
                    }`}
                  >
                    <ChevronDown
                      className="h-2.5 w-2.5 opacity-60"
                      strokeWidth={1.5}
                    />
                    {active && (
                      <span
                        className="absolute -bottom-2 left-0 right-2 h-0.5 rounded-t"
                        style={{ background: "var(--action)" }}
                      />
                    )}
                  </button>
                </div>
                {wsOpen && (
                  <div
                    className="absolute left-0 top-[calc(100%+6px)] z-[100] min-w-[280px] rounded-lg p-1.5"
                    style={{
                      background: "var(--surface-1)",
                      border: "1px solid var(--line-2)",
                      boxShadow: "0 12px 32px rgb(15 23 42 / 0.16)",
                    }}
                  >
                    <button
                      onClick={() => {
                        setWsOpen(false);
                        onSelect("workspaces");
                      }}
                      className="flex w-full items-center gap-2.5 rounded-[5px] px-2.5 py-2 text-left"
                      style={{
                        background: "var(--action-tint)",
                        color: "var(--action)",
                      }}
                    >
                      <Compass className="h-[13px] w-[13px]" strokeWidth={1.5} />
                      <div>
                        <div className="text-[12.5px] font-medium">
                          Explore workspaces
                        </div>
                        <div
                          className="mt-px text-[11px]"
                          style={{ color: "var(--ink-3)" }}
                        >
                          Marketplace · install new packages
                        </div>
                      </div>
                    </button>
                    <div
                      className="my-1 h-px"
                      style={{ background: "var(--line-1)" }}
                    />
                    <div
                      className="px-2.5 py-1.5 text-[10px] font-bold tracking-wider"
                      style={{ color: "var(--ink-4)" }}
                    >
                      RECENTLY VIEWED
                    </div>
                    {RECENT.map((w) => {
                      const Icon = RECENT_ICONS[w.icon] ?? Telescope;
                      return (
                        <button
                          key={w.id}
                          onClick={() => {
                            setWsOpen(false);
                            onSwitchWorkspace(w.id);
                          }}
                          className="flex w-full items-center gap-2.5 rounded-[5px] px-2.5 py-2 text-left transition-colors hover:bg-[var(--surface-2)]"
                          style={{ color: "var(--ink-2)" }}
                        >
                          <Icon className="h-[13px] w-[13px]" strokeWidth={1.5} />
                          <div>
                            <div className="text-[12.5px] font-medium">
                              {w.label}
                            </div>
                            <div
                              className="mt-px text-[11px]"
                              style={{ color: "var(--ink-3)" }}
                            >
                              {w.vendor}
                            </div>
                          </div>
                        </button>
                      );
                    })}
                  </div>
                )}
              </div>
            );
          }
          return (
            <button
              key={m.id}
              onClick={() => {
                onSelect(m.id);
                if (m.id === "caspian") onSwitchWorkspace("caspian");
              }}
              className={`relative flex flex-[0_0_auto] cursor-pointer items-center whitespace-nowrap rounded px-3 py-2 text-[12px] font-medium leading-none transition-colors ${
                active
                  ? "bg-white/8 text-white"
                  : "text-[rgba(229,233,240,0.62)] hover:bg-white/5 hover:text-white"
              }`}
            >
              {m.label}
              {active && (
                <span
                  className="absolute -bottom-2 left-2 right-2 h-0.5 rounded-t"
                  style={{ background: "var(--action)" }}
                />
              )}
            </button>
          );
        })}
      </div>
      <div className="flex-1" />
      {onRunWorkflow && (
        <button
          onClick={onRunWorkflow}
          className="mr-2 inline-flex h-[26px] flex-[0_0_auto] items-center gap-1.5 whitespace-nowrap rounded-md border px-2.5 text-[12px] font-medium transition-colors hover:bg-white/5"
          style={{
            color: "rgba(255,255,255,0.85)",
            borderColor: "rgba(255,255,255,0.15)",
            background: "rgba(255,255,255,0.04)",
          }}
        >
          <Play className="h-3 w-3" strokeWidth={1.5} />
          Run workflow
          <ChevronDown
            className="h-2.5 w-2.5 opacity-60"
            strokeWidth={1.5}
          />
        </button>
      )}
      {showPaneToggles && panes && onTogglePane && (
        <div
          className="mr-2 flex flex-[0_0_auto] gap-0.5 rounded-md p-0.5"
          style={{
            background: "rgba(255,255,255,0.06)",
            border: "1px solid rgba(255,255,255,0.08)",
          }}
        >
          {(Object.keys(PANE_LABELS) as (keyof PaneVisibility)[]).map((pane) => {
            const on = panes[pane];
            return (
              <button
                key={pane}
                onClick={() => onTogglePane(pane)}
                title={PANE_TITLES[pane]}
                className={`grid h-[22px] w-6 flex-[0_0_auto] place-items-center rounded text-[11px] font-semibold tracking-wider ${
                  on
                    ? ""
                    : "text-[rgba(229,233,240,0.55)] hover:text-white"
                }`}
                style={
                  on
                    ? {
                        background: "rgba(255,255,255,0.92)",
                        color: "var(--action)",
                        boxShadow: "var(--shadow-1)",
                      }
                    : undefined
                }
              >
                {PANE_LABELS[pane]}
              </button>
            );
          })}
        </div>
      )}
      <div className="flex items-center gap-1">
        <button
          className="grid h-[26px] w-[26px] place-items-center rounded-[5px] text-white/70 hover:bg-white/8 hover:text-white"
          title="Search"
        >
          <Search className="h-[13px] w-[13px]" strokeWidth={1.5} />
        </button>
        <button
          className="grid h-[26px] w-[26px] place-items-center rounded-[5px] text-white/70 hover:bg-white/8 hover:text-white"
          title="Help"
        >
          <HelpCircle className="h-[13px] w-[13px]" strokeWidth={1.5} />
        </button>
        <div
          className="ml-1.5 grid h-[26px] w-[26px] place-items-center rounded-full text-[10.5px] font-semibold text-white"
          style={{ background: "var(--action)" }}
          title={user.name}
        >
          {user.initials}
        </div>
      </div>
      {workspaceId /* keep param referenced */ && null}
    </div>
  );
}
