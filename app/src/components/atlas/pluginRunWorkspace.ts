import type { PluginApprovalRow, PluginRun, RunEvent } from "../../api/plugins";
import { workspaceFromManifest } from "./manifests";
import type { FileNode, FileTreeNode, Session, WorkbenchTab } from "./data";
import type { PluginManifest } from "./trust";
import type { Workspace } from "./types";

type PluginRunWorkspaceSurface = {
  workspace: Workspace;
  sessions: Session[];
  tabs: WorkbenchTab[];
  filesTree: FileTreeNode[];
  canvas: Record<string, unknown>;
  fileTabs: Record<string, WorkbenchTab>;
};

type PluginWorkspaceScaffold = Pick<
  PluginRunWorkspaceSurface,
  "tabs" | "filesTree" | "canvas" | "fileTabs"
>;

type BuildSurfaceArgs = {
  manifest: PluginManifest;
  run: PluginRun;
  runs: PluginRun[];
  events: RunEvent[];
  approvals: PluginApprovalRow[];
  canvas: Record<string, unknown>;
};

export function buildPluginWorkspaceScaffold(
  manifest: PluginManifest,
): PluginWorkspaceScaffold {
  const canvas: Record<string, unknown> = { manifest };
  const tabs = buildTabs(manifest, canvas);
  const fileTabs = buildFileTabs(manifest, canvas, tabs);
  const filesTree = buildFilesTree(manifest, canvas, fileTabs);
  return { tabs, filesTree, canvas, fileTabs };
}

export function buildPluginRunWorkspaceSurface({
  manifest,
  run,
  runs,
  events,
  approvals,
  canvas,
}: BuildSurfaceArgs): PluginRunWorkspaceSurface {
  const baseWorkspace = workspaceFromManifest(manifest);
  const projectedCanvas = buildProjectedCanvas(manifest, run, canvas);
  const tabs = buildTabs(manifest, projectedCanvas);
  const fileTabs = buildFileTabs(manifest, projectedCanvas, tabs);
  const filesTree = buildFilesTree(manifest, projectedCanvas, fileTabs);
  return {
    workspace: {
      ...baseWorkspace,
      runState: toWorkspaceRunState(run.state),
      runStep: summarizeCurrentStep(run, events, approvals),
      runElapsed: formatElapsed(run.startedAt, run.completedAt),
      lastRefresh: latestTimestamp(events),
      anchoredFrom: `Anchor · ${run.patientId}`,
    },
    sessions: buildPluginRunSessions(runs),
    tabs,
    filesTree,
    canvas: projectedCanvas,
    fileTabs,
  };
}

export function buildPluginRunSessions(runs: PluginRun[]): Session[] {
  return [...runs]
    .sort((a, b) => b.startedAt.localeCompare(a.startedAt))
    .map((run) => ({
      id: run.id,
      title: run.title ?? run.workflowId ?? run.id,
      state: toSessionState(run.state),
      meta:
        run.state === "waiting" || run.state === "awaiting-consent"
          ? "approval / consent gate"
          : run.completedAt
            ? `completed · ${run.completedAt.slice(11, 16)}`
            : `started · ${run.startedAt.slice(11, 16)}`,
      workflow: run.workflowId ?? undefined,
    }));
}

