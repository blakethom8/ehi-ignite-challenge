import {
  ArrowRight,
  Boxes,
  Database,
  Globe,
  Pill,
  Play,
  Send,
  Settings,
  Telescope,
  UserRound,
  Workflow,
} from "lucide-react";
import { WORKFLOWS } from "./data";
import type { Workspace, WorkspaceId } from "./types";

const PACKAGE_ICONS: Record<string, typeof Telescope> = {
  Telescope,
  Pill,
  Send,
  Boxes,
};

type PackageHomeProps = {
  workspace: Workspace;
  onStartRun: () => void;
};

export function PackageHome({ workspace, onStartRun }: PackageHomeProps) {
  const Icon = PACKAGE_ICONS[workspace.icon] ?? Telescope;
  const workflows = WORKFLOWS[workspace.id as WorkspaceId] ?? [];
  const perms = [
    { icon: Database, label: "Reads patient anchors", detail: "Read-only handle from Caspian. No PHI leaves the run.", warn: false },
    { icon: Globe, label: "Calls external registries", detail: "ClinicalTrials.gov, NCI Trial Connect, NIH ClinicalTrials API.", warn: false },
    { icon: Send, label: "Sends outbound packets", detail: "Gated by explicit per-run approval. De-identification preset required.", warn: true },
  ];
  const recent = [
    { id: "r_4128", patient: "M. Hollister", workflow: "Shortlist trials", started: "2025-05-10 11:54", status: "running", outcome: "8 of 14 candidates ranked" },
    { id: "r_4118", patient: "R. Aoki", workflow: "Eligibility check", started: "2025-05-09 14:20", status: "complete", outcome: "3 eligible · 2 pending consent" },
    { id: "r_4102", patient: "D. Cabrera", workflow: "Draft outreach packet", started: "2025-05-08 09:11", status: "waiting", outcome: "Approval pending · site coordinator" },
    { id: "r_4087", patient: "M. Hollister", workflow: "Site coordination follow-up", started: "2025-05-06 16:02", status: "complete", outcome: "Closed · site declined enrollment" },
  ];

  return (
    <div
      className="flex min-h-0 flex-1 flex-col overflow-hidden"
      style={{ background: "var(--bg-app)" }}
    >
      <div className="mx-auto w-full max-w-[1100px] flex-1 overflow-y-auto px-10 pb-16 pt-7">
        <header
          className="flex items-start gap-5 border-b pb-7"
          style={{ borderColor: "var(--line-1)" }}
        >
          <div
            className="grid h-14 w-14 flex-[0_0_56px] place-items-center rounded-[12px]"
            style={{ background: "rgba(67,56,202,0.12)", color: "#4338ca" }}
          >
            <Icon className="h-7 w-7" strokeWidth={1.5} />
          </div>
          <div className="min-w-0 flex-1">
            <div
              className="text-[10.5px] font-bold uppercase tracking-[0.12em]"
              style={{ color: "var(--ink-3)" }}
            >
              MARKETPLACE PACKAGE · INSTALLED
            </div>
            <div
              className="mt-2 flex items-baseline gap-2.5 text-[26px] font-semibold leading-[1.1] tracking-tight"
              style={{ color: "var(--ink-1)" }}
            >
              {workspace.title}
              <span
                className="rounded px-2 py-0.5 text-[14px] font-medium"
                style={{
                  background: "rgba(67,56,202,0.08)",
                  color: "#4338ca",
                  fontFamily: "var(--font-mono)",
                }}
              >
                @{workspace.version}
              </span>
            </div>
            <div className="mt-1.5 text-[12.5px]" style={{ color: "var(--ink-3)" }}>
              by {workspace.vendor} · auto-update on · last refresh {workspace.lastRefresh}
            </div>
            <p
              className="mt-3.5 max-w-[70ch] text-[13.5px] leading-[1.55]"
              style={{ color: "var(--ink-2)" }}
            >
              {workspace.id === "trial-finder"
                ? "Pulls a consented patient anchor from Caspian and runs a clinical-trial discovery loop against external registries. Produces ranked candidate boards, eligibility checks, and outreach packets — every outbound action gated by per-run approval in the active session thread."
                : workspace.id === "med-access"
                ? "Coordinates patient-assistance program enrollment and prior-auth packets. Reads the active medication list from Caspian and submits packets after explicit clinician approval."
                : "Runs follow-up loops with trial sites: appointment confirmation, missing-records nudges, eligibility re-checks. Operational overhead, automated."}
            </p>
          </div>
          <div className="flex flex-col gap-2">
            <button
              onClick={onStartRun}
              className="inline-flex items-center justify-center gap-1.5 whitespace-nowrap rounded-md px-4 py-2 text-[12.5px] font-medium text-white"
              style={{ background: "var(--action)" }}
            >
              <Play className="h-3 w-3" strokeWidth={1.5} />
              Start new run
            </button>
            <button
              className="inline-flex items-center justify-center gap-1.5 whitespace-nowrap rounded-md border px-4 py-2 text-[12.5px] font-medium hover:bg-[var(--surface-2)]"
              style={{
                background: "var(--surface-1)",
                borderColor: "var(--line-2)",
                color: "var(--ink-1)",
              }}
            >
              <Settings className="h-3 w-3" strokeWidth={1.5} />
              Configure
            </button>
          </div>
        </header>

        <Section
          title="Permissions ledger"
          note="What this package is allowed to do, scoped to your workspace."
        >
          <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
            {perms.map((p, i) => {
              const PIcon = p.icon;
              return (
                <div
                  key={i}
                  className="flex gap-2.5 rounded-md border p-3.5"
                  style={{
                    background: p.warn ? "rgba(180,83,9,0.04)" : "var(--surface-1)",
                    borderColor: p.warn ? "rgba(180,83,9,0.25)" : "var(--line-1)",
                  }}
                >
                  <div
                    className="grid h-[26px] w-[26px] flex-[0_0_26px] place-items-center rounded-md"
                    style={{
                      background: p.warn ? "rgba(180,83,9,0.12)" : "var(--surface-2)",
                      color: p.warn ? "#b45309" : "var(--ink-2)",
                    }}
                  >
                    <PIcon className="h-3.5 w-3.5" strokeWidth={1.5} />
                  </div>
                  <div>
                    <div
                      className="text-[12.5px] font-semibold"
                      style={{ color: "var(--ink-1)" }}
                    >
                      {p.label}
                    </div>
                    <div
                      className="mt-0.5 text-[11.5px] leading-[1.4]"
                      style={{ color: "var(--ink-3)" }}
                    >
                      {p.detail}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </Section>

        <Section
          title="Workflows"
          note="Pick a workflow to start a new run. The run becomes a session in this workspace."
        >
          <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
            {workflows.map((w) => (
              <button
                key={w.id}
                onClick={onStartRun}
                className="flex flex-col gap-2 rounded-md border p-4 text-left transition-colors hover:border-[var(--action-line)] hover:shadow-[0_1px_0_var(--action-tint)]"
                style={{ background: "var(--surface-1)", borderColor: "var(--line-1)" }}
              >
                <div className="flex items-center gap-2" style={{ color: "var(--ink-2)" }}>
                  <Workflow className="h-3.5 w-3.5" strokeWidth={1.5} />
                  <div
                    className="text-[13.5px] font-semibold"
                    style={{ color: "var(--ink-1)" }}
                  >
                    {w.title}
                  </div>
                </div>
                <div
                  className="text-[12px] leading-[1.45]"
                  style={{ color: "var(--ink-3)" }}
                >
                  {w.desc}
                </div>
                <div className="flex flex-wrap gap-1">
                  {w.tags.map((t) => (
                    <span
                      key={t}
                      className="rounded-[3px] border px-1.5 py-0.5 text-[10.5px]"
                      style={{
                        background: "var(--surface-2)",
                        borderColor: "var(--line-1)",
                        color: "var(--ink-3)",
                      }}
                    >
                      {t}
                    </span>
                  ))}
                </div>
                <div
                  className="mt-1 flex items-center justify-between border-t border-dashed pt-2 text-[11px]"
                  style={{ borderColor: "var(--line-1)" }}
                >
                  <span style={{ color: "var(--ink-3)" }}>Needs: patient anchor</span>
                  <span
                    className="inline-flex items-center gap-1 font-medium"
                    style={{ color: "var(--action)" }}
                  >
                    Start <ArrowRight className="h-3 w-3" strokeWidth={1.5} />
                  </span>
                </div>
              </button>
            ))}
          </div>
        </Section>

        <Section
          title="Recent runs"
          note="Re-enter a session or audit a completed run."
        >
          <div
            className="overflow-hidden rounded-md border"
            style={{ background: "var(--surface-1)", borderColor: "var(--line-1)" }}
          >
            <div
              className="grid items-center gap-3 border-b px-3.5 py-2.5 text-[10.5px] font-bold uppercase tracking-wider"
              style={{
                background: "var(--surface-2)",
                borderColor: "var(--line-1)",
                color: "var(--ink-3)",
                gridTemplateColumns: "90px 130px 1.2fr 130px 110px 1.4fr 28px",
              }}
            >
              <div>Run</div>
              <div>Patient</div>
              <div>Workflow</div>
              <div>Started</div>
              <div>Status</div>
              <div>Outcome</div>
              <div />
            </div>
            {recent.map((r) => (
              <div
                key={r.id}
                onClick={onStartRun}
                className="grid cursor-pointer items-center gap-3 border-t px-3.5 py-2.5 text-[12px] transition-colors hover:bg-[var(--surface-2)]"
                style={{
                  borderColor: "var(--line-1)",
                  color: "var(--ink-2)",
                  gridTemplateColumns: "90px 130px 1.2fr 130px 110px 1.4fr 28px",
                }}
              >
                <div style={{ fontFamily: "var(--font-mono)", color: "var(--ink-1)", fontSize: 11.5 }}>
                  {r.id}
                </div>
                <div className="inline-flex items-center gap-1.5">
                  <UserRound className="h-2.5 w-2.5" strokeWidth={1.5} />
                  {r.patient}
                </div>
                <div>{r.workflow}</div>
                <div style={{ fontFamily: "var(--font-mono)", color: "var(--ink-3)", fontSize: 11 }}>
                  {r.started}
                </div>
                <div>
                  <RunPill status={r.status} />
                </div>
                <div style={{ color: "var(--ink-3)", fontSize: 11.5 }}>{r.outcome}</div>
                <div className="flex justify-end" style={{ color: "var(--ink-3)" }}>
                  <ArrowRight className="h-3 w-3" strokeWidth={1.5} />
                </div>
              </div>
            ))}
          </div>
        </Section>

        <Section title="About this package">
          <div
            className="overflow-hidden rounded-md border"
            style={{ background: "var(--surface-1)", borderColor: "var(--line-1)" }}
          >
            <AboutRow label="Vendor" value={workspace.vendor ?? "—"} />
            <AboutRow label="Version" value={`@${workspace.version}`} />
            <AboutRow label="Installed by" value="R. Patel · 2025-04-02" />
            <AboutRow label="Update channel" value="Stable · auto" />
            <AboutRow label="Trust posture" value="Consented external · per-run approval" />
            <AboutRow label="Audit log" value="Open in Review →" link />
          </div>
        </Section>
      </div>
    </div>
  );
}

function Section({
  title,
  note,
  children,
}: {
  title: string;
  note?: string;
  children: React.ReactNode;
}) {
  return (
    <section className="mt-7">
      <header className="mb-3.5">
        <div
          className="text-[14.5px] font-semibold tracking-tight"
          style={{ color: "var(--ink-1)" }}
        >
          {title}
        </div>
        {note && (
          <div className="mt-0.5 text-[12px]" style={{ color: "var(--ink-3)" }}>
            {note}
          </div>
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
  } else if (status === "waiting") {
    bg = "rgba(180,83,9,0.08)";
    color = "#b45309";
    dot = "#b45309";
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

function AboutRow({
  label,
  value,
  link,
}: {
  label: string;
  value: string;
  link?: boolean;
}) {
  return (
    <div
      className="grid grid-cols-[180px_1fr] border-t px-3.5 py-2.5 text-[12.5px] first:border-t-0"
      style={{ borderColor: "var(--line-1)" }}
    >
      <span style={{ color: "var(--ink-3)" }}>{label}</span>
      {link ? (
        <a href="#" onClick={(e) => e.preventDefault()} style={{ color: "var(--action)" }}>
          {value}
        </a>
      ) : (
        <strong style={{ color: "var(--ink-1)", fontWeight: 500 }}>{value}</strong>
      )}
    </div>
  );
}
