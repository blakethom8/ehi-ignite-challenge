/**
 * Live plugin run panel.
 *
 * Drives a real backend run end-to-end:
 *  - awaiting-consent → renders a PluginConsentCard
 *  - running → tool launcher + workbench tabs
 *  - pending outbound → renders an ApprovalCard for the open approval
 *  - revoked / complete → terminal state notice
 *
 * Per HARNESS-SURFACES §8 + §11: no domain logic here. Tool args are
 * declared inline per workflow but the *handlers* are server-side.
 * Renderers project the canvas state straight from the run events.
 */

import { useMemo, useState } from "react";
import {
  AlertTriangle,
  CheckCircle2,
  Database,
  Eye,
  Globe,
  Loader2,
  Play,
  Send,
  ShieldCheck,
  X,
} from "lucide-react";
import { RENDERERS } from "./renderers";
import { usePluginRun } from "./usePluginRun";
import type {
  PluginApprovalRequest,
  PluginManifest,
  UserIdentity,
} from "./trust";

const DEMO_CLINICIAN: UserIdentity = {
  id: "demo-clinician",
  name: "Demo Clinician",
  role: "clinician",
};

const DEMO_ATTENDING: UserIdentity = {
  id: "demo-attending",
  name: "Demo Attending",
  role: "attending",
};

type ToolRecipe = {
  toolId: string;
  label: string;
  /** Per-tool payload. */
  payload: Record<string, unknown>;
  /** When set, fire this as an approval request rather than a direct call. */
  outbound?: {
    action: PluginApprovalRequest["action"];
    description: string;
    destination: string;
    approverRole?: UserIdentity["role"];
  };
  /** Pick a canvas value to use as the payloadPreview (defaults to the tool's preview field). */
  previewFromCanvas?: string;
};

const RECIPES: Record<string, ToolRecipe[]> = {
  "trial-finder": [
    { toolId: "trial.search", label: "Search ClinicalTrials.gov", payload: { connector: "clinicaltrials-gov" } },
    { toolId: "trial.search", label: "Search NCI Trial Connect", payload: { connector: "nci-trial-connect" } },
    { toolId: "trial.score_fit", label: "Score NCT-0421187 fit", payload: { nctId: "NCT-0421187" } },
    { toolId: "packet.draft", label: "Draft outreach packet (NCT-0421187)", payload: { nctId: "NCT-0421187" } },
    {
      toolId: "packet.send",
      label: "Send packet to MSKCC",
      payload: { channel: "site-packet", site: "MSKCC", artifactId: "outreach-packet-NCT-0421187" },
      previewFromCanvas: "packet.draft",
      outbound: {
        action: "send-packet",
        description: "Route the outreach packet for NCT-0421187 to MSKCC.",
        destination: "MSKCC",
      },
    },
  ],
  "med-access": [
    { toolId: "med.lookup_formulary", label: "Look up formulary", payload: { connector: "surescripts-formulary" } },
    { toolId: "med.identify_barriers", label: "Identify barriers", payload: {} },
    { toolId: "pap.match", label: "Match PAP options", payload: { connector: "manufacturer-pap-api", drug: "apixaban" } },
    { toolId: "pa.compose", label: "Compose apixaban PA", payload: { drug: "apixaban" } },
    {
      toolId: "pa.submit",
      label: "Submit PA to payer",
      payload: { channel: "pa-submission", drug: "apixaban" },
      previewFromCanvas: "pa.compose",
      outbound: {
        action: "submit-application",
        description: "Submit prior auth packet to Aetna Open Access PPO.",
        destination: "Aetna Open Access PPO",
      },
    },
    {
      toolId: "pap.enroll",
      label: "Enroll in BMS3B Bridges PAP",
      payload: { channel: "pap-enrollment" },
      previewFromCanvas: "pap.match",
      outbound: {
        action: "register-patient",
        description: "Enroll patient in the BMS3B Bridges manufacturer assistance program.",
        destination: "BMS3B Bridges PAP",
      },
    },
  ],
  "second-opinion": [
    { toolId: "referral.compose_packet", label: "Compose endo referral", payload: { specialty: "endocrinology" } },
    { toolId: "referral.apply_redactions", label: "Apply redactions", payload: {} },
    {
      toolId: "referral.route",
      label: "Route packet (requires attending)",
      payload: { channel: "consulting-network", specialty: "endocrinology" },
      previewFromCanvas: "referral.compose_packet",
      outbound: {
        action: "send-packet",
        description: "Route the endocrinology referral packet to ConferMD.",
        destination: "ConferMD endocrinology network",
        approverRole: "attending",
      },
    },
    {
      toolId: "referral.fetch_response",
      label: "Poll specialist response",
      payload: { connector: "confermd-network" },
    },
  ],
};

