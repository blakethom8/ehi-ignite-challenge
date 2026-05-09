# EHI Ignite Report — Screenshot / Mockup Shot List

Goal: final PDF should have 5–7 visuals. Each visual should prove a rubric point, not just decorate the report.

## Required visuals

### 1. Architecture diagram

- Source: `report/assets/architecture-diagram.mmd`
- Purpose: show why this is not a PDF chatbot.
- Caption: “Fragmented EHI exports become a FHIR-compatible clinical fact graph before the language model reasons over them.”
- Rubric: Integration & Scaling, AI Innovation.

### 2. Source Intake

- Surface: app Source Intake if available; otherwise use wireframe from `docs/ideas/DATA-AGGREGATOR-WIREFRAMES.md`.
- Must show:
  - multiple files/sources
  - type/preparation state
  - ready-to-harmonize signal
- Caption: “Each source is classified and prepared before it can influence the record.”
- Rubric: Relevance, Integration.

### 3. Harmonized Record / Source Contributions

- Surface: Harmonized Record tab or wireframe.
- Must show:
  - canonical facts
  - sources count
  - shared vs unique contributions
  - provenance/drilldown
- Caption: “The same clinical fact can be traced across sources, with conflicts routed to review.”
- Rubric: Interpretability, Integration, AI Innovation.

### 4. Clinical summary / Safety panel

- Surface: Clinical Overview or Safety Panel.
- Must show:
  - high-signal summary
  - action-oriented flags
  - “5 facts in 30 seconds” feeling
- Caption: “The record becomes a usable clinical briefing, not a raw export viewer.”
- Rubric: Interpretability & Ease of Use.

### 5. Assistant with evidence packet / citations

- Surface: Provider Assistant.
- Must show:
  - patient-scoped question
  - evidence/tool/context chip
  - direct answer
  - missing information
  - source/citation if implemented
- Caption: “The assistant reasons over a bounded evidence packet assembled from structured facts.”
- Rubric: AI Innovation, Interpretability.

### 6. Data Lab / Methodology

- Surface: Data Lab Methodology or FHIR Primer.
- Must show:
  - pipeline stages
  - data definitions
  - coverage/trust logic
- Caption: “Reviewers can inspect how raw FHIR becomes clinical interpretation.”
- Rubric: AI Innovation, Ease of Use.

### 7. Evaluation / PDF Lab result

- Surface: local-model/PDF extraction report, CLI output, or small table.
- Must show:
  - pipeline candidates
  - scope (labs/vitals, narrative, etc.)
  - F1/latency/cost where available
  - MedGemma/Ollama status
- Caption: “Extraction architecture is benchmarked against gold outputs instead of chosen by intuition.”
- Rubric: Technical Feasibility, AI Innovation.

## Capture standards

- Desktop viewport: 1440 × 900 or similar.
- Use synthetic data or non-PHI demo artifacts only.
- Hide API keys, local paths with personal details, and irrelevant browser UI.
- Prefer one visual per report section.
- Add short annotation callouts directly on screenshots when useful.

## Final PDF visual order

1. Architecture diagram near Solution section.
2. Source Intake + Harmonized Record in Product Concept section.
3. Clinical Summary or Safety Panel in Use Case section.
4. Assistant evidence screenshot in Innovation section.
5. Data Lab screenshot in Transparency/Methodology section.
6. Evaluation table near Technical Feasibility.
