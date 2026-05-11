# Plugin Runtime — Product Spec

**Status:** Build-ready spec for a coding agent. No code lands from this document — the next agent implements against it.
**Audience:** A coding agent (Sonnet, Opus, GPT-5, etc.) picking up this build cold. The spec is self-contained — you should not need a human in the loop to clarify anything in §4–§8.
**Owner:** EHI Ignite platform team.
**Why this is mission critical:** The Atlas redesign UI is making an architecture promise about two trust postures sitting inside one shell. The plugin runtime is what makes that promise real. Without it, the marketplace is theatre and Caspian-vs-Plugin is only a visual variant. With it, EHI Ignite has a defensible third-party extensibility story.

---

## 0. Front matter

### Prerequisites — read these first, in order

1. [`.claude/handoff/atlas/README.md`](../../.claude/handoff/atlas/README.md) — Atlas product spec (the IA, the two workspace families, the boundary-pill table in §"Caspian vs. Marketplace boundaries")
2. [`docs/architecture/AGENTIC-HARNESS.md`](../architecture/AGENTIC-HARNESS.md) — Runtime contract for Caspian vs. Plugins. **This spec extends that doc; do not duplicate its content.**
3. [`app/src/components/atlas/trust.ts`](../../app/src/components/atlas/trust.ts) — Frontend type stub for the manifest, anchor, and provenance contracts. Read this end-to-end before reading §4 below.
4. [`app/src/components/atlas/README.md`](../../app/src/components/atlas/README.md) — Current shared-component inventory.
5. [`app/src/components/atlas/data.ts`](../../app/src/components/atlas/data.ts) — Current fixture. The thing this build replaces with a manifest-driven loader.

### Scope

**In scope for this build:**
- A typed, versioned `PluginManifest` format (JSON + TS + Pydantic)
- A manifest loader + verifier (frontend reads JSON; backend Pydantic-validates and signature-checks)
- Anchor package compilation server-side (signed, scope-limited, expiring)
- A consent-gate flow (per-run approval before any outbound action; per-action approval for each outbound)
- A provenance log (append-only, signed records of every outbound action)
- A plugin tool registry that enforces declared permissions
- Three production-quality plugin examples (Trial Finder, Medication Access, Second Opinion) with full manifests, fixtures, workbench tab definitions, workflow specs
- Plugin home + active-session UI driven entirely by the manifest (no hardcoded plugin branches in shell code)

**Explicitly out of scope:**
- Marketplace install/upgrade UX (the manifest can be present; install flow comes later)
- Sandboxed execution (in-process capability check is sufficient for v1 — the spec calls out where to add isolation later)
- Vendor key federation / external registry (self-signed vendor keys for v1)
- Plugin-to-plugin composition
- A real Trial Finder against ClinicalTrials.gov (the example plugin renders fixture data; the connector wiring is a follow-up build)

### Status when you start

- The shell exists (`components/atlas/`). The five panes work. Citation chips, approval cards, inspector — all rendering.
- The fixture-driven plugin UI works for one plugin (Trial Finder) on `data.ts` hardcoded shape.
- `trust.ts` declares the types you need to honor. Nothing imports them yet.
- `api/` has zero plugin awareness.

### Definition of done

Tracked in §11. Read §11 *before* you start — it's the rubric.

---

## 1. Core concepts (one-page recap)

Read `docs/architecture/AGENTIC-HARNESS.md` for the deep version. This is the executive summary you can carry in your head:

A **plugin** is a versioned, vendor-published unit of installable functionality that runs inside the Atlas workspace shell against a *scoped, signed slice of a patient's data*. It cannot read the raw chart. It cannot widen its scope at runtime. Every outbound action it takes is gated by a clinician's per-run consent and a per-action approval, and every successful outbound write is recorded as a provenance row.

Four objects move through the runtime:

1. **`PluginManifest`** — what the vendor publishes. Identity, version, declared permissions, connectors, exports, model preset, signature. Loaded once when the plugin is enabled; verified on every run.
2. **`AnchorPackage`** — what the plugin actually sees when a run starts. A curated, redacted slice of the patient record matching the manifest's declared scope. Signed by Atlas. Expires.
3. **`ApprovalRequest`** — what surfaces in chat when the plugin wants to do something gated. Two shapes: clinical (Caspian only) and outbound (plugin only). Outbound approvals carry a payload preview the clinician reviews verbatim.
4. **`ProvenanceRecord`** — what gets written when an outbound action completes. Signed audit row: who, what, when, which plugin version, which redaction preset. Append-only.

Two ground rules the runtime must hold:

> **Rule 1.** A plugin can read nothing outside what its manifest's `permissions` declared and what the anchor package contains.
> **Rule 2.** A plugin can write nothing outbound without an unexpired per-run consent token AND a per-action approval signed by an authorized clinician.

If either rule is breakable from any code path, the marketplace promise is broken. Treat these as load-bearing invariants.

---

## 2. The manifest format

The manifest is the contract between vendor and platform. It is **the only place** a plugin declares what it can read, what it can call, and what it can produce.

### 2.1 Storage

- Vendor publishes a `manifest.json` (signed). v1 lives in the repo at `data/plugins/{plugin-id}/manifest.json`. Future: a real registry.
- The bytes are versioned. A new manifest version is a new file path (`{plugin-id}/v2.4.1/manifest.json` — semver in the directory).
- The signature is **detached** — a separate `manifest.sig` file, ed25519 over the canonical JSON.

### 2.2 Schema — JSON