type Props = {
  manifest: PluginManifest;
  runId: string;
  onRevoke?: () => void;
};

export function PluginRunPanel({ manifest, runId, onRevoke }: Props) {
  const bundle = usePluginRun(runId);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<string>(manifest.ui.workbenchTabs[0]?.id ?? "");
  const recipes = RECIPES[manifest.id] ?? [];

  if (bundle.isLoading || !bundle.run) {
    return (
      <div className="grid h-full place-items-center text-[12.5px]" style={{ color: "var(--ink-3)" }}>
        <Loader2 className="mb-2 h-5 w-5 animate-spin" />
        Loading run {runId}…
      </div>
    );
  }

  const run = bundle.run;

  return (
    <div className="grid h-full min-h-0 grid-cols-[420px_1fr] overflow-hidden">
      {/* Left: chat-like flow */}
      <aside
        className="flex h-full min-h-0 flex-col border-r"
        style={{ borderColor: "var(--line-1)", background: "var(--surface-0)" }}
      >
        <header className="flex items-center justify-between gap-2 border-b px-4 py-3" style={{ borderColor: "var(--line-1)" }}>
          <div className="min-w-0">
            <div className="text-[11px] font-semibold uppercase tracking-wider" style={{ color: "var(--ink-3)" }}>
              Run · {run.id}
            </div>
            <div className="mt-0.5 text-[13px] font-semibold" style={{ color: "var(--ink-1)" }}>
              {run.title ?? "Active run"}
            </div>
          </div>
          <RunStatePill state={run.state} />
        </header>

        <div className="flex-1 overflow-y-auto px-4 py-3">
          {errorMessage && (
            <ErrorBubble onClose={() => setErrorMessage(null)}>{errorMessage}</ErrorBubble>
          )}

          {run.state === "awaiting-consent" && (
            <ConsentCard
              manifest={manifest}
              onGrant={async () => {
                try {
                  await bundle.grantConsent(DEMO_CLINICIAN);
                } catch (e: unknown) {
                  setErrorMessage(asMessage(e));
                }
              }}
            />
          )}

          {run.state !== "awaiting-consent" && run.state !== "revoked" && (
            <>
              <SectionLabel>Plugin tools</SectionLabel>
              <div className="flex flex-col gap-2">
                {recipes.map((r, i) => (
                  <ToolButton
                    key={`${r.toolId}-${i}`}
                    label={r.label}
                    outbound={Boolean(r.outbound)}
                    onClick={async () => {
                      setErrorMessage(null);
                      try {
                        if (r.outbound) {
                          const preview = (bundle.canvas[r.previewFromCanvas ?? r.toolId] as { preview?: string } | undefined)?.preview ??
                            `Send ${r.toolId} with payload:\n${JSON.stringify(r.payload, null, 2)}`;
                          await bundle.requestApproval({
                            toolId: r.toolId,
                            toolPayload: r.payload,
                            action: r.outbound.action,
                            description: r.outbound.description,
                            payloadPreview: preview,
                            destination: r.outbound.destination,
                            approverRole: r.outbound.approverRole ?? "clinician",
                          });
                        } else {
                          await bundle.callTool(r.toolId, r.payload);
                        }
                      } catch (e: unknown) {
                        setErrorMessage(asMessage(e));
                      }
                    }}
                  />
                ))}
              </div>
            </>
          )}

          {bundle.pendingApproval && (
            <ApprovalCard
              approval={bundle.pendingApproval}
              onApprove={async () => {
                try {
                  const approver = bundle.pendingApproval?.approverRole === "attending" ? DEMO_ATTENDING : DEMO_CLINICIAN;
                  await bundle.approve(bundle.pendingApproval!.id, approver);
                } catch (e: unknown) {
                  setErrorMessage(asMessage(e));
                }
              }}
              onDeny={async () => {
                try {
                  await bundle.deny(bundle.pendingApproval!.id, DEMO_CLINICIAN);
                } catch (e: unknown) {
                  setErrorMessage(asMessage(e));
                }
              }}
            />
          )}

          {run.state === "revoked" && (
            <div className="rounded-md border p-3 text-[12.5px]" style={{ background: "rgba(220,38,38,0.05)", borderColor: "rgba(220,38,38,0.4)", color: "var(--ink-1)" }}>
              Consent revoked. All pending outbound approvals were voided. The run is closed; provenance rows from earlier outbound actions are preserved.
            </div>
          )}

          <SectionLabel className="mt-5">Event trace</SectionLabel>
          <EventTrace events={bundle.events} approvals={bundle.approvals} />
        </div>

        <footer className="flex items-center justify-between gap-2 border-t px-4 py-2 text-[11px]" style={{ borderColor: "var(--line-1)", color: "var(--ink-3)" }}>
          <span>{bundle.events.length} events · {bundle.approvals.length} approvals</span>
          {run.state !== "revoked" && run.state !== "complete" && (
            <button
              onClick={async () => {
                await bundle.revokeConsent(DEMO_CLINICIAN);
                onRevoke?.();
              }}
              className="rounded px-2 py-1 text-[11px] font-medium hover:bg-[var(--surface-2)]"
              style={{ color: "#dc2626" }}
            >
              Revoke consent
            </button>
          )}
        </footer>
      </aside>

      {/* Right: workbench */}
      <section className="flex h-full min-h-0 flex-col overflow-hidden" style={{ background: "var(--surface-0)" }}>
        <div className="flex h-9 items-center gap-2 border-b px-3" style={{ borderColor: "var(--line-1)", background: "var(--bg-chrome)" }}>
          {manifest.ui.workbenchTabs.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className="rounded px-2 py-1 text-[12px]"
              style={{
                background: activeTab === tab.id ? "var(--surface-0)" : "transparent",
                color: activeTab === tab.id ? "var(--ink-1)" : "var(--ink-3)",
                border: activeTab === tab.id ? "1px solid var(--line-2)" : "1px solid transparent",
              }}
            >
              {tab.label}
            </button>
          ))}
        </div>
        <div className="flex-1 overflow-y-auto">
          <WorkbenchBody
            manifest={manifest}
            activeTab={activeTab}
            canvas={bundle.canvas}
            runId={runId}
          />
        </div>
      </section>
    </div>
  );
}

