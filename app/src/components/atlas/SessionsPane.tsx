import { Activity, ChevronDown, Home, MessageSquareText, Pin, Plus, Search, Telescope, Workflow } from "lucide-react";
import { SESSIONS, WORKFLOWS, type Session } from "./data";
import type { Workspace, WorkspaceId } from "./types";
import { Link } from "react-router-dom";

const WORKFLOW_ICONS: Record<string, typeof Activity> = {
  preop: Activity,
  shortlist: Telescope,
  default: MessageSquareText,
};

type SessionsPaneProps = {
  workspace: Workspace;
  activeSessionId: string | "__home__" | null;
  onSelectSession: (id: string | "__home__") => void;
};

export function SessionsPane({ workspace, activeSessionId, onSelectSession }: SessionsPaneProps) {
  const sessions = SESSIONS[workspace.id as WorkspaceId] ?? [];
  const workflows = WORKFLOWS[workspace.id as WorkspaceId] ?? [];

  return (
    <div
      className="flex h-full flex-col overflow-hidden"
      style={{
        background: "var(--bg-chrome)",
        borderRight: "1px solid var(--line-1)",
      }}
    >
      <Link
        to={workspace.id === "caspian" ? "/caspian" : `/workspaces/${workspace.id}`}
        className="mx-2 mt-3 flex cursor-pointer items-center gap-2 rounded-md border px-2.5 py-1.5 transition-colors hover:border-[var(--line-2)]"
        style={{
          background: "var(--surface-0)",
          borderColor: "var(--line-1)",
          textDecoration: "none",
        }}
      >
        <div
          className="grid h-[22px] w-[22px] place-items-center rounded-[5px]"
          style={{ background: workspace.tint, color: workspace.color }}
        >
          {workspace.family === "clinical" ? (
            <Activity className="h-3.5 w-3.5" strokeWidth={1.5} />
          ) : (
            <Telescope className="h-3.5 w-3.5" strokeWidth={1.5} />
          )}
        </div>
        <div className="min-w-0 flex-1">
          <div
            className="text-[12.5px] font-semibold leading-tight"
            style={{ color: "var(--ink-1)" }}
          >
            {workspace.title}
          </div>
          <div
            className="mt-px text-[10.5px] tracking-wider"
            style={{ color: "var(--ink-3)" }}
          >
            {workspace.subtitle}
          </div>
        </div>
        <ChevronDown
          className="h-3 w-3"
          strokeWidth={1.5}
          style={{ color: "var(--ink-4)" }}
        />
      </Link>
      <div className="relative mx-2 mt-3">
        <Search
          className="absolute left-2 top-1/2 h-3 w-3 -translate-y-1/2"
          style={{ color: "var(--ink-4)" }}
          strokeWidth={1.5}
        />
        <input
          placeholder="Search sessions, files, citations"
          className="h-7 w-full rounded-md border bg-transparent pl-6 pr-2 text-[12px] outline-none"
          style={{
            background: "var(--surface-0)",
            borderColor: "var(--line-1)",
            color: "var(--ink-1)",
          }}
        />
        <span
          className="absolute right-1.5 top-1/2 inline-flex h-[18px] -translate-y-1/2 items-center rounded border px-1.5 text-[10.5px]"
          style={{
            background: "var(--surface-2)",
            borderColor: "var(--line-1)",
            color: "var(--ink-3)",
            fontFamily: "var(--font-mono)",
          }}
        >
          ⌘K
        </span>
      </div>
      <div className="flex-1 overflow-y-auto pb-3">
        {workspace.family === "plugin" && (
          <Group title="Package">
            <button
              onClick={() => onSelectSession("__home__")}
              className={`flex w-full items-start gap-2 rounded-md px-2 py-1.5 text-left transition-colors ${
                activeSessionId === "__home__"
                  ? "shadow-[var(--shadow-1)]"
                  : "hover:bg-[var(--surface-2)]"
              }`}
              style={
                activeSessionId === "__home__"
                  ? { background: "var(--surface-0)" }
                  : undefined
              }
            >
              <Home
                className="mt-0.5 h-3 w-3"
                strokeWidth={1.5}
                style={{
                  color:
                    activeSessionId === "__home__"
                      ? "var(--action)"
                      : "var(--ink-4)",
                }}
              />
              <div className="min-w-0">
                <div
                  className="truncate text-[12.5px] font-medium leading-tight"
                  style={{ color: "var(--ink-2)" }}
                >
                  Package home
                </div>
                <div
                  className="mt-0.5 text-[10.5px]"
                  style={{ color: "var(--ink-4)" }}
                >
                  About · Workflows · Recent runs
                </div>
              </div>
            </button>
          </Group>
        )}
        <Group title="Recent sessions" right={`${sessions.length}`}>
          {sessions.map((s) => (
            <SessionRow
              key={s.id}
              session={s}
              active={s.id === activeSessionId}
              onClick={() => onSelectSession(s.id)}
            />
          ))}
        </Group>
        <Group title="Workflow library" right="BROWSE">
          {workflows.slice(0, 3).map((w) => (
            <div
              key={w.id}
              className="flex cursor-pointer items-center gap-1.5 rounded-md px-2 py-1.5 text-[12px] hover:bg-[var(--surface-2)]"
              style={{ color: "var(--ink-3)" }}
            >
              <Workflow className="h-3 w-3" strokeWidth={1.5} />
              {w.title}
            </div>
          ))}
        </Group>
        <Group title="Pinned artifacts">
          {workspace.family === "clinical" ? (
            <>
              <PinRow label="pre-op-packet-v2.md" />
              <PinRow label="clearance-summary.json" />
            </>
          ) : (
            <>
              <PinRow label="ranked-shortlist.md" />
              <PinRow label="manifest.json" />
            </>
          )}
        </Group>
      </div>
      <button
        className="mx-2 mb-2 flex items-center justify-center gap-1.5 rounded-md border border-dashed px-2.5 py-2 text-[12px] font-medium transition-colors hover:border-[var(--action)] hover:bg-[var(--action-tint)] hover:text-[var(--action)]"
        style={{ borderColor: "var(--line-2)", color: "var(--ink-3)" }}
      >
        <Plus className="h-3 w-3" strokeWidth={1.5} />
        New session
      </button>
    </div>
  );
}