function buildProjectedCanvas(
  manifest: PluginManifest,
  run: PluginRun,
  canvas: Record<string, unknown>,
): Record<string, unknown> {
  const next: Record<string, unknown> = {
    ...canvas,
    manifest,
  };

  const anchor = run.anchor?.data ?? {};
  const diagnoses = renderBulletDoc(
    "Diagnoses",
    (anchor["diagnoses.active"] as Array<Record<string, unknown>> | undefined)?.map(
      (row) => String(row.display ?? row.code ?? "Diagnosis"),
    ) ?? [],
  );
  const biomarkers = renderBulletDoc(
    "Biomarkers",
    (anchor["biomarkers"] as Array<Record<string, unknown>> | undefined)?.map(
      (row) =>
        `${String(row.marker ?? "marker")} · ${String(row.status ?? "unknown")}${
          row.lastTested ? ` · ${String(row.lastTested)}` : ""
        }`,
    ) ?? [],
  );
  const geography = anchor["demographics.geography"] ?? {};
  const meds = renderBulletDoc(
    "Active medications",
    (anchor["medications.active"] as Array<Record<string, unknown>> | undefined)?.map(
      (row) => `${String(row.display ?? "Medication")} · ${String(row.dose ?? row.startDate ?? "")}`.trim(),
    ) ?? [],
  );
  const encounters = renderBulletDoc(
    "Recent encounters",
    (anchor["encounters.recent"] as Array<Record<string, unknown>> | undefined)?.map(
      (row) =>
        `${String(row.date ?? "date")} · ${String(row.type ?? "encounter")} · ${String(row.provider ?? "provider")}`,
    ) ?? [],
  );

  if (manifest.id === "trial-finder") {
    next.shortlist = {
      preview: buildTrialShortlist(next["trial.search"], next["trial.score_fit"]),
    };
    next["packet-outline"] = canvas["packet.draft"] ?? {
      preview: "_Run `packet.draft` to create the outreach packet._",
    };
    next["diagnoses.md"] = { preview: diagnoses };
    next["biomarkers.csv"] = { preview: biomarkers };
    next["geography.json"] = geography;
  }

  if (manifest.id === "med-access") {
    next["pa-packet.md"] = canvas["pa.compose"] ?? {
      preview: "_Run `pa.compose` to populate the PA packet._",
    };
    next["barriers.json"] = canvas["med.identify_barriers"] ?? { barriers: [] };
    next["pap-matches.md"] = {
      preview: renderBulletDoc(
        "Manufacturer programs",
        ((canvas["pap.match"] as { matches?: Array<Record<string, unknown>> } | undefined)?.matches ?? []).map(
          (row) =>
            `${String(row.manufacturer ?? "Program")} · ${String(row.drug ?? "")}${
              row.incomeBandMax ? ` · income <= $${String(row.incomeBandMax)}k` : ""
            }`,
        ),
      ),
    };
    next["active-meds.md"] = { preview: meds };
    next["diagnoses.md"] = { preview: diagnoses };
  }

  if (manifest.id === "second-opinion") {
    next["referral-packet.md"] = canvas["referral.compose_packet"] ?? {
      preview: "_Run `referral.compose_packet` to draft the referral packet._",
    };
    next["redaction-preview.md"] = {
      hunks: buildRedactionPreview(
        canvas["referral.compose_packet"],
        canvas["referral.apply_redactions"],
      ),
    };
    next["diagnoses.md"] = { preview: diagnoses };
    next["recent-encounters.md"] = { preview: encounters };
  }

  return next;
}

function buildTabs(
  manifest: PluginManifest,
  canvas: Record<string, unknown>,
): WorkbenchTab[] {
  const tabs = manifest.ui.workbenchTabs.map((tab) => ({
    id: tab.id,
    label: tab.label,
    icon: iconForRenderer(tab.renderer, tab.label),
    kind: tab.kind,
    renderer: tab.renderer,
    dirty: tab.label.endsWith(".md"),
  })) satisfies WorkbenchTab[];

  const artifactTabs = Object.values(canvas)
    .flatMap((payload) => (isArtifactPayload(payload) ? [payload] : []))
    .filter((payload, index, all) =>
      all.findIndex((candidate) => candidate.artifactId === payload.artifactId) === index,
    )
    .map((payload) => ({
      id: String(payload.artifactId),
      label: String(payload.artifactId),
      icon: payload.hunks ? "GitCompare" : "FileText",
      kind: payload.hunks ? "diff" : "packet-outline",
      renderer: payload.hunks ? "diff.unified" : payload.preview ? "markdown.doc" : "json.viewer",
      dirty: true,
    })) satisfies WorkbenchTab[];

  return [...tabs, ...artifactTabs];
}

function buildFileTabs(
  manifest: PluginManifest,
  canvas: Record<string, unknown>,
  tabs: WorkbenchTab[],
): Record<string, WorkbenchTab> {
  const byFileId: Record<string, WorkbenchTab> = {};
  const tabById = new Map(tabs.map((tab) => [tab.id, tab] as const));
  const tabByLabel = new Map(tabs.map((tab) => [tab.label, tab] as const));

  for (const file of manifest.ui.files) {
    const fileId = `file:${file.name}`;
    const tab =
      tabByLabel.get(file.name) ??
      inferFileTab(file.name, canvas, manifest.id) ??
      makeTabFromFileName(file.name);
    byFileId[fileId] = tab;
  }

  const manifestTab =
    tabByLabel.get("manifest.json") ??
    tabById.get("manifest") ??
    makeTabFromFileName("manifest.json");
  byFileId["pkg:manifest"] = manifestTab;

  for (const payload of Object.values(canvas)) {
    if (!isArtifactPayload(payload) || !payload.artifactId) continue;
    const tab = tabById.get(String(payload.artifactId));
    if (tab) byFileId[`artifact:${String(payload.artifactId)}`] = tab;
  }

  return byFileId;
}

