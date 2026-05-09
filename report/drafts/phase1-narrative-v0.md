# Phase 1 Submission Narrative — Draft v0

> Working draft for the EHIgnite Challenge report. This is intentionally a structured outline with reusable language, not final prose yet.

## Submission entry name options

1. **Atlas: A FHIR-Grounded AI Record Layer for Patient EHI**
2. **EHI Atlas: Turning Patient Exports into Source-Backed Clinical Intelligence**
3. **ChartGraph: A Provenance-Backed Patient Record for Trustworthy AI**
4. **Record Atlas: Making Single Patient EHI AI-Ready**

Current favorite: **EHI Atlas** — clear, broad, not too technical.

## Short submission description — under 1,000 characters

EHI Atlas transforms fragmented Single Patient EHI exports — FHIR bundles, C-CDAs, PDFs, and portal downloads — into a FHIR-compatible, provenance-backed clinical fact graph. Instead of asking a language model to summarize raw documents directly, Atlas first structures, validates, deduplicates, and cites clinical facts. A constrained AI assistant then queries this evidence layer to generate readable summaries, trends, safety checks, contradiction alerts, and clinician-ready handoffs. The result is a patient-controlled record that is usable by patients, explainable to clinicians, and portable across care settings.

## Executive framing

Patients increasingly have a legal right to receive their health information, but the practical output is often a folder of files: raw FHIR bundles, C-CDAs, PDFs, portal exports, and scanned reports. The data is technically available but not meaningfully usable. Patients cannot easily tell what changed, what matters, what conflicts, or what to ask their doctor. Clinicians cannot safely rely on a black-box summary unless the facts can be traced back to their source.

Our solution makes Single Patient EHI exports AI-ready. We convert fragmented records into a FHIR-compatible, provenance-backed clinical fact graph. Language models then operate through constrained tools over that graph to produce cited summaries, charts, safety checks, missing-information flags, and handoff packets.

The core principle is simple:

> The LLM is not the database. The LLM is the reasoning layer over a structured, auditable clinical record.

## 1. Description of the solution and problem addressed

### Problem

EHI exports are too hard to use in their raw form:

- They are fragmented across portals, care sites, labs, claims, and document formats.
- They mix clinically important facts with administrative noise.
- They are often document-centric rather than question-centric.
- They lack a patient-friendly view of what changed, what matters, and what requires follow-up.
- Current AI summarization approaches risk hallucination when models reason directly over raw, unvalidated documents.

### Solution

EHI Atlas ingests multiple patient record sources and normalizes them into a standards-aligned clinical evidence layer:

```text
Fragmented EHI exports
→ source preparation and extraction
→ FHIR-compatible clinical facts
→ provenance, validation, deduplication, conflict detection
→ constrained AI tools
→ summaries, charts, Q&A, handoffs
```

We turn documents into resources before asking AI to reason.

The platform supports:

- **Source Intake** — upload/prepare FHIR bundles, PDFs, C-CDAs, lab reports, and portal exports.
- **Harmonized Record** — merge extracted facts into canonical clinical resources while retaining source references.
- **Patient Context** — capture patient/caregiver context that formal EHI may miss.
- **Publish Chart** — create a portable, shareable chart snapshot for review, second opinions, or care coordination.
- **Assistant** — answer questions using source-backed tools over the harmonized record.
- **Data Lab** — expose methodology, data definitions, coverage, and interpretability artifacts for transparency.

## 2. Why FHIR is central

FHIR is not the user interface and it is not the final product. FHIR is the structured clinical substrate that makes trustworthy AI possible.

Raw document summarization asks a model to infer facts from text every time. A FHIR-compatible fact graph lets the system parse once, structure once, validate once, and cite forever.

FHIR helps because it gives clinical facts stable identities and typed semantics:

- `Observation` for labs/vitals
- `MedicationRequest` / `MedicationStatement` for medications
- `Condition` for problems/diagnoses
- `Encounter` for visits
- `DiagnosticReport` and `DocumentReference` for source documents
- `Provenance` for where facts came from and how they were transformed

This enables an agent harness with reusable tools:

```text
get_recent_labs(loinc, window)
get_active_medications(rxnorm_class)
get_condition_history(problem)
compare_sources(fact_id)
get_source_provenance(fact_id)
build_patient_summary(audience, purpose)
```

That is more portable than prompt logic tied to random PDFs, CDAs, or C-CDAs. C-CDA and CDA are valuable inputs, but they are document-centric. FHIR gives us a resource-centric computational layer that an AI system can query consistently.

## 3. Scenarios addressed

### Integration Across Settings

The system is designed to combine records from multiple places of care. Source adapters convert each export into a shared clinical fact layer, preserving where each fact came from. A lab result from a PDF, a medication from a C-CDA, and a condition from a FHIR export can appear together in one harmonized record.

### Customization for Clinical Domains

The current prototype focuses on pre-operative/safety chart review and longitudinal record exploration. Domain-specific tools can retrieve the right subset of facts for a question: medications, labs, conditions, allergies, procedures, and timeline events.

