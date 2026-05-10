import { Bell, ChevronDown, Command, Play } from "lucide-react";
import type { PaneVisibility } from "./types";

export type Crumb = { label: string; href?: string; active?: boolean };

type TitlebarProps = {
  crumbs: Crumb[];
  panes: PaneVisibility;
  onTogglePane: (pane: keyof PaneVisibility) => void;
  onRunWorkflow?: () => void;
  onCommand?: () => void;
  showRunWorkflow?: boolean;
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

export function Titlebar({
  crumbs,
  panes,
  onTogglePane,
  onRunWorkflow,
  onCommand,
  showRunWorkflow = true,
  showPaneToggles = true,
}: TitlebarProps) {
  return (
    <div
      className="flex h-11 items-center gap-3 px-3 text-[12px]"
      style={{
        background: "var(--chrome-titlebar)",
        color: "rgba(255,255,255,0.85)",
        borderBottom: "1px solid rgba(255,255,255,0.06)",
      }}
    >
      <div className="flex gap-2 pl-1 pr-1.5">
        <span
          className="h-3 w-3 rounded-full"
          style={{ background: "#ff5f57" }}
        />
        <span
          className="h-3 w-3 rounded-full"
          style={{ background: "#febc2e" }}
        />
        <span
          className="h-3 w-3 rounded-full"
          style={{ background: "#28c840" }}
        />
      </div>
      <div className="flex min-w-0 flex-1 items-center gap-2 pl-2">
        <div
          className="grid h-[22px] w-[22px] place-items-center rounded-[5px] text-[11px] font-bold tracking-wide"
          style={{ background: "#ffffff", color: "var(--ink-1)" }}
          aria-hidden
        >
          A
        </div>
        <strong className="font-semibold text-white">Atlas</strong>
        {crumbs.map((c, i) => (
          <span key={i} className="flex min-w-0 items-center gap-2">
            <span style={{ color: "rgba(255,255,255,0.35)" }}>/</span>
            <span
              className={`truncate ${c.active ? "font-medium text-white" : ""}`}
              style={{
                color: c.active
                  ? "#ffffff"
                  : "rgba(255,255,255,0.65)",
              }}
            >
              {c.label}
            </span>
          </span>
        ))}
      </div>
      {showRunWorkflow && (
        <button
          onClick={onRunWorkflow}
          className="inline-flex h-[26px] flex-[0_0_auto] items-center gap-1.5 whitespace-nowrap rounded-md border px-2.5 text-[12px] font-medium transition-colors hover:bg-white/5"
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
      <button
        onClick={onCommand}
        className="grid h-[26px] w-[26px] place-items-center rounded-[5px] text-white/65 hover:bg-white/8 hover:text-white"
        title="Command palette ⌘K"
      >
        <Command className="h-3.5 w-3.5" strokeWidth={1.5} />
      </button>
      <button
        className="grid h-[26px] w-[26px] place-items-center rounded-[5px] text-white/65 hover:bg-white/8 hover:text-white"
        title="Notifications"
      >
        <Bell className="h-3.5 w-3.5" strokeWidth={1.5} />
      </button>
      {showPaneToggles && (
        <div
          className="flex gap-0.5 rounded-md p-0.5"
          style={{
            background: "rgba(255,255,255,0.06)",
            border: "1px solid rgba(255,255,255,0.08)",
          }}
        >
          {(Object.keys(PANE_LABELS) as (keyof PaneVisibility)[]).map((p) => {
            const on = panes[p];
            return (
              <button
                key={p}
                onClick={() => onTogglePane(p)}
                title={PANE_TITLES[p]}
                className={`grid h-[22px] w-6 place-items-center rounded text-[11px] font-semibold tracking-wider ${
                  on
                    ? ""
                    : "text-white/55 hover:text-white"
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
                {PANE_LABELS[p]}
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}
