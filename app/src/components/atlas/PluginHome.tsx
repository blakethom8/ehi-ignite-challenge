/**
 * Plugin home — fully manifest-driven.
 *
 * Read `manifest.ui.homeSections` to decide which sections render +
 * in what order. Each section reads its data from the manifest (hero,
 * permissions, workflows, about) or from the runtime
 * (recent-runs from /api/plugins/{id}/runs).
 *
 * Per HARNESS-SURFACES §8: no business logic. Pure projection.
 */

import {
  ArrowRight,
  Beaker,
  Boxes,
  Database,
  FileText,
  Globe,
  Pill,
  Play,
  Send,
  Settings,
  Stethoscope,
  Telescope,
  Tag,
  UserRound,
  Users2,
  Workflow,
} from "lucide-react";
import { useRunsForPlugin } from "./manifests";
import type { PluginManifest } from "./trust";

const PLUGIN_ICONS: Record<string, typeof Telescope> = {
  Telescope,
  Pill,
  Send,
  Boxes,
  Stethoscope,
  UserRound,
  FileText,
  Beaker,
  Users2,
};

type PluginHomeProps = {
  manifest: PluginManifest;
  onStartRun: (workflowId?: string) => void;
};

export function PluginHome({ manifest, onStartRun }: PluginHomeProps) {
  const Icon = PLUGIN_ICONS[manifest.icon] ?? Boxes;
  const sections = manifest.ui.homeSections;
  const runsQuery = useRunsForPlugin(sections.includes("recent-runs") ? manifest.id : undefined);

  const tintBg = withAlpha(manifest.color, 0.12);
  const tintText = manifest.color;

  return (
    <div className="flex min-h-0 flex-1 flex-col overflow-hidden" style={{ background: "var(--bg-app)" }}>
      <div className="mx-auto w-full max-w-[1100px] flex-1 overflow-y-auto px-10 pb-16 pt-7">
        {sections.includes("hero") && (
          <header className="flex items-start gap-5 border-b pb-7" style={{ borderColor: "var(--line-1)" }}>
            <div
              className="grid h-14 w-14 flex-[0_0_56px] place-items-center rounded-[12px]"
              style={{ background: tintBg, color: tintText }}
            >
              <Icon className="h-7 w-7" strokeWidth={1.5} />
            </div>
            <div className="min-w-0 flex-1">
              <div className="text-[10.5px] font-bold uppercase tracking-[0.12em]" style={{ color: "var(--ink-3)" }}>
                PLUGIN · INSTALLED
              </div>
              <div
                className="mt-2 flex items-baseline gap-2.5 text-[26px] font-semibold leading-[1.1] tracking-tight"
                style={{ color: "var(--ink-1)" }}
              >
                {manifest.displayName}
                <span
                  className="rounded px-2 py-0.5 text-[14px] font-medium"
                  style={{ background: withAlpha(manifest.color, 0.08), color: manifest.color, fontFamily: "var(--font-mono)" }}
                >
                  @{manifest.version}
                </span>
              </div>
              <div className="mt-1.5 text-[12.5px]" style={{ color: "var(--ink-3)" }}>
                by {manifest.vendor.name} · {manifest.trust.boundaryLabel}
              </div>
              <p className="mt-3.5 max-w-[70ch] text-[13.5px] leading-[1.55]" style={{ color: "var(--ink-2)" }}>
                {manifest.description}
              </p>
            </div>
            <div className="flex flex-col gap-2">
              <button
                onClick={() => onStartRun()}
                className="inline-flex items-center justify-center gap-1.5 whitespace-nowrap rounded-md px-4 py-2 text-[12.5px] font-medium text-white"
                style={{ background: "var(--action)" }}
              >
                <Play className="h-3 w-3" strokeWidth={1.5} />
                Start new run
              </button>
              <button
                className="inline-flex items-center justify-center gap-1.5 whitespace-nowrap rounded-md border px-4 py-2 text-[12.5px] font-medium hover:bg-[var(--surface-2)]"
                style={{ background: "var(--surface-1)", borderColor: "var(--line-2)", color: "var(--ink-1)" }}
              >
                <Settings className="h-3 w-3" strokeWidth={1.5} />
                Configure
              </button>
            </div>
          </header>
        )}

        {sections.includes("permissions-ledger") && <PermissionsLedger manifest={manifest} />}
        {sections.includes("workflows") && <WorkflowGrid manifest={manifest} onStartRun={onStartRun} />}
        {sections.includes("recent-runs") && (
          <RecentRunsTable
            runs={(runsQuery.data ?? []) as RunRow[]}
            loading={runsQuery.isLoading}
            onOpen={(workflowId) => onStartRun(workflowId)}
          />
        )}
        {sections.includes("about") && <AboutSection manifest={manifest} />}
      </div>
    </div>
  );
}

