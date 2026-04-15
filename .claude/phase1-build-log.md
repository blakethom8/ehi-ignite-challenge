# Phase 1 Build Log

Append-only. The phase1-orchestrator writes one entry per completed (or failed) task. Entry format is documented in `.claude/agents/phase1-orchestrator.md` under "Build-log format."

---

### P1-T01 — Fix patient-id contract mismatch

**Shipped:** 2026-04-14
**Kind:** builder
**Rubric target:** Cat 3 Interpretability & Ease of Use (40 pts) · +5 expected
**Commit:** `31789ca`
**Files:**
- `api/core/loader.py` (+88 / −7) — UUID → filename-stem resolver with corpus-cache fastpath + bundle-scan fallback

**What it does:** Extends `path_from_patient_id()` so the loader accepts both ID shapes the frontend hands it — the filename stem (landing-page card path) and the FHIR Patient resource UUID from inside the bundle JSON (sidebar / corpus-cache path). The fix reads the existing `.corpus_cache.json` to build the UUID → stem map in O(1), with a full directory scan as a fallback when the cache is absent. The `lru_cache` on `_cached_load()` uses the canonical filename stem as its key in both cases, so the same patient never parses twice under two different keys.

**Root cause (deeper than the brief described):** the list endpoint returns `idx.patient_id`, which is the **FHIR Patient *resource* id** (set inside the bundle JSON), not a UUID embedded in the filename. A naive regex-on-filename approach would not have worked — the builder had to go through the corpus cache to get the correct resource-id → filename mapping.

**Verification:**
- **API smoke (bare UUID):** `/api/patients/5cbc121b-cd71-4428-b8b7-31e53eba8184/overview → 200` · patient = Aaron697 Brekke496 · `/key-labs → 200` · PASS
- **API smoke (filename stem, additive):** `/api/patients/Shelly431_Corwin846_9da0dcfc-.../overview → 200` · stem PASS
- **End-to-end UI re-verify (orchestrator, post-build):** reloaded `/explorer`, sidebar rendered 1,180 patient buttons, clicked `Shelly431 Corwin846 · 2282 resources`, URL became `/explorer?patient=eec393be-2569-46db-a974-33d7c853d690`, main body rendered `Surgery Hold — Review Required`, `Medications REVIEW · Conditions FLAGGED · Labs CLEARED`, `Top concern: Hypertension`, full stat cards, demographics, data span, and resource-distribution chart. **`Failed to load patient data.` is gone.**

**Judge impact:** closes the critical P0 blocker from `docs/JUDGE-WALKTHROUGH.md §2 Stop 2`. A judge picking any patient from the sidebar (the most natural interaction after landing in the Clinical workspace) no longer hits a broken state. Recovers the full +5 pts from Cat 3 cited in the walkthrough and removes the #1 "things a panelist would lose us points on" item from §5 of the walkthrough.

**Notes for the next cycle:**
- The API preview server was stopped during the builder's edit cycle and had to be restarted by the orchestrator before the UI re-verify. Sub-agents that edit Python files may cause uvicorn reload flaps — if a future cycle sees 502s in the network panel, check `preview_list` first.
- No changes required outside `api/core/loader.py`. `api/routers/patients.py` was not touched; the fix is purely additive in the loader.

---

### P1-T02 — Synthea R4 + no-PHI posture on header and landing

**Shipped:** 2026-04-14
**Kind:** refiner (first refiner dispatch of the Phase 1 loop)
**Rubric target:** Cat 4 Privacy, Security & Compliance (15 pts) · +5 expected (partial — see self-eval)
**Commit:** `feae7e5`
**Files:**
- `app/src/components/Layout.tsx` (+5 / −1) — persistent `Synthetic data · Synthea R4` chip in the top header
- `app/src/pages/Landing.tsx` (+4 / −0) — `No PHI · Synthetic Synthea R4 data · Local compute` footnote under the hero CTAs

**What it does:** Surfaces the submission's privacy posture as two always-visible, subordinate labels. The Layout-shell header chip renders on every `/explorer/*` and `/analysis/*` route (not `/`, which uses its own standalone header). The landing-page footnote renders directly below "Open Clinical Dashboard / Explore the Data". Both use middle-dot separators and design-system tokens — no new CSS, no marketing vocabulary.

**Verification:**
- **Landing (`/`, live preview re-verify):** `main.innerText` contains `"No PHI · Synthetic Synthea R4 data · Local compute"` on the line immediately following the two CTA buttons. PASS.
- **Explorer (`/explorer`, live preview re-verify):** `header.innerText` = `"EHI IGNITE\n\nSynthetic data · Synthea R4\n\nClinical Intelligence Workspace\n\nClinical\nData Lab"`. The posture chip is in the persistent header, visible on the first paint of any Clinical or Data Lab route. PASS.
- **Self-eval (from refiner):** "A panelist skimming explorer or any clinical view will see the 'Synthetic data · Synthea R4' chip within the first second — it is in the persistent header, top-left. The landing-page footnote lands before any scroll, directly under the primary CTA pair, and uses 'No PHI' and 'Synthetic' — the precise regulatory vocabulary a Cat 4 scorer looks for. The copy is dry and specific with no marketing vocabulary. These two changes plausibly recover most of the +5 Cat 4 delta, though full recovery of the category will also require a deeper HIPAA/compliance narrative — the header chip and footnote alone are a posture signal, not a compliance argument."