function buildFilesTree(
  manifest: PluginManifest,
  canvas: Record<string, unknown>,
  fileTabs: Record<string, WorkbenchTab>,
): FileTreeNode[] {
  const groupFiles = new Map<string, FileNode[]>();

  for (const file of manifest.ui.files) {
    const list = groupFiles.get(file.group) ?? [];
    list.push({
      type: "file",
      id: `file:${file.name}`,
      name: file.name,
      ext: extensionOf(file.name),
      icon: file.icon,
      dirty: file.dirty,
    });
    groupFiles.set(file.group, list);
  }

  const dynamicArtifacts = Object.values(canvas)
    .flatMap((payload) => (isArtifactPayload(payload) ? [payload] : []))
    .filter((payload) => payload.artifactId)
    .map((payload) => ({
      type: "file" as const,
      id: `artifact:${String(payload.artifactId)}`,
      name: `${String(payload.artifactId)}${payload.preview ? ".md" : ".json"}`,
      ext: payload.preview ? "md" : "json",
      icon: payload.hunks ? "GitCompare" : payload.preview ? "FileText" : "Braces",
      dirty: true,
    }));

  const folders: FileTreeNode[] = [
    { type: "group", label: "Run workspace" },
  ];

  for (const [group, files] of groupFiles.entries()) {
    folders.push({
      type: "folder",
      name: group,
      expanded: true,
      children: files,
    });
  }

  folders.push({
    type: "folder",
    name: "package",
    expanded: false,
    children: [
      {
        type: "file",
        id: "pkg:manifest",
        name: "manifest.json",
        ext: "json",
        icon: "Braces",
      },
    ],
  });

  if (dynamicArtifacts.length > 0) {
    folders.push({
      type: "folder",
      name: "run-artifacts",
      expanded: true,
      children: dynamicArtifacts,
    });
  }

  if (manifest.id === "trial-finder") {
    folders.push({ type: "group", label: "Pinned" });
    folders.push({ type: "ref", id: "trial.search", label: "tool:trial.search", sub: "Candidate board" });
  }

  return folders.filter((node) => {
    if (node.type !== "folder") return true;
    return node.children.some((file) => fileTabs[file.id]);
  });
}

function inferFileTab(
  fileName: string,
  canvas: Record<string, unknown>,
  pluginId: PluginManifest["id"],
): WorkbenchTab | null {
  if (pluginId === "trial-finder") {
    if (fileName === "candidate-board.json") {
      return {
        id: "candidate-board",
        label: "Candidate board",
        icon: "Beaker",
        kind: "trial-board",
        renderer: "trial.board",
      };
    }
    if (fileName === "packet-outline.md") {
      return {
        id: "packet-outline",
        label: "packet-outline.md",
        icon: "FileText",
        kind: "packet-outline",
        renderer: "markdown.doc",
      };
    }
  }
  if (pluginId === "med-access") {
    if (fileName === "barriers.json") {
      return {
        id: "barriers",
        label: "Barriers",
        icon: "Braces",
        kind: "barriers-list",
        renderer: "list.barriers",
      };
    }
    if (fileName === "pa-packet.md") {
      return {
        id: "pa-form",
        label: "PA form preview",
        icon: "FileText",
        kind: "pa-form",
        renderer: "form.pa",
        dirty: true,
      };
    }
    if (fileName === "pap-matches.md") {
      return {
        id: "pap-matches.md",
        label: "pap-matches.md",
        icon: "FileText",
        kind: "packet-outline",
        renderer: "markdown.doc",
      };
    }
  }
  if (pluginId === "second-opinion") {
    if (fileName === "referral-packet.md") {
      return {
        id: "packet",
        label: "Referral packet",
        icon: "FileText",
        kind: "referral-packet",
        renderer: "packet.referral",
        dirty: true,
      };
    }
    if (fileName === "redaction-preview.md") {
      return {
        id: "redaction-preview.md",
        label: "redaction-preview.md",
        icon: "GitCompare",
        kind: "diff",
        renderer: "diff.unified",
      };
    }
  }

  const payload = canvas[fileName];
  if (!payload) return null;
  return makeTabFromFileName(fileName);
}

function makeTabFromFileName(fileName: string): WorkbenchTab {
  const ext = extensionOf(fileName);
  if (ext === "json") {
    return {
      id: fileName,
      label: fileName,
      icon: "Braces",
      kind: "manifest-json",
      renderer: "json.viewer",
    };
  }
  if (fileName.includes("diff") || fileName.includes("redaction-preview")) {
    return {
      id: fileName,
      label: fileName,
      icon: "GitCompare",
      kind: "diff",
      renderer: "diff.unified",
    };
  }
  return {
    id: fileName,
    label: fileName,
    icon: "FileText",
    kind: "packet-outline",
    renderer: "markdown.doc",
  };
}

