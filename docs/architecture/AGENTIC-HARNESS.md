# Agentic Harness — Caspian vs. Plugins

> Where the architecture promise lives. The frontend redesign in
> `claude/atlas-phase-1-tokens-31Kmr` makes a UI promise about two
> distinct trust postures sitting inside one shared shell. This
> document is the contract for the runtime that has to enforce it.
>
> Status: **Architecture decision, not yet enforced.** Frontend
> structure aligns with this; backend does not. See §10 for what's
> built vs. what's stubbed.

---

## 1. The thesis

Atlas is one shared agentic harness with two workspace families.

```
                    SHARED HARNESS
              (workspace shell + primitives)
                          │
              ┌───────────┴───────────┐
              │                       │
          CASPIAN                  PLUGINS
       first-party,            installable,
       full trust              consented boundary
```

The user sees the same five-pane workspace in both cases — that's the
point of the shared shell. **The runtime, accountability, and data
scope are genuinely different.** Treating them as the same thing under
the hood would erase the trust posture the UI is advertising.

One-liner:

> **Caspian is a trusted clinical co-pilot. A plugin is an attested,
> sandboxed, consented service.**

---

## 2. What MUST be shared

The interaction contract. These are codified in
`app/src/components/atlas/`:

- Five-pane workspace layout (`WorkspaceFrame`, sessions / chat /
  workbench / files / inspector)
- Pane resizers, toggles (S/C/P/F/I), localStorage persistence
- Chat protocol: turns, tool traces, citation chips, action chips,
  approval cards
- Workbench tab system + artifact preview
- Files pane + pinned objects
- Inspector pane (Evidence / Trace / Context tabs)
- Session lifecycle + event stream
- Tool-call envelope format
- Citation chip → inspector flow

Both Caspian and any plugin sit inside a `WorkspaceFrame` and produce
the same kinds of typed events. The shell is durable; the runtime is
where the divergence lives.

---

## 3. What MUST differ

| Concern | **Caspian** | **Plugin** |
|---|---|---|
| **Identity** | Runs as the clinician. | Runs as the plugin (vendor identity), with a delegated patient-anchor token. |
| **Data access** | Direct SQL-on-FHIR. Full chart. | Reads a *signed anchor package* — a curated, redacted slice. Cannot widen scope. |
| **Tool registry** | Full clinical tools (`fhir.search`, `fhir.read`, `artifact.draft`, `approval.request`). | Only declared tools from the plugin manifest. Outbound tools gated. |
| **Approvals** | Clinical-state changes ("apply this 48 h apixaban hold"). | Boundary crossings ("send this packet to MSKCC"). Different shape, different audit log. |
| **Sandbox** | None — trusted runtime. | Isolated execution. Plugin cannot reach Caspian state; communicates only via declared tools. |
| **State** | Atlas DB, clinician-visible. | Per-plugin working folder. Vendor *may* persist their own state with its own retention. |
| **Lifecycle** | Always available. Atlas owns it. | Installable, removable, versionable. Per-org enable/disable. Manifest-driven upgrades. |
| **Audit** | Clinical access log (who saw what when). | **Provenance log** — signed record per outbound action: vendor identity + version + run id + redaction preset + approver. |
| **Model preset** | Atlas's clinical-tuned default. | Plugin can declare a preset (within Atlas's allowlist). |
| **Manifest** | None — Caspian *is* the platform. | `manifest.json` — declared permissions, connectors, exports, consent requirements, signature. |
| **Boundary pill (UI)** | 🔒 *Private patient boundary* (green) | 🌐 *Consented external* (amber) |
| **Entry view** | Most recent session. | Plugin home — permissions ledger, workflows, recent runs. |
| **Approval scope** | Per-action. | Per-run *and* per-action; outbound packets need a per-run consent gate before per-action approvals fire. |

---

## 4. The trust contract — types