```json
{
  "schemaVersion": "1.0.0",
  "id": "trial-finder",
  "version": "2.4.1",
  "vendor": {
    "id": "helix-clinical",
    "name": "Helix Clinical",
    "keyFingerprint": "ed25519:r1k7…3pq"
  },
  "displayName": "Trial Finder",
  "subtitle": "Clinical-trial discovery + outreach",
  "description": "Pulls a consented patient anchor from Caspian and runs a clinical-trial discovery loop against external registries. Produces ranked candidate boards, eligibility checks, and outreach packets — every outbound action gated by per-run approval.",
  "icon": "Telescope",
  "color": "#4338ca",
  "trust": {
    "posture": "consented-external",
    "boundaryLabel": "Consented external · registry lookup",
    "requiresPerRunConsent": true
  },
  "anchor": {
    "scope": [
      "demographics.age-band",
      "demographics.sex",
      "demographics.geography",
      "diagnoses.active",
      "biomarkers",
      "labs.recent",
      "performance-status"
    ],
    "redactionPreset": "de-id-v3",
    "ttlSeconds": 3600
  },
  "connectors": [
    {
      "id": "clinicaltrials-gov",
      "label": "ClinicalTrials.gov",
      "endpointPattern": "https://clinicaltrials.gov/api/v2/**",
      "auth": "none"
    },
    {
      "id": "nci-trial-connect",
      "label": "NCI Trial Connect",
      "endpointPattern": "https://trialconnect.cancer.gov/api/**",
      "auth": "vendor-token"
    }
  ],
  "permissions": [
    { "kind": "read-anchor", "scope": ["diagnoses.active", "biomarkers", "labs.recent", "performance-status"] },
    { "kind": "call-external", "connector": "clinicaltrials-gov" },
    { "kind": "call-external", "connector": "nci-trial-connect" },
    { "kind": "send-outbound", "channel": "site-packet" }
  ],
  "workflows": [
    {
      "id": "shortlist",
      "title": "Shortlist candidate trials",
      "description": "Search registries against the patient anchors and rank likely fits.",
      "tags": ["external"],
      "needs": ["diagnoses.active", "biomarkers"],
      "produces": ["candidate-board"]
    },
    {
      "id": "review",
      "title": "Review eligibility fit",
      "description": "Compare inclusion/exclusion against shortlist.",
      "tags": ["review"],
      "needs": ["candidate-board"],
      "produces": ["eligibility-report"]
    },
    {
      "id": "packet",
      "title": "Draft outreach packet",
      "description": "Prepare a redacted artifact for site contact.",
      "tags": ["export"],
      "needs": ["candidate-board"],
      "produces": ["outreach-packet"]
    }
  ],
  "tools": [
    { "id": "trial.search",       "label": "Search trials",        "category": "clinical-trial", "permission": "call-external" },
    { "id": "trial.fetch_detail", "label": "Fetch trial detail",   "category": "clinical-trial", "permission": "call-external" },
    { "id": "trial.score_fit",    "label": "Score patient fit",    "category": "clinical-trial", "permission": "read-anchor"   },
    { "id": "packet.draft",       "label": "Draft outreach packet","category": "artifact",       "permission": "read-anchor"   },
    { "id": "packet.send",        "label": "Send packet",          "category": "outbound",       "permission": "send-outbound" }
  ],
  "ui": {
    "homeSections": ["hero", "permissions-ledger", "workflows", "recent-runs", "about"],
    "workbenchTabs": [
      { "id": "candidate-board",  "label": "Candidate board",      "kind": "trial-board",      "renderer": "trial.board"   },
      { "id": "shortlist",        "label": "ranked-shortlist.md",  "kind": "packet-outline",   "renderer": "markdown.doc"  },
      { "id": "manifest",         "label": "manifest.json",        "kind": "manifest-json",    "renderer": "json.viewer"   }
    ],
    "files": [
      { "group": "working",        "name": "ranked-shortlist.md",  "icon": "FileText",         "dirty": true },
      { "group": "working",        "name": "candidate-board.json", "icon": "Braces" },
      { "group": "working",        "name": "packet-outline.md",    "icon": "FileText" },
      { "group": "anchors",        "name": "diagnoses.md",         "icon": "FileText" },
      { "group": "anchors",        "name": "biomarkers.csv",       "icon": "FileSpreadsheet" },
      { "group": "anchors",        "name": "geography.json",       "icon": "Braces" }
    ],
    "agent": {
      "avatarInitials": "Tf",
      "avatarColor": "var(--mod-trials)",
      "modelPreset": "marketplace-act"
    }
  },
  "exports": ["markdown", "json", "shareable-bundle"],
  "signature": "ed25519:…(over the entire object minus this field)"
}
```

### 2.3 Schema — TypeScript (extends `trust.ts`)

The frontend type already exists at `app/src/components/atlas/trust.ts`. This build EXTENDS it:

```ts
// app/src/components/atlas/trust.ts (additions)

export type PluginUISpec = {
  homeSections: Array<
    | "hero"
    | "permissions-ledger"
    | "workflows"
    | "recent-runs"
    | "about"
    | "tasks"
    | "calendar"
  >;
  workbenchTabs: WorkbenchTabSpec[];
  files: PluginFileSeed[];
  agent: {
    avatarInitials: string;
    avatarColor: string;     // CSS var ok
    modelPreset: ModelPresetId;
  };
};

export type WorkbenchTabSpec = {
  id: string;
  label: string;
  kind: WorkbenchKind;
  renderer: WorkbenchRenderer;
};

export type WorkbenchKind =
  | "trial-board"
  | "candidate-detail"
  | "eligibility-form"
  | "barriers-list"
  | "pa-form"
  | "manufacturer-program-matcher"
  | "specialty-picker"
  | "referral-packet"
  | "network-status-board"
  | "packet-outline"
  | "anticoag-note"
  | "preop-brief"
  | "summary-json"
  | "diff"
  | "manifest-json";

export type WorkbenchRenderer =
  | "trial.board"
  | "trial.detail"
  | "form.eligibility"
  | "list.barriers"
  | "form.pa"
  | "matcher.manufacturer"
  | "picker.specialty"
  | "packet.referral"
  | "board.network-status"
  | "markdown.doc"
  | "json.viewer"
  | "diff.unified";

export type PluginFileSeed = {
  group: string;
  name: string;
  icon: string;
  dirty?: boolean;
};

// PluginManifest gets the .ui field too:
export type PluginManifest = {
  // …all the previously declared fields…
  schemaVersion: string;
  displayName: string;
  subtitle: string;
  description: string;
  icon: string;
  color: string;
  trust: {
    posture: "consented-external" | "internal-cohort";
    boundaryLabel: string;
    requiresPerRunConsent: boolean;
  };
  anchor: {
    scope: AnchorScopeField[];
    redactionPreset: RedactionPreset;
    ttlSeconds: number;
  };
  tools: PluginToolDecl[];
  workflows: WorkflowDecl[];
  ui: PluginUISpec;
};

export type PluginToolDecl = {
  id: string;
  label: string;
  category: "clinical-trial" | "patient" | "external" | "outbound" | "artifact" | "transparency";
  permission: "read-anchor" | "call-external" | "send-outbound";
};

export type WorkflowDecl = {
  id: string;
  title: string;
  description: string;
  tags: string[];
  needs: string[];
  produces: string[];
};
```

### 2.4 Schema — Pydantic (backend)

