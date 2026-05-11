import { useState } from "react";
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
import type { PluginApprovalRow } from "../../api/plugins";
import type { WorkbenchTab } from "./data";
import type { PluginManifest, UserIdentity } from "./trust";
import type { PluginRunStateBundle } from "./usePluginRun";

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
  payload: Record<string, unknown>;
  outbound?: {
    action: "send-packet" | "register-patient" | "submit-application";
    description: string;
    destination: string;
    approverRole?: UserIdentity["role"];
  };
  previewFromCanvas?: string;
};

const RECIPES: Record<string, ToolRecipe[]> = {
  "trial-finder": [
    { toolId: "trial.search", label: "Search ClinicalTrials.gov", payload: { connector: "clinicaltrials-gov" } },
    { toolId: "trial.search", label: "Search NCI Trial Connect", payload: { connector: "nci-trial-connect" } },
    { toolId: "trial.score_fit", label: "Score NCT-0421187 fit", payload: { nctId: "NCT-0421187" } },
    { toolId: "packet.draft", label: "Draft outreach packet", payload: { nctId: "NCT-0421187" } },
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
  ],
  "second-opinion": [
    { toolId: "referral.compose_packet", label: "Compose endo referral", payload: { specialty: "endocrinology" } },
    { toolId: "referral.apply_redactions", label: "Apply redactions", payload: {} },
    {
      toolId: "referral.route",
      label: "Route packet to network",
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

type PluginRunChatPaneProps = {
  manifest: PluginManifest;
  runId: string;
  bundle: PluginRunStateBundle;
  onRevoke?: () => void;
  onOpenArtifact?: (tab: WorkbenchTab) => void;
};

export function PluginRunChatPane({
  manifest,
  runId,
  bundle,
  onRevoke,
  onOpenArtifact,
}: PluginRunChatPaneProps) {
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
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
    <section
      className="grid h-full min-h-0 grid-rows-[auto_1fr_auto] overflow-hidden"
      style={{
        background: "var(--surface-1)",
        borderRight: "1px solid var(--line-1)",
      }}
    >
      <header className="flex items-center justify-between gap-2 border-b px-4 py-3" style={{ borderColor: "var(--line-1)" }}>
        <div className="min-w-0">
          <div className="text-[11px] font-semibold uppercase tracking-wider" style={{ color: "var(--ink-3)" }}>
            Live run · {run.id}
          </div>
          <div className="mt-0.5 text-[13px] font-semibold" style={{ color: "var(--ink-1)" }}>
            {run.title ?? manifest.displayName}
          </div>
        </div>
        <RunStatePill state={run.state} />
      </header>

      <div className="overflow-y-auto px-4 py-3">
        {errorMessage && (
          <ErrorBubble onClose={() => setErrorMessage(null)}>{errorMessage}</ErrorBubble>
        )}

        {run.state === "awaiting-consent" && (
          <ConsentCard
            manifest={manifest}
            onGrant={async () => {
              try {
                await bundle.grantConsent(DEMO_CLINICIAN);
              } catch (error: unknown) {
                setErrorMessage(asMessage(error));
              }
            }}
          />
        )}

        {run.state !== "awaiting-consent" && run.state !== "revoked" && (
          <>
            <SectionLabel>Run tools</SectionLabel>
            <div className="flex flex-col gap-2">
              {recipes.map((recipe, index) => (
                <ToolButton
                  key={`${recipe.toolId}-${index}`}
                  label={recipe.label}
                  outbound={Boolean(recipe.outbound)}
                  onClick={async () => {
                    setErrorMessage(null);
                    try {
                      if (recipe.outbound) {
                        const preview =
                          (bundle.canvas[recipe.previewFromCanvas ?? recipe.toolId] as { preview?: string } | undefined)
                            ?.preview ??
                          `Send ${recipe.toolId} with payload:\n${JSON.stringify(recipe.payload, null, 2)}`;
                        await bundle.requestApproval({
                          toolId: recipe.toolId,
                          toolPayload: recipe.payload,
                          action: recipe.outbound.action,
                          description: recipe.outbound.description,
                          payloadPreview: preview,
                          destination: recipe.outbound.destination,
                          approverRole: recipe.outbound.approverRole ?? "clinician",
                        });
                      } else {
                        const result = await bundle.callTool(recipe.toolId, recipe.payload);
                        const artifactId =
                          typeof result.artifactId === "string" ? result.artifactId : null;
                        if (artifactId) onOpenArtifact?.(artifactTab(artifactId));
                      }
                    } catch (error: unknown) {
                      setErrorMessage(asMessage(error));
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
                const approver =
                  bundle.pendingApproval?.approverRole === "attending"
                    ? DEMO_ATTENDING
                    : DEMO_CLINICIAN;
                const result = (await bundle.approve(bundle.pendingApproval!.id, approver)) as {
                  result?: Record<string, unknown>;
                };
                const artifactId =
                  typeof result.result?.artifactId === "string"
                    ? String(result.result.artifactId)
                    : null;
                if (artifactId) onOpenArtifact?.(artifactTab(artifactId));
              } catch (error: unknown) {
                setErrorMessage(asMessage(error));
              }
            }}
            onDeny={async () => {
              try {
                await bundle.deny(bundle.pendingApproval!.id, DEMO_CLINICIAN);
              } catch (error: unknown) {
                setErrorMessage(asMessage(error));
              }
            }}
          />
        )}

        {run.state === "revoked" && (
          <div className="rounded-md border p-3 text-[12.5px]" style={{ background: "rgba(220,38,38,0.05)", borderColor: "rgba(220,38,38,0.4)", color: "var(--ink-1)" }}>
            Consent revoked. The run is closed, but the generated artifacts and audit trail stay available in this workspace.
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
    </section>
  );
}

function ConsentCard({ manifest, onGrant }: { manifest: PluginManifest; onGrant: () => void }) {
  const connectors = manifest.connectors.map((connector) => connector.label).join(", ");
  const channels = manifest.permissions
    .filter((permission) => permission.kind === "send-outbound")
    .map((permission) => permission.channel)
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
            <span>May produce outbound: {channels} (every send still requires per-action approval)</span>
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
      </div>
    </div>
  );
}

function ApprovalCard({
  approval,
  onApprove,
  onDeny,
}: {
  approval: PluginApprovalRow;
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

function EventTrace({
  events,
  approvals,
}: {
  events: Array<{ id: string; ts: string; kind: string; payload: Record<string, unknown> }>;
  approvals: PluginApprovalRow[];
}) {
  return (
    <div className="flex flex-col gap-1">
      {events.length === 0 && (
        <div className="text-[11.5px]" style={{ color: "var(--ink-3)" }}>No events yet.</div>
      )}
      {events.map((event) => {
        const ts = event.ts.split("T")[1]?.replace("Z", "") ?? event.ts;
        return (
          <div key={event.id} className="text-[11.5px] leading-[1.5]" style={{ color: "var(--ink-2)" }}>
            <code style={{ color: "var(--ink-3)", fontFamily: "var(--font-mono)" }}>{ts}</code>{" "}
            <strong style={{ color: "var(--ink-1)" }}>{event.kind}</strong>{" "}
            <span style={{ color: "var(--ink-3)" }}>{summarizeEvent(event.kind, event.payload)}</span>
          </div>
        );
      })}
      {approvals.filter((approval) => approval.status !== "pending").length > 0 && (
        <div className="mt-2 text-[10.5px] font-semibold uppercase tracking-wider" style={{ color: "var(--ink-3)" }}>
          Resolved approvals
        </div>
      )}
      {approvals
        .filter((approval) => approval.status !== "pending")
        .map((approval) => (
          <div key={approval.id} className="text-[11.5px]" style={{ color: "var(--ink-3)" }}>
            <code style={{ fontFamily: "var(--font-mono)" }}>{approval.toolId}</code> · {approval.status} · by{" "}
            {approval.resolvedBy ?? "—"}
          </div>
        ))}
    </div>
  );
}

function summarizeEvent(kind: string, payload: Record<string, unknown>): string {
  if (kind === "tool.result") {
    return `→ ${String((payload as { toolId?: string }).toolId ?? "")}`;
  }
  if (kind === "approval.requested") {
    return `${String((payload as { action?: string }).action ?? "")} → ${String((payload as { destination?: string }).destination ?? "")}`;
  }
  if (kind === "approval.approved" || kind === "approval.denied") {
    return String((payload as { approvalId?: string }).approvalId ?? "");
  }
  if (kind === "run.consent-granted") return "consent token minted";
  if (kind === "run.consent-revoked") return "consent revoked";
  return "";
}

function SectionLabel({
  children,
  className = "",
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <div className={`mb-2 text-[10.5px] font-semibold uppercase tracking-wider ${className}`} style={{ color: "var(--ink-3)" }}>
      {children}
    </div>
  );
}

function ToolButton({
  label,
  outbound,
  onClick,
}: {
  label: string;
  outbound: boolean;
  onClick: () => void;
}) {
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

function ErrorBubble({
  children,
  onClose,
}: {
  children: React.ReactNode;
  onClose: () => void;
}) {
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

function asMessage(error: unknown): string {
  if (error instanceof Error) return `${error.name}: ${error.message}`;
  return String(error);
}

function artifactTab(artifactId: string): WorkbenchTab {
  return {
    id: artifactId,
    label: artifactId,
    icon: "FileText",
    kind: "packet-outline",
    renderer: "markdown.doc",
    dirty: true,
  };
}
