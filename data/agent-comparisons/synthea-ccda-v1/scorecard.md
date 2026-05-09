# EHI Atlas Agent Comparison Scorecard — Synthea + C-CDA V1

Date: 2026-05-08
Dataset: `data/agent-comparisons/synthea-ccda-v1`

## Arms compared

| Arm | Inputs | Output |
|---|---|---|
| Raw | `ehr-snapshot-2018.json`, `ehr-snapshot-2024.json` | `arms/raw/outputs.md` |
| Package | `synthea-demo-with-ccda.zip` only | `arms/package/outputs.md` |
| Package + raw | `synthea-demo-with-ccda.zip` first, raw files for spot-checking | `arms/package-plus-raw/outputs.md` |

## Executive finding

The comparison supports the core hypothesis:

> Prepared, provenance-backed evidence makes agent outputs more traceable, reusable, and source-aware than raw-file reading alone.

The raw arm produced a strong narrative from the two FHIR files, but it entirely missed the C-CDA medication/problem source because it was not part of the raw arm inputs. The package arms immediately surfaced the C-CDA as a first-class source, cited provenance IDs, disclosed missing allergy data, identified lipid conflicts from `conflicts.json`, and produced more reusable chart/source-contribution outputs.

The best overall result was **package + raw**: the package provided structure/provenance, while raw files filled in status/dose/context fields that the V1 canonical facts currently omit.

## Scores

Scale: 1 = poor, 5 = excellent.

| Dimension | Raw | Package | Package + raw | Notes |
|---|---:|---:|---:|---|
| Correctness | 4 | 4 | 5 | Raw was accurate for its two FHIR files, but lacked C-CDA. Package captured the full prepared package. Package+raw verified status/details. |
| Completeness | 3 | 4 | 5 | Package arms included C-CDA-only problems/meds and package-level missing-info/conflict signals. |
| Traceability | 3 | 5 | 5 | Raw cited filenames/resource IDs; package arms cited fact IDs, source refs, and provenance refs. |
| Interpretability | 4 | 4 | 5 | Package+raw was the clearest: concise clinical handoff with uncertainty labels. |
| Cross-source reasoning | 3 | 5 | 5 | Package source-contribution file made shared/unique facts explicit. Raw inferred across two snapshots only. |
| Missing-info handling | 4 | 5 | 5 | Package arms used explicit `missing-information.json`; raw inferred missing allergies/reference ranges manually. |
| Chart readiness | 4 | 5 | 5 | Package arms used canonical facts/labs export and preserved conflicts instead of collapsing duplicates. |
| Reusability | 3 | 5 | 5 | Package outputs are keyed to reusable fact/provenance/source IDs. Raw output is mostly prose/table extraction. |
| Auditability | 4 | 5 | 5 | Package audit used structured provenance. Package+raw also documented when raw was used to fill omitted canonical fields. |
| **Average** | **3.56** | **4.67** | **5.00** | Prepared evidence materially improved traceability and reuse. |

## What raw did well

- Produced a coherent patient summary from FHIR bundles.
- Found the 2018 lipid conflicts by inspecting raw observations.
- Noted creatinine/eGFR discordance.
- Noted missing allergies and missing reference ranges.
- Built a usable lab table.

## Raw limitations observed

- No durable source-contribution map; it had to infer source differences manually.
- Citations were less standardized: filenames and resource IDs rather than canonical fact/provenance IDs.
- No packaged C-CDA input, so it missed hypertension, cerebral infarction, COPD, and older medication facts contributed by the C-CDA source.
- Reuse would require repeating the extraction/reasoning process in each new agent session.

## What package did better

- Used `MANIFEST.json` and package source inventory to identify all sources.
- Included C-CDA-derived facts as first-class evidence.
- Used `source-contributions.json` to explain shared vs unique facts.
- Used `conflicts.json` to identify four 2018 lipid conflicts directly.
- Used `missing-information.json` to state no allergy list facts were found.
- Cited facts/provenance/source refs consistently.

## What package + raw did best

- Used package evidence first, then raw files for details that V1 canonical facts omit.
- Verified raw status/dose details for medication/condition currentness.
- More carefully distinguished supported facts from interpretation.
- Best clinician handoff and agent-audit sections.

## Product implications

1. **The package is the product proof.** The zip converts scattered source data into a portable evidence workspace that another agent can use immediately.
2. **The evidence layer improves traceability.** Provenance/source refs make claims easier to audit than ad hoc raw-file citations.
3. **Hybrid is the right operating model.** Structured package first, raw files available for verification/gap investigation.
4. **V1 canonical facts need richer fields.** Raw spot-checking helped because canonical facts currently omit some clinical status, dose, and reference-range details.
5. **C-CDA support is strategically important.** Even lightweight C-CDA normalization added clinically meaningful problems/medications that were absent from the two FHIR snapshots.

## Recommended report language

> In an internal comparison, an agent given raw FHIR files produced a reasonable summary, but an agent given the EHI Atlas workspace package produced more traceable and reusable outputs. The package exposed source contribution, provenance, missing allergy documentation, same-day lipid conflicts, and C-CDA-only problem/medication facts without requiring the agent to rediscover those structures from scratch. The strongest result came from a hybrid mode: use the patient-owned workspace package first, then inspect raw files only to verify or fill gaps.

## Next engineering improvements

- Preserve raw clinical status, medication dose/timing, and reference ranges in canonical facts.
- Add richer C-CDA normalization for allergies, encounters, sections, and medication status/end dates.
- Add an automated scoring helper that checks each arm for provenance refs, missing-info mentions, conflict mentions, and source-contribution coverage.
- Include this scorecard as a compact table in the Phase 1 narrative.
