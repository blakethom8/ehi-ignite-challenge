// Atlas Agentic Workspaces — seed data fixtures
// Mirrors .claude/handoff/atlas/prototype/data.js

import type { Workspace, WorkspaceId } from "./types";

export const WORKSPACES: Record<WorkspaceId, Workspace> = {
  "caspian": {
    id: "caspian",
    family: "clinical",
    title: "Caspian",
    subtitle: "First-party clinical workspace",
    icon: "Stethoscope",
    color: "#1d4ed8",
    tint: "rgba(29, 78, 216, 0.10)",
    boundary: "Private patient boundary",
    boundaryTone: "ok",
  },
  "trial-finder": {
    id: "trial-finder",
    family: "plugin",
    title: "Trial Finder",
    subtitle: "Plugin",
    icon: "Telescope",
    color: "#4338ca",
    tint: "rgba(67, 56, 202, 0.10)",
    boundary: "Consented external · registry lookup",
    boundaryTone: "warn",
    vendor: "Helix Clinical",
    version: "2.4.1",
    permissions: ["read patient anchors", "external registry", "outbound packet"],
    runState: "running",
    runStep: "8 of 14",
    runElapsed: "4m 12s",
    lastRefresh: "11:54",
    anchoredFrom: "Caspian · Hollister",
  },
  "med-access": {
    id: "med-access",
    family: "plugin",
    title: "Medication Access",
    subtitle: "Plugin",
    icon: "Pill",
    color: "#0f766e",
    tint: "rgba(15, 118, 110, 0.10)",
    boundary: "Consented external · assistance program",
    boundaryTone: "warn",
    vendor: "RxBridge",
    version: "1.7.0",
    permissions: ["read medications", "external program", "outbound packet"],
    runState: "idle",
    runStep: "—",
    runElapsed: "0s",
    lastRefresh: "—",
    anchoredFrom: "Caspian · Hollister",
  },
  "site-coord": {
    id: "site-coord",
    family: "plugin",
    title: "Site Coordination",
    subtitle: "Plugin",
    icon: "Send",
    color: "#475569",
    tint: "rgba(71, 85, 105, 0.10)",
    boundary: "Consented external · scheduled batch",
    boundaryTone: "warn",
    vendor: "TrialOps",
    version: "0.9.3-beta",
    permissions: ["read appointments", "external sites", "scheduled outreach"],
    runState: "idle",
    runStep: "—",
    runElapsed: "0s",
    lastRefresh: "—",
    anchoredFrom: "Caspian · Hollister",
  },
};

export const PATIENT = {
  name: "M. Hollister",
  mrn: "MRN 8.4127.881",
  ageSex: "68 F",
  tier: "Complex · Tier C",
  fhirCount: "1,184 resources",
  encounters: 47,
};

export type SessionState = "running" | "needs" | "done" | "draft";

export type Session = {
  id: string;
  title: string;
  state: SessionState;
  meta: string;
  workflow?: string;
};

export const SESSIONS: Record<WorkspaceId, Session[]> = {
  "caspian": [
    { id: "s1", title: "Pre-op clearance — Hollister", state: "running", meta: "in progress", workflow: "preop" },
    { id: "s2", title: "Medication safety review", state: "needs", meta: "1 approval pending", workflow: "medsafety" },
    { id: "s3", title: "Longitudinal synthesis", state: "done", meta: "saved · 4h ago" },
    { id: "s4", title: "Specialist briefing — cardiology", state: "draft", meta: "draft only" },
    { id: "s5", title: "ER discharge follow-up", state: "done", meta: "yesterday" },
  ],
  "trial-finder": [
    { id: "t1", title: "Trial shortlist — Hollister", state: "running", meta: "candidate review · 8 of 14", workflow: "shortlist" },
    { id: "t2", title: "Outreach packet — NCT-0421187", state: "needs", meta: "1 approval before send" },
    { id: "t3", title: "Eligibility check batch", state: "done", meta: "2 days ago" },
  ],
  "med-access": [
    { id: "m1", title: "Apixaban PA — Hollister", state: "needs", meta: "manufacturer reply pending" },
  ],
  "site-coord": [
    { id: "c1", title: "MSKCC follow-up loop", state: "draft", meta: "drafted · review queue" },
  ],
};

export type Workflow = {
  id: string;
  title: string;
  desc: string;
  tags: string[];
};