### Interactive Patient Tools

The assistant answers patient or caregiver questions in plain language while citing the evidence it used and surfacing missing information. The goal is not a black-box chatbot; it is an explainable interface over a patient-controlled record.

## 4. Prototype/application status

Current prototype work includes:

- FHIR explorer over a synthetic Synthea R4 corpus.
- Clinical workspace with overview, safety panel, interactions, timeline, care journey, conditions, procedures, immunizations, clearance, and assistant views.
- Data Lab / methodology environment explaining FHIR data definitions, coverage, pipeline stages, and trust/interpretability gates.
- Provider assistant that builds query-filtered clinical context rather than injecting raw bundles into the model.
- Source intake / harmonized record design direction for multi-source patient record aggregation.
- PDF extraction pipelines, including cloud vision extraction and new local MedGemma/Ollama experimentation.

Important current build evidence:

- Corpus: 1,180 synthetic FHIR R4 patients and 527,000+ resources in the existing data lab.
- Assistant: patient-scoped evidence retrieval with visible context/tool calls.
- PDF lab: evaluating extraction quality against gold-standard outputs.
- Local models: MedGemma 4B via Ollama tested as an isolated benchmark candidate for labs/vitals extraction.

## 5. Technical feasibility and scalability

The architecture separates source-specific ingestion from standards-aligned reasoning.

### Ingestion adapters

Each input format gets an adapter:

- FHIR Bundle adapter
- C-CDA/CDA adapter
- PDF/document extraction adapter
- lab report parser
- future portal/API connectors

Adapters produce prepared artifacts and candidate clinical facts.

### Canonical clinical fact layer

Facts are normalized into a FHIR-compatible representation with:

- clinical code where available, such as LOINC or RxNorm
- normalized value/unit/date
- source document reference
- confidence and extraction method
- provenance trail
- review/conflict state

### Agent harness

The LLM does not read every raw file on every request. Instead:

1. classify user intent
2. retrieve relevant structured facts
3. apply deterministic validation and context budgets
4. call the LLM with a compact evidence packet
5. require source-backed explanation and missing-information disclosure

This makes the agent transportable. The same tools can operate over different EHI sources after they are mapped to the clinical fact layer.

## 6. Innovation

The innovation is not merely using AI on health records. It is the combination of:

- FHIR-compatible clinical fact graph
- source-level provenance
- deterministic validation before generation
- constrained language model tools
- transparent context packets
- explicit missing-information reporting
- cross-source deduplication and conflict detection
- local/specialized model experimentation for extraction

Most AI summarization demos follow this path:

```text
Documents → LLM → Summary
```

Our approach is:

```text
Documents → Clinical resources → Validated fact graph → LLM harness → Cited insight
```

That difference matters for healthcare trust.

## 7. Potential impact

### For patients and caregivers

- Understand what is in their record.
- Ask plain-language questions.
- See trends and changes over time.
- Prepare for visits with source-backed questions.
- Bring a coherent, portable summary to a new clinician.

### For clinicians

- Review the right facts quickly.
- See where each fact came from.
- Identify missing information.
- Spot conflicts across sources.
- Generate handoff packets without trusting an unexplained black box.

### For health systems and interoperability

- Convert EHI availability into EHI usability.
- Use standards-aligned data structures rather than one-off prompt pipelines.
- Add new data sources through adapters.
- Keep patient-level record intelligence portable across settings.

## 8. Wireframes/mockups to include

Needed assets for final PDF:

1. Overall architecture diagram:
   - EHI exports → adapters → FHIR-compatible fact graph → agent tools → summaries/charts/handoffs.
2. Source Intake screen.
3. Harmonized Record screen with source contributions and provenance.
4. Assistant answer showing citations, missing information, and evidence packet.
5. Data Lab / methodology screen showing how the system validates and explains outputs.
6. Example patient timeline or lab trend chart.
7. Optional: local model / PDF extraction evaluation screenshot.

## 9. Team / entity language draft

Blake Thomson brings a healthcare data strategy and business development background from Cedars-Sinai, where his work focuses on claims data, referral ecosystems, provider networks, and translating complex healthcare data into operational strategy. This submission combines that domain perspective with hands-on prototyping in FHIR data modeling, agentic workflows, PDF extraction, clinical context engineering, and patient-facing health information design.

The project is intentionally built from both sides: healthcare workflow first, technical architecture second. The goal is not to demonstrate AI novelty in isolation, but to make patient-controlled health information practically useful, explainable, and portable.

## 10. Open items before final report

- Confirm exact page/font requirements from logged-in portal.
- Pick final product name.
- Capture screenshots/mockups from current app.
- Decide final primary use case: pre-op review vs general patient record portability vs caregiver/second opinion workflow.
- Write final one-page architecture narrative.
- Add privacy/security section: synthetic data, local processing option, PHI handling assumptions, HIPAA-aware deployment.
- Add evaluation section: FHIR corpus, PDF gold standard, MedGemma/Ollama local model testing, extraction quality metrics.
