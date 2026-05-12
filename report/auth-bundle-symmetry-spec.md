# Spec: Authenticated Bundle Symmetry + Snapshots Page Build-out

> Follow-on to the Guest pipeline work (commits `a93294d` + `7223a22`). The
> Guest experience now produces the canonical 26-file workspace ZIP and
> collects patient voice + audience inline; the authenticated path benefits
> from the bundle changes automatically but is missing three integrations
> that close the symmetry and unlock the Snapshots page. This spec covers
> three deliverables, each independently shippable.

---

## Context

After Phases 1–5 the bundle packager is unified, but the authenticated
side has gaps:

1. **Patient context never reaches the bundle.** `/patient-record/context`
   runs a rich gap-card intake that already writes a FHIR Bundle of
   patient voice (`data/patient-context/<patient>/fhir/<session>.json`)
   plus four markdown files (`PATIENT_CONTEXT.md`, `QUESTIONS.md`,
   `SOURCES.md`, `AGENT.md`). The workspace exporter ignores all of it,
   so authenticated users have two parallel export systems for the same
   patient.

2. **No audience selector at export.** Guests pick an audience in Step
   3 and the matching packet gets `primary: true`. The packager already
   accepts `WorkspaceInput.audience`; the authenticated route just
   doesn't pass it.

3. **The Snapshots page is minimal.** Phase 5 lifted the list
   component and routed the page, but it only renders snapshots with
   Activate buttons. The data exists for three additional affordances:
   per-snapshot bundle download, narrative version history, and
   side-by-side snapshot diffs.

Each deliverable is independent; ordering reflects user value, not
technical dependency.

---

## Deliverable 1 — Patient context flows into the authenticated bundle

### Why

A patient or clinician who walks through `/patient-record/context`
expects the resulting context to live in the same ZIP as the rest of
their chart. Today the context page produces its own markdown bundle
and the workspace export ignores it.

### What ships

When a workspace is exported for a patient with at least one
patient-context session, the ZIP gains:

- `context/PATIENT_CONTEXT.md` — copy of the session's main markdown.
- `context/QUESTIONS.md` — open + answered gap-card questions.
- `context/SOURCES.md` — source posture and gap checklist.
- `context/AGENT.md` — agent instructions for reading the bundle.
- `context/session.json` — structured `{patient_id, session_id, facts, gap_cards, generated_at}`.

Plus, the existing packets gain context:

- `packets/patient-summary.context.json:patient_voice` — populated from
  the session's facts (concatenated `f.summary` entries).
- `packets/patient-summary.context.json:patient_context_facts` — the
  full facts array (`[{id, summary, statement, created_at}]`).

The patient-voice FHIR Bundle is also injected as an additional source
in `WorkspaceInput.sources`, so the patient voice flows through
`build_evidence()` and contributes facts + provenance to
`evidence/canonical-facts.json` with provenance method
`patient_context_voice`.

### Files to modify

- `scripts/export_workspace_package.py`
  - Extend `WorkspaceInput` dataclass with `patient_context: dict | None = None`
    (containing `markdown_files`, `session_json`, `voice_summary`).
  - In `build_package_from_input()`, after writing existing files:
    - Write `context/*.md` entries from `workspace_input.patient_context["markdown_files"]`.
    - Write `context/session.json`.
    - Append the new files to `manifest_files`.
  - Update `build_packets()` to read `patient_voice` from `WorkspaceInput.patient_voice`
    (already supported) and add `patient_context_facts` from the new field
    when present.

- `api/core/patient_context.py` — new helper:
  - `def latest_session_for_patient(patient_id: str) -> dict | None` — walks
    `STORE_ROOT / patient_id /` directories, picks the most recent by
    `session_json["created_at"]`, returns `{session_id, session, markdown_paths, fhir_bundle_path}`.
  - `def load_session_artifacts(patient_id: str, session_id: str) -> dict` —
    reads `session.json`, the four markdown files, and the FHIR bundle
    if present.

