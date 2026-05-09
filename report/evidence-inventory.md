# EHI Ignite Report — Build Evidence Inventory

Purpose: collect concrete proof points from the current EHI Atlas build so the Phase 1 narrative is grounded in implemented work, not just concept language.

## Core thesis evidence

| Claim in report | Evidence we can cite/show | Current repo/source |
|---|---|---|
| We convert fragmented EHI into a structured clinical fact layer. | FHIR explorer and harmonization architecture over Synthea R4; PDF-to-FHIR pipeline emits FHIR Bundle output. | `docs/architecture/PDF-PROCESSOR.md`, `docs/architecture/EXTRACTION-DATA-MODEL.md` |
| The LLM is a reasoning layer, not the source of truth. | Provider assistant builds query-filtered clinical context from facts, safety flags, medications, conditions, allergies, encounters. | `docs/architecture/FHIR-AGENT-CONTEXT-ENGINEERING-REPORT.md` |
| The system can ingest non-FHIR documents. | PDF processor uses vision + multipass extraction; local MedGemma path installed/tested for lab/vital extraction. | `docs/architecture/PDF-PROCESSOR.md`, `docs/local-models/medgemma-ollama.md` |
| We preserve provenance and auditability. | FHIR resources carry source locator metadata; harmonization layer tracks source contributions and provenance. | `docs/architecture/EXTRACTION-DATA-MODEL.md`, `docs/ideas/AGENTIC-PDF-HARMONIZATION.md` |
| The product is designed for interpretability. | Data Lab, FHIR Primer, Methodology, Coverage, Flight School, visible tool-call/evidence context. | `docs/JUDGE-WALKTHROUGH-DATALAB.md`, `docs/JUDGE-WALKTHROUGH.md` |
| The system improves EHI readability/actionability. | “5 facts in 30 seconds,” pre-op safety panel, assistant returns direct verdicts, missing information, and action list. | `docs/JUDGE-WALKTHROUGH.md` |

## Current product surfaces to reference

### Clinical workspace

Use for screenshots/mockups:

- Landing / featured patient cards
- Clinical Overview
- Safety Panel
- Interactions
- Timeline / Care Journey
- Assistant
- Raw FHIR / evidence viewer if available

Key story:

> A clinician or care team can move from a large patient export to a concise safety summary, then drill down to the evidence behind each claim.

### Data Lab / methodology environment

Use for screenshots/mockups:

- Data Lab Overview
- FHIR Primer
- Flight School
- Methodology
- Definitions
- Coverage

Key story:

> The submission is not only a demo application. It exposes its own methodology so reviewers can see how FHIR facts become clinical interpretations.

Strong language from prior judge walkthrough:

- “Absence is a first-class signal.”
- “How a FHIR bundle becomes a surgical briefing.”
- “Transparent, explainable AI methods.”

### Source Intake / Harmonized Record

Use wireframes initially if not fully polished in UI:

- Source Intake: files, type detection, preparation state
- Harmonized Record: canonical facts, review queue, source contributions, provenance
- Publish Chart: portable/shareable chart snapshot

Key story:

> New data sources become adapters into the same fact layer, not one-off prompt workflows.

## Current technical capabilities

### FHIR / synthetic corpus

- 1,180 synthetic FHIR R4 patients.
- 527,000+ resources referenced in Data Lab walkthrough.
- Corpus includes patient-level resource distributions, encounters, observations, medication requests, conditions, procedures, immunizations, claims/EOB data.

### Assistant/context engineering

Current context path:

1. Patient-scoped question.
2. Intent-aware evidence retrieval.
3. Risk snapshot and relevant facts.
4. Compact context packet to the LLM.
5. Cited answer with missing information surfaced.

Report-friendly framing:

> The assistant does not ingest the raw bundle. It receives a bounded evidence packet assembled from validated clinical facts.

### PDF extraction

Current PDF architecture:

```text
PDF
→ Pass 0 document context
→ focused per-resource extraction passes
→ FHIR resources
→ post-pass reconciliation
→ document Bundle
→ harmonization layer
```

Strategic claim:

> PDFs, C-CDAs, and portal exports remain source artifacts. The downstream system reasons over resources.

### Local model lab

MedGemma/Ollama status:

- Ollama installed locally.
- `medgemma:4b` pulled.
- New `medgemma-ollama` pipeline created.
- Scope intentionally limited to labs/vitals.
- First live smoke test succeeded on first page with one Observation extracted.

Report angle:

> The architecture is model-flexible. Frontier models can handle difficult narrative extraction while local/specialized models are benchmarked for bounded tabular tasks, supporting privacy, cost, and deployment flexibility.

## Evidence gaps to fill before final submission

- Exact challenge portal formatting requirements.
- Final screenshots at clean desktop viewport.
- One end-to-end demo run with artifacts captured:
  - source files uploaded
  - extraction result
  - harmonized facts
  - assistant answer with citations
  - source provenance drilldown
- Quantitative extraction metrics:
  - FHIR corpus size
  - PDF extraction precision/recall where gold exists
  - latency/cost for at least two pipeline candidates
  - local MedGemma benchmark status
- Privacy/security posture:
  - synthetic data in demo
  - no PHI in repo
  - deployment model for HIPAA-sensitive use
  - patient-controlled export/sharing assumptions

## Recommended final proof package

Include in final PDF or appendix:

1. Architecture diagram.
2. One screenshot of source intake/harmonization.
3. One screenshot of clinical summary or safety panel.
4. One screenshot of assistant showing evidence/missing information.
5. One screenshot of methodology/Data Lab.
6. One small table of current evaluation results.
7. One table mapping challenge criteria to implemented/proposed features.