export const WORKFLOWS: Record<WorkspaceId, Workflow[]> = {
  "caspian": [
    { id: "preop", title: "Run pre-op review", desc: "Surfaces medication holds, anesthesia notes, recent labs, and clearance recommendation.", tags: ["pre-surgery", "evidence-grounded"] },
    { id: "medsafety", title: "Medication safety audit", desc: "Interactions, contraindications, dosing against renal function and active conditions.", tags: ["safety"] },
    { id: "longi", title: "Longitudinal synthesis", desc: "Multi-year condition trajectory across encounters.", tags: ["narrative"] },
    { id: "brief", title: "Specialist briefing packet", desc: "Compact handoff artifact for an outside specialist.", tags: ["export"] },
  ],
  "trial-finder": [
    { id: "shortlist", title: "Shortlist candidate trials", desc: "Search registries against the patient anchors and rank likely fits.", tags: ["external"] },
    { id: "review", title: "Review eligibility fit", desc: "Compare inclusion/exclusion against shortlist.", tags: ["review"] },
    { id: "packet", title: "Draft outreach packet", desc: "Prepare reusable artifact for site contact.", tags: ["export"] },
  ],
  "med-access": [
    { id: "pa", title: "File prior authorization", desc: "Compile the PA packet for a chosen medication and submit to the payer portal.", tags: ["external"] },
    { id: "pap", title: "Enroll patient assistance", desc: "Identify the right manufacturer assistance program and prepare the application.", tags: ["external"] },
  ],
  "site-coord": [
    { id: "followup", title: "Run follow-up loop", desc: "Confirm appointments, nudge for missing records, surface eligibility re-checks.", tags: ["scheduled"] },
  ],
};

export type FileTreeNode =
  | { type: "group"; label: string }
  | {
      type: "folder";
      name: string;
      expanded?: boolean;
      children: FileNode[];
    }
  | { type: "ref"; id: string; label: string; sub: string };

export type FileNode = {
  type: "file";
  name: string;
  id: string;
  ext: string;
  icon: string;
  dirty?: boolean;
};

export const FILE_TREES: Record<WorkspaceId, FileTreeNode[]> = {
  "caspian": [
    { type: "group", label: "Patient workspace" },
    {
      type: "folder",
      name: "context",
      expanded: true,
      children: [
        { type: "file", name: "pre-op-brief.md", id: "f_brief", ext: "md", icon: "FileText" },
        { type: "file", name: "anticoagulation-note.txt", id: "f_anticoag", ext: "txt", icon: "FileText" },
        { type: "file", name: "recent-labs.csv", id: "f_labs", ext: "csv", icon: "FileSpreadsheet" },
        { type: "file", name: "operative-history.md", id: "f_history", ext: "md", icon: "FileText" },
      ],
    },
    {
      type: "folder",
      name: "artifacts",
      expanded: true,
      children: [
        { type: "file", name: "pre-op-packet-v2.md", id: "f_packetv2", ext: "md", icon: "FileText", dirty: true },
        { type: "file", name: "pre-op-packet-v1.md", id: "f_packetv1", ext: "md", icon: "FileText" },
        { type: "file", name: "clearance-summary.json", id: "f_summary", ext: "json", icon: "Braces" },
      ],
    },
    {
      type: "folder",
      name: "workflow",
      expanded: false,
      children: [
        { type: "file", name: "workflow.md", id: "f_workflow", ext: "md", icon: "FileText" },
        { type: "file", name: "settings.json", id: "f_settings", ext: "json", icon: "Braces" },
      ],
    },
    { type: "group", label: "Pinned objects" },
    { type: "ref", id: "c_1042", label: "citation:c_1042", sub: "Apixaban hold guidance" },
    { type: "ref", id: "c_1078", label: "citation:c_1078", sub: "Recent CBC · 2025-04-22" },
    { type: "ref", id: "task_anticoag", label: "task:approval-anticoag", sub: "1 unresolved approval" },
  ],
  "trial-finder": [
    { type: "group", label: "Package workspace" },
    {
      type: "folder",
      name: "working",
      expanded: true,
      children: [
        { type: "file", name: "ranked-shortlist.md", id: "f_shortlist", ext: "md", icon: "FileText", dirty: true },
        { type: "file", name: "candidate-board.json", id: "f_board", ext: "json", icon: "Braces" },
        { type: "file", name: "packet-outline.md", id: "f_packet", ext: "md", icon: "FileText" },
      ],
    },
    {
      type: "folder",
      name: "patient-anchors",
      expanded: true,
      children: [
        { type: "file", name: "diagnoses.md", id: "f_dx", ext: "md", icon: "FileText" },
        { type: "file", name: "biomarkers.csv", id: "f_bio", ext: "csv", icon: "FileSpreadsheet" },
        { type: "file", name: "geography.json", id: "f_geo", ext: "json", icon: "Braces" },
      ],
    },
    {
      type: "folder",
      name: "package",
      expanded: false,
      children: [
        { type: "file", name: "manifest.json", id: "f_manifest", ext: "json", icon: "Braces" },
        { type: "file", name: "trial-finder.json", id: "f_pkg", ext: "json", icon: "Braces" },
      ],
    },
    { type: "group", label: "Pinned" },
    { type: "ref", id: "trial_0421187", label: "trial:NCT-0421187", sub: "High clinical fit" },
    { type: "ref", id: "trial_0387714", label: "trial:NCT-0387714", sub: "Pending biomarker" },
  ],
  "med-access": [
    { type: "group", label: "Package workspace" },
    {
      type: "folder",
      name: "working",
      expanded: true,
      children: [
        { type: "file", name: "pa-packet.md", id: "f_pa", ext: "md", icon: "FileText", dirty: true },
      ],
    },
    {
      type: "folder",
      name: "package",
      expanded: false,
      children: [
        { type: "file", name: "manifest.json", id: "f_manifest", ext: "json", icon: "Braces" },
      ],
    },
  ],
  "site-coord": [
    { type: "group", label: "Package workspace" },
    {
      type: "folder",
      name: "working",
      expanded: true,
      children: [
        { type: "file", name: "outreach-template.md", id: "f_template", ext: "md", icon: "FileText" },
      ],
    },
    {
      type: "folder",
      name: "package",
      expanded: false,
      children: [
        { type: "file", name: "manifest.json", id: "f_manifest", ext: "json", icon: "Braces" },
      ],
    },
  ],
};

