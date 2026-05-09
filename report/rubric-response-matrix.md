# EHI Ignite Report — Rubric Response Matrix

Use this as a checklist while editing the final PDF. Every section should map back to judge scoring.

## 1. Relevance & Problem Alignment — 25 pts

### What judges are looking for

- Direct focus on Single Patient EHI Exports.
- Clear real-world problem.
- User-centered scenario.
- A usable/readable summary of relevant health information.

### Our strongest response

EHI exports are technically accessible but practically unusable: patients receive fragmented files that do not answer “what changed, what matters, and what should I do next?” Atlas turns those exports into a patient-controlled, source-backed record that supports summaries, charts, Q&A, and handoffs.

### Proof points

- Source Intake + Harmonized Record workflow.
- “The right five facts in thirty seconds” clinical workspace.
- Patient/caregiver and clinician use cases.
- Support for FHIR, C-CDA, PDFs, and portal exports.

### Language to use

> The problem is not only data access. The problem is usable understanding.

> Atlas turns EHI availability into EHI usability.

## 2. Integration & Scaling — 20 pts

### What judges are looking for

- Practicality across EHRs/care settings.
- Standards-based design.
- Ability to scale beyond one file/source/demo.

### Our strongest response

Atlas uses adapters for source-specific formats and maps outputs into a FHIR-compatible clinical fact graph. New sources become adapters into the same evidence layer rather than new bespoke applications.

### Proof points

- FHIR-compatible core.
- C-CDA/CDA/PDF as inputs.
- Deterministic harmonization and provenance.
- Synthea corpus scale: 1,180 patients / 527k+ resources.
- PDF pipeline emits FHIR Bundle outputs.

### Language to use

> Source-specific at the edge, standards-aligned at the core.

> The assistant becomes portable because its tools operate over stable clinical concepts, not one-off document layouts.

## 3. Interpretability & Ease of Use — 40 pts

### What judges are looking for

- Clear UI/UX.
- Readable/actionable summaries.
- Patient, clinician, and care-team usability.
- Novel ways to make data understandable.

### Our strongest response

Atlas separates the raw record from purpose-built views: Source Intake, Harmonized Record, Patient Context, Publish Chart, Clinical Summary, Assistant, and Data Lab. Users see summaries and actions first, with source drilldown available when needed.

### Proof points

- Safety panel and clinical overview.
- Assistant answers with missing information.
- Data Lab explains methodology.
- Source contribution/provenance views.
- Explicit absence signals.

### Language to use

> The interface should not ask users to browse a database. It should answer the clinical or patient question, then show the evidence.

> Absence is a first-class signal.

## 4. Privacy, Security, Compliance — 15 pts

### What judges are looking for

- HIPAA/privacy awareness.
- Safe handling of sensitive health data.
- Configurable access/sharing.
- Avoidance of reckless AI data flow.

### Our strongest response

Atlas is designed around patient-controlled records, source-level provenance, evidence minimization, and deployability inside controlled environments. The demo uses synthetic data where possible and treats local/private inference as an architectural option.

### Proof points

- Synthetic data in public demo.
- No model needs full raw-bundle context for most questions.
- Context packets contain minimum necessary evidence.
- Source artifacts and structured facts are separable.
- Future tenant/private deployment path.

### Language to use

> The LLM receives the minimum necessary evidence packet for the question, not unrestricted access to every raw artifact by default.

> Provenance is a safety feature: it prevents orphaned clinical claims.

## 5. Bonus: AI Innovation — +20 pts

### What judges are looking for

- Novel AI use.
- Explainable/transparent AI methods.
- Privacy-compliant AI.
- Thoughtful guardrails.

### Our strongest response

The innovation is a FHIR-grounded AI harness: language models reason over a validated, provenance-backed fact graph through constrained tools. The system can show which facts were used, where they came from, and what remains unknown.

### Proof points

- Context packet architecture.
- Visible tool/evidence context in assistant.
- Deterministic-first harmonization.
- PDF extraction benchmark/eval harness.
- MedGemma/Ollama local model testing as model-flexibility evidence.

### Language to use

> The model is not asked to remember the chart. It is asked to reason over a bounded evidence packet assembled from the chart.

> Parse once, structure once, validate once, cite forever.

## Final report balance recommendation

If the PDF is limited to 10 pages, prioritize pages roughly like this:

1. Executive summary + problem — 1 page
2. Solution architecture — 1.5 pages
3. Product workflow/mockups — 2 pages
4. Technical feasibility/scaling — 1.5 pages
5. AI innovation/transparency — 1.5 pages
6. Privacy/security — 0.75 page
7. Impact + team — 0.75 page
8. Evaluation/prototype status callout — integrated throughout or 1 compact page

Do not spend too much space explaining FHIR generically. Explain why FHIR makes the AI safer, more portable, and more auditable.
