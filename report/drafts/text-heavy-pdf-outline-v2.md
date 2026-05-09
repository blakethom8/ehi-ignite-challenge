# Text-Heavy PDF Outline v2

Goal: move away from a card-heavy, generated-looking PDF and toward a professional 8–10 page concept paper with a few high-value visuals.

## Page 1 — Executive Summary

- Title: EHI Atlas: A Patient-Owned Synthesis Layer for Fragmented Health Records
- 2–3 paragraph opening:
  - access/movement are improving
  - understanding/action are still unsolved
  - Atlas creates the patient-owned workspace
- Small summary box: scenarios addressed and rubric fit

## Page 2 — The Problem: Access Is Not Ownership

Narrative structure:

- patients can download or authorize pulls, but still lack a living workspace
- point-in-time provider pulls do not create patient control
- moving jobs/states/insurance/care settings scatters history
- raw C-CDA/PDF/FHIR exports require interpretation

Potential heading:

> The exchange moves data; it does not necessarily move meaning.

## Page 3 — The Solution: Patient-Owned Synthesis

Narrative structure:

- gather records from many sources
- create consistent evidence structure
- preserve provenance
- harmonize duplicates/conflicts
- add patient context
- generate purpose-specific summaries/handoffs

Visual: simple workflow diagram.

## Page 4 — User Workflow and Interpretability

Narrative structure:

- Source Intake
- Harmonized Record
- Patient Context
- Publish/Share Packet
- Assistant as optional interface

Visual: one mockup or two small wireframes.

Key rubric link:

Interpretability and ease of use: show where facts came from, what conflicts, what is missing, and what matters now.

## Page 5 — Technical Approach

Narrative structure:

- source-specific adapters
- C-CDA/PDF/FHIR/portal downloads as inputs
- FHIR-compatible internal evidence layer
- provenance and validation
- harmonization

Important stance:

C-CDA is a supported input, not the final intelligence layer.

## Page 6 — AI Over Prepared Evidence

Narrative structure:

- not raw-document chatbot
- bounded evidence packet
- source-backed Q&A
- missing information disclosure
- charting from structured facts
- model flexibility as implementation detail

Visual: evidence packet → assistant answer example.

## Page 7 — Privacy, Security, and Patient Control

Narrative structure:

- patient-owned workspace
- scoped sharing
- purpose-specific packets
- provenance/auditability
- minimum necessary context for AI
- HIPAA-aware deployment path

## Page 8 — Feasibility, Prototype, and Evaluation

Narrative structure:

- current FHIR corpus
- clinical workspace/data lab
- PDF extraction pipelines
- MedGemma/Ollama local testing
- evaluation/gold standard plan

Visual: compact table.

## Page 9 — Impact and Scaling

Narrative structure:

- patients/caregivers
- clinicians/care teams
- interoperability ecosystem
- TEFCA tailwind/complementarity
- scaling through adapters

## Page 10 — Team and Closing / Rubric Alignment

Narrative structure:

- Blake background
- why this team is suited
- rubric table
- close with “record access → record ownership”

## Editing principles

- Prefer paragraphs over cards.
- Use cards only for key callouts.
- Tie every technical detail to a user/rubric benefit.
- Keep TEFCA to one concise paragraph.
- Keep AI to one clear section plus references throughout.
- Lead with ownership and interpretability.

## Portability thread to weave through pages

The report should repeatedly distinguish the durable workspace from any one interface:

- The web app is one interface.
- The assistant is one interface.
- A CLI can be another interface.
- Future clinical agents can be another interface.
- The patient-owned evidence workspace is the durable asset.

Suggested addition to Page 5 or 6:

> Atlas is designed as a portable evidence workspace, not a closed assistant. The same structured record can support a web interface, command-line review, deterministic charting, local models, frontier models such as Claude, or future clinical agent systems. This portability is part of patient ownership: the patient can carry usable evidence across tools rather than starting over with each new application.
