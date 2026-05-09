import type {
  TrialCandidate,
  TrialPursuit,
  WorkspaceArtifact,
  WorkspaceEvent,
  WorkspaceSession,
} from "./contracts";

export type ChatMessage = {
  id: string;
  role: "assistant" | "user";
  content: string;
  at: string;
};

export const mockSession: WorkspaceSession = {
  id: "aws-demo-session-001",
  workspaceId: "clinical-trials.trial-finder",
  patientId: "workspace-shelly431",
  status: "running",
  activeSkill: "trial-matching",
  createdAt: "2026-05-09T09:15:00Z",
  updatedAt: "2026-05-09T09:24:00Z",
};

export const mockMessages: ChatMessage[] = [
  {
    id: "m1",
    role: "assistant",
    at: "09:15",
    content:
      "What kind of clinical trials are you interested in? You can tell me the disease area, geography, phase, intervention type, sponsor preferences, travel limits, or anything the patient or clinician wants to avoid.",
  },
  {
    id: "m2",
    role: "user",
    at: "09:16",
    content:
      "Look for cardiometabolic trials that would not conflict with renal impairment, anticoagulation, or upcoming surgery. Keep travel realistic.",
  },
  {
    id: "m3",
    role: "assistant",
    at: "09:19",
    content:
      "I searched active recruiting trials and found three worth reviewing. I am separating clinical fit from operational burden so the pursuit list only includes trials that are practical to contact.",
  },
];

export const mockCandidates: TrialCandidate[] = [
  {
    id: "candidate-renal-cv-01",
    nctId: "NCT06124511",
    title: "Renal and Cardiovascular Outcomes With SGLT2 Therapy in Older Adults",
    status: "Recruiting",
    phase: "Phase 3",
    conditions: ["Chronic Kidney Disease", "Cardiovascular Risk"],
    interventions: ["SGLT2 inhibitor", "Standard of care"],
    enrollment: 860,
    operationalBurden: "medium",
    matchScore: 84,
    inclusionMatches: ["CKD stage 3 signal", "cardiovascular risk factors", "age eligible"],
    exclusionRisks: ["perioperative medication holds need PI review", "recent anticoagulant use may require screening"],
    sourceSnapshotIds: ["src-ctgov-renal-cv"],
  },
  {
    id: "candidate-anticoag-02",
    nctId: "NCT05888242",
    title: "Remote Monitoring for Anticoagulated Patients With Multiple Chronic Conditions",
    status: "Recruiting",
    phase: "Not Applicable",
    conditions: ["Atrial Fibrillation", "Medication Safety"],
    interventions: ["Remote monitoring", "Clinical pharmacist review"],
    enrollment: 420,
    operationalBurden: "low",
    matchScore: 78,
    inclusionMatches: ["anticoagulation appears clinically relevant", "remote follow-up", "low visit burden"],
    exclusionRisks: ["requires stable internet access", "trial may not accept imminent procedure window"],
    sourceSnapshotIds: ["src-ctgov-anticoag"],
  },
  {
    id: "candidate-obesity-03",
    nctId: "NCT06450917",
    title: "Metabolic Risk Reduction After GLP-1 Therapy in Patients With Surgical Risk",
    status: "Active, not recruiting",
    phase: "Phase 4",
    conditions: ["Metabolic Syndrome", "Obesity", "Surgical Risk"],
    interventions: ["GLP-1 receptor agonist", "Lifestyle counseling"],
    enrollment: 240,
    operationalBurden: "high",
    matchScore: 61,
    inclusionMatches: ["metabolic risk profile", "surgery-relevant outcome measures"],
    exclusionRisks: ["not currently recruiting", "GI adverse-effect history needs review", "higher visit burden"],
    sourceSnapshotIds: ["src-ctgov-glp1"],
  },
];

export const mockPursuits: TrialPursuit[] = [
  {
    id: "pursuit-001",
    patientId: "workspace-shelly431",
    candidateId: "candidate-renal-cv-01",
    status: "reviewing",
    owner: "Blake",
    updatedAt: "2026-05-09T09:24:00Z",
    tasks: [
      { id: "task-001", title: "Confirm eGFR trend and latest creatinine", status: "open", dueAt: "2026-05-10" },
      { id: "task-002", title: "Ask site whether perioperative patients are paused or excluded", status: "open" },
    ],
    notes: [
      {
        id: "note-001",
        body: "Potentially strong fit if procedure timing does not exclude the patient.",
        createdAt: "2026-05-09T09:23:00Z",
      },
    ],
  },
  {
    id: "pursuit-002",
    patientId: "workspace-shelly431",
    candidateId: "candidate-anticoag-02",
    status: "interested",
    owner: "Blake",
    updatedAt: "2026-05-09T09:21:00Z",
    tasks: [{ id: "task-003", title: "Review anticoagulant indication and dosing history", status: "done" }],
    notes: [{ id: "note-002", body: "Low-burden option; keep as backup pursuit.", createdAt: "2026-05-09T09:21:00Z" }],
  },
];

export const mockArtifacts: WorkspaceArtifact[] = [
  {
    id: "artifact-criteria-001",
    label: "Renal CV criteria summary",
    kind: "markdown",
    updatedAt: "09:22",
    summary: "Draft inclusion/exclusion summary with source citations and unresolved screening questions.",
  },
  {
    id: "artifact-run-export-001",
    label: "Run bundle preview",
    kind: "export",
    updatedAt: "09:24",
    summary: "Messages, tool calls, candidate objects, source snapshots, and pursuit decisions.",
  },
];

export const mockEvents: WorkspaceEvent[] = [
  {
    id: "evt-001",
    sessionId: mockSession.id,
    type: "user.message",
    content: "Look for cardiometabolic trials with realistic travel.",
    createdAt: "2026-05-09T09:16:00Z",
  },
  {
    id: "evt-002",
    sessionId: mockSession.id,
    type: "tool.call",
    toolId: "patient.query_sql",
    args: { facts: ["conditions", "medications", "latest_labs"] },
    createdAt: "2026-05-09T09:17:00Z",
  },
  {
    id: "evt-003",
    sessionId: mockSession.id,
    type: "tool.result",
    toolId: "patient.query_sql",
    ok: true,
    summary: "Found CKD signal, anticoagulation context, and surgery-relevant risks.",
    createdAt: "2026-05-09T09:17:09Z",
  },
  {
    id: "evt-004",
    sessionId: mockSession.id,
    type: "tool.call",
    toolId: "clinical_trials.search",
    args: { query: "CKD cardiovascular older adults recruiting" },
    createdAt: "2026-05-09T09:18:00Z",
  },
  {
    id: "evt-005",
    sessionId: mockSession.id,
    type: "canvas.object.updated",
    objectKind: "TrialCandidate",
    objectId: "candidate-renal-cv-01",
    patch: { matchScore: 84, operationalBurden: "medium" },
    createdAt: "2026-05-09T09:19:00Z",
  },
  {
    id: "evt-006",
    sessionId: mockSession.id,
    type: "approval.requested",
    label: "Contact trial site",
    reason: "External outreach requires explicit user approval.",
    requestedAction: { candidateId: "candidate-renal-cv-01", channel: "email" },
    createdAt: "2026-05-09T09:24:00Z",
  },
];