- `scripts/export_workspace_package.py:workspace_input_from_collection()`:
  - Resolve `patient_id` from the harmonize collection (already available
    via `evidence["patient"]["id"]` shape, but we need it earlier).
  - Call `latest_session_for_patient(patient_id)`.
  - If a session exists:
    - Populate `WorkspaceInput.patient_voice` from concatenated facts.
    - Populate `WorkspaceInput.patient_context = {...}`.
    - Append the FHIR bundle as a new entry in `WorkspaceInput.sources`
      with `source_id="patient-context-voice"`, `kind="fhir-bundle"`,
      `resources=[...]` so `build_evidence()` picks it up.

- `scripts/validate_workspace_package.py:REQUIRED` — leave as-is; the
  context files are conditional, not required.

### API surface

No new endpoints. The existing `GET /api/harmonize/{id}/export-workspace`
gains the new files in its response ZIP automatically.

### Edge cases

- No context session exists yet → bundle is unchanged (graceful no-op).
- Multiple sessions → take the most recent one. Future: allow choosing
  a session via `?context_session_id=` query param.
- Session has zero facts → write `context/` markdown anyway (empty
  facts is meaningful — shows the user opened the page but didn't
  answer); leave `patient_voice` empty.
- FHIR bundle missing (no Anthropic key, generation failed) → still
  write markdown + session.json; don't inject a source.

### Verification

- New backend test `api/tests/test_workspace_export_patient_context.py`:
  - Seed a context session under a tmpdir-overridden `STORE_ROOT`.
  - Run the synthea export, assert ZIP contains `context/PATIENT_CONTEXT.md`
    and `packets/patient-summary.context.json:patient_voice` is non-empty.
  - Assert `evidence/canonical-facts.json` contains at least one fact
    with provenance method `patient_context_voice`.
- Manual: start API + app as an authenticated user, run `/patient-record/context`,
  answer 1-2 gaps, generate the markdown bundle, then click "Download
  workspace" from Publish Readiness and inspect the ZIP.

### Effort

~4–6 hours. One new core helper, ~50 lines in the packager, one new
test file.

---

## Deliverable 2 — Audience selector at authenticated export

### Why

Guests already get this; authenticated users don't. Same packager,
trivial plumbing.

### What ships

- `GET /api/harmonize/{id}/export-workspace?audience=preop-review` →
  the matching packet gets `primary: true`. Other behaviors unchanged.
- UI: an audience dropdown next to the "Download workspace" button on
  `PublishReadinessPage` and on the new Snapshots page.
- ZIP filename includes audience when set:
  `synthea-demo-preop-review.zip` (otherwise unchanged).

### Files to modify

- `api/routers/harmonize.py:export_workspace_package()`:
  - Add `audience: str | None = None` query param. Validate against
    `{"patient-summary", "clinician-handoff", "second-opinion", "preop-review"}`
    or `None`.
  - Pass to `workspace_input_from_collection(collection, audience=audience)`.
- `scripts/export_workspace_package.py:workspace_input_from_collection()`:
  - Accept optional `audience` kwarg, set on `WorkspaceInput`.
- `app/src/api/client.ts`:
  - `exportWorkspaceUrl(collectionId, audience?)` helper that returns
    the correct URL with optional query param (since the download is a
    plain anchor, not an axios call).
- `app/src/pages/PatientRecord/aggregator/shared.tsx`:
  - Add audience dropdown near the existing "Download workspace" link
    on `PublishReadinessPage`.
- `app/src/pages/PatientRecord/Snapshots.tsx`:
  - Add the same dropdown above the snapshot list (applies to per-row
    downloads from Deliverable 3a).

### API surface

```
GET /api/harmonize/{collection_id}/export-workspace
    ?audience=patient-summary | clinician-handoff | second-opinion | preop-review
    &include_originals=false
    &snapshot=<snapshot_id>   # see Deliverable 3a
```

All params optional; backward compatible.

### Edge cases

- Unknown audience value → return 400 with the allowed list.
- Audience supplied but no matching packet — impossible, packets are
  fixed; validator catches it first.