// ============================================================
// Children
// ============================================================

function WorkbenchBody({
  manifest,
  activeTab,
  canvas,
  runId,
}: {
  manifest: PluginManifest;
  activeTab: string;
  canvas: Record<string, unknown>;
  runId: string;
}) {
  const tab = manifest.ui.workbenchTabs.find((t) => t.id === activeTab);
  if (!tab) {
    return (
      <div className="p-8 text-[13px]" style={{ color: "var(--ink-4)" }}>No tab open.</div>
    );
  }
  const Renderer = RENDERERS[tab.renderer];
  if (!Renderer) {
    return (
      <div className="p-8 text-[13px]" style={{ color: "var(--warn)" }}>
        No renderer registered for: {tab.renderer}
      </div>
    );
  }
  // Provide a virtual "manifest" canvas key for json.viewer of the manifest tab.
  const fullCanvas = useMemo(() => ({ ...canvas, manifest }), [canvas, manifest]);
  return <Renderer runId={runId} canvas={fullCanvas} tabId={tab.id} />;
}

function ConsentCard({ manifest, onGrant }: { manifest: PluginManifest; onGrant: () => void }) {
  const connectors = manifest.connectors.map((c) => c.label).join(", ");
  const channels = manifest.permissions
    .filter((p) => p.kind === "send-outbound")
    .map((p) => (p as { channel: string }).channel)
    .join(", ");
  return (
    <div
      className="mb-4 rounded-md border p-4"
      style={{ background: "rgba(180,83,9,0.04)", borderColor: "rgba(180,83,9,0.4)" }}
    >
      <div className="mb-2 flex items-center gap-2 text-[10.5px] font-bold uppercase tracking-wider" style={{ color: "#b45309" }}>
        <ShieldCheck className="h-3.5 w-3.5" strokeWidth={1.5} />
        Consent requested · {manifest.displayName}
      </div>
      <p className="text-[13px] leading-[1.55]" style={{ color: "var(--ink-1)" }}>
        {manifest.displayName} will be granted a consented patient anchor for this run.
      </p>
      <ul className="mt-3 space-y-1 text-[12.5px]" style={{ color: "var(--ink-2)" }}>
        <li className="flex items-start gap-2">
          <Database className="mt-0.5 h-3 w-3" strokeWidth={1.5} />
          <span>Reads: {manifest.anchor.scope.join(", ")} (preset: {manifest.anchor.redactionPreset})</span>
        </li>
        {connectors && (
          <li className="flex items-start gap-2">
            <Globe className="mt-0.5 h-3 w-3" strokeWidth={1.5} />
            <span>Calls: {connectors}</span>
          </li>
        )}
        {channels && (
          <li className="flex items-start gap-2">
            <Send className="mt-0.5 h-3 w-3" strokeWidth={1.5} />
            <span>May produce outbound: {channels} (every send requires per-action approval)</span>
          </li>
        )}
      </ul>
      <div className="mt-4 flex gap-2">
        <button
          onClick={onGrant}
          className="inline-flex items-center justify-center gap-1.5 rounded-md px-4 py-2 text-[12.5px] font-medium text-white"
          style={{ background: "var(--action)" }}
        >
          <CheckCircle2 className="h-3 w-3" strokeWidth={1.5} />
          Grant consent for this run
        </button>
        <button
          className="rounded-md border px-4 py-2 text-[12.5px] font-medium"
          style={{ background: "var(--surface-1)", borderColor: "var(--line-2)", color: "var(--ink-1)" }}
        >
          Cancel
        </button>
      </div>
    </div>
  );
}