```python
# api/trust/models.py

from pydantic import BaseModel, Field, validator
from typing import Literal

AnchorScopeField = Literal[
    "demographics.age-band",
    "demographics.sex",
    "demographics.geography",
    "diagnoses.active",
    "diagnoses.history",
    "medications.active",
    "medications.history",
    "allergies",
    "biomarkers",
    "labs.recent",
    "encounters.recent",
    "performance-status",
]

RedactionPreset = Literal[
    "de-id-v1", "de-id-v2", "de-id-v3", "research-grade", "minimal"
]


class VendorIdentity(BaseModel):
    id: str
    name: str
    keyFingerprint: str


class TrustPosture(BaseModel):
    posture: Literal["consented-external", "internal-cohort"]
    boundaryLabel: str
    requiresPerRunConsent: bool


class AnchorSpec(BaseModel):
    scope: list[AnchorScopeField]
    redactionPreset: RedactionPreset
    ttlSeconds: int = Field(gt=0, le=86400)


class Permission(BaseModel):
    kind: Literal["read-anchor", "call-external", "send-outbound"]
    scope: list[AnchorScopeField] | None = None
    connector: str | None = None
    channel: str | None = None

    @validator("scope", always=True)
    def scope_required_for_read(cls, v, values):
        if values.get("kind") == "read-anchor" and not v:
            raise ValueError("read-anchor permission requires scope")
        return v


class Connector(BaseModel):
    id: str
    label: str
    endpointPattern: str
    auth: Literal["none", "vendor-token", "user-delegated"] = "none"


class PluginToolDecl(BaseModel):
    id: str
    label: str
    category: Literal[
        "clinical-trial", "patient", "external",
        "outbound", "artifact", "transparency"
    ]
    permission: Literal["read-anchor", "call-external", "send-outbound"]


class WorkflowDecl(BaseModel):
    id: str
    title: str
    description: str
    tags: list[str]
    needs: list[str]
    produces: list[str]


class PluginUISpec(BaseModel):
    homeSections: list[str]
    workbenchTabs: list[dict]
    files: list[dict]
    agent: dict


class PluginManifest(BaseModel):
    schemaVersion: str
    id: str
    version: str
    vendor: VendorIdentity
    displayName: str
    subtitle: str
    description: str
    icon: str
    color: str
    trust: TrustPosture
    anchor: AnchorSpec
    connectors: list[Connector]
    permissions: list[Permission]
    workflows: list[WorkflowDecl]
    tools: list[PluginToolDecl]
    ui: PluginUISpec
    exports: list[Literal["markdown", "json", "shareable-bundle"]]
    signature: str

    @validator("permissions")
    def declared_connectors_must_exist(cls, perms, values):
        connectors = {c.id for c in values.get("connectors", [])}
        for p in perms:
            if p.kind == "call-external" and p.connector not in connectors:
                raise ValueError(f"permission references undeclared connector: {p.connector}")
        return perms
```

### 2.5 Loading + verification

```python
# api/plugins/manifest.py

from pathlib import Path
import json
import nacl.signing  # or cryptography.hazmat — pick one

def load_manifest(plugin_id: str, version: str) -> PluginManifest:
    """Load + parse + verify a plugin manifest from disk.

    Verification:
      1. Parse JSON, validate against PluginManifest (Pydantic raises on invalid)
      2. Look up vendor public key by manifest.vendor.keyFingerprint in the
         vendor allowlist (data/plugins/vendors.json)
      3. Verify the detached signature over canonical-JSON of the manifest
         (manifest with `signature` field removed)
      4. Return the validated PluginManifest, or raise PluginManifestError
    """

class PluginManifestError(Exception):
    pass
```

**Vendor allowlist:** `data/plugins/vendors.json` — a JSON array of `{id, name, keyFingerprint, publicKey}`. v1 = self-managed. v2 = federated registry.

---

## 3. Anchor package format

An **anchor package** is the only patient-data handle a plugin ever sees. It is compiled fresh per-run, signed by Atlas, and expires.

### 3.1 Compilation

When a clinician starts a plugin run, the backend:

