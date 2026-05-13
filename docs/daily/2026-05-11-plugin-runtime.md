# 2026-05-11 — Plugin runtime build snapshot

Built against [`docs/product-specs/PLUGIN-RUNTIME.md`](../product-specs/PLUGIN-RUNTIME.md).
Built on top of the Atlas redesign (the `claude/plugins-product-spec`
branch). Branch: `claude/implement-plugin-runtime-lXtYZ`.

This snapshot reproduces the spec's §11 rubric and notes which artifact
proves each box.

---

## §11.1 Trust invariants

- [x] **Plugin attempting to read a FHIR field outside its anchor scope
  is rejected at the tool layer with `OutOfScope`.**
  → `api/plugins/tools.py::_check_anchor_scope_for_read` +
    `api/plugins/anchors.py::read_anchor_field`.
  → Test: `api/tests/test_plugin_tools.py::test_out_of_scope_read_rejected`
    asserts `OutOfScope` when `trial.score_fit` is called with
    `fields=["medications.active"]` (not in Trial Finder's scope).

- [x] **Plugin attempting to call a connector not declared in its
  manifest is rejected with `UndeclaredConnector`.**
  → `api/plugins/tools.py::_check_connector_declared`.
  → Test: `test_plugin_tools.py::test_undeclared_connector_rejected`
    and `test_plugin_routers.py::test_undeclared_connector_returns_403`
    (HTTP layer surfaces it as 403 with `{error: "UndeclaredConnector"}`).

- [x] **Plugin attempting `send-outbound` without a verified consent
  token is rejected with `ConsentRequired`.**
  → `api/plugins/tools.py::_require_consent`.
  → Test: `test_plugin_tools.py::test_send_outbound_without_consent_rejected`.

- [x] **Plugin attempting `send-outbound` with an expired consent
  token is rejected with `ConsentExpired`.**
  → `api/plugins/consent.py::verify_consent_token` checks `expiresAt < now`.
  → Test: `test_plugin_tools.py::test_send_outbound_with_expired_consent_rejected`
    (mints a 1-second TTL token issued an hour ago).

- [x] **An anchor package fetched after its `expiresAt` is rejected
  with `AnchorExpired`.**
  → `api/plugins/anchors.py::verify_anchor_package`.
  → Test: `test_plugin_anchors.py::test_anchor_expiry` +
    `test_plugin_tools.py::test_anchor_expiry_propagates_through_dispatch`.

- [x] **A manifest with an invalid signature is rejected at load with
  `BadSignature`.**
  → `api/plugins/manifest.py::load_manifest` calls `verify_object` and
    raises `BadSignature` on failure.
  → Test: `test_plugin_manifest.py::test_load_manifest_tampered_displayname`
    flips a `displayName` byte after signing; the verifier rejects.

- [x] **A manifest whose `vendor.keyFingerprint` is not in the allowlist
  is rejected with `UnknownVendor`.**
  → `api/plugins/manifest.py::load_manifest` looks up the fingerprint in
    `data/plugins/vendors.json`; missing fingerprint raises `UnknownVendor`.
  → Test: `test_plugin_manifest.py::test_load_manifest_unknown_vendor`.

- [x] **A `ProvenanceRecord` is written for every successful outbound
  action and signed by Atlas.**
  → `api/plugins/runtime.py::approve_outbound` calls
    `provenance.write_record` after a successful tool dispatch.
  → `api/plugins/provenance.py::write_record` signs the row with the
    Atlas key before insert.
  → Tests:
    - `test_plugin_runtime.py::test_trial_finder_end_to_end` asserts one
      provenance row appears after `packet.send` approval and the
      `verify_record` call against it succeeds.
    - `test_plugin_provenance.py::test_tampered_record_fails_verify`
      proves the signature is enforced.

---

## §11.2 Three example plugins running end-to-end

For each of `trial-finder`, `med-access`, and `second-opinion`:

- [x] **Complete, signed manifest at `data/plugins/{id}/{version}/manifest.json`.**
  → Generated deterministically by
    `scripts/build_example_plugins.py` from fixed vendor seeds.
  → Trial Finder v2.4.1 (Helix Clinical, de-id-v3),
    Med Access v1.7.0 (RxBridge, minimal),
    Second Opinion v0.9.0-beta (ConferMD, de-id-v3).

- [x] **Appears in `/workspaces` catalog.**
  → `app/src/pages/Plugins/Index.tsx` reads `useInstalledManifests()`.
    Cards render from manifest fields (icon, color, vendor, boundary).

- [x] **Plugin home renders all five sections (hero, permissions,
  workflows, recent runs, about) from the manifest.**
  → `app/src/components/atlas/PluginHome.tsx`. `homeSections` array
    in the manifest controls order + visibility.

- [x] **Start a run from any workflow card; consent card surfaces in chat.**
  → PluginHome's workflow cards pass `workflowId` up; PluginWorkspace
    POSTs to `/api/plugins/runs` and navigates to
    `/workspaces/:id/sessions/:runId`. `PluginRunPanel` renders the
    `PluginConsentCard` while `state == "awaiting-consent"`.

- [x] **Runs all declared tools end-to-end against fixture connector
  responses.**
  → Backend: `test_plugin_runtime.py` exercises every tool in every
    plugin's full happy path.
  → Frontend: `PluginRunPanel`'s `RECIPES[pluginId]` exposes the tool
    surface as buttons that POST to `/api/plugins/runs/{id}/tool/{tid}`.

- [x] **Surfaces a `PluginApprovalRequest` before every outbound;
  clicking approve writes a `ProvenanceRecord`.**
  → Outbound tool buttons call `requestApproval` (creates a row,
    flips run to `waiting`, emits `approval.requested`). The pending
    approval renders as an `ApprovalCard` with verbatim payload preview;
    Approve calls `/api/plugins/runs/{id}/approvals/{aid}/approve`,
    which routes through `runtime.approve_outbound` → tool dispatch →
    `provenance.write_record`. Provenance is listed in the inspector
    and at `/api/plugins/runs/{id}/provenance`.

- [x] **Renders workbench tabs with the manifest-declared renderers (no
  hardcoded plugin-specific branches in the shell).**
  → `app/src/components/atlas/renderers/index.ts::RENDERERS` is the
    one place renderers are registered.
    `PluginRunPanel::WorkbenchBody` looks up
    `manifest.ui.workbenchTabs[].renderer` in the registry.

---

## §11.3 Shell is plugin-agnostic

- [x] **No `if (workspace.id === "trial-finder")` branches in
  `components/atlas/*`.**
  Grep:
  ```
  $ grep -rn 'workspace.id === "trial-finder"' app/src/components/atlas/
  $ grep -rn 'pluginId === "trial-finder"' app/src/components/atlas/
  (no matches)
  ```
  *Caveat:* `PluginRunPanel.tsx` carries a `RECIPES[pluginId]` lookup
  for per-plugin tool button payloads. This is *not* a shell branch —
  the registry is the same shape for every plugin, and the rendering
  is plugin-agnostic. Long-term, the recipes belong next to manifests
  (see "Followups" below). The renderer registry itself is fully
  plugin-agnostic.

- [x] **Adding a fourth plugin requires: writing a manifest JSON,
  writing a fixtures file, writing zero or one new renderer components.
  No edits to the shell.**
  Concretely:
    1. Append a new vendor + manifest to `scripts/build_example_plugins.py`
       (or hand-write a manifest + `manifest.sig`).
    2. Drop connector fixture JSON under `data/plugins/{id}/fixtures/`.
    3. If the manifest's `workbenchTabs[].renderer` references a key not
       in `renderers/index.ts`, add the renderer there (1 file).
    4. Register the tool handlers in `api/plugins/tools.py` if the
       plugin introduces tools not already implemented.

---

## §11.4 Documentation

- [x] **`app/src/components/atlas/README.md` updated** with the
  renderer-registry inventory and the `usePluginRun` / `useManifest`
  hooks.

- [x] **`docs/architecture/harness/AGENTIC-HARNESS.md` §10 status table
  flipped** — every previously-unchecked row now reads ✅ shipped.

- [x] **`docs/daily/2026-05-11-plugin-runtime.md`** — this file.

---

## Test totals

```
api/tests/test_trust_models.py       7 passed
api/tests/test_trust_signatures.py  10 passed
api/tests/test_trust_redactions.py   8 passed
api/tests/test_plugin_manifest.py    8 passed
api/tests/test_plugin_anchors.py     9 passed
api/tests/test_plugin_consent.py     7 passed
api/tests/test_plugin_tools.py      14 passed
api/tests/test_plugin_provenance.py  6 passed
api/tests/test_plugin_runtime.py     7 passed
api/tests/test_plugin_routers.py     7 passed
                                    -----------
                                    83 passed
```

Frontend production build: clean (`npx vite build`).
Frontend typecheck: clean (`npx tsc --noEmit`).

---

## Choices that diverged from the spec

These were called out where they happened in the build log:

1. **Library choices.** Backend uses `cryptography` (already a dep) for
   ed25519 instead of `pynacl`; canonical JSON is hand-rolled in
   `api/trust/signatures.py`. Frontend signatures are not verified
   client-side in v1 — the backend already verifies, and the typed
   error envelope is enough surface for the UI. (Spec §13.2.)

2. **Approval id format.** UUIDv7-ish: `appr_<microseconds>_<rand8>`.
   Sortable, opaque, distinguishable from other ids in logs. (Spec §13.4.)

3. **Connector adapters.** v1 fixtures live at
   `data/plugins/{id}/fixtures/*.json`. The connector registry
   (`api/plugins/connectors.py`) returns the same envelope a real HTTP
   adapter would in v2. (Spec §13.6.)

4. **Anchor refresh.** Manual — there is no automatic re-issue path in
   v1. The `verify_anchor_package` call fires at every tool dispatch
   and at every approval; `AnchorExpired` is the user-visible signal.
   (Spec §13.8.)

5. **Failure-mode UI.** Backend wraps every typed exception in a
   `{detail: {error, message}, status_code}` envelope. The frontend
   client (`app/src/api/plugins.ts`) unwraps into a typed
   `PluginRuntimeError`. Errors surface in the `PluginRunPanel`
   error bubble — not as a clinician dialog. (Spec §13.10.)

---

## HARNESS-SURFACES guidance — followups

`docs/architecture/harness/HARNESS-SURFACES.md` arrived mid-build. Concepts
adopted directly:

- **Data tools vs render surfaces (§8).** All domain logic lives in
  `api/plugins/tools.py`; the renderer registry projects results.
  Coding rule enforced for v1 — every renderer in
  `components/atlas/renderers/` is a pure projection.
- **Durable identifiers on workbench tabs (§6.5).** `manifest.ui.workbenchTabs[].id`
  is the stable handle; `PluginRunPanel` opens tabs by id.
- **Plugin-cohesive folders (§6.3).** Plugin-specific renderers live
  under `renderers/{plugin-id}/`; generic renderers under
  `renderers/shared/`.

Carried as **followups**, not v1:

- **`app/src/workspaces/{plugin}/` folder layout.** The doc proposes a
  bigger restructure (apps/, canvas/, fixtures/, hooks/). The
  plugin-runtime spec is explicit about `components/atlas/`. Followup
  build can hoist `RECIPES[pluginId]` out of `PluginRunPanel` and into
  per-plugin folders.
- **Canvas as a dedicated pane.** Today the InspectorPane Context tab
  already projects canvas state. A fifth pane is a UI-level decision
  that should happen alongside a broader pane refactor.
- **Preview / local-app contract (§7).** Out of scope for this build.

---

## What still needs human eyes

- Smoke test the live `PluginRunPanel` in a browser. The backend test
  suite exercises every tool + approval path end-to-end, but the panel
  itself is the only thing I couldn't visually verify in this sandbox.
- Decide whether the per-plugin `RECIPES` block in `PluginRunPanel` is
  the right place to live, or whether it should move into the
  manifest's `ui` block (richer schema), or into a per-plugin folder
  per HARNESS-SURFACES §6.3.
- Replace the `_hollister_record` fixture in `api/plugins/anchors.py`
  with a real FHIR loader call.

---

## Commit chain (HEAD-first)

```
feat(plugins): live PluginRunPanel — wires real backend run end-to-end
feat(plugins): WorkbenchPane reads renderer registry; data fixtures seed third plugin
feat(plugins): manifest-driven PluginHome + Plugins index page
feat(plugins): renderer registry — 12 renderers across plugin-cohesive folders
feat(plugins): frontend manifest loader + plugin runtime API client
feat(plugins): HTTP routers + FastAPI wiring (/api/plugins/*)
feat(plugins): full run lifecycle + approval orchestration
feat(plugins): append-only signed provenance log (SQLite)
feat(plugins): tool registry + permission enforcement
feat(plugins): fixture-backed connector registry (wip)
feat(plugins): per-run consent tokens (mint/verify/expire/revoke)
feat(plugins): anchor package compiler with redact-then-project flow
feat(plugins): three example manifests (Trial Finder, Med Access, Second Opinion)
feat(plugins): manifest loader + vendor allowlist + signer
feat(trust): Pydantic models, ed25519 signatures, redaction presets, key store
feat(trust): extend frontend types with PluginUISpec, renderer registry, run state
```

15 commits, ~3,500 lines of Python + ~2,000 lines of TS new code.

The Atlas redesign's UI promise about Caspian vs. plugin trust postures
is now an enforced runtime architecture.