function ApprovalCard({
  approval,
  onApprove,
  onDeny,
}: {
  approval: {
    id: string;
    action: string;
    description: string;
    destination: string;
    redactionPreset: string;
    payloadPreview: string;
    approverRole: string;
  };
  onApprove: () => void;
  onDeny: () => void;
}) {
  return (
    <div
      className="my-4 rounded-md border p-4"
      style={{ background: "rgba(180,83,9,0.06)", borderColor: "rgba(180,83,9,0.45)" }}
    >
      <div className="mb-2 flex items-center justify-between text-[10.5px] font-bold uppercase tracking-wider" style={{ color: "#b45309" }}>
        <span className="inline-flex items-center gap-2">
          <AlertTriangle className="h-3.5 w-3.5" strokeWidth={1.5} />
          Outbound approval · {approval.action}
        </span>
        <span style={{ color: "var(--ink-3)" }}>role: {approval.approverRole}</span>
      </div>
      <p className="text-[13px] leading-[1.55]" style={{ color: "var(--ink-1)" }}>{approval.description}</p>
      <div className="mt-2 text-[12px]" style={{ color: "var(--ink-3)" }}>
        Destination: <strong style={{ color: "var(--ink-2)" }}>{approval.destination}</strong> · Redaction: <code style={{ fontFamily: "var(--font-mono)" }}>{approval.redactionPreset}</code>
      </div>
      <details className="mt-2">
        <summary className="cursor-pointer text-[11.5px] font-semibold" style={{ color: "var(--ink-2)" }}>
          <Eye className="mr-1 inline h-3 w-3" strokeWidth={1.5} />
          Payload preview (verbatim)
        </summary>
        <pre
          className="mt-2 max-h-[260px] overflow-auto rounded border p-2.5 text-[11.5px] leading-[1.5]"
          style={{ background: "var(--surface-0)", borderColor: "var(--line-1)", color: "var(--ink-1)", fontFamily: "var(--font-mono)" }}
        >
          {approval.payloadPreview}
        </pre>
      </details>
      <div className="mt-3 flex gap-2">
        <button
          onClick={onApprove}
          className="inline-flex items-center gap-1.5 rounded-md px-3.5 py-1.5 text-[12px] font-medium text-white"
          style={{ background: "var(--action)" }}
        >
          <CheckCircle2 className="h-3 w-3" strokeWidth={1.5} />
          Approve
        </button>
        <button
          onClick={onDeny}
          className="rounded-md border px-3.5 py-1.5 text-[12px] font-medium"
          style={{ background: "var(--surface-1)", borderColor: "var(--line-2)", color: "var(--ink-1)" }}
        >
          Deny
        </button>
      </div>
    </div>
  );
}

