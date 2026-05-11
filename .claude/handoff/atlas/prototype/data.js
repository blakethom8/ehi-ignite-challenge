// Atlas Agentic Shell — data fixtures

const WORKSPACES = {
  "clinical-insights": {
    id: "clinical-insights",
    family: "clinical",
    title: "Caspian",
    subtitle: "First-party clinical workspace",
    icon: "Stethoscope",
    productLine: "Clinical Insights",
    version: "internal",
    color: "#1d4ed8",
    tint: "rgba(29, 78, 216, 0.10)",
    boundary: "Private patient boundary",
    boundaryTone: "ok",
  },
  "trial-finder": {
    id: "trial-finder",
    family: "marketplace",
    title: "Trial Finder",
    subtitle: "Marketplace workspace package",
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
};

const PATIENT = {
  name: "M. Hollister",
  mrn: "MRN 8.4127.881",
  ageSex: "68 F",
  tier: "Complex · Tier C",
  fhirCount: "1,184 resources",
  encounters: 47,
};

const SESSIONS = {
  "clinical-insights": [
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
};

const WORKFLOWS = {
  "clinical-insights": [
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
};

// Files trees per workspace
const FILE_TREES = {
  "clinical-insights": [
    { type: "group", label: "Patient workspace" },
    { type: "folder", name: "context", expanded: true, children: [
      { type: "file", name: "pre-op-brief.md", id: "f_brief", ext: "md", icon: "FileText" },
      { type: "file", name: "anticoagulation-note.txt", id: "f_anticoag", ext: "txt", icon: "FileText" },
      { type: "file", name: "recent-labs.csv", id: "f_labs", ext: "csv", icon: "FileSpreadsheet" },
      { type: "file", name: "operative-history.md", id: "f_history", ext: "md", icon: "FileText" },
    ]},
    { type: "folder", name: "artifacts", expanded: true, children: [
      { type: "file", name: "pre-op-packet-v2.md", id: "f_packetv2", ext: "md", icon: "FileText", dirty: true },
      { type: "file", name: "pre-op-packet-v1.md", id: "f_packetv1", ext: "md", icon: "FileText" },
      { type: "file", name: "clearance-summary.json", id: "f_summary", ext: "json", icon: "Braces" },
    ]},
    { type: "folder", name: "workflow", expanded: false, children: [
      { type: "file", name: "workflow.md", id: "f_workflow", ext: "md", icon: "FileText" },
      { type: "file", name: "settings.json", id: "f_settings", ext: "json", icon: "Braces" },
    ]},
    { type: "group", label: "Pinned objects" },
    { type: "ref", id: "c_1042", label: "citation:c_1042", sub: "Apixaban hold guidance" },
    { type: "ref", id: "c_1078", label: "citation:c_1078", sub: "Recent CBC · 2025-04-22" },
    { type: "ref", id: "task_anticoag", label: "task:approval-anticoag", sub: "1 unresolved approval" },
  ],
  "trial-finder": [
    { type: "group", label: "Package workspace" },
    { type: "folder", name: "working", expanded: true, children: [
      { type: "file", name: "ranked-shortlist.md", id: "f_shortlist", ext: "md", icon: "FileText", dirty: true },
      { type: "file", name: "candidate-board.json", id: "f_board", ext: "json", icon: "Braces" },
      { type: "file", name: "packet-outline.md", id: "f_packet", ext: "md", icon: "FileText" },
    ]},
    { type: "folder", name: "patient-anchors", expanded: true, children: [
      { type: "file", name: "diagnoses.md", id: "f_dx", ext: "md", icon: "FileText" },
      { type: "file", name: "biomarkers.csv", id: "f_bio", ext: "csv", icon: "FileSpreadsheet" },
      { type: "file", name: "geography.json", id: "f_geo", ext: "json", icon: "Braces" },
    ]},
    { type: "folder", name: "package", expanded: false, children: [
      { type: "file", name: "manifest.json", id: "f_manifest", ext: "json", icon: "Braces" },
      { type: "file", name: "trial-finder.json", id: "f_pkg", ext: "json", icon: "Braces" },
    ]},
    { type: "group", label: "Pinned" },
    { type: "ref", id: "trial_0421187", label: "trial:NCT-0421187", sub: "High clinical fit" },
    { type: "ref", id: "trial_0387714", label: "trial:NCT-0387714", sub: "Pending biomarker" },
  ],
};

// Citations corpus
const CITATIONS = {
  c_1042: {
    id: "c_1042",
    type: "FHIR · MedicationStatement",
    title: "Apixaban 5 mg BID",
    snippet: "Active since 2023-06-14. Indication: atrial fibrillation. Last refilled 2025-04-02. Surgical hold guidance per institutional protocol: hold ≥48 h pre-op for moderate-bleed-risk procedures, ≥72 h for high-bleed-risk.",
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
    snippet: "Hgb 12.4 g/dL · WBC 6.8 × 10^9/L · Platelets 218 × 10^9/L. Within acceptable preoperative range. No active bleeding signs.",
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
    snippet: "INR repeat ordered 2025-05-06 in anticipation of OR date 2025-05-12. No result yet. Surgical team to confirm value < 1.4 before clearance.",
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
    snippet: "Scheduled: open inguinal hernia repair (CPT 49505). Estimated blood loss moderate. Anesthesia consult cleared 2025-04-18. No prior airway complication on file.",
    source: "DocumentReference/doc-44012",
    encounter: "Enc/2025-04-18",
    author: "Chen, R. (MD)",
    date: "2025-04-18",
    related: [{ id: "c_1042", text: "Apixaban 5 mg BID" }],
  },
};

Object.assign(window, { WORKSPACES, PATIENT, SESSIONS, WORKFLOWS, FILE_TREES, CITATIONS });
window.WORKFLOWS = WORKFLOWS;
window.AtlasData = { WORKSPACES, PATIENT, SESSIONS, WORKFLOWS, FILE_TREES, CITATIONS };
