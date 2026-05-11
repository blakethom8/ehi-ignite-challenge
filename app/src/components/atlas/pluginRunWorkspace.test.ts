import { describe, expect, it } from "vitest";
import type { PluginRun } from "../../api/plugins";
import type { PluginManifest } from "./trust";
import { buildPluginRunWorkspaceSurface } from "./pluginRunWorkspace";

const manifest: PluginManifest = {
  schemaVersion: "1.0.0",
  id: "trial-finder",
  version: "2.4.1",
  vendor: {
    id: "vendor-1",
    name: "Helix Clinical",
    keyFingerprint: "fp-demo",
  },
  displayName: "Trial Finder",
  subtitle: "Plugin",
  description: "Test manifest",
  icon: "Telescope",
  color: "#4338ca",
  trust: {
    posture: "consented-external",
    boundaryLabel: "Consented external · registry lookup",
    requiresPerRunConsent: true,
  },
  anchor: {
    scope: ["diagnoses.active", "biomarkers", "demographics.geography"],
    redactionPreset: "de-id-v3",
    ttlSeconds: 3600,
  },
  connectors: [],
  permissions: [{ kind: "read-anchor", scope: ["diagnoses.active", "biomarkers", "demographics.geography"] }],
  workflows: [],
  tools: [],
  ui: {
    homeSections: ["hero"],
    workbenchTabs: [
      { id: "candidate-board", label: "Candidate board", kind: "trial-board", renderer: "trial.board" },
      { id: "shortlist", label: "ranked-shortlist.md", kind: "packet-outline", renderer: "markdown.doc" },
      { id: "manifest", label: "manifest.json", kind: "manifest-json", renderer: "json.viewer" },
    ],
    files: [
      { group: "working", name: "ranked-shortlist.md", icon: "FileText", dirty: true },
      { group: "working", name: "packet-outline.md", icon: "FileText" },
      { group: "anchors", name: "diagnoses.md", icon: "FileText" },
      { group: "anchors", name: "biomarkers.csv", icon: "FileSpreadsheet" },
      { group: "anchors", name: "geography.json", icon: "Braces" },
    ],
    agent: {
      avatarInitials: "Tf",
      avatarColor: "var(--mod-trials)",
      modelPreset: "marketplace-act",
    },
  },
  exports: ["markdown"],
  signature: "sig-demo",
};

const run: PluginRun = {
  id: "r_live123",
  pluginId: "trial-finder",
  pluginVersion: "2.4.1",
  patientId: "8.4127.881",
  state: "running",
  workflowId: "shortlist",
  title: "Trial shortlist",
  startedBy: { id: "u_1", name: "Dr. Q", role: "clinician" },
  startedAt: "2026-05-10T19:45:00Z",
  completedAt: null,
  anchor: {
    schemaVersion: "1.0.0",
    pluginId: "trial-finder",
    pluginVersion: "2.4.1",
    patientId: "8.4127.881",
    runId: "r_live123",
    issuedAt: "2026-05-10T19:45:00Z",
    expiresAt: "2026-05-10T20:45:00Z",
    redactionPreset: "de-id-v3",
    scope: ["diagnoses.active", "biomarkers", "demographics.geography"],
    data: {
      "diagnoses.active": [{ display: "Chronic myeloid leukemia" }],
      biomarkers: [{ marker: "BCR-ABL1", status: "positive", lastTested: "2026-04-22" }],
      "demographics.geography": { city: "San Francisco", state: "CA" },
    },
    signature: "sig-demo",
  },
  canvas: {},
};

describe("buildPluginRunWorkspaceSurface", () => {
  it("projects live plugin run artifacts, files, and workspace state into the shared shell contract", () => {
    const surface = buildPluginRunWorkspaceSurface({
      manifest,
      run,
      runs: [run],
      events: [
        {
          id: "evt_1",
          runId: run.id,
          ts: "2026-05-10T19:46:00Z",
          kind: "tool.result",
          payload: {
            toolId: "trial.search",
            result: {
              studies: [{ nctId: "NCT-0421187", title: "Phase III CML", phase: "III", site: "MSKCC", distanceMi: 38, fit: 0.92, biomarkerMatch: true }],
            },
          },
        },
      ],
      approvals: [],
      canvas: {
        "trial.search": {
          studies: [{ nctId: "NCT-0421187", title: "Phase III CML", phase: "III", site: "MSKCC", distanceMi: 38, fit: 0.92, biomarkerMatch: true }],
        },
        "packet.draft": {
          artifactId: "outreach-packet-NCT-0421187",
          preview: "# Outreach packet\n\nDraft body",
        },
      },
    });

    expect(surface.workspace.runState).toBe("running");
    expect(surface.workspace.runStep).toContain("trial.search");
    expect(surface.tabs.some((tab) => tab.id === "outreach-packet-NCT-0421187")).toBe(true);
    expect(surface.fileTabs["artifact:outreach-packet-NCT-0421187"]?.id).toBe("outreach-packet-NCT-0421187");
    expect(surface.filesTree.some((node) => node.type === "folder" && node.name === "run-artifacts")).toBe(true);
    expect((surface.canvas.shortlist as { preview: string }).preview).toContain("NCT-0421187");
    expect((surface.canvas["diagnoses.md"] as { preview: string }).preview).toContain("Chronic myeloid leukemia");
  });
});