// ============================================================
// Sections
// ============================================================

function PermissionsLedger({ manifest }: { manifest: PluginManifest }) {
  const cards = manifest.permissions.map((p, i) => {
    if (p.kind === "read-anchor") {
      return {
        key: `read-${i}`,
        icon: Database,
        label: "Reads patient anchors",
        detail: `Scope: ${p.scope.join(", ")}. Redaction preset: ${manifest.anchor.redactionPreset}.`,
        warn: false,
      };
    }
    if (p.kind === "call-external") {
      const c = manifest.connectors.find((c) => c.id === p.connector);
      return {
        key: `ext-${i}`,
        icon: Globe,
        label: `Calls ${c?.label ?? p.connector}`,
        detail: `Endpoint pattern: ${c?.endpointPattern ?? "—"}. Auth: ${c?.auth ?? "—"}.`,
        warn: false,
      };
    }
    return {
      key: `out-${i}`,
      icon: Send,
      label: `Sends outbound · ${p.channel}`,
      detail: "Gated by per-run consent + per-action approval. Every send writes a provenance row.",
      warn: true,
    };
  });

  return (
    <Section title="Permissions ledger" note="What this plugin is allowed to do, scoped to your workspace.">
      <div className="grid grid-cols-1 gap-3 md:grid-cols-2 lg:grid-cols-3">
        {cards.map((c) => {
          const PIcon = c.icon;
          return (
            <div
              key={c.key}
              className="flex gap-2.5 rounded-md border p-3.5"
              style={{
                background: c.warn ? "rgba(180,83,9,0.04)" : "var(--surface-1)",
                borderColor: c.warn ? "rgba(180,83,9,0.25)" : "var(--line-1)",
              }}
            >
              <div
                className="grid h-[26px] w-[26px] flex-[0_0_26px] place-items-center rounded-md"
                style={{ background: c.warn ? "rgba(180,83,9,0.12)" : "var(--surface-2)", color: c.warn ? "#b45309" : "var(--ink-2)" }}
              >
                <PIcon className="h-3.5 w-3.5" strokeWidth={1.5} />
              </div>
              <div>
                <div className="text-[12.5px] font-semibold" style={{ color: "var(--ink-1)" }}>{c.label}</div>
                <div className="mt-0.5 text-[11.5px] leading-[1.4]" style={{ color: "var(--ink-3)" }}>{c.detail}</div>
              </div>
            </div>
          );
        })}
      </div>
    </Section>
  );
}