These are the types the frontend should hold (Phase 2 of the cleanup
adds them as a stub at `app/src/components/atlas/trust.ts`). The
backend should refuse to mint or honor any value that doesn't satisfy
the corresponding Pydantic model.

```ts
// What a vendor publishes.
type PluginManifest = {
  id: PluginId;                       // e.g. "trial-finder"
  version: string;                    // semver
  vendor: VendorIdentity;             // signed identity
  signature: string;                  // signs the rest of the manifest
  permissions: Permission[];          // declared scope of patient anchor
  connectors: Connector[];            // external systems it will call
  exports: ExportKind[];              // what it can produce
  requiresConsent: boolean;           // outbound boundary?
  modelPreset?: ModelPresetId;        // within Atlas's allowlist
};

// What the plugin actually receives at run time.
type AnchorPackage = {
  pluginId: PluginId;
  patientId: string;
  scope: AnchorScope;                 // e.g. ["diagnosis", "biomarkers"]
  redactions: RedactionPreset;        // de-identification preset applied
  signature: string;                  // signed by Atlas
  issuedAt: string;
  expiresAt: string;                  // anchor packages expire
};

// What the audit log records for every outbound action.
type ProvenanceRecord = {
  runId: string;
  pluginId: PluginId;
  pluginVersion: string;
  vendor: VendorIdentity;
  action: OutboundActionKind;         // "send_packet" | "register_patient" | …
  approver: UserIdentity;
  redactionPreset: RedactionPreset;
  artifactId?: string;                // what was sent
  ts: string;
};
```

Caspian has none of these. It runs against the patient's actual
record under the clinician's identity.

---

## 5. Backend split

Today's `api/` doesn't enforce any of this. The intended shape:

```
api/
  workspace/                          ← shared
    sessions.py                       session CRUD (both use)
    events.py                         event stream (both use)
    artifacts.py                      durable artifacts (both use)
    tools/
      envelope.py                     tool-call protocol (both use)

  caspian/                            ← first-party only
    fhir_tools.py                     direct chart access
    clinical_approvals.py             clinical-state approvals
    clinical_audit.py                 clinical access log

  plugins/                            ← plugin runtime only
    manifest.py                       load + verify plugin manifest
    anchors.py                        compile + sign patient anchor package
    sandbox.py                        run plugin tools in isolated context
    consent_gate.py                   outbound-boundary approval flow
    provenance.py                     cross-boundary audit log
    registry.py                       install / upgrade / disable

  trust/                              ← shared types + verification
    models.py                         Pydantic mirrors of trust.ts
    signatures.py                     signing / verification
```

Three things matter most for the first real plugin run:

1. **Manifest verification** — the plugin can't run if its manifest
   isn't signed by an allowlisted vendor key.
2. **Anchor compilation** — the plugin only sees what's in the anchor.
   The anchor is constructed server-side; the plugin can't ask for more.
3. **Consent gate** — outbound actions block on a per-run approval card
   surfaced in the user's chat.

Sandbox + provenance are necessary but can be added incrementally
once the manifest + anchor + consent loop is real.

---

## 6. Frontend marker (today)

The only thing currently encoding the distinction in code is one
field:

```ts
// app/src/components/atlas/types.ts
type Workspace = {
  …
  family: "clinical" | "plugin";
  …
};
```

`family === "clinical"` selects the Caspian context strip + Caspian
chat boundary pill. `family === "plugin"` selects the plugin context
strip + amber boundary pill + run-state chip.

This is enough for visual fidelity. It is **not** enough to enforce
trust. A misconfigured fixture could give a plugin direct FHIR access
because nothing in the runtime checks.

---

## 7. Why this matters for the product

Three concrete consequences:

1. **A plugin should never be able to read a medication list it didn't
   declare in its anchor scope.** Today the frontend uses the same
   `useWorkspaceState` hook for both. The hook reads from a fixture
   and doesn't enforce scope. The first real backend wiring must.