export type Citation = {
  id: string;
  type: string;
  title: string;
  snippet: string;
  source: string;
  encounter: string;
  author: string;
  date: string;
  related: { id: string; text: string }[];
};

export const CITATIONS: Record<string, Citation> = {
  c_1042: {
    id: "c_1042",
    type: "FHIR · MedicationStatement",
    title: "Apixaban 5 mg BID",
    snippet:
      "Active since 2023-06-14. Indication: atrial fibrillation. Last refilled 2025-04-02. Surgical hold guidance per institutional protocol: hold ≥48 h pre-op for moderate-bleed-risk procedures, ≥72 h for high-bleed-risk.",
    source: "MedicationStatement/med-8841",
    encounter: "Enc/2025-04-02",
    author: "Patel, A. (PharmD)",
    date: "2023-06-14",
    related: [
      { id: "c_1078", text: "Recent CBC · 2025-04-22" },
      { id: "c_1091", text: "INR pending — order placed" },
      { id: "c_1094", text: "Operative note — moderate-bleed-risk" },
    ],
  },
  c_1078: {
    id: "c_1078",
    type: "FHIR · Observation (CBC)",
    title: "Complete blood count — 2025-04-22",
    snippet:
      "Hgb 12.4 g/dL · WBC 6.8 × 10^9/L · Platelets 218 × 10^9/L. Within acceptable preoperative range. No active bleeding signs.",
    source: "Observation/obs-21477",
    encounter: "Enc/2025-04-22",
    author: "Lab 7720",
    date: "2025-04-22",
    related: [
      { id: "c_1091", text: "INR pending — order placed" },
      { id: "c_1042", text: "Apixaban 5 mg BID" },
    ],
  },
  c_1091: {
    id: "c_1091",
    type: "FHIR · ServiceRequest",
    title: "INR — order pending",
    snippet:
      "INR repeat ordered 2025-05-06 in anticipation of OR date 2025-05-12. No result yet. Surgical team to confirm value < 1.4 before clearance.",
    source: "ServiceRequest/req-9981",
    encounter: "Enc/2025-05-06",
    author: "Hernandez, M. (MD)",
    date: "2025-05-06",
    related: [{ id: "c_1078", text: "Recent CBC · 2025-04-22" }],
  },
  c_1094: {
    id: "c_1094",
    type: "FHIR · DocumentReference",
    title: "Operative note — scheduled procedure",
    snippet:
      "Scheduled: open inguinal hernia repair (CPT 49505). Estimated blood loss moderate. Anesthesia consult cleared 2025-04-18. No prior airway complication on file.",
    source: "DocumentReference/doc-44012",
    encounter: "Enc/2025-04-18",
    author: "Chen, R. (MD)",
    date: "2025-04-18",
    related: [{ id: "c_1042", text: "Apixaban 5 mg BID" }],
  },
};