function WorkflowGrid({
  manifest,
  onStartRun,
}: {
  manifest: PluginManifest;
  onStartRun: (workflowId: string) => void;
}) {
  return (
    <Section
      title="Workflows"
      note="Pick a workflow to start a new run. The run becomes a session in this workspace."
    >
      <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
        {manifest.workflows.map((w) => (
          <button
            key={w.id}
            onClick={() => onStartRun(w.id)}
            className="flex flex-col gap-2 rounded-md border p-4 text-left transition-colors hover:border-[var(--action-line)] hover:shadow-[0_1px_0_var(--action-tint)]"
            style={{ background: "var(--surface-1)", borderColor: "var(--line-1)" }}
          >
            <div className="flex items-center gap-2" style={{ color: "var(--ink-2)" }}>
              <Workflow className="h-3.5 w-3.5" strokeWidth={1.5} />
              <div className="text-[13.5px] font-semibold" style={{ color: "var(--ink-1)" }}>
                {w.title}
              </div>
            </div>
            <div className="text-[12px] leading-[1.45]" style={{ color: "var(--ink-3)" }}>{w.description}</div>
            <div className="flex flex-wrap gap-1">
              {w.tags.map((t) => (
                <span
                  key={t}
                  className="rounded-[3px] border px-1.5 py-0.5 text-[10.5px]"
                  style={{ background: "var(--surface-2)", borderColor: "var(--line-1)", color: "var(--ink-3)" }}
                >
                  {t}
                </span>
              ))}
            </div>
            <div
              className="mt-1 flex items-center justify-between border-t border-dashed pt-2 text-[11px]"
              style={{ borderColor: "var(--line-1)" }}
            >
              <span style={{ color: "var(--ink-3)" }}>
                Needs: {w.needs.length > 0 ? w.needs.join(", ") : "patient anchor"}
              </span>
              <span className="inline-flex items-center gap-1 font-medium" style={{ color: "var(--action)" }}>
                Start <ArrowRight className="h-3 w-3" strokeWidth={1.5} />
              </span>
            </div>
          </button>
        ))}
      </div>
    </Section>
  );
}

type RunRow = {
  id: string;
  pluginId: string;
  workflowId: string | null;
  title: string | null;
  state: string;
  startedAt: string;
  startedBy: { name: string };
};

function RecentRunsTable({
  runs,
  loading,
  onOpen,
}: {
  runs: RunRow[];
  loading: boolean;
  onOpen: (workflowId?: string) => void;
}) {
  return (
    <Section title="Recent runs" note="Re-enter a session or audit a completed run.">
      <div className="overflow-hidden rounded-md border" style={{ background: "var(--surface-1)", borderColor: "var(--line-1)" }}>
        <div
          className="grid items-center gap-3 border-b px-3.5 py-2.5 text-[10.5px] font-bold uppercase tracking-wider"
          style={{ background: "var(--surface-2)", borderColor: "var(--line-1)", color: "var(--ink-3)", gridTemplateColumns: "110px 1.4fr 1fr 140px 110px 28px" }}
        >
          <div>Run</div>
          <div>Title</div>
          <div>Workflow</div>
          <div>Started</div>
          <div>State</div>
          <div />
        </div>
        {loading && (
          <div className="px-3.5 py-3 text-[12.5px]" style={{ color: "var(--ink-3)" }}>Loading…</div>
        )}
        {!loading && runs.length === 0 && (
          <div className="px-3.5 py-3 text-[12.5px]" style={{ color: "var(--ink-3)" }}>
            No runs yet for this plugin. Start one from a workflow card.
          </div>
        )}
        {runs.map((r) => (
          <div
            key={r.id}
            onClick={() => onOpen(r.workflowId ?? undefined)}
            className="grid cursor-pointer items-center gap-3 border-t px-3.5 py-2.5 text-[12px] transition-colors hover:bg-[var(--surface-2)]"
            style={{ borderColor: "var(--line-1)", color: "var(--ink-2)", gridTemplateColumns: "110px 1.4fr 1fr 140px 110px 28px" }}
          >
            <div style={{ fontFamily: "var(--font-mono)", color: "var(--ink-1)", fontSize: 11.5 }}>{r.id}</div>
            <div>{r.title ?? "—"}</div>
            <div style={{ color: "var(--ink-3)" }}>{r.workflowId ?? "—"}</div>
            <div style={{ fontFamily: "var(--font-mono)", color: "var(--ink-3)", fontSize: 11 }}>{r.startedAt}</div>
            <div><RunPill status={r.state} /></div>
            <div className="flex justify-end" style={{ color: "var(--ink-3)" }}>
              <ArrowRight className="h-3 w-3" strokeWidth={1.5} />
            </div>
          </div>
        ))}
      </div>
    </Section>
  );
}