function Group({
  title,
  right,
  children,
}: {
  title: string;
  right?: string;
  children: React.ReactNode;
}) {
  return (
    <div className="px-2 pt-2">
      <div
        className="flex items-center justify-between px-2 py-1.5 text-[10.5px] font-semibold uppercase tracking-wider"
        style={{ color: "var(--ink-4)" }}
      >
        <span>{title}</span>
        {right && (
          <span className="font-medium normal-case tracking-normal">
            {right}
          </span>
        )}
      </div>
      {children}
    </div>
  );
}

function SessionRow({
  session,
  active,
  onClick,
}: {
  session: Session;
  active: boolean;
  onClick: () => void;
}) {
  const Icon = WORKFLOW_ICONS[session.workflow ?? "default"] ?? MessageSquareText;
  return (
    <button
      onClick={onClick}
      className={`flex w-full items-start gap-2 rounded-md px-2 py-1.5 text-left transition-colors ${
        active ? "shadow-[var(--shadow-1)]" : "hover:bg-[var(--surface-2)]"
      }`}
      style={active ? { background: "var(--surface-0)" } : undefined}
    >
      <Icon
        className="mt-0.5 h-3 w-3"
        strokeWidth={1.5}
        style={{ color: active ? "var(--action)" : "var(--ink-4)" }}
      />
      <div className="min-w-0 flex-1">
        <div
          className="truncate text-[12.5px] font-medium leading-tight"
          style={{ color: active ? "var(--ink-1)" : "var(--ink-2)" }}
        >
          {session.title}
        </div>
        <div
          className="mt-0.5 flex items-center gap-1.5 truncate text-[10.5px]"
          style={{ color: "var(--ink-4)" }}
        >
          <StateDot state={session.state} />
          <span className="truncate">{session.meta}</span>
        </div>
      </div>
    </button>
  );
}

function StateDot({ state }: { state: Session["state"] }) {
  let bg = "var(--ink-5)";
  let ring = "transparent";
  if (state === "running") {
    bg = "var(--action)";
    ring = "var(--action-tint)";
  } else if (state === "needs") bg = "var(--caution)";
  else if (state === "done") bg = "var(--clear)";
  return (
    <span
      className="inline-block h-1.5 w-1.5 rounded-full"
      style={{ background: bg, boxShadow: `0 0 0 3px ${ring}` }}
    />
  );
}

function PinRow({ label }: { label: string }) {
  return (
    <div
      className="flex cursor-pointer items-center gap-1.5 rounded-md px-2 py-1.5 text-[12px] hover:bg-[var(--surface-2)] hover:text-[var(--ink-1)]"
      style={{ color: "var(--ink-3)" }}
    >
      <Pin className="h-3 w-3" strokeWidth={1.5} />
      {label}
    </div>
  );
}