### Verification

- Update `api/tests/test_workspace_export_api.py` with a new test:
  `?audience=preop-review` → ZIP's `packets/preop-review.context.json:primary == true`.
- Manual: pick "Pre-op review" from the dropdown, download, unzip,
  verify only that packet has `primary: true`.

### Effort

~2 hours. ~20 lines backend, ~30 lines frontend, one test.

---

## Deliverable 3 — Snapshots page upgrades

Three sub-deliverables; each independently shippable.

### 3a — Download bundle pinned to a snapshot

#### Why

Today the export endpoint always builds against `latest.json`. If you
publish snapshot A, then re-harmonize, the bundle you download no
longer matches snapshot A. Pinned downloads give stable artifacts.

#### What ships

- `GET /api/harmonize/{id}/export-workspace?snapshot=<snapshot_id>` →
  bundle built against the run that snapshot pins, not the latest run.
- Per-row "Download" button on `SnapshotList.tsx`.
- ZIP cached at `data/workspace-packages/{collection}/{snapshot_id}.zip`
  so repeated downloads of the same snapshot are instant.

#### Files to modify

- `api/routers/harmonize.py:export_workspace_package()`:
  - Add `snapshot: str | None = None` query param.
  - If present, look up the snapshot via
    `api.core.published_charts.get_snapshot(collection_id, snapshot_id)`,
    get its `run_id`, pass `run_id` override to the adapter.
- `scripts/export_workspace_package.py`:
  - `workspace_input_from_collection(collection, *, audience=None, run_id=None)`:
    - If `run_id` is set, load `data/harmonization-runs/<collection>/<run_id>.json`
      instead of `latest.json`. (Today `load_harmonization()` only knows
      `latest.json` — refactor to accept run_id.)
- `app/src/api/client.ts`:
  - Extend `exportWorkspaceUrl()` from Deliverable 2 to accept
    `snapshot?: string` and emit `?snapshot=...`.
