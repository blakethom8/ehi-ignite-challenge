# EHI Ignite Report

Working folder for the Phase 1 EHIgnite Challenge submission narrative, supporting language, screenshots/mockups, and source requirement documents.

## Current target

Build a Phase 1 proposal around this thesis:

> We make patient records AI-ready by transforming fragmented EHI exports into a FHIR-compatible, provenance-backed clinical fact graph that language models can query safely, transparently, and portably.

## Folder structure

- `submission-requirements.md` — distilled official/submission structure and judging rubric.
- `drafts/phase1-narrative-v0.md` — first working report draft/outline.
- `source-docs/` — downloaded challenge documents and source artifacts.
- `assets/` — screenshots, diagrams, mockups, workflow images for the final PDF.

## Source documents captured

- `source-docs/2026-05-07_EHIgnite_Challenge_Presentation.pdf`

## Working language anchors

- FHIR is not the app; FHIR is the structured clinical substrate for trustworthy AI.
- We turn documents into resources before asking AI to reason.
- The LLM is not the database or source of truth; it is a reasoning layer over a structured, auditable clinical record.
- Parse once, structure once, validate once, cite forever.
- The output is not a pile of documents. It is a portable, source-backed patient fact graph that can produce summaries, charts, contradiction checks, and handoffs.
