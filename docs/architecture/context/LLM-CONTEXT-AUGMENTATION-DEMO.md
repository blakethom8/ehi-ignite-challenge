# Phase 1 Demo — Walkthrough & Smoke

> Companion to [LLM-CONTEXT-AUGMENTATION-PLAN.md](./LLM-CONTEXT-AUGMENTATION-PLAN.md). Captures the 90-second submission video script and the verification steps.

## Demo patient

**Lorenzo669** — `Lorenzo669_Cuellar188_2c57a897-8381-44a6-920f-e074fa6f74cf`.

Picked because his Synthea chart carries:
- A rich cardiometabolic arc (Prediabetes → Diabetes → CKD → Hypertriglyceridemia → Metabolic Syndrome → Coronary Heart Disease) — the home for the lisinopril demo.
- A clean diagnostic-workup episode (Suspected lung cancer → NSCLC → TNM Stage 1, all within ~2 weeks of 2006-09).

These map to the two hand-seeded EpisodeOfCare resources in `data/narratives/Lorenzo669_Cuellar188_2c57a897-8381-44a6-920f-e074fa6f74cf/episodes.json` (T4 of the plan).

## 90-second video script

| t | Beat | What the reviewer sees | Asserted by smoke |
|---|---|---|---|
| 0:00–0:10 | Upload Cedars + Function Health PDFs into a Lorenzo669 workspace. | Existing upload + harmonize flow runs. | n/a (existing) |
| 0:10–0:25 | Open Patient Context. Patient says: *"I stopped lisinopril about 3 weeks ago — was making me cough. Also taking fish oil every morning, my cardiologist suggested it."* Click Export. | A FHIR Bundle is written under `data/patient-context/<patient>/fhir/<session>.json` with one stopped `MedicationStatement` for lisinopril (effectivePeriod.end ~25d before today) and one active for fish oil. | **Beat 2** of `scripts/demo_smoke.py` |
| 0:25–0:40 | Click Harmonize. Open the merged record. The lisinopril row shows **status: stopped** with three source chips (Cedars [active], FH [active], Patient [stopped]). Hover the Patient chip → the turn is quoted verbatim. Provenance trail: Patient → turn → session. | The merged `MergedMedication` has `canonical_status="stopped"`, and `mint_provenance(...)` attaches `resolution-rule = patient-voice-status-override` on the patient-voice entity (and only there). | **Beat 3** |
| 0:40–0:55 | Open the "Care episodes" panel. Two cards: "Cardiometabolic management" + "Lung cancer workup". Click the first → drawer with one-page narrative; the "Patient's own words" section quotes the lisinopril turn verbatim. | Both episodes' `current.json` Compositions write to disk; each has all five required sections; the cardiometabolic narrative's "Patient's own words" section is non-empty. | **Beat 4** |
| 0:55–1:15 | Open Caspian. The first sentence of its greeting is: *"In the patient's own words: stopped lisinopril ~3 weeks ago due to cough; started fish oil daily on cardiology recommendation."* Ask: *"Is this patient on any ACE inhibitors?"* The response cites both the patient turn and the Cedars contradiction. | `ClinicalContext.to_prompt()` leads with `"In the patient's own words: ..."` before the structured sections; episode briefs render under `## CARE EPISODES`. | **Beat 5** |
| 1:15–1:30 | Open "Conflicts to review." One caveat: *Lisinopril active status — verdict: stopped (high confidence). Rationale: Patient asserted stoppage 2026-04-20; Cedars active flag has not been refreshed since 2025-09.* | `caveats.json` parses to a `HarmonizationCaveat` with `verdict="stopped"`, confidence high, dissenting Cedars + FH sources. *(T7 — Phase 1 stretch; not yet shipped in this branch.)* | **Beat 6 — pending T7** |

## Running the smoke

```
uv run python scripts/demo_smoke.py
```

Exits 0 on success, prints which beat broke on failure. Uses `Fake*`
backends throughout, so no Anthropic budget required.

Beats 1–5 are validated by the smoke today. Beat 6 (caveats panel) is
Phase 1 stretch (T7 in the plan); when the adjudicator ships, the
smoke gains a beat that loads `caveats.json` and checks at least one
entry exists.

## Required artifacts to make the demo runnable in the live app

| Artifact | Built by | Location |
|---|---|---|
| `episodes.json` | `scripts/seed_demo_episodes.py` (committed) | `data/narratives/<patient>/episodes.json` |
| Patient Context FHIR bundle | T1 — runs on `export_markdown()` | `data/patient-context/<patient>/fhir/<session>.json` |
| Per-episode Composition | T5 — runs from T6 publish hook | `data/narratives/<patient>/<slug>/current.json` |
| Voice summary | T8a — runs from T6 publish hook | `data/patient-context/<patient>/voice_summary.json` |
| Caveats | T7 (stretch) | `data/patient-context/<patient>/caveats.json` |

## Frontend handoff

T8c — the UI panels (Patient's-Words card, Care Episodes drawer,
Conflicts panel) — is **not** built in this branch. Backend handoff:

- `ClinicalContext.patient_voice` carries `summary` + `citations` (turn ids). UI should render the summary as a card at the top of the merged-record page; clicking opens the session's Patient Context turns.
- `ClinicalContext.episode_briefs` is a list of `{episode_id, type, period_start, period_end, one_liner}`. UI should render each as a card; click → drawer that loads the corresponding `current.json` from `/api/narratives/<patient>/<episode-slug>/current` (endpoint TBD; the data is on disk now).
- `ClinicalContext.caveats` is a list of `{fact_path, verdict, confidence, rationale, dissenting_sources}`. UI should render under "Conflicts to review"; low-confidence entries (carry `caveat-blocker=true` extension in the underlying FHIR) get a blocker badge.

## Out of scope for Phase 1

- T7 conflict adjudicator (stretch).
- T8c frontend panels.
- A new HTTP endpoint to read narrative `current.json` from the frontend — the merged-record page can read directly from `data/narratives/...` over the existing static-file route, or the next agent adds `GET /api/narratives/{patient_id}/{episode_slug}`.
