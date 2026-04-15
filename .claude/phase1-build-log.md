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