2. **A plugin's outbound packet must carry a provenance record.** When
   Trial Finder sends an outreach packet to MSKCC, every downstream
   audit needs to know: *who* approved it, *which* version of the
   plugin produced it, *what* redaction preset was applied. Caspian
   has no analog — it doesn't send packets externally.

3. **A plugin can be revoked.** If TrialOps is removed from the org
   in 2027, every running session under that plugin must terminate;
   any pending outbound action must be voided. Caspian can never be
   revoked — it's the platform.

If we don't encode this, the marketplace story is theatre. The Atlas
spec is explicit: the boundary pill is a promise the runtime has to
keep.

---

## 8. Approvals are different (and the chat shows it)

| Approval shape | Caspian | Plugin |
|---|---|---|
| **Trigger** | Clinical state change (apply hold, mark cleared, draft order) | Outbound boundary crossing (send packet, contact registry, write external record) |
| **Approver** | Clinician (the user). | Clinician *plus*, optionally, an attending in the loop. |
| **Granularity** | Per action. | Per run (consent gate) + per action (each outbound). |
| **Audit row** | Clinical audit log. | Provenance record (signed). |
| **Reversible?** | Often (draft → revise). | Rarely (packet sent is sent). |

The frontend `ApprovalCard` component is shared. The *shape* of the
approval data the card renders is different between families.

---

## 9. Open questions for the next pass

1. **Sandbox model.** Are plugin tools executed in-process with a
   capability check, or in a separate worker / container? Trade-off
   between latency and isolation guarantees.
2. **Anchor refresh.** What happens when a Caspian session adds a new
   condition mid-run while a Trial Finder plugin is already running on
   an anchor compiled before that change? Re-issue, or stale?
3. **Vendor identity attestation.** Do we self-sign vendor keys for
   the marketplace, federate to a registry (similar to npm), or
   require attestation per-org install?
4. **Plugin → plugin composition.** Can a plugin's output become
   another plugin's input? (e.g. Trial Finder → Site Coordination.)
   If yes, who consents, and where does provenance chain?
5. **Caspian-as-publisher.** The Caspian team might publish secondary
   Caspian-branded plugins eventually. How do we mark "first-party
   plugin" vs. "third-party plugin"? Is that a distinct trust tier?

---

## 10. Status

- [x] **Frontend structure** — `pages/Caspian/` and `pages/Plugins/` separated; module bar + workspace shell distinguishes families visually.
- [x] **Frontend marker** — `Workspace.family: "clinical" | "plugin"` drives context strip + boundary pill.
- [ ] **Frontend trust types** — `AnchorPackage`, `PluginManifest`, `ProvenanceRecord` are not yet in code. (See §4.)
- [ ] **Backend enforcement** — `api/` has no awareness of the distinction. All the differentiation in §3 is currently aspirational.
- [ ] **Manifest loader** — no plugin manifest format defined; current fixture is hardcoded in `components/atlas/data.ts`.
- [ ] **Anchor compiler** — no anchor package mechanism; plugins read whatever the fixture exposes.
- [ ] **Consent gate** — `ApprovalCard` UI exists; the run-blocking semantics behind it don't.
- [ ] **Provenance log** — not started.

The frontend redesign is what shipped. This document is the contract
for what the runtime has to look like to honor the UI promise.

---

## Cross-references

- `.claude/handoff/atlas/README.md` — the Atlas product spec (boundary pill table is in §"Caspian vs. Marketplace boundaries")
- `design/agentic-shell-spec/02-workspace-model.md` — workspace package anatomy + first-party vs. marketplace contract
- `design/agentic-shell-spec/01-shell-spec.md` — shell roles, pane contracts, interaction model
- `app/src/components/atlas/README.md` — current shared-component inventory
- `app/src/components/atlas/types.ts` — current `Workspace.family` marker
- `app/src/components/atlas/trust.ts` — (after this commit) frontend trust-boundary type stubs
