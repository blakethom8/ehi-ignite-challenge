# EHIgnite Challenge — Phase 1 Submission Requirements

_Last updated: 2026-05-08 from ehignitechallenge.org, HealthIT.gov challenge material, and the 2026-05-07 challenge presentation._

## Deadline

- Official rules PDF says Phase 1 submissions are due **May 13, 2026 at 11:59 PM PST**.
- The public website fetched on 2026-05-08 shows **May 20, 2026 at 11:59 PM PST**. This conflicts with the official rules PDF. Verify the final deadline in the logged-in portal before final submission.

## Required Phase 1 package

A complete Phase 1 package appears to include:

1. **Registration / participant information**
   - Team name
   - Team lead / member details
   - Brief expertise relevant to EHI usability, interoperability, health IT, UX, data science, clinical workflows, or AI
   - Eligibility and privacy/HIPAA acknowledgements

2. **Project overview / submission metadata**
   - Submission entry name
   - Short solution description, reportedly under **1,000 characters**
   - Intended EHI scenario(s) addressed

3. **Submission narrative uploaded as PDF**
   - English
   - **10 pages max**.
   - **One-inch margins**.
   - **Calibri, 11-point or larger**.
   - Must describe the proposed concept/design, implementation approach, and supporting visuals.
   - Do not use HHS, ONC, or other federal logos or imply federal endorsement.

## Required solution scope

Submissions should directly address **Single Patient EHI Exports** and make exported patient information more:

- usable
- readable
- actionable
- understandable for patients, clinicians, and/or care teams

The solution must create a **usable, readable summary of relevant health information**.

## Required scenarios

The proposal must address at least one of five scenarios:

1. **Interactive Patient Tools** — patient-facing Q&A and understandable explanations.
2. **Customization for Clinical Domains** — domain-specific queries and organization of exports.
3. **Integration Across Settings** — combine EHI exports from multiple care locations.
4. **Streamlined Payer Use Cases** — facilitate insurance/payer workflows and API sharing.
5. **Participant-Defined Use Case** — unique EHI usability use case.

## Best-fit scenarios for our submission

Primary:

- **Integration Across Settings** — harmonize fragmented EHI exports, PDFs, C-CDAs, and FHIR bundles into a portable patient fact graph.
- **Customization for Clinical Domains** — start with pre-op / safety / longitudinal chart review and support domain-specific summary packets.
- **Interactive Patient Tools** — agent answers questions over the record with citations and missing-information flags.

Secondary:

- **Participant-Defined Use Case** — AI-ready patient record layer / source-backed clinical fact graph.

## Narrative sections to include

Based on public challenge material and summarized structure, our report should include these sections:

1. **Description of the Solution and Problem Addressed**
   - Why raw EHI exports are technically available but practically unusable.
   - How our solution converts fragmented exports into an AI-ready, provenance-backed clinical fact graph.
   - What user problem is solved: patient/caregiver/clinician needs a reliable summary, trends, source-backed answers, and handoff.

2. **Description of the Submitting Individual, Team, or Entity**
   - Blake's health system business development/data strategy background.
   - Claims/data strategy, healthcare ecosystem knowledge, and LLM/agentic systems prototyping.
   - Built prototype evidence: FHIR explorer, PDF extraction, harmonization lab, local MedGemma testing.

3. **Wireframes and Mockups**
   - Source Intake
   - Harmonized Record
   - Patient Context
   - Publish Chart / portable packet
   - Assistant / cited Q&A
   - Data Lab / methodology / transparency views

4. **Technical Feasibility and Scalability**
   - Ingest adapters for FHIR R4 bundles, C-CDA/CDA, PDFs, portal exports.
   - Canonical FHIR-compatible resource layer with provenance.
   - Deterministic validation/harmonization before LLM reasoning.
   - LLM harness uses constrained tools over structured facts rather than free-form document guessing.
   - Scales by adding source adapters, not rewriting the agent.

5. **Innovation**
   - FHIR as structured clinical substrate for trustworthy AI.
   - Language model harness behind FHIR-compatible structures.
   - Transparent context packets, source citations, missing-information surfacing, contradiction/conflict detection.
   - Local/specialized model experiments for document extraction and cost/privacy optionality.

6. **Potential Impact**
   - Patients get a usable record, not a folder of files.
   - Clinicians get rapid, source-backed summaries and trends.
   - Care teams can reconcile information across settings.
   - The record becomes portable across applications because it is standards-aligned.

## Judging criteria / scoring lens

Existing repository judge notes identify this rubric:

| Category | Weight | What it rewards |
|---|---:|---|
| Relevance & Problem Alignment | 25 | Direct fit to EHI export usability problems and real-world scenario alignment. |
| Integration & Scaling | 20 | Workflow practicality, standards, multi-EHR / multi-provider scaling. |
| Interpretability & Ease of Use | 40 | Readability, actionable design, user-centered workflows. |
| Privacy, Security, Compliance | 15 | HIPAA/privacy posture, settings, no unsafe data handling. |
| Bonus: AI Innovation | +20 | Transparent, explainable, privacy-compliant AI. |

## Standards and technical references to name

- FHIR R4
- US Core IG v6 where applicable
- SMART App Launch Framework 2.0 where relevant
- 21st Century Cures Act / ONC information blocking context
- TEFCA as broader interoperability context, without overstating direct access
- C-CDA/CDA as important input formats, not ideal agent reasoning substrate

## Key framing decision

Do **not** frame this as “just a PDF summarizer.”

Frame it as:

> A FHIR-grounded AI workbench that transforms fragmented Single Patient EHI exports into a harmonized, provenance-backed clinical fact graph, then uses constrained language model tools to generate readable summaries, charts, contradiction checks, and clinician-ready handoffs.
