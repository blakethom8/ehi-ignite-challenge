# Synthesis Layer (Patient Narrative + Augmentations) — Task Queue

> Scoped but **deferred**. Adds a "consumer pass" lifecycle to the pipeline: after the 13 specialist producer passes complete and the merged Bundle is assembled, run synthesis passes that produce derived insights for downstream agent consumption. Strategic context: `docs/daily/2026-05-07-ClaudeCode.md` Entry 9 idea #2 + #3.

**Status: ⛔ Awaiting product input on output schema and downstream consumption.** Do not dispatch builders until those questions resolve.

---

## Why deferred

This is a real architectural addition (not just a new pass — a new lifecycle pattern). Three product questions need answers first:

1. **Who consumes the synthesis output?** Clinical Insights chat (likely yes), patient journey UI (probably yes), Care Journey timeline (maybe), other agents (TBD). Each consumer's needs shape the schema differently.
2. **What's the right output shape?**
   - **FHIR Composition** with sections — interoperable, fits the bundle naturally, but verbose and constraining.
   - **Custom JSON** keyed off the bundle (e.g., `meta.extension[patient-narrative]`) — simpler, more flexible, less interoperable.
   - **Both** — Composition for the FHIR-native consumers, custom JSON for the agent-native consumers.
3. **How do we evaluate qualitative output?** F1 doesn't apply. Probably rubric-based human grading; possibly LLM-as-judge with calibrated rubrics. This question needs to be answered alongside the testing-platform deepening (Entry 9 testing escalation).

Without these answers, building the pass is premature.

---

## SYNTH-T01 (deferred) · PatientNarrative consumer pass

- **Status:** ⛔ Blocked on product Q1–Q3 above
- **Goal:** A new pass (lifecycle: consumer, runs after merger) that takes the assembled FHIR Bundle as input and emits a structured Patient Narrative.

### What's known about the output

Synthesis output candidates (per Entry 9):
- Chronological summary of key events
- Patterns / themes (allergic patient, metabolic-syndrome trajectory, etc.)
- Acuity periods (date ranges of high care intensity)
- Care episodes (medication courses, condition trajectories)
- Time-series trend descriptors per LOINC ("HbA1c rising 5.2 → 5.7 → 5.9 over 18 months")

### Open design questions

- **Date scope:** narrative covers all dates in the bundle, or a specific window (last 12 months / since-last-PCP-visit / etc.)?
- **Section granularity:** one section per theme? per organ system? per encounter? per year?
- **Verbatim vs derived:** does the narrative quote source text, or always paraphrase? (Quoting preserves provenance; paraphrase is more readable.)
- **Linkage back to source resources:** does each narrative claim carry a `Reference` to the FHIR resources that support it?

---

## SYNTH-T02 (deferred) · Augmentations module

- **Status:** ⛔ Blocked
- **Goal:** Smaller post-synthesis augmentations: episode segmentation, time-series summaries, provenance graph indexing, pre-computed Q&A targets.
- **Lifecycle:** runs after the Bundle is merged + LOINC-resolved + encounter-linked. Consumes the bundle, doesn't modify resources, emits sidecar data structures.

### What's known about the output

- **Episode segmentation:** group `MedicationRequest` resources into "courses" by drug + dose continuity; group `Condition` into "trajectories" by code + status changes.
- **Time-series summaries:** per-LOINC, descriptive summary across all observations of that test ("3 readings over 18 months, trending up").
- **Provenance lookups:** pre-built indexes — "facts derived from page X", "facts contributed by source Y".
- **Pre-computed Q&A:** common questions a downstream agent would ask, answered against the bundle. Open question: do we hardcode the question set, or have it driven by another LLM pass that proposes questions?

---

## SYNTH-T03 (deferred) · Synthesis-pipeline variant

- **Status:** ⛔ Blocked on T01 + T02
- **Goal:** Register `multipass-fhir-with-synthesis` (or similar) as a pipeline variant that runs the standard 13 specialist passes + post-passes + the synthesis layer. Most consumers will want this; the standard `multipass-fhir` will remain available for callers that just want the structured Bundle.

---

## What needs to happen before this queue dispatches

1. Product call on Q1–Q3 (consumers, schema, eval)
2. PDF-LAB-STUDIO infrastructure for narrative-quality grading (Entry 9 testing escalation)
3. At least one downstream consumer ready to integrate — otherwise we're building synthesis output that nothing uses

The bidirectional-scout build (`.claude/bidirectional-scout-queue.md`) is the active pipeline experiment this session. Synthesis is the next-natural addition once the producer-pass family is mature and the consumer-pass requirements are clearer.

---

*Created 2026-05-07. Deferred — do not dispatch.*