function EventTrace({ events, approvals }: { events: Array<{ id: string; ts: string; kind: string; payload: Record<string, unknown> }>; approvals: Array<{ status: string; toolId: string; resolvedBy?: string | null }> }) {
  return (
    <div className="flex flex-col gap-1">
      {events.length === 0 && (
        <div className="text-[11.5px]" style={{ color: "var(--ink-3)" }}>No events yet.</div>
      )}
      {events.map((e) => {
        const ts = e.ts.split("T")[1]?.replace("Z", "") ?? e.ts;
        return (
          <div key={e.id} className="text-[11.5px] leading-[1.5]" style={{ color: "var(--ink-2)" }}>
            <code style={{ color: "var(--ink-3)", fontFamily: "var(--font-mono)" }}>{ts}</code>{" "}
            <strong style={{ color: "var(--ink-1)" }}>{e.kind}</strong>{" "}
            <span style={{ color: "var(--ink-3)" }}>
              {summarizeEvent(e.kind, e.payload)}
            </span>
          </div>
        );
      })}
      {approvals.filter((a) => a.status !== "pending").length > 0 && (
        <div className="mt-2 text-[10.5px] font-semibold uppercase tracking-wider" style={{ color: "var(--ink-3)" }}>
          Resolved approvals
        </div>
      )}
      {approvals
        .filter((a) => a.status !== "pending")
        .map((a, i) => (
          <div key={i} className="text-[11.5px]" style={{ color: "var(--ink-3)" }}>
            <code style={{ fontFamily: "var(--font-mono)" }}>{a.toolId}</code> · {a.status} · by {a.resolvedBy ?? "—"}
          </div>
        ))}
    </div>
  );
}

function summarizeEvent(kind: string, payload: Record<string, unknown>): string {
  if (kind === "tool.result") {
    const p = payload as { toolId?: string };
    return `→ ${p.toolId ?? ""}`;
  }
  if (kind === "approval.requested") {
    const p = payload as { action?: string; destination?: string };
    return `${p.action} → ${p.destination}`;
  }
  if (kind === "approval.approved" || kind === "approval.denied") {
    const p = payload as { approvalId?: string };
    return `${p.approvalId ?? ""}`;
  }
  if (kind === "run.consent-granted") return "consent token minted";
  if (kind === "run.consent-revoked") return "consent revoked";
  return "";
}

function SectionLabel({ children, className = "" }: { children: React.ReactNode; className?: string }) {
  return (
    <div className={`mb-2 text-[10.5px] font-semibold uppercase tracking-wider ${className}`} style={{ color: "var(--ink-3)" }}>
      {children}
    </div>
  );
}

function ToolButton({ label, outbound, onClick }: { label: string; outbound: boolean; onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      className="inline-flex items-center justify-between gap-2 rounded-md border px-3 py-2 text-left text-[12.5px] hover:bg-[var(--surface-2)]"
      style={{
        background: "var(--surface-1)",
        borderColor: outbound ? "rgba(180,83,9,0.35)" : "var(--line-1)",
        color: "var(--ink-1)",
      }}
    >
      <span className="inline-flex items-center gap-2">
        {outbound ? <Send className="h-3 w-3" strokeWidth={1.5} style={{ color: "#b45309" }} /> : <Play className="h-3 w-3" strokeWidth={1.5} />}
        {label}
      </span>
      {outbound && (
        <span className="rounded px-1.5 py-0.5 text-[10px] font-semibold uppercase" style={{ background: "rgba(180,83,9,0.1)", color: "#b45309" }}>
          gated
        </span>
      )}
    </button>
  );
}

function RunStatePill({ state }: { state: string }) {
  let bg = "var(--surface-2)";
  let color = "var(--ink-2)";
  if (state === "running") {
    bg = "rgba(4,120,87,0.1)";
    color = "var(--clear)";
  } else if (state === "waiting" || state === "awaiting-consent") {
    bg = "rgba(180,83,9,0.1)";
    color = "#b45309";
  } else if (state === "revoked" || state === "failed") {
    bg = "rgba(220,38,38,0.1)";
    color = "#dc2626";
  }
  return (
    <span className="rounded px-2 py-0.5 text-[10.5px] font-semibold uppercase tracking-wider" style={{ background: bg, color }}>
      {state}
    </span>
  );
}

function ErrorBubble({ children, onClose }: { children: React.ReactNode; onClose: () => void }) {
  return (
    <div
      className="mb-3 flex items-start gap-2 rounded-md border px-3 py-2 text-[12.5px]"
      style={{ background: "rgba(220,38,38,0.05)", borderColor: "rgba(220,38,38,0.4)", color: "var(--ink-1)" }}
    >
      <AlertTriangle className="mt-0.5 h-3.5 w-3.5" strokeWidth={1.5} style={{ color: "#dc2626" }} />
      <div className="flex-1">{children}</div>
      <button onClick={onClose} style={{ color: "var(--ink-3)" }}>
        <X className="h-3 w-3" strokeWidth={1.5} />
      </button>
    </div>
  );
}

function asMessage(e: unknown): string {
  if (e instanceof Error) return `${e.name}: ${e.message}`;
  return String(e);
}
