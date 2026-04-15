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