function renderBulletDoc(title: string, lines: string[]): string {
  return [`# ${title}`, "", ...(lines.length > 0 ? lines.map((line) => `- ${line}`) : ["- No data in scope yet."])].join("\n");
}

function buildTrialShortlist(search: unknown, score: unknown): string {
  const studies = ((search as { studies?: Array<Record<string, unknown>> } | undefined)?.studies ?? []).slice(0, 5);
  const fit = (score as { nctId?: string; fit?: number } | undefined) ?? {};
  const body = studies.map((study) => {
    const isScored = fit.nctId === study.nctId && typeof fit.fit === "number";
    return `- ${String(study.nctId ?? "NCT")} · ${String(study.title ?? "")}${
      isScored ? ` · fit ${(fit.fit ?? 0).toFixed(2)}` : ""
    }`;
  });
  return renderBulletDoc("Ranked shortlist", body);
}

function buildRedactionPreview(compose: unknown, redactions: unknown): string {
  const preview = (compose as { preview?: string } | undefined)?.preview;
  const summary = (redactions as { summary?: string } | undefined)?.summary;
  if (!preview) {
    return ["--- referral-packet.md", "+++ redaction-preview.md", "@@", "- No referral packet drafted yet.", "+ Run referral.compose_packet first."].join("\n");
  }
  return [
    "--- referral-packet.md",
    "+++ redaction-preview.md",
    "@@",
    `- ${preview.split("\n")[0] ?? "# Referral packet"}`,
    `+ ${summary ?? "Applied configured redaction preset."}`,
  ].join("\n");
}

function isArtifactPayload(value: unknown): value is {
  artifactId?: string;
  preview?: string;
  hunks?: string;
} {
  return Boolean(value) && typeof value === "object" && (
    "artifactId" in (value as Record<string, unknown>) ||
    "preview" in (value as Record<string, unknown>) ||
    "hunks" in (value as Record<string, unknown>)
  );
}

function latestTimestamp(events: RunEvent[]): string {
  const latest = events.at(-1)?.ts;
  return latest ? latest.slice(11, 16) : "—";
}

function summarizeCurrentStep(
  run: PluginRun,
  events: RunEvent[],
  approvals: PluginApprovalRow[],
): string {
  if (run.state === "awaiting-consent") return "consent required";
  const pending = approvals.find((approval) => approval.status === "pending");
  if (pending) return `approval · ${pending.action}`;
  const latestTool = [...events].reverse().find((event) => event.kind === "tool.result");
  if (latestTool) {
    return `tool · ${String((latestTool.payload as { toolId?: string }).toolId ?? "result")}`;
  }
  return run.workflowId ?? run.state;
}

function toWorkspaceRunState(state: PluginRun["state"]): Workspace["runState"] {
  if (state === "running") return "running";
  if (state === "waiting" || state === "awaiting-consent") return "waiting";
  if (state === "complete") return "complete";
  return "idle";
}

function toSessionState(state: PluginRun["state"]): Session["state"] {
  if (state === "running") return "running";
  if (state === "waiting" || state === "awaiting-consent") return "needs";
  if (state === "complete") return "done";
  return "draft";
}

function formatElapsed(startedAt: string, completedAt: string | null): string {
  const start = Date.parse(startedAt);
  const end = completedAt ? Date.parse(completedAt) : Date.now();
  if (Number.isNaN(start) || Number.isNaN(end) || end <= start) return "0m";
  const minutes = Math.max(1, Math.round((end - start) / 60_000));
  if (minutes < 60) return `${minutes}m`;
  const hours = Math.floor(minutes / 60);
  const rem = minutes % 60;
  return rem === 0 ? `${hours}h` : `${hours}h ${rem}m`;
}

function extensionOf(fileName: string): string {
  const raw = fileName.split(".").pop();
  return raw ?? "txt";
}

function iconForRenderer(
  renderer: PluginManifest["ui"]["workbenchTabs"][number]["renderer"],
  label: string,
): WorkbenchTab["icon"] {
  if (renderer === "trial.board" || renderer === "list.barriers") return "Beaker";
  if (renderer === "json.viewer") return "Braces";
  if (renderer === "diff.unified") return "GitCompare";
  if (label.endsWith(".json")) return "Braces";
  return "FileText";
}