**Judge impact:** closes the #1 "losses remembered" item for Cat 4 from `docs/JUDGE-WALKTHROUGH.md §2 Stop 1` — there is now a posture statement visible on every screen a judge will see. Closes the Cat 4 gap from 7 → ~11 (partial); remaining delta to the 14-point target needs a compliance page (not yet queued).

**Notes for the next cycle:**
- The landing page uses a standalone header, not `Layout.tsx`. Any future task targeting "the header" needs to specify whether it means the Landing header or the Layout-shell header — they are separate components. Worth documenting in the next walkthrough pass.
- The refiner did not invent work outside the brief when it noticed the landing-header gap — exactly the behavior we want. The honest self-eval ("partial, not full +5") is the pattern for future refiner reports.

---

### DL-T02 — Surface the Data Lab from Clinical entry points

**Shipped:** 2026-04-14
**Kind:** builder (orchestrator collapsed the refiner-then-builder pattern — phrasing decided in the brief)
**Rubric target:** Cat 3 Interpretability (40) +2 · Cat 5 AI Innovation (+20) +2 · +4 expected total
**Commit:** `278f844`
**Files:**
- `app/src/pages/Explorer/Safety.tsx` (+12 / −0) — "Why you can trust this · Methodology →" chip on each safety card with an active flag
- `app/src/pages/Explorer/Assistant.tsx` (+15 / −1) — adjacent-line "See the methodology that built this context →" link rendered when `build_clinical_context` is in the trace
- `app/src/pages/Explorer/Overview.tsx` (+50 / −13) — Flight School banner in the empty state ("First time here? Take the 15-minute Flight School →")

**What it does:** Turns the Data Lab / Analysis section from a hidden rubric asset into a visible one. A judge walking only the Clinical side now hits three discoverability touch points that route into the existing Methodology and Flight School pages. This was flagged in `docs/JUDGE-WALKTHROUGH-DATALAB.md §4 DL-T02` as the single highest-ROI Data Lab task because no new content is authored — existing high-quality pages simply get surfaced.

**Judge impact (from DATALAB walkthrough §6 Takeaway 3):** *"The best explainability content in the submission is invisible to a reviewer who only walks the Clinical side."* Not anymore. A Cat 5 scorer reviewing the Safety Panel can one-click into the Methodology page; a Cat 5 scorer reading an Assistant response sees an anchor link to the same page; a Cat 3 scorer landing on the Clinical empty state is directed to the 15-minute curriculum that pre-loads the product's vocabulary before they walk the clinical surfaces.

**Change-2 implementation note (from builder):** The `ToolCallCard` component uses a `<button>` as its outermost element — wrapping a button in an `<a>` tag is invalid HTML. The builder took the documented adjacent-line fallback: a `<Link target="_blank" rel="noopener noreferrer">` rendered immediately after the `ToolCallsSection`, only when `build_clinical_context` is among the trace's tool calls. This is the correct call — forcing an anchor wrapper on the button would have been an HTML semantics bug.

**Verification:**
- **TypeScript strict check:** `npx tsc --noEmit` exit 0, no output
- **Vite build:** `✓ 1860 modules transformed, built in 918ms — no errors`
- **Safety Panel live check (orchestrator):** navigated to `/explorer/safety?patient=Shelly431_Corwin846_…`, `innerText` contains both "Why you can trust this" and "Methodology" on cards with active flags
- **Overview empty-state live check:** navigated to `/explorer` with no patient, `innerText` contains both "Flight School" and "First time here"
- **Assistant mount check:** navigated to `/explorer/assistant?patient=Shelly431_Corwin846_…`, page renders 69k characters of body content without error; adjacent-line link renders conditionally on tool-call presence (expected — only appears after an actual Assistant query is run)

**Notes for the next cycle:**
- The refiner agent was not invoked for this task. Collapsing refiner-then-builder into a single builder dispatch with orchestrator-decided copy is a valid pattern when the refiner pass is small (a few short phrases, known placements) and the implementation work is the dominant cost. Document this pattern in the orchestrator file next time the rules get edited.
- `EmptyState` import removed from `Overview.tsx` as a consequence of the Change 3 edit — legitimate cleanup, not scope creep. Builder correctly flagged it in NOTES.
- The Flight School banner's mint/teal palette (`#f0faf8` / `#b2e8e0` / `#187574`) matches the Data Lab theme already present in `TIER_STYLES`, reinforcing the visual bridge between the two modes without introducing new design tokens.
