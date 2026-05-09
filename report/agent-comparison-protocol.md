# Agent Comparison Protocol — Raw Files vs Portable Workspace Package

Date: 2026-05-08
Status: build-ready evaluation design

## Goal

Test whether a patient-owned evidence workspace improves agent performance compared with giving the same agent raw files directly.

This is the key evidence for the submission's portability claim:

> Atlas does not need to be the only agent. Atlas creates a structured workspace that makes many agents more transparent, traceable, and useful.

## Comparison arms

### Arm A — Raw files only

Give the agent a folder/zip of raw inputs:

- PDFs
- C-CDA XML
- FHIR JSON
- lab reports
- portal exports

Prompt it to answer questions and build summaries directly.

### Arm B — Portable workspace package

Give the same agent the EHI Atlas exported package:

- `MANIFEST.json`
- `AGENT-INSTRUCTIONS.md`
- evidence files
- provenance
- source contributions
- conflicts
- missing information
- context packets
- exports

Prompt it with the same tasks.

### Arm C — Portable workspace + raw files

Give the agent both the workspace package and the original raw sources.

Instruction:

- use structured evidence first
- inspect raw sources only to verify or resolve gaps
- cite provenance where possible

This may be the most realistic production pattern.

## Agents to compare

- Claude / Claude Code
- Codex
- Optional: local model if convenient
- Optional: Atlas assistant using same context packets

## Test datasets

### Dataset 1 — Lab PDF with gold output

Purpose:

- extraction correctness
- abnormal lab summary
- chart-ready output
- source traceability

Inputs:

- corrected lab report PDF
- existing Opus gold output
- Atlas extracted/harmonized output

### Dataset 2 — Multi-source synthetic workspace

Purpose:

- source contribution
- cross-source deduplication
- missing information
- handoff generation

Inputs:

- Synthea split snapshots / `synthea-demo`
- any staged extracted PDF bundle if available
- Atlas workspace package

### Dataset 3 — C-CDA + PDF + FHIR mixed source

Purpose:

- prove C-CDA is a supported input, not the intelligence layer
- mixed-format portability

Inputs:

- Josh Mandel sample C-CDA if available/safe
- FHIR bundle
- PDF lab or health summary
- Atlas workspace package

## Standard prompts

Use the same prompts for each arm.

### Prompt 1 — Patient summary

> You are helping a patient understand their medical record. Produce a concise, plain-language summary of the five most important things in this record. Include what changed recently, what information appears missing, and what the patient should ask their doctor. Cite sources for important claims when source information is available.

### Prompt 2 — Clinician handoff

> Create a one-page clinician handoff for a specialist reviewing this patient. Include active medications, allergies, key conditions, recent abnormal labs, missing information, and source citations. Do not invent facts. If evidence is unclear, say so.

### Prompt 3 — Source contribution

> Explain what each source contributed to the patient record. Identify facts that appear in more than one source, facts unique to a source, and any conflicts or duplicates that require review.

### Prompt 4 — Chart-ready labs

> Create a chart-ready table of kidney, liver, metabolic, and hematology labs over time. Include test name, date, value, unit, reference range, abnormal flag, and source. State which labs are missing or not comparable.

### Prompt 5 — Agent audit

> Audit your own answer. List every important claim, the source or evidence you used, and any claim that lacks adequate support.

## Scoring dimensions

Score 1–5.

| Dimension | What to evaluate |
|---|---|
| Correctness | Factual match to gold/source review. |
| Completeness | Captures key facts and relevant absences. |
| Traceability | Important claims cite source/provenance. |
| Interpretability | Output is readable and useful to target audience. |
| Cross-source reasoning | Dedupes and compares sources correctly. |
| Missing-info handling | States gaps clearly. |
| Chart readiness | Produces structured tables usable for charts. |
| Reusability | Output can feed other tasks, not just prose. |
| Auditability | Agent can explain what evidence supported each claim. |

## Expected outcomes

The workspace package should improve:

- source citation quality
- cross-source deduplication
- missing information disclosure
- chart-ready outputs
- self-audit quality
- consistency across agents

Raw files may still be competitive for:

- broad narrative summarization
- unknown document exploration
- finding surprising facts outside current schemas

This is acceptable. The claim is not that structure replaces agent intelligence. The claim is that structure gives agent intelligence a better workspace.

## Report-ready language after running test

If successful:

> In comparison testing, agents given the EHI Atlas workspace package produced more traceable and reusable outputs than agents given raw files alone, especially for source contribution, missing-information disclosure, and chart-ready lab summaries.

If mixed:

> Early comparison testing showed that raw agents are strong at broad narrative summarization, while the EHI Atlas workspace improves traceability, source comparison, chartability, and reusable outputs. This supports a hybrid model: agents remain useful, but they perform better when grounded in a patient-owned evidence workspace.

## Action items

1. Build package exporter for `synthea-demo`.
2. Build package exporter for one PDF/lab collection.
3. Include at least one C-CDA source in a mixed dataset.
4. Run Claude and Codex with raw files vs package.
5. Score outputs using the rubric above.
6. Add a compact evaluation table to the report.