- `app/src/components/atlas/snapshots/SnapshotList.tsx`:
  - Add `onDownload?: (snapshotId: string) => void` prop.
  - Add a "Download" button per row when `onDownload` is set.
  - Backward compatible: when `onDownload` is absent (e.g., on the
    aggregator's existing Publish Readiness page), no download button
    renders.
- `app/src/pages/PatientRecord/Snapshots.tsx`:
  - Wire `onDownload(snapshotId)` to a function that builds the URL
    via the client helper and triggers an anchor download.

#### Edge cases

- Snapshot's underlying run file has been GC'd → 404 with "Snapshot
  source data no longer available; activate the snapshot to refresh."
- Cache invalidation: snapshots are immutable by design, so the cache
  is safe to keep forever. Manual cleanup if disk pressure becomes an
  issue.

#### Verification

- New backend test in `test_workspace_export_api.py`: publish run A,
  re-harmonize to run B, download bundle `?snapshot=<A>` — assert its
  facts match run A, not B.
- Manual: publish two snapshots, download each, diff the ZIPs.

#### Effort

~3 hours.

---

### 3b — Surface narrative version history

#### Why

`lib/narratives/storage.py:write_current_narrative()` already archives
every prior Composition to
`data/narratives/<patient>/<slug>/history/<timestamp>.json`. Nothing in
the UI exposes this. Authenticated users have no way to see how a
narrative evolved across runs.

#### What ships

- New backend endpoint
  `GET /api/patients/{patient_id}/episodes/{slug}/narrative-history` →
  list of `{archived_at, composition_id, replaces_id}` sorted newest-
  first.
- New backend endpoint
  `GET /api/patients/{patient_id}/episodes/{slug}/narrative-history/{timestamp}` →
  the archived Composition resource.
- New "Narrative history" panel on `Snapshots.tsx` below the snapshot
  list. Lists episodes; per-episode expandable list of versions, each
  with a "View" button that opens an `EpisodeNarrativeDrawer` showing
  the archived Composition.
- Bundle inclusion: `?include_narrative_history=true` query param on
  export-workspace adds `fhir/narratives/<slug>/history/<timestamp>.json`
  files alongside `current.json`. Default is `false` to keep bundles
  small.

#### Files to modify

- `api/routers/patients.py` (or wherever patient endpoints live):
  - Two new endpoints described above.
- `api/core/narrative_history.py` (new — thin):
  - `list_history(patient_id, slug) -> list[dict]` — walks
    `lib/narratives/storage.history_dir_for(...)`, returns sorted list.
  - `load_archived(patient_id, slug, timestamp) -> dict | None`.
- `app/src/api/client.ts`:
  - `getNarrativeHistory(patientId, slug)`.
  - `getArchivedNarrative(patientId, slug, timestamp)`.
- `app/src/components/atlas/harmonize-review/EpisodeNarrativeDrawer.tsx`:
  - Lift this component out of `PatientContextPanels.tsx` (was a Phase
    3 plan item I skipped). Accept either a `compositionQuery` (today's
    behavior) or a pre-loaded `composition` prop (used by history
    viewer).
  - Update `PatientContextPanels.tsx` to import from the new location.
- `app/src/components/atlas/snapshots/NarrativeHistoryPanel.tsx` (new):
  - Renders the per-episode history list with View buttons.
- `app/src/pages/PatientRecord/Snapshots.tsx`:
  - Render `<NarrativeHistoryPanel>` below `<SnapshotList>` when there's
    a patient_id in scope.
- `scripts/export_workspace_package.py`:
  - Extend `load_patient_narratives()` to optionally include history.

#### Edge cases

- No narratives for this patient → panel renders "No narratives yet —
  publish a snapshot to generate."
- History dir exists but is empty (first version, never replaced) →
  show only the "current" entry with "(current)" badge.

#### Verification

- New backend test: write three versions of a narrative via
  `write_current_narrative()`, hit the history endpoint, assert all
  three are listed in reverse-chronological order.
- Manual: publish twice with edits between, open the Snapshots page,
  expand the affected episode, verify both versions render with the
  correct dates.

#### Effort

~6–8 hours. Mostly UI work; the data layer is done.

---

### 3c — Side-by-side snapshot diff

#### Why

Today snapshot deltas are summarized in a one-line headline
(`change_summary.headline`). For a real "what changed" view you need
fact-level set diffs.

#### What ships

- New endpoint
  `GET /api/harmonize/{id}/snapshots/{a}/diff?against={b}` returns
  `{added: [...], removed: [...], changed: [{fact_id, before, after}]}`.
- New `SnapshotDiffModal.tsx` component (modal opened from a "Diff"
  button per snapshot row).
- "Diff vs previous" button per snapshot row in `SnapshotList.tsx`
  (defaults to comparing against the chronologically previous snapshot).
- "Diff vs…" menu lets the user pick any other snapshot to compare
  against.

#### Files to modify

- `api/core/published_charts.py`:
  - `def compute_snapshot_diff(collection_id, snapshot_a, snapshot_b) -> dict`:
    Load each snapshot's underlying run's canonical-facts. Set-diff by
    `fact_id`. For ids in both, compare `value`, `date`, `status`,
    `display`; classify as `changed` when any field differs.
- `api/routers/harmonize.py`:
  - New `GET /{collection_id}/snapshots/{snapshot_id}/diff` endpoint.
- `app/src/api/client.ts`:
  - `getSnapshotDiff(collectionId, a, b)`.
- `app/src/components/atlas/snapshots/SnapshotDiffModal.tsx` (new):
  - Three-column display: Added | Removed | Changed.
  - Search/filter within results.
- `app/src/components/atlas/snapshots/SnapshotList.tsx`:
  - Add `onDiff?: (snapshotId: string) => void` prop. Renders a Diff
    button per row when set. Backward compatible.
- `app/src/pages/PatientRecord/Snapshots.tsx`:
  - Wire the prop to a state-driven modal open.

#### Edge cases

- First-published snapshot has no chronological predecessor → render
  "Initial snapshot" badge; Diff button disabled with tooltip.
- Very large diffs (1000+ facts) → paginate or truncate at 200 with a
  banner; full diff still available via the API for programmatic use.
- Snapshot's underlying run file GC'd → 404 like 3a.

#### Verification

- New backend test in `test_published_charts.py`: build two runs
  differing by 1 added fact, 1 removed fact, 1 changed value; assert
  the diff endpoint returns exactly those three.
- Manual: publish, edit some facts, re-publish, click Diff — modal
  shows the changes.

#### Effort

~6–8 hours. Backend diff logic is mechanical set diff; UI is a
focused modal.

---

## Recommended sequencing

These are independent; the order below reflects user value, not
technical dependency.

1. **Deliverable 1 — patient context into bundle** (most impactful,
   ~half a day). Closes the parallel-export systems gap. Unlocks the
   thesis "all the patient's data — chart + voice — in one bundle the
   agent can use."

2. **Deliverable 2 — audience selector** (smallest, ~2 hours).
   Bundles naturally with 3a since both add params to the same
   endpoint and the same UI surfaces (Publish Readiness, Snapshots
   page).

3. **Deliverable 3a — snapshot-pinned download** (~3 hours). Makes
   the Snapshots page operational rather than informational. Stable
   downloadable artifacts that don't drift on re-harmonization.

4. **Deliverable 3b — narrative history** (~6–8 hours). Surfaces
   work that's already silently happening on every publish. Highest
   "wow factor" of the three Snapshots upgrades.

5. **Deliverable 3c — snapshot diff** (~6–8 hours). Nice-to-have;
   only needed if 3b plus the existing headline aren't enough for
   users to understand what changed. Could be deferred.

**Suggested first commit:** 1 + 2 + 3a bundled together. They share
files (`workspace_input_from_collection`, `Snapshots.tsx`,
`SnapshotList.tsx`, the export endpoint) and shipping them together
makes the Snapshots page genuinely useful in one stroke.

3b and 3c become natural follow-ons in a second commit.

---

## Files touched at a glance

| Deliverable | Backend | Frontend | Tests |
|---|---|---|---|
| 1 — Context into bundle | `scripts/export_workspace_package.py`, `api/core/patient_context.py` (+ helper) | (none required) | `api/tests/test_workspace_export_patient_context.py` (new) |
| 2 — Audience param | `api/routers/harmonize.py`, `scripts/export_workspace_package.py` | `app/src/api/client.ts`, `aggregator/shared.tsx`, `Snapshots.tsx` | `test_workspace_export_api.py` (extend) |
| 3a — Snapshot-pinned download | `api/routers/harmonize.py`, `scripts/export_workspace_package.py` | `app/src/api/client.ts`, `SnapshotList.tsx`, `Snapshots.tsx` | `test_workspace_export_api.py` (extend) |
| 3b — Narrative history | `api/routers/patients.py`, `api/core/narrative_history.py` (new) | `EpisodeNarrativeDrawer.tsx` (lift), `NarrativeHistoryPanel.tsx` (new), `Snapshots.tsx` | `test_narrative_history.py` (new) |
| 3c — Snapshot diff | `api/core/published_charts.py`, `api/routers/harmonize.py` | `SnapshotDiffModal.tsx` (new), `SnapshotList.tsx`, `Snapshots.tsx` | `test_published_charts.py` (extend) |

---

## Open questions for the user

1. **Multiple context sessions per patient.** Take the most recent
   only (V1 recommendation), or allow choosing via a session picker?
2. **Bundle filename when audience is set.** Use audience in filename
   (e.g., `synthea-demo-preop-review.zip`) or keep the existing
   `synthea-demo.zip`? Recommendation: include audience for clarity.
3. **Narrative history in bundle by default?** Recommendation: off by
   default, opt-in via `?include_narrative_history=true` to keep bundle
   size reasonable. The Snapshots UI shows history regardless.
4. **Diff default comparison.** Against chronologically previous
   snapshot (recommended), or against the active snapshot?
