import { Database, Globe, Link2, Loader, Lock, Pause, Pin, Send, Telescope, UserRound } from "lucide-react";
import { PATIENT } from "./data";
import type { Workspace } from "./types";

const ICONS: Record<string, typeof Telescope> = {
  Telescope,
  UserRound,
  Database,
  Globe,
  Send,
};

type ContextStripProps = {
  workspace: Workspace;
};

export function ContextStrip({ workspace }: ContextStripProps) {
  if (workspace.family === "clinical") {
    return <CaspianStrip />;
  }
  return <PackageStrip workspace={workspace} />;
}

function CaspianStrip() {
  return (
    <div
      className="flex h-10 items-center gap-2 overflow-hidden whitespace-nowrap border-b px-3.5 text-[12px]"
      style={{
        background: "var(--bg-chrome)",
        color: "var(--ink-2)",
        borderColor: "var(--line-1)",
      }}
    >
      <div
        className="grid h-[22px] w-[22px] place-items-center rounded-md"
        style={{ background: "var(--action-tint)", color: "var(--action)" }}
      >
        <UserRound className="h-3.5 w-3.5" strokeWidth={1.5} />
      </div>
      <div
        className="text-[13px] font-semibold tracking-tight"
        style={{ color: "var(--ink-1)" }}
      >
        {PATIENT.name}
      </div>
      <Sep />
      <Mono>{PATIENT.mrn}</Mono>
      <Sep />
      <Meta>{PATIENT.ageSex}</Meta>
      <Sep />
      <span
        className="inline-flex items-center gap-1.5 font-medium"
        style={{ color: "var(--ink-2)" }}
      >
        <span className="h-1.5 w-1.5 rounded-full" style={{ background: "#b45309" }} />
        {PATIENT.tier}
      </span>
      <Sep />
      <Meta>
        <Database className="h-2.5 w-2.5" strokeWidth={1.5} />
        {PATIENT.fhirCount}
      </Meta>
      <Sep />
      <Meta>{PATIENT.encounters} encounters</Meta>
      <div className="flex-1" />
      <Pill>
        <Pin className="h-2.5 w-2.5" strokeWidth={1.5} />
        Pinned to session
      </Pill>
      <Pill tone="green">
        <Lock className="h-2.5 w-2.5" strokeWidth={1.5} />
        Private patient boundary
      </Pill>
    </div>
  );
}

function PackageStrip({ workspace }: { workspace: Workspace }) {
  const Icon = ICONS[workspace.icon] ?? Telescope;
  const PermIcons = [Database, Globe, Send];
  return (
    <div
      className="flex h-10 items-center gap-2 overflow-hidden whitespace-nowrap border-b px-3.5 text-[12px]"
      style={{
        background: "var(--bg-chrome)",
        color: "var(--ink-2)",
        borderColor: "var(--line-1)",
      }}
    >
      <div
        className="grid h-[22px] w-[22px] place-items-center rounded-md"
        style={{ background: "rgba(67,56,202,0.12)", color: "#4338ca" }}
      >
        <Icon className="h-3.5 w-3.5" strokeWidth={1.5} />
      </div>
      <div
        className="text-[13px] font-semibold tracking-tight"
        style={{ color: "var(--ink-1)" }}
      >
        {workspace.title}
      </div>
      <span
        className="rounded-[3px] px-1.5 py-px text-[11px]"
        style={{
          background: "rgba(67,56,202,0.08)",
          color: "#4338ca",
          fontFamily: "var(--font-mono)",
        }}
      >
        @{workspace.version}
      </span>
      <Sep />
      <Meta>{workspace.vendor}</Meta>
      <Sep />
      <div className="flex gap-1">
        {workspace.permissions?.map((p, i) => {
          const PermIcon = PermIcons[i] ?? Database;
          return (
            <span
              key={i}
              className="inline-flex items-center gap-1 rounded-[3px] border px-1.5 py-px text-[11px]"
              style={{
                background: "var(--surface-2)",
                borderColor: "var(--line-1)",
                color: "var(--ink-3)",
              }}
            >
              <PermIcon className="h-2.5 w-2.5" strokeWidth={1.5} />
              {p}
            </span>
          );
        })}
      </div>
      <div className="flex-1" />
      <div
        className="inline-flex items-center gap-1.5 rounded border px-2.5 py-0.5"
        style={{ background: "var(--surface-2)", borderColor: "var(--line-1)" }}
      >
        <RunDot state={workspace.runState ?? "idle"} />
        <span
          className="text-[10px] font-bold tracking-wider"
          style={{ color: "var(--ink-1)" }}
        >
          {(workspace.runState ?? "idle").toUpperCase()}
        </span>
        <Sep />
        <Meta>step {workspace.runStep}</Meta>
        <Sep />
        <Mono>{workspace.runElapsed}</Mono>
      </div>
      <button
        className="inline-flex items-center gap-1 rounded border px-2.5 py-1 text-[11px] font-medium hover:bg-[var(--surface-2)]"
        style={{
          background: "var(--surface-1)",
          borderColor: "var(--line-2)",
          color: "var(--ink-1)",
        }}
      >
        <Pause className="h-2.5 w-2.5" strokeWidth={1.5} />
        Pause
      </button>
      <Pill tone="warn">
        <Link2 className="h-2.5 w-2.5" strokeWidth={1.5} />
        {workspace.anchoredFrom}
      </Pill>
    </div>
  );
}

function Sep() {
  return <span style={{ color: "var(--ink-4)" }}>·</span>;
}

function Mono({ children }: { children: React.ReactNode }) {
  return (
    <span
      className="text-[11px]"
      style={{ fontFamily: "var(--font-mono)", color: "var(--ink-3)" }}
    >
      {children}
    </span>
  );
}

function Meta({ children }: { children: React.ReactNode }) {
  return (
    <span
      className="inline-flex items-center gap-1 text-[12px]"
      style={{ color: "var(--ink-3)" }}
    >
      {children}
    </span>
  );
}

function Pill({
  children,
  tone,
}: {
  children: React.ReactNode;
  tone?: "green" | "warn";
}) {
  let style: React.CSSProperties = {
    background: "var(--surface-2)",
    color: "var(--ink-2)",
    borderColor: "var(--line-1)",
  };
  if (tone === "green") {
    style = {
      background: "rgba(4,120,87,0.08)",
      color: "var(--clear)",
      borderColor: "rgba(4,120,87,0.18)",
    };
  } else if (tone === "warn") {
    style = {
      background: "rgba(180,83,9,0.08)",
      color: "#b45309",
      borderColor: "rgba(180,83,9,0.22)",
    };
  }
  return (
    <span
      className="inline-flex items-center gap-1.5 rounded-full border px-2 py-0.5 text-[11px] font-medium"
      style={style}
    >
      {children}
    </span>
  );
}

function RunDot({ state }: { state: "running" | "complete" | "idle" | "waiting" }) {
  if (state === "running") {
    return (
      <span
        className="relative inline-flex h-1.5 w-1.5 items-center justify-center rounded-full"
        style={{ background: "var(--clear)" }}
      >
        <Loader
          className="absolute h-3 w-3 animate-spin opacity-0"
          strokeWidth={1.5}
        />
      </span>
    );
  }
  return (
    <span
      className="h-1.5 w-1.5 rounded-full"
      style={{ background: state === "complete" ? "var(--clear)" : "var(--ink-4)" }}
    />
  );
}