1. Looks up the verified manifest
2. Reads the *full* patient record (server-side, with clinician's identity)
3. Projects it down to the manifest's `anchor.scope` fields
4. Applies the redaction preset (`de-id-v3`, etc.)
5. Wraps it as an `AnchorPackage`
6. Signs the package with Atlas's signing key
7. Hands the signed package + a per-run consent token to the plugin runtime

The plugin runtime hands the package to the plugin's tools. The tools may ONLY read fields enumerated in `anchor.scope` AND declared in their own `permission: read-anchor` scope.

### 3.2 Schema — JSON

```json
{
  "schemaVersion": "1.0.0",
  "pluginId": "trial-finder",
  "pluginVersion": "2.4.1",
  "patientId": "8.4127.881",
  "runId": "r_4128",
  "issuedAt": "2026-05-10T17:42:11Z",
  "expiresAt": "2026-05-10T18:42:11Z",
  "redactionPreset": "de-id-v3",
  "scope": ["diagnoses.active", "biomarkers", "labs.recent", "performance-status"],
  "data": {
    "diagnoses.active": [
      { "code": "C92.10", "system": "ICD-10", "display": "Chronic myeloid leukemia, BCR-ABL positive, in chronic phase", "onsetYear": 2022 }
    ],
    "biomarkers": [
      { "marker": "BCR-ABL1 (t9;22)", "status": "positive", "method": "FISH", "lastTested": "2024-11-04" }
    ],
    "labs.recent": [
      { "code": "26464-8",  "system": "LOINC", "display": "Leukocytes [#/volume] in Blood", "value": 6.8, "unit": "10^9/L", "date": "2026-04-22" },
      { "code": "718-7",    "system": "LOINC", "display": "Hemoglobin [Mass/volume] in Blood", "value": 12.4, "unit": "g/dL", "date": "2026-04-22" }
    ],
    "performance-status": { "scale": "ECOG", "value": 1, "date": "2026-04-18" }
  },
  "signature": "ed25519:…(over the rest)"
}
```

### 3.3 What the plugin does NOT see

- The patient's name, MRN, DOB, address (redaction preset stripped them)
- Any condition, medication, observation outside the declared scope
- Any clinician identifiers
- Provider notes (unless the manifest declared `documents` scope, which Trial Finder does not)

### 3.4 Anchor refresh + expiry

- `expiresAt = issuedAt + manifest.anchor.ttlSeconds`
- A plugin tool call with an expired anchor MUST fail with `AnchorExpired` and prompt the clinician to refresh
- If the underlying patient state changes during a run, the next anchor refresh picks up the new state — but in-flight tool calls do not (they hold the snapshot)

---

## 4. Consent gate + approvals

The boundary pill is meaningless without an enforced gate. The flow:

### 4.1 Run-level consent (once per run)

1. Clinician clicks "Start new run" on the plugin home, or selects an existing draft run.
2. Backend creates a `PluginRun` row in state `awaiting-consent`.
3. The first agent reply in the run's chat surfaces a `PluginConsentCard` (a special `ApprovalCard` variant):
   - Title: `CONSENT REQUESTED · {plugin.displayName}`
   - Body: lists what the plugin will be able to do this run — the bound scope, the connectors it will call, the kinds of outbound it can produce
   - Two buttons: `Grant consent for this run` (primary) / `Cancel`
4. On grant, backend mints a per-run consent token (signed, scoped to `{pluginId, runId, expiresAt = run.expiresAt}`) and stores it on the run.
5. Subsequent tool calls in the run carry the consent token. The backend verifies on every call.
6. Tools without `send-outbound` permission don't need the token at the per-call level — the run-level consent is sufficient.

### 4.2 Per-action consent (every outbound)

For tools with `permission: send-outbound`:

1. Plugin agent declares intent to send: emits a `PluginApprovalRequest`.
2. `ApprovalCard` renders in chat with:
   - `payloadPreview` — a verbatim copy of what would be sent (no transformations)
   - The `redactionPreset` applied to the payload
   - The destination (connector + endpoint)
   - The approver role required
3. Two buttons: primary action label (e.g. `Send packet`) / secondary (e.g. `Review consent first`).
4. On approval, backend:
   - Verifies the run-level consent token is still unexpired
   - Calls the outbound connector with the verbatim payload
   - On success, writes a `ProvenanceRecord`
   - Emits a `tool.result` event back into the chat

### 4.3 What gets denied

- Tool calls without a verified consent token → `ConsentRequired` error → backend surfaces a fresh `PluginConsentCard` in chat
- Tool calls referencing fields outside the manifest's `anchor.scope` → `OutOfScope` error → logged + visible failure in chat trace; no clinician dialog
- Outbound calls to connectors not declared in the manifest → `UndeclaredConnector` error → same as above
- Approved outbound that returns success from the connector but lacks a payload that matches the redaction preset → `RedactionMismatch` error, action voided

### 4.4 Reversibility

- Per-run consent can be revoked mid-run by the clinician (a "Revoke consent" button in the run-state pill on the context strip). All pending outbound approvals invalidate.
- A clinician revoking consent does NOT roll back already-sent outbound actions. Provenance preserves the record.

---

## 5. Provenance log

Every successful outbound action writes one provenance row. Schema:

```python
class ProvenanceRecord(BaseModel):
    id: UUID                          # provenance row id
    runId: str
    pluginId: str
    pluginVersion: str
    vendor: VendorIdentity            # snapshotted (vendor may be removed later)
    action: Literal["send-packet", "register-patient", "submit-application",
                    "schedule-followup", "post-update"]
    approver: UserIdentity            # who signed off
    redactionPreset: RedactionPreset
    artifactId: str | None            # what was sent
    endpoint: str                     # the resolved connector endpoint
    responseStatus: int               # connector HTTP status
    responseSummary: str              # 200-char excerpt
    ts: datetime                      # ISO 8601
    signature: str                    # signed row
```

**Storage:** `data/provenance.db` (SQLite). Append-only. No update or delete is permitted via API — only direct DBA-level intervention with a documented audit trail. v2 = WORM storage on S3 + object-lock.

**Surfacing in UI:** the plugin's recent-runs table reads from `ProvenanceRecord` rows. The inspector's Trace tab lists the rows for the currently-open run.

---

## 6. Plugin lifecycle

| State | Trigger | Effect |
|---|---|---|
| `published` | Vendor publishes manifest + signature | Manifest sits in registry; not installed |
| `installed` | Org admin installs | Manifest written to `data/plugins/{id}/{version}/`, allowlisted for the org |
| `enabled` | Org admin enables | Visible in `/workspaces` catalog for clinicians in the org |
| `disabled` | Org admin disables | Hidden from catalog; existing runs continue until completion; new runs blocked |
| `revoked` | Org admin revokes OR vendor key revoked | All runs terminate immediately; pending outbound approvals voided; provenance rows preserved |
| `upgraded` | New version installed | Both versions coexist; in-progress runs finish on their original version; new runs use the latest by default |

v1 implements `installed` + `enabled` + `disabled` + `revoked`. `published` (a registry) and `upgraded` (version coexistence) are v2.

---

## 7. Three plugin examples (fully built)

These three plugins must ship with this build. Each one is genuinely different — different anchor scope, different connectors, different workbench tabs, different approval shapes. They cover the design space.

---

### Example A — Trial Finder

**Mental model:** *"A clinical-trial discovery and outreach assistant."* Searches registries for trials matching the patient, ranks them, drafts redacted outreach packets to study sites.

**Vendor:** Helix Clinical
**Trust:** consented-external · per-run consent required
**Files location:** `data/plugins/trial-finder/2.4.1/manifest.json` (this is the canonical example — full JSON appears in §2.2 above)

**Anchor scope** — what the plugin sees:
```
diagnoses.active
biomarkers
labs.recent
performance-status
demographics.age-band
demographics.sex
demographics.geography
```

**Workflows** — three:
1. `shortlist` — needs `diagnoses.active` + `biomarkers`; produces `candidate-board`
2. `review` — needs `candidate-board`; produces `eligibility-report`
3. `packet` — needs `candidate-board`; produces `outreach-packet`

**Connectors** — two:
- `clinicaltrials-gov` — public; no auth
- `nci-trial-connect` — vendor-token auth

**Tools** — five:
- `trial.search` (call-external)
- `trial.fetch_detail` (call-external)
- `trial.score_fit` (read-anchor)
- `packet.draft` (read-anchor)
- `packet.send` (send-outbound) ← gated

**Outbound channels** — one:
- `site-packet` — secure messaging to a study site contact

**Approval flow:**
1. Run start → `PluginConsentCard` shows "Trial Finder will: search ClinicalTrials.gov + NCI Trial Connect, draft outreach packets, send packets to sites you approve."
2. Each packet send → `PluginApprovalRequest` shows payload preview, destination site, redaction preset, two buttons (`Send packet` / `Review consent first`)
3. On send → ProvenanceRecord written with `action: "send-packet"`, `artifactId: outreach-packet-N`, endpoint resolved

**Workbench tabs** — three default:
- `Candidate board` (`trial-board` kind) — renders the ranked trial cards with fit meters
- `ranked-shortlist.md` (`packet-outline` kind) — markdown doc, the agent edits this as it goes
- `manifest.json` (`manifest-json` kind) — the live manifest, viewable

**Sessions (seed data):**
```
t1  "Trial shortlist — Hollister"          running  shortlist
t2  "Outreach packet — NCT-0421187"         needs    packet
t3  "Eligibility check batch"               done     review
```

**Files seed:**
```
working/
  ranked-shortlist.md         dirty
  candidate-board.json
  packet-outline.md
anchors/
  diagnoses.md
  biomarkers.csv
  geography.json
package/
  manifest.json
  trial-finder.json
```

**Pinned objects:**
```
trial:NCT-0421187  High clinical fit
trial:NCT-0387714  Pending biomarker
```

**Agent identity:** avatar "Tf" on `--mod-trials`, model preset `marketplace-act`

**Initial chat seed:** see existing `INITIAL_CHAT["trial-finder"]` in `components/atlas/data.ts` — keep that copy verbatim.

---

### Example B — Medication Access

**Mental model:** *"A patient-assistance and prior-authorization concierge."* Identifies medication-access barriers, matches the patient to manufacturer assistance programs, prepares and files prior-auth packets with payer portals.

**Vendor:** RxBridge
**Trust:** consented-external · per-run consent required
**Files location:** `data/plugins/med-access/1.7.0/manifest.json`

**Anchor scope:**
```
medications.active
medications.history
diagnoses.active
allergies
demographics.age-band
demographics.geography
```

(Note the difference from Trial Finder: no biomarkers, no labs, no performance-status. Different lens on the same patient.)

**Workflows** — four:
1. `identify-barriers` — needs `medications.active` + `diagnoses.active`; produces `barriers-list`
2. `match-pap` — needs `barriers-list`; produces `pap-matches` (PAP = Patient Assistance Program)
3. `file-pa` — needs `barriers-list`; produces `pa-packet` then `pa-submission-receipt`
4. `appeal-denial` — needs `pa-submission-receipt` (with denial); produces `appeal-packet`

**Connectors** — three:
- `surescripts-formulary` — formulary lookup, no auth (we use a federated identifier)
- `manufacturer-pap-api` — vendor-token auth (per-manufacturer)
- `payer-portal-edi` — user-delegated auth (clinician's portal login flows through)

**Tools** — six:
- `med.lookup_formulary` (call-external)
- `med.identify_barriers` (read-anchor)
- `pap.match` (call-external)
- `pap.enroll` (send-outbound) ← gated
- `pa.compose` (read-anchor)
- `pa.submit` (send-outbound) ← gated

**Outbound channels** — two:
- `pap-enrollment` — application submission to a manufacturer assistance program
- `pa-submission` — prior-auth packet submission to a payer portal

**Approval flow** — notably different from Trial Finder:
- Run start → `PluginConsentCard` shows "Medication Access will: look up formularies, match to manufacturer programs, **and submit packets to payers and manufacturers you approve.**"
- Each PAP enrollment → approval with `payloadPreview: <enrollment form>`, redaction `minimal` (patient identifiers are REQUIRED for these — clinician sees that in the preview), `approverRole: clinician`
- Each PA submission → approval with `payloadPreview: <clinical justification + supporting evidence>`, redaction `minimal`, `approverRole: clinician` (and on appeals, `attending`)
- This is the example that shows redaction is NOT one-size-fits-all — PAP enrollment must carry the patient's real name to actually enroll them. The boundary pill stays amber; the consent gate is the audit.

**Workbench tabs** — four:
- `Barriers` (`barriers-list` kind)
- `PA form preview` (`pa-form` kind)
- `Manufacturer programs` (`manufacturer-program-matcher` kind)
- `Submission status` (`board.network-status` kind) — tracks pending submissions

**Sessions (seed):**
```
m1  "Apixaban PA — Hollister"               needs    file-pa     manufacturer reply pending
m2  "Eliquis assistance — Hollister"        running  match-pap
m3  "Metformin formulary check — Hollister" done     identify-barriers
```

**Files seed:**
```
working/
  pa-packet.md            dirty
  barriers.json
  pap-matches.md
anchors/
  active-meds.md
  diagnoses.md
package/
  manifest.json
```

**Pinned:**
```
med:apixaban-5mg-bid       Active, PA needed
program:bms-bridges        Match found (apixaban)
```

**Agent identity:** avatar "Mx" on `--mod-meds`, model preset `marketplace-act`

**Initial chat seed (new):**
```
user: "Hollister is being switched to apixaban next month and her plan won't cover it. Walk me through getting her access."

assistant (Mx, after consent granted):
  trace: med.identify_barriers(medications.active, diagnoses.active)
  blocks:
    - "Pulled the active medication list and active diagnoses against Hollister's plan formulary. Apixaban is non-formulary on her current plan (Aetna Open Access PPO). Two pathways forward: (1) file a prior auth with clinical justification [c_2104], or (2) enroll in the manufacturer's assistance program — BMS3B Bridges — which the formulary check confirms she qualifies for (income band + diagnosis match) [c_2106]."
    - "I can do either or both. The PAP enrollment ships her real identifiers to BMS3B (that's how the program works — no anonymous enrollment). The PA submission to Aetna ships clinical justification + medication history + a supporting reference to the eligibility criteria; the redaction preset is `minimal` because the payer needs the patient identified."
  actions:
    - { label: "Match PAP options",      target: "open-pap-matches",   icon: "Pill" }
    - { label: "Compose PA",             target: "open-pa-form",       icon: "FileText" }
    - { label: "Inspect manifest",       target: "open-manifest",      icon: "Boxes" }
  approval:
    body: "Submit the apixaban PA to Aetna Open Access PPO with clinical justification draft attached? Submission uses the `minimal` redaction preset because the payer requires patient identifiers. Submission is logged in provenance."
    primary: "Submit PA"
    secondary: "Review consent first"
```

---

### Example C — Second Opinion

**Mental model:** *"A specialist referral and second-opinion packager."* Composes a redacted clinical packet for an outside specialist, routes it to a chosen consulting network, tracks the response.

**Vendor:** ConferMD
**Trust:** consented-external · per-run consent required
**Files location:** `data/plugins/second-opinion/0.9.0-beta/manifest.json`

**Anchor scope:**
```
diagnoses.active
diagnoses.history
labs.recent
encounters.recent
allergies
performance-status
```

(Different lens again: needs encounter history and current diagnoses, no biomarkers, no medications, no demographics.)

**Workflows** — three:
1. `compose-packet` — needs full anchor; produces `referral-packet`
2. `route-packet` — needs `referral-packet`; produces `referral-submission-receipt`
3. `track-response` — needs `referral-submission-receipt`; produces `consulting-opinion`

**Connectors** — one:
- `confermd-network` — vendor-token auth, ConferMD specialist network

**Tools** — four:
- `referral.compose_packet` (read-anchor)
- `referral.apply_redactions` (read-anchor)
- `referral.route` (send-outbound) ← gated
- `referral.fetch_response` (call-external)

**Outbound channels** — one:
- `consulting-network` — secure messaging into ConferMD's specialist routing system

**Approval flow:**
- Run start → standard `PluginConsentCard`
- Each route action → `PluginApprovalRequest` with payload preview showing the **entire packet verbatim** (redactions applied), the specialty selected, the specific specialist ID if chosen, the redaction preset
- `approverRole: attending` (this is the only example where an attending sign-off is required by default — clinician composes, attending approves)
- On approval → `ProvenanceRecord` with `action: "send-packet"`, response logged when specialist responds

**Workbench tabs** — three:
- `Specialty picker` (`specialty-picker` kind) — choose specialty, optionally specific specialist
- `Referral packet` (`referral-packet` kind) — the composed packet, redactions applied; this is the document the attending reviews verbatim
- `Network status` (`board.network-status` kind) — sent / acknowledged / responded / closed

**Sessions (seed):**
```
o1  "Endocrinology second opinion — Hollister"    needs   compose-packet    attending review pending
o2  "Cardiology referral — Hollister"             done    track-response    response received
```

**Files seed:**
```
working/
  referral-packet.md       dirty
  redaction-preview.md
anchors/
  diagnoses.md
  recent-encounters.md
package/
  manifest.json
```

**Pinned:**
```
specialty:endocrinology   Pending response
specialist:dr-yates-msk   Selected for endo referral
```

**Agent identity:** avatar "So" on `#0f766e` (teal, no existing mod color), model preset `clinical-balanced` (this plugin's reasoning is more clinical-grounded than action-oriented)

**Initial chat seed (new):**
```
user: "Get an endocrinology second opinion on Hollister's recent thyroid panel — TSH dropped to 0.2 while she's on long-term levothyroxine."

assistant (So, after consent granted):
  trace: referral.compose_packet(scope=labs.recent + diagnoses.history)
  blocks:
    - "Drafted an endocrinology referral packet. Anchor scope includes Hollister's recent labs (TSH 0.2 mIU/L, 2026-04-22; free T4 1.6 ng/dL) [c_3041] and her thyroid history (hypothyroidism on levothyroxine 100 mcg since 2019) [c_3042]. The composed packet de-identifies to age band + sex + zip3."
    - "Redaction preview is in `redaction-preview.md`. The packet is ready to route to ConferMD's endocrinology network. Routing requires attending approval before it leaves the workspace."
  actions:
    - { label: "Review redaction",       target: "open-redaction-preview", icon: "FileText" }
    - { label: "Pick specialist",        target: "open-specialty-picker",  icon: "UserRound" }
  approval:
    body: "Route the redacted endocrinology referral to ConferMD's endo network with the current packet contents? Attending sign-off required. Routing is logged and irreversible once acknowledged by the consulting specialist."
    primary: "Route packet"
    secondary: "Send to attending review"
    approverRole: "attending"
```

---

### Summary — what makes the three examples genuinely different

| Dimension | Trial Finder | Medication Access | Second Opinion |
|---|---|---|---|
| **Anchor scope** | Biomarkers, labs, performance | Medications, allergies | Encounters, labs, history |
| **Connector count** | 2 external registries | 3 (formulary + PAP + payer portal) | 1 (ConferMD) |
| **Auth shapes** | none + vendor-token | none + vendor-token + user-delegated | vendor-token only |
| **Outbound channels** | site-packet | pap-enrollment + pa-submission | consulting-network |
| **Redaction default** | `de-id-v3` | `minimal` (identifiers required) | `de-id-v3` (then `minimal` for routing) |
| **Approval role** | clinician | clinician (attending on appeals) | **attending** by default |
| **Reversibility** | packet send is final | PAP enrollment final; PA can be withdrawn before payer adjudicates | routing final once acknowledged |
| **Workbench primary** | board (visual ranking) | form (PA composition) | document (referral packet) |
| **Agent posture** | action-oriented | action-oriented | clinical-balanced |

---

## 8. Frontend wiring plan

### 8.1 Replace the hardcoded `data.ts` plugin shape

Today `WORKSPACES["trial-finder"]` is a hand-shaped object literal. Replace with a manifest loader:

```ts
// app/src/components/atlas/manifests.ts (new)

import { z } from "zod";       // or io-ts — pick one for runtime validation
import type { PluginManifest } from "./trust";

const MANIFEST_SCHEMA = z.object({ /* mirror of PluginManifest */ });

export async function loadInstalledManifests(): Promise<PluginManifest[]> {
  // v1: fetch from /api/plugins/installed (returns verified manifests)
  const res = await fetch("/api/plugins/installed");
  const raw = await res.json();
  return raw.map((m: unknown) => MANIFEST_SCHEMA.parse(m));
}

export function workspaceFromManifest(m: PluginManifest): Workspace {
  return {
    id: m.id as WorkspaceId,
    family: "plugin",
    title: m.displayName,
    subtitle: m.subtitle,
    icon: m.icon,
    color: m.color,
    tint: tintFromColor(m.color),
    boundary: m.trust.boundaryLabel,
    boundaryTone: "warn",
    vendor: m.vendor.name,
    version: m.version,
    permissions: m.permissions
      .filter((p) => p.kind === "call-external" || p.kind === "send-outbound")
      .map(humanReadablePermissionLabel),
    // …runState etc. come from the active run, not the manifest
  };
}
```

### 8.2 `useWorkspaceState` reads from manifests

Replace `WORKSPACES[workspaceId]` lookups with a `useManifests()` hook backed by React Query. Caspian stays hardcoded (no manifest — it's not a plugin).

### 8.3 `PluginHome` renders entirely from the manifest

Today `pages/Plugins/Index.tsx` has hand-shaped permission ledger cards. Replace with:

```tsx
<PluginHome
  manifest={manifest}
  recentRuns={recentRuns}   // from /api/plugins/{id}/runs
  onStartRun={() => navigate(`/workspaces/${manifest.id}/sessions/new`)}
/>
```

The permissions ledger reads `manifest.permissions` + `manifest.connectors`. The workflow cards read `manifest.workflows`. The recent-runs table reads `recentRuns` from the backend (which reads from `ProvenanceRecord`).

### 8.4 `WorkbenchPane` becomes manifest-driven

Today `WorkbenchPane` has a `renderTab(tab)` switch over hardcoded `tab.kind`. Replace with a renderer registry:

```ts
// app/src/components/atlas/renderers/index.ts

export const RENDERERS: Record<WorkbenchRenderer, React.FC<RendererProps>> = {
  "trial.board":        TrialBoardRenderer,
  "trial.detail":       TrialDetailRenderer,
  "form.eligibility":   EligibilityFormRenderer,
  "list.barriers":      BarriersListRenderer,
  "form.pa":            PaFormRenderer,
  "matcher.manufacturer": ManufacturerMatcherRenderer,
  "picker.specialty":   SpecialtyPickerRenderer,
  "packet.referral":    ReferralPacketRenderer,
  "board.network-status": NetworkStatusBoardRenderer,
  "markdown.doc":       MarkdownDocRenderer,
  "json.viewer":        JsonViewerRenderer,
  "diff.unified":       UnifiedDiffRenderer,
};
```

Each renderer is a React component that takes a `RendererProps` (artifact id + anchor data + on-update handler). When the manifest's `workbenchTabs[].renderer` resolves to a registered key, `WorkbenchPane` mounts that component.

This is what makes adding a new plugin a config + N-renderers change, not a shell change.

### 8.5 `ContextStrip` reads run state from the run, manifest identity from the manifest

Today `ContextStrip` reads `workspace.runState` / `workspace.runStep` / `workspace.runElapsed` from the workspace object. Move these to the active run:

```ts
type ActiveRun = {
  id: string;
  pluginId: PluginId;
  state: "awaiting-consent" | "running" | "complete" | "waiting" | "idle";
  step?: string;
  elapsed?: string;
  consentToken?: string;     // signed, expires with the run
  anchorPackage?: AnchorPackage;
};
```

`ContextStrip` for a plugin renders identity from the manifest + run state from the active run.

### 8.6 Approval flow

Today `ApprovalCard` is a static component rendered when a chat message includes `msg.approval`. Replace with a typed approval queue:

- Backend POSTs `ApprovalRequest` events into the chat event stream
- `ChatPane` renders each as an `ApprovalCard`
- Clicking primary action POSTs to `/api/runs/{runId}/approvals/{approvalId}/approve` with the approver's identity
- Backend verifies consent token + writes provenance + emits `tool.result` event

### 8.7 Routes — already exist

Today: `/workspaces`, `/workspaces/:pluginId`, `/workspaces/:pluginId/sessions/:id`. Keep these. Just make the page components read from `useManifest(pluginId)` instead of a fixture lookup.

---

## 9. Backend wiring plan

### 9.1 Directory layout (mirrors AGENTIC-HARNESS §5)

```
api/
  workspace/
    sessions.py            session CRUD (already exists conceptually)
    events.py              event stream
    artifacts.py           durable artifacts
    tools/envelope.py      tool-call protocol

  caspian/
    fhir_tools.py          direct chart access (already-ish exists)
    clinical_approvals.py
    clinical_audit.py

  plugins/
    __init__.py
    manifest.py            load_manifest, verify_signature, vendor allowlist
    registry.py            installed plugins, enable/disable/revoke
    anchors.py             compile_anchor_package, sign, verify, expire
    consent.py             mint_consent_token, verify_consent
    runtime.py             run lifecycle: start, advance, terminate
    tools.py               tool registry; enforces declared permissions
    connectors/
      __init__.py
      clinicaltrials_gov.py
      nci_trial_connect.py
      surescripts_formulary.py
      manufacturer_pap.py
      payer_portal_edi.py
      confermd_network.py
    consent_gate.py        per-action approval flow
    provenance.py          append-only audit log
    routers/
      installed.py         GET /api/plugins/installed
      manifest.py          GET /api/plugins/{id}/manifest
      runs.py              POST /api/runs ; GET /api/runs/{id}
      approvals.py         POST /api/runs/{id}/approvals/{aid}/approve

  trust/
    __init__.py
    models.py              Pydantic mirrors of trust.ts
    signatures.py          ed25519 signing / verification helpers
    redactions.py          de-id presets (de-id-v1/2/3, research-grade, minimal)
    keys.py                vendor allowlist + Atlas signing key
```

### 9.2 Storage

```
data/
  plugins/
    vendors.json            vendor allowlist (vendor id, name, key fingerprint, public key)
    trial-finder/
      2.4.1/
        manifest.json
        manifest.sig
    med-access/
      1.7.0/
        manifest.json
        manifest.sig
    second-opinion/
      0.9.0-beta/
        manifest.json
        manifest.sig

  provenance.db             SQLite, append-only via API
  runs.db                   active + historical runs (anchor packages, consent tokens, run state)
```

### 9.3 Endpoint list

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/plugins/installed` | List enabled manifests for the org |
| GET | `/api/plugins/{id}/manifest` | Fetch a specific verified manifest |
| GET | `/api/plugins/{id}/runs` | Recent runs for a plugin |
| POST | `/api/runs` | Start a new run (returns `runId`, pending consent) |
| POST | `/api/runs/{runId}/consent` | Grant per-run consent; returns consent token |
| POST | `/api/runs/{runId}/approvals/{approvalId}/approve` | Approve a single outbound action |
| POST | `/api/runs/{runId}/approvals/{approvalId}/deny` | Deny |
| POST | `/api/runs/{runId}/revoke-consent` | Revoke per-run consent mid-run |
| POST | `/api/runs/{runId}/tool/{toolId}` | Execute a tool call (server enforces permissions + consent) |
| GET | `/api/runs/{runId}/events` | SSE stream of events for the run |
| GET | `/api/runs/{runId}/provenance` | Provenance rows for the run |

### 9.4 Signing

- **Atlas signing key:** ed25519 keypair. Public key embedded in the frontend bundle for client-side verification of anchor packages. Private key in env (`ATLAS_SIGNING_KEY`).
- **Vendor keys:** ed25519. Public keys in `data/plugins/vendors.json`. Vendor manages their own private key.
- **Canonical JSON:** sort keys lexicographically, no whitespace, UTF-8, NFC normalization on strings. Both sides MUST produce the same bytes.

---

## 10. Plugin home + active session UX driven by manifest

The shell already has a `PluginHome` component and a `WorkspaceFrame`. Today both are driven by hardcoded plugin shape. Make them driven by the manifest.

### 10.1 PluginHome sections (ordered)

The manifest's `ui.homeSections` array controls section visibility + order. Renderers:

| Key | Renderer | Reads |
|---|---|---|
| `hero` | `PluginHero` | manifest: displayName, version, vendor, description, icon, color |
| `permissions-ledger` | `PermissionsLedger` | manifest: permissions, connectors |
| `workflows` | `WorkflowGrid` | manifest: workflows |
| `recent-runs` | `RecentRunsTable` | `/api/plugins/{id}/runs` |
| `about` | `AboutSection` | manifest: vendor, version + computed `installedBy`, `updateChannel`, `trustPosture` |
| `tasks` | `TasksBoard` | per-plugin tasks DB (v2 — out of scope for v1) |
| `calendar` | `CalendarStrip` | per-plugin scheduled actions (v2) |

The three example plugins all use `hero · permissions-ledger · workflows · recent-runs · about`. Future plugins can compose differently.

### 10.2 Active session

`WorkspaceFrame` already knows how to render the 5-pane shell. The manifest-driven parts:

- `SessionsPane` reads workflow library from `manifest.workflows`
- `ChatPane` reads agent identity from `manifest.ui.agent` (avatar, color, model preset)
- `WorkbenchPane` reads tabs + renderers from `manifest.ui.workbenchTabs`
- `FilesPane` seeds the tree from `manifest.ui.files`
- `InspectorPane` Trace tab streams from `/api/runs/{runId}/events` filtered to `tool.*` events
- `InspectorPane` Context tab shows pinned objects from the run + the **anchor package contents** (read-only view — clinician can see exactly what the plugin sees)

---

## 11. Acceptance criteria (the rubric)

Done = all checked. Read this **before** writing code.

### 11.1 Trust invariants

- [ ] A plugin attempting to read a FHIR field outside its anchor scope is rejected at the tool layer with `OutOfScope`. Test: in `trial-finder`, remove `biomarkers` from the run's anchor scope at runtime; call `trial.score_fit`; expect failure.
- [ ] A plugin attempting to call a connector not declared in its manifest is rejected with `UndeclaredConnector`. Test: monkey-patch the Trial Finder runtime to call `surescripts-formulary`; expect failure.
- [ ] A plugin attempting `send-outbound` without a verified consent token is rejected with `ConsentRequired`. Test: start a run, skip consent, attempt `packet.send`; expect failure.
- [ ] A plugin attempting `send-outbound` with an expired consent token is rejected with `ConsentExpired`. Test: mint a consent token with `ttlSeconds: 1`; wait; attempt; expect failure.
- [ ] An anchor package fetched after its `expiresAt` is rejected with `AnchorExpired`. Test: same as above.
- [ ] A manifest with an invalid signature is rejected at load with `BadSignature`. Test: tamper with a manifest's `displayName` after signing; reload; expect failure.
- [ ] A manifest whose `vendor.keyFingerprint` is not in the allowlist is rejected with `UnknownVendor`. Test: substitute a random fingerprint; reload; expect failure.
- [ ] A `ProvenanceRecord` is written for every successful outbound action and signed by Atlas. Test: send a Trial Finder packet; check `data/provenance.db` has a matching row; verify signature.

### 11.2 Three example plugins running end-to-end

Each example plugin must:

- [ ] Have a complete, signed manifest at `data/plugins/{id}/{version}/manifest.json`
- [ ] Appear in `/workspaces` catalog
- [ ] Render a plugin home with all five sections (hero, permissions, workflows, recent runs, about) from the manifest
- [ ] Start a run from any workflow card; consent card surfaces in chat
- [ ] Run all of its declared tools end-to-end against fixture connector responses
- [ ] Surface a `PluginApprovalRequest` before every outbound; clicking approve writes a `ProvenanceRecord`
- [ ] Render its workbench tabs with the manifest-declared renderers (no hardcoded plugin-specific branches in the shell)

### 11.3 Shell is plugin-agnostic

- [ ] No `if (workspace.id === "trial-finder")` branches in `components/atlas/*`. Search the codebase. All plugin-specific behavior comes through `manifest.ui` or renderer registry lookups.
- [ ] Adding a fourth plugin requires: writing a manifest JSON, writing a fixtures file, writing zero or one new renderer components. No edits to the shell.

### 11.4 Documentation

- [ ] `app/src/components/atlas/README.md` updated to reference the renderer registry + manifest loader
- [ ] `docs/architecture/AGENTIC-HARNESS.md` §10 status table flipped: "Plugin manifest loader: ✅ shipped"
- [ ] A `docs/daily/2026-MM-DD.md` snapshot capturing the build, with the rubric reproduced and every box checked

---

## 12. Test plan

### 12.1 Unit tests (backend)

```
api/tests/test_trust_models.py        Pydantic validation
api/tests/test_trust_signatures.py    ed25519 sign + verify, canonical JSON
api/tests/test_trust_redactions.py    each preset transforms inputs as expected
api/tests/test_plugin_manifest.py     load + verify happy path + 6 negative cases
api/tests/test_plugin_anchors.py      compile, sign, verify, expire
api/tests/test_plugin_consent.py      mint, verify, expire, revoke
api/tests/test_plugin_tools.py        permission enforcement per kind
api/tests/test_plugin_provenance.py   append-only + signed rows
api/tests/test_plugin_runtime.py      full run lifecycle for each example plugin
```

### 12.2 Frontend tests

- Vitest unit on `manifests.ts` (parse + shape)
- React Testing Library on `PluginHome` rendering each example plugin's manifest
- A Playwright e2e:
  - Visit `/workspaces/trial-finder` → plugin home renders
  - Click `Start new run` → consent card appears in chat
  - Click `Grant consent` → consent card replaced by agent's first turn
  - Open workbench `Candidate board` tab → trial-board renderer mounts
  - Click `Send packet` action → approval card appears
  - Click `Approve` → provenance row written (check via `/api/plugins/trial-finder/runs`)

### 12.3 Manual smoke

Walk the same flow for Medication Access and Second Opinion. Each should feel like a different product, sharing only the shell.

---

## 13. Open questions (settle before you start §11)

These are real architectural decisions the spec doesn't pin. Pick + record:

1. **Runtime validation library.** `zod` is reasonable for the frontend manifest parser. Backend is Pydantic. Confirm both choices.
2. **Signing library.** `pynacl` for backend ed25519 is the obvious pick. Frontend verification of anchor packages — use `@noble/ed25519`.
3. **Consent token format.** Sketch suggests signed JWT-like (compact serialization of `{pluginId, runId, scope, exp}` + ed25519 signature). Confirm.
4. **Approval ID generation.** UUIDv7 (sortable) or content-addressed hash? Lean UUIDv7.
5. **`marketplace-act` model preset** isn't defined anywhere in code today. Pick the actual model (Claude Sonnet? Haiku for cost?) and where the preset registry lives.
6. **Connector responses for fixture plugins.** v1 fixtures live as JSON in `data/plugins/{id}/fixtures/`. v2 routes through real connector adapters. Confirm fixture-first.
7. **PluginRun state machine.** Spec implies `awaiting-consent → running → (waiting | complete | failed | revoked)`. Confirm states + transitions + which fire events.
8. **Anchor refresh trigger.** Manual ("Refresh anchor" button on context strip) only, or also automatic on FHIR write event? Lean manual for v1.
9. **Provenance signature key rotation.** v1: single Atlas signing key, rotate manually. v2: per-org keys. Confirm v1 sufficient.
10. **Failure mode UI.** When `OutOfScope` / `UndeclaredConnector` / etc. fire, what surfaces in chat? Lean: surface as a `tool.result` event with `ok: false` + the error message, NOT as a clinician dialog. The agent reads the error and explains it.

---

## 14. Implementation order (the work queue)

If a single agent picks this up, do it in this order:

1. **Trust types** — finish `app/src/components/atlas/trust.ts` (extend per §2.3). One commit.
2. **Pydantic models** — `api/trust/models.py` end-to-end + tests. One commit.
3. **Signatures + canonical JSON** — `api/trust/signatures.py` end-to-end + tests. One commit.
4. **Redaction presets** — `api/trust/redactions.py` end-to-end + tests. One commit.
5. **Manifest loader + vendor allowlist** — `api/plugins/manifest.py` + `data/plugins/vendors.json` + tests. One commit.
6. **Three example manifests** — `data/plugins/{trial-finder,med-access,second-opinion}/{version}/manifest.json` + signature files + fixture connector responses. One commit per plugin.
7. **Anchor compiler** — `api/plugins/anchors.py` + tests. One commit.
8. **Consent tokens** — `api/plugins/consent.py` + tests. One commit.
9. **Tool registry + permission enforcement** — `api/plugins/tools.py` + tests. One commit.
10. **Provenance log** — `api/plugins/provenance.py` + tests. One commit.
11. **Run lifecycle** — `api/plugins/runtime.py` + tests. One commit.
12. **Routers + endpoints** — `api/plugins/routers/*` + tests. One commit.
13. **Frontend manifest loader** — `components/atlas/manifests.ts` + `useManifests` hook. One commit.
14. **Renderer registry** — `components/atlas/renderers/*` for every `WorkbenchRenderer` value. One commit per family (board, form, document, viewer).
15. **Refactor `PluginHome`** — read from manifest. One commit.
16. **Refactor `WorkbenchPane`** — read from renderer registry. One commit.
17. **Refactor `ContextStrip`** — read run state from active run. One commit.
18. **Wire approval flow** — chat → backend → provenance. One commit.
19. **Three plugins running end-to-end** — fixture connectors return realistic responses; full flow works for each. One commit per plugin.
20. **Acceptance pass** — walk the rubric in §11 and check every box. One commit per category to close it out.
21. **Snapshot + handoff** — write `docs/daily/2026-MM-DD-plugin-runtime.md` capturing the build.

Estimated: 12–18 commits, ~3–5 days for an Opus or Sonnet 4.6+ agent with a clear runway.

---

## 15. What to read again before you start

In this order:

1. This spec (you just read it — re-skim §11 the rubric)
2. `app/src/components/atlas/trust.ts` (extend, don't replace)
3. `docs/architecture/AGENTIC-HARNESS.md` (the why)
4. `app/src/components/atlas/data.ts` (the thing you're replacing)
5. `app/src/components/atlas/PluginHome.tsx` (the component you'll make manifest-driven)
6. `app/src/components/atlas/WorkbenchPane.tsx` (the component that gets the renderer registry)
7. `.claude/handoff/atlas/README.md` §"Caspian vs. Marketplace boundaries" (the boundary contract)

Then start at §14 step 1.

---

## 16. What to do if you get stuck

- If the spec is ambiguous, write down what you're doing and why, then ship the smaller decision. Don't ask a human — the human is asleep.
- If a Pydantic model can't validate something the JSON example shows, the JSON example is canonical. Update the model.
- If the frontend renderer doesn't have a kind it needs, add it to the `WorkbenchRenderer` union and write the renderer. Don't fake it with a generic renderer.
- If the rubric in §11 is impossible to satisfy with the current architecture, stop and document what you'd change. Don't fudge a test.

Good luck. This is the build that turns the Atlas redesign from a UI promise into a defensible product.