// ----- chat seed -----

export type ChatBlock = string;

export type ChatTrace = { tool: string; target: string };

export type ChatApproval = { body: string; primary: string; secondary: string };

export type ChatAction = { label: string; icon: string; target: string };

export type ChatMessage =
  | {
      id: string;
      role: "user";
      content: string;
    }
  | {
      id: string;
      role: "assistant";
      time?: string;
      trace?: ChatTrace;
      blocks: ChatBlock[];
      approval?: ChatApproval;
      actions?: ChatAction[];
    };

export const INITIAL_CHAT: Record<WorkspaceId, ChatMessage[]> = {
  "caspian": [
    {
      id: "u1",
      role: "user",
      content:
        "Open M. Hollister's chart. She's on the OR schedule for 5/12 for an inguinal hernia repair. Where do we stand on pre-op?",
    },
    {
      id: "a1",
      role: "assistant",
      time: "11:42",
      trace: { tool: "fhir.search", target: "MedicationStatement?patient=8.4127.881&status=active" },
      blocks: [
        "Hollister, 68F, scheduled 2025-05-12 for open inguinal hernia repair (CPT 49505). Active list confirms chronic atrial fibrillation on apixaban 5 mg BID [c_1042]. Bleed risk for the planned procedure is moderate.",
        "I have drafted a clearance briefing in [pre-op-packet-v2.md]. The disposition is REVIEW — the apixaban hold interval needs explicit attending sign-off and we are still waiting on the repeat INR [c_1091].",
      ],
      actions: [
        { label: "Open packet", icon: "FileText", target: "open-packet" },
        { label: "View anticoag note", icon: "FileText", target: "open-anticoag" },
        { label: "Cite c_1042 in inspector", icon: "Quote", target: "cite-c_1042" },
      ],
    },
    {
      id: "u2",
      role: "user",
      content: "What's the recommended hold for the apixaban — and is bridging needed?",
    },
    {
      id: "a2",
      role: "assistant",
      time: "11:43",
      blocks: [
        "Per institutional protocol and the patient's profile: hold apixaban ≥ 48 h before incision and restart 24 h after hemostasis is confirmed [c_1042]. Bridging with LMWH is not indicated — CHA2DS2-VASc is 3 and there is no mechanical valve history on the chart.",
        "Hematologic baseline is acceptable: Hgb 12.4 g/dL and platelets 218 × 10⁹/L on 2025-04-22 [c_1078]. The repeat INR is pending — surgical team to confirm < 1.4 morning-of [c_1091].",
      ],
      approval: {
        body: "Apply the apixaban 48 h pre-op hold and mark the packet ready for attending review? This is a controlled action and will be logged.",
        primary: "Approve hold",
        secondary: "Hold for attending",
      },
    },
  ],
  "trial-finder": [
    {
      id: "u1",
      role: "user",
      content:
        "Run a trial shortlist for Hollister. She's stable post-CML diagnosis, BCR-ABL+, prior imatinib intolerance. Caregiver radius 50 mi from home.",
    },
    {
      id: "a1",
      role: "assistant",
      time: "12:08",
      trace: { tool: "marketplace.run", target: "trial-finder@2.4.1 / shortlist" },
      blocks: [
        "Pulled patient anchors from the Caspian workspace under a consented, read-only handle. No patient identifiers leave this run [manifest.json]. Searching ClinicalTrials.gov against: chronic myeloid leukemia, BCR-ABL+, post-imatinib intolerance, ECOG 1, 50 mi radius.",
        "14 candidates returned. Ranking by clinical fit × operational fit × consent posture. Top three are queued in [ranked-shortlist.md] and the full board is open in the Workbench.",
      ],
      actions: [
        { label: "Open candidate board", icon: "Beaker", target: "open-board" },
        { label: "Open shortlist", icon: "FileText", target: "open-shortlist" },
        { label: "Inspect package manifest", icon: "Boxes", target: "open-manifest" },
      ],
    },
    {
      id: "u2",
      role: "user",
      content: "Walk me through NCT-0421187 first — and what would need approval before we reach out to the site?",
    },
    {
      id: "a2",
      role: "assistant",
      time: "12:10",
      blocks: [
        "NCT-0421187 is a Phase III ABL-tyrosine kinase inhibitor trial for post-imatinib intolerance patients at MSKCC. Clinical fit is 0.92 — biomarker, line of therapy, and performance status all match. Travel is ~38 mi; caregiver support is documented.",
        "Outreach is gated. Before I draft and send the outreach packet I will request a single approval card in this thread covering: (1) explicit consent to contact an external registry on the patient's behalf, and (2) the de-identification preset to apply.",
      ],
      approval: {
        body: "Draft the outreach packet for NCT-0421187 under preset de-id-v3, ready to send pending consent confirmation. Nothing leaves the workspace until the consent step is signed.",
        primary: "Draft packet",
        secondary: "Review consent first",
      },
    },
  ],
  "med-access": [],
  "site-coord": [],
};