function AboutSection({ manifest }: { manifest: PluginManifest }) {
  return (
    <Section title="About this plugin">
      <div className="overflow-hidden rounded-md border" style={{ background: "var(--surface-1)", borderColor: "var(--line-1)" }}>
        <AboutRow label="Vendor" value={manifest.vendor.name} />
        <AboutRow label="Vendor key" value={manifest.vendor.keyFingerprint} mono />
        <AboutRow label="Version" value={`@${manifest.version}`} mono />
        <AboutRow label="Anchor scope" value={manifest.anchor.scope.join(", ")} />
        <AboutRow label="Redaction preset" value={manifest.anchor.redactionPreset} mono />
        <AboutRow label="Anchor TTL" value={`${manifest.anchor.ttlSeconds}s`} />
        <AboutRow label="Trust posture" value={`${manifest.trust.posture} · ${manifest.trust.boundaryLabel}`} />
        <AboutRow label="Exports" value={manifest.exports.join(", ")} />
      </div>
    </Section>
  );
}

// ============================================================
// Primitives
// ============================================================

function Section({ title, note, children }: { title: string; note?: string; children: React.ReactNode }) {
  return (
    <section className="mt-7">
      <header className="mb-3.5">
        <div className="text-[14.5px] font-semibold tracking-tight" style={{ color: "var(--ink-1)" }}>
          {title}
        </div>
        {note && (
          <div className="mt-0.5 text-[12px]" style={{ color: "var(--ink-3)" }}>{note}</div>
        )}
      </header>
      {children}
    </section>
  );
}

function RunPill({ status }: { status: string }) {
  let bg = "var(--surface-2)";
  let color = "var(--ink-2)";
  let dot = "var(--ink-3)";
  if (status === "running") {
    bg = "rgba(4,120,87,0.08)";
    color = "var(--clear)";
    dot = "var(--clear)";
  } else if (status === "waiting" || status === "awaiting-consent") {
    bg = "rgba(180,83,9,0.08)";
    color = "#b45309";
    dot = "#b45309";
  } else if (status === "revoked" || status === "failed") {
    bg = "rgba(220,38,38,0.08)";
    color = "#dc2626";
    dot = "#dc2626";
  }
  return (
    <span
      className="inline-flex items-center gap-1.5 rounded px-2 py-0.5 text-[10.5px] font-semibold uppercase tracking-wider"
      style={{ background: bg, color }}
    >
      <span className="h-1.5 w-1.5 rounded-full" style={{ background: dot }} />
      {status}
    </span>
  );
}

function AboutRow({ label, value, mono = false }: { label: string; value: string; mono?: boolean }) {
  return (
    <div className="grid grid-cols-[180px_1fr] border-t px-3.5 py-2.5 text-[12.5px] first:border-t-0" style={{ borderColor: "var(--line-1)" }}>
      <span style={{ color: "var(--ink-3)" }}>{label}</span>
      <strong
        style={{
          color: "var(--ink-1)",
          fontWeight: 500,
          fontFamily: mono ? "var(--font-mono)" : undefined,
          fontSize: mono ? 11.5 : undefined,
        }}
      >
        {value}
      </strong>
    </div>
  );
}

function withAlpha(color: string, alpha: number): string {
  if (color.startsWith("var(")) {
    // For CSS vars we can't compute; return a neutral tint.
    return `rgba(67, 56, 202, ${alpha})`;
  }
  if (!color.startsWith("#") || color.length !== 7) {
    return `rgba(67, 56, 202, ${alpha})`;
  }
  const r = parseInt(color.slice(1, 3), 16);
  const g = parseInt(color.slice(3, 5), 16);
  const b = parseInt(color.slice(5, 7), 16);
  return `rgba(${r}, ${g}, ${b}, ${alpha})`;
}