export type WorkbenchTab = {
  id: string;
  label: string;
  icon: string;
  kind:
    | "preop-brief"
    | "anticoag-note"
    | "summary-json"
    | "diff"
    | "trial-board"
    | "packet-outline"
    | "manifest-json";
  dirty?: boolean;
};

export const INITIAL_TABS: Record<WorkspaceId, WorkbenchTab[]> = {
  "caspian": [
    { id: "tab_brief", label: "pre-op-packet-v2.md", icon: "FileText", kind: "preop-brief", dirty: true },
    { id: "tab_diff", label: "v1 → v2 diff", icon: "GitCompare", kind: "diff" },
    { id: "tab_sum", label: "clearance-summary.json", icon: "Braces", kind: "summary-json" },
  ],
  "trial-finder": [
    { id: "tab_board", label: "candidate-board.json", icon: "Beaker", kind: "trial-board" },
    { id: "tab_short", label: "ranked-shortlist.md", icon: "FileText", kind: "packet-outline", dirty: true },
    { id: "tab_man", label: "manifest.json", icon: "Braces", kind: "manifest-json" },
  ],
  "med-access": [],
  "site-coord": [],
};

export const FILE_TO_TAB: Record<string, WorkbenchTab> = {
  f_brief: { id: "tab_brief", label: "pre-op-packet-v2.md", icon: "FileText", kind: "preop-brief", dirty: true },
  f_packetv2: { id: "tab_brief", label: "pre-op-packet-v2.md", icon: "FileText", kind: "preop-brief", dirty: true },
  f_packetv1: { id: "tab_diff", label: "v1 → v2 diff", icon: "GitCompare", kind: "diff" },
  f_anticoag: { id: "tab_anti", label: "anticoagulation-note.txt", icon: "FileText", kind: "anticoag-note" },
  f_summary: { id: "tab_sum", label: "clearance-summary.json", icon: "Braces", kind: "summary-json" },
  f_board: { id: "tab_board", label: "candidate-board.json", icon: "Beaker", kind: "trial-board" },
  f_shortlist: { id: "tab_short", label: "ranked-shortlist.md", icon: "FileText", kind: "packet-outline", dirty: true },
  f_packet: { id: "tab_short", label: "ranked-shortlist.md", icon: "FileText", kind: "packet-outline", dirty: true },
  f_manifest: { id: "tab_man", label: "manifest.json", icon: "Braces", kind: "manifest-json" },
  f_pkg: { id: "tab_man", label: "manifest.json", icon: "Braces", kind: "manifest-json" },
};

export const ACTION_TO_TAB: Record<string, WorkbenchTab> = {
  "open-packet": FILE_TO_TAB.f_brief,
  "open-anticoag": FILE_TO_TAB.f_anticoag,
  "open-board": FILE_TO_TAB.f_board,
  "open-shortlist": FILE_TO_TAB.f_shortlist,
  "open-manifest": FILE_TO_TAB.f_manifest,
};
