# EHIgnite Challenge Phase 1 Narrative — Draft v1

_Working polished draft. Target: convert into a <=10 page PDF with screenshots, diagrams, and concise prose after portal requirements are verified._

## Candidate title

**EHI Atlas: A Patient-Owned, Portable Evidence Workspace for Fragmented EHI**

## Short submission description

EHI Atlas transforms fragmented Single Patient EHI exports — FHIR bundles, C-CDAs, PDFs, and portal downloads — into a patient-owned, portable evidence workspace. Atlas gives clinical facts a consistent structure across source types, preserves provenance, harmonizes duplicate or conflicting information, and turns the result into readable summaries, trends, safety checks, and handoffs. The same workspace can support a web application, command-line review tools, local models, frontier models, or future clinical agent systems. AI assists by reasoning over prepared evidence rather than re-parsing every raw document from scratch.

---

# 1. Problem and solution

## The problem: EHI is available, but not yet usable

The 21st Century Cures Act and ONC information blocking rules have accelerated patient access to Electronic Health Information. But access alone does not make the data useful. A typical Single Patient EHI export can arrive as a mix of FHIR bundles, C-CDA documents, PDFs, lab reports, portal downloads, and scanned clinical artifacts. These files are technically available but practically difficult to use.

Patients and caregivers need answers to questions like:

- What changed since my last visit?
- Which medications am I actually taking now?
- What lab trends should I ask about?
- What information is missing before a second opinion, surgery, or specialist visit?
- Which facts came from which provider or source document?

Clinicians and care teams face a related problem. They may receive patient-supplied records, but a black-box summary is not enough. In clinical contexts, a useful summary must show its work. Every important claim should trace back to a source, date, and clinical fact.

There is also a patient-ownership gap. A provider-mediated, point-in-time pull can help at the moment of care, but it does not give the patient a living workspace for their clinical history. A person who changes jobs, moves out of state, changes insurance, seeks a second opinion, or helps an aging parent still needs a durable place to gather, understand, update, and selectively share their records.

## The solution: make EHI understandable before making it intelligent

EHI Atlas converts fragmented patient exports into an interpretable, source-backed clinical workspace that belongs to the patient rather than to any one portal, provider, model, or application. The system ingests patient files, prepares each source, maps facts into a consistent FHIR-compatible structure, preserves provenance, harmonizes across sources, and then exposes the result through summaries, charts, Q&A, review queues, command-line tools, and portable handoffs.

The product is deliberately different from a direct “documents to chatbot” workflow.

```text
Common AI summarization pattern:
Documents → LLM → Summary

EHI Atlas pattern:
Documents → FHIR-compatible facts → Provenance + validation → Portable evidence workspace → Human review, charts, CLI tools, and AI assistance
```

The central principle is:

> The model is not the product. The durable product is the patient-owned evidence workspace; models and agents are interfaces on top.

In practice, this means Atlas can parse once, structure once, validate once, and cite forever.

---

# 2. Use cases and challenge scenarios addressed

EHI Atlas addresses three challenge scenarios directly.

## Scenario 3: Integration across settings

Patients receive information from multiple care locations: health systems, labs, imaging centers, primary care offices, specialists, payers, and patient portals. Atlas treats each source as an input into one harmonized record. A lab value extracted from a PDF, a medication from a C-CDA, and a condition from a FHIR export can coexist in the same patient fact graph while retaining links back to their original sources.

The result is not a new folder of documents. It is a portable clinical evidence layer that can travel across use cases, tools, and agent systems.

## Scenario 2: Customization for clinical domains

Different users need different views of the same EHI. A patient preparing for a specialist visit, a surgeon reviewing pre-operative risk, and a caregiver coordinating medications all ask different questions.

Atlas supports domain-specific retrieval over the same underlying record. The current prototype emphasizes safety-oriented chart review: medications, conditions, allergies, labs, interactions, timelines, and missing information. The same structure can support oncology summaries, second opinions, chronic disease management, trial matching, payer workflows, or caregiver handoffs.

## Scenario 1: Interactive patient tools

Atlas includes an assistant that answers questions over the harmonized record. The assistant is constrained to use structured evidence rather than free-form guessing over raw files. Its responses can include citations, missing-information warnings, and drilldowns into source records.

The goal is not a generic medical chatbot. It is an explainable interface to the patient’s own record.

---

# 3. Why FHIR is the right substrate for trustworthy AI

FHIR is not the app, and users should not need to understand FHIR to benefit from the system. FHIR-compatible structure is the evidence layer that makes the record consistent, auditable, and easier to interpret across file types.

Raw PDFs, CDAs, and C-CDAs are important source artifacts, but they are not the ideal reasoning substrate for an agent. They are document-centric. Language models can read them, but repeated document reading makes every request dependent on prompt wording, page layout, context window limits, and model behavior.

FHIR-compatible resources turn document fragments into typed clinical facts:

| Clinical concept | FHIR-compatible representation |
|---|---|
| Lab result or vital sign | Observation |
| Medication | MedicationRequest / MedicationStatement |
| Diagnosis or problem | Condition |
| Visit or care event | Encounter |
| Report or source document | DiagnosticReport / DocumentReference |
| Source trail | Provenance |

That structure lets the application, command-line review tools, and AI assistants use stable operations:

```text
get_recent_labs(loinc, window)
get_active_medications(rxnorm_class)
get_condition_history(problem)
compare_sources(fact_id)
get_source_provenance(fact_id)
build_patient_summary(audience, purpose)
```

This is more transportable than a prompt designed for one PDF format or one C-CDA layout. New sources become adapters into the same evidence layer. The downstream workspace, charts, summaries, CLI exports, assistant, and handoffs continue to operate over the same clinical concepts. This means the patient-owned workspace can be useful even as the preferred agent harness changes from one model or product to another.

The best framing is:

> FHIR-compatible structure is the common evidence layer behind an interpretable patient record workspace. AI is one interface on top of that workspace; CLI tools, exports, charts, and future agents are others.

---

# 4. Product concept and user experience

EHI Atlas is organized around a patient-controlled record workspace.

## Source Intake

The user adds files: FHIR exports, PDFs, C-CDAs, lab reports, portal downloads, or future connected sources. Atlas classifies each file, prepares it for extraction, and reports whether it is ready to harmonize.

## Harmonized Record

Prepared sources become a canonical record. The user can inspect labs, medications, conditions, allergies, immunizations, procedures, and encounters. Each fact can show its source contributions: which file or export contained it, whether another source agreed, and whether a conflict needs review.

## Patient Context

Patient-reported context can be added alongside formal EHI: goals, symptoms, concerns, care team notes, or questions for a visit. This acknowledges that the formal medical record is necessary but incomplete.

## Publish Chart

The user can create a portable chart snapshot for a specific purpose: second opinion, pre-op review, specialist visit, caregiver handoff, or payer workflow. The snapshot can include readable summaries, source references, and selected structured facts.

## Portable workspace package and CLI review

Atlas should not trap the patient's record inside one web application. A downloadable workspace package can expose the same evidence environment for review, export, and integration: source inventory, structured facts, provenance, source contributions, conflicts, missing-information signals, and agent-ready context packets. A command-line interface can inspect the package by listing sources, searching facts, showing provenance, generating timelines, exporting context packets, and producing purpose-specific markdown, JSON, CSV, or FHIR outputs. This demonstrates that the value is the patient-owned evidence environment, not a single assistant surface.

## Assistant and charts

The assistant answers questions using the harmonized record. Charts and summaries are generated from structured facts, not from one-off document reading. For example, “chart kidney function over time” can deterministically retrieve creatinine/eGFR Observations before any AI explanation is written. This makes the chart interpretable first and intelligent second.

---

# 5. Current prototype status

The current build demonstrates the core architecture and several user-facing surfaces.

## FHIR data exploration and clinical workspace

The prototype includes a FHIR explorer over a synthetic Synthea R4 corpus of approximately 1,180 patients and more than 527,000 resources. The clinical workspace includes patient overview, safety panel, medication interactions, timelines, care journey, conditions, procedures, immunizations, clearance views, and assistant interaction.

A recurring product target is:

> The right five facts in thirty seconds.

This keeps the interface focused on usability rather than raw data display.

## Data Lab and methodology environment

The app includes a Data Lab that explains the underlying data model, FHIR resource types, coverage, definitions, and methodology. This is an important trust surface. Reviewers and users can see how the system moves from raw resources to clinical interpretation.

One guiding principle is:

> Absence is a first-class signal.

For example, “no active anticoagulants found” should be represented explicitly when the evidence supports it, rather than hidden as a silent absence.

## Assistant/context engineering

The assistant already uses a query-filtered context path. Instead of sending raw bundles to the LLM, the system builds focused evidence from safety flags, medication classes, conditions, allergies, encounters, and other structured facts. Future context packets will make this even more explicit by recording evidence units, priorities, citations, token budgets, and missing information.

## PDF, C-CDA, and document extraction

Atlas includes a PDF-to-FHIR extraction architecture and should explicitly support C-CDA as a first-class source input. The PDF design uses a document-context pass followed by focused resource-specific extraction passes. C-CDA should be parsed as a document-centric exchange artifact and mapped into the same FHIR-compatible evidence structure rather than treated as the final intelligence layer. Outputs from every source type are passed to the harmonization layer with source metadata.

Recent local model work added a MedGemma 4B / Ollama pipeline for labs and vitals extraction. This is intentionally isolated as a benchmark candidate, not assumed to be the winning architecture. The broader system is model-flexible: frontier models can handle complex narrative extraction while local or specialized models can be evaluated for bounded tabular tasks.

---

# 6. Technical feasibility and scalability

Atlas separates source-specific ingestion from standards-aligned reasoning.

## Adapter-based ingestion

Each input type receives an adapter:

- FHIR Bundle adapter
- C-CDA/CDA adapter, including CCD section mapping into clinical facts
- PDF/document extraction adapter
- lab report parser
- future portal/API connectors

Adapters produce prepared artifacts and candidate clinical facts. The downstream system does not need to know whether a lab came from a PDF, FHIR export, or C-CDA; it receives a normalized Observation with provenance.

## Deterministic harmonization

Atlas keeps the core harmonization layer deterministic. Matching facts across sources, resolving units/dates/codes, minting provenance, and computing source contribution diffs should not be left to free-form model judgment. Models can extract or explain, but validation and merge logic should be explicit and testable.

## Constrained AI layer

The assistant operates over a bounded evidence packet. A typical flow is:

1. Classify user intent.
2. Retrieve relevant structured facts.
3. Apply context budgets and validation.
4. Ask the LLM to explain, summarize, or reason from the evidence.
5. Return citations, missing-information warnings, and next actions.

This makes the AI layer safer and more portable. The same tools can work across multiple EHRs and document sources once their data is mapped to the clinical fact layer.

## Deployment path

The architecture supports multiple deployment models:

- local/single-user prototype with synthetic or user-supplied data
- health-system tenant deployment
- patient-controlled record workspace
- command-line review and export tooling
- cloud worker for batch extraction
- local model path for privacy-sensitive or lower-cost extraction tasks

The model can change behind the interface. Claude, local models, future medical agents, and deterministic CLI tools can all use the same prepared evidence. The durable architecture is the fact graph, provenance, validation, and tool contracts.

---

# 7. Innovation

The innovation is not simply “use AI to summarize medical records.” It is the combination of standards-aligned clinical structure and constrained language model reasoning.

Key innovations:

1. **Patient-owned portable evidence workspace** — the durable asset is a reusable record environment, not a one-off summary.
2. **Provenance-backed clinical fact graph** — every important fact can trace to source documents and transformations.
3. **Deterministic-first harmonization** — cross-source merging and conflict detection are explicit and testable.
4. **Portable tooling surface** — the same structured record can support web UI, CLI review, exports, local models, frontier models, and future clinical agents.
5. **Transparent context packets** — AI tools can show what evidence they used and what they did not know.
6. **Model-flexible extraction** — cloud, local, and specialized models can be benchmarked behind the same FHIR output contract.

The result is a safer and more portable pattern for clinical AI:

```text
Parse once. Structure once. Validate once. Cite forever.
```

---

# 8. Privacy, security, and compliance posture

The prototype demonstration uses synthetic Synthea data where possible and keeps private/PHI-like test artifacts out of source control. The architecture is designed to support HIPAA-aware deployment patterns, including customer-controlled environments, tenant isolation, and local or private inference options where needed.

Important principles:

- Raw files remain source artifacts with access controls.
- Structured facts retain provenance to avoid orphaned claims.
- The LLM receives only the minimum necessary evidence packet for the question.
- Patient-controlled sharing can be scoped to a chart snapshot, export, context packet, or use case.
- Synthetic data is used for public demo and evaluation surfaces.

For the challenge, the focus is Phase 1 concept/design. In Phase 2, the privacy section should be expanded into concrete authentication, authorization, audit logging, data retention, and deployment controls.

---

# 9. Potential impact

## Patients and caregivers

Patients receive a usable record, not a folder of files. They can ask plain-language questions, see trends, identify missing information, prepare for visits, export selected evidence, and bring a coherent summary to a new clinician or tool.

## Clinicians and care teams

Clinicians can review high-signal summaries with source references. They can see where each fact came from, identify conflicts, and use the record for handoffs or focused review without trusting a black-box summary.

## Interoperability ecosystem

The system turns EHI availability into EHI usability and ownership. By using FHIR-compatible structure as the evidence layer, Atlas makes patient records more portable across applications, agent harnesses, command-line tools, and workflows. It supports the spirit of interoperability: not just moving data, but making it computable, explainable, actionable, and patient-controlled.

---

# 10. Team / submitting entity

Blake Thomson brings healthcare data strategy and business development experience from Cedars-Sinai, where his work focuses on claims data, referral ecosystems, provider networks, and translating complex healthcare data into operational strategy. This submission combines healthcare domain understanding with hands-on prototyping in FHIR data modeling, agentic workflows, PDF extraction, clinical context engineering, local model evaluation, and patient-facing health information design.

The project is intentionally built from both sides: healthcare workflow first, technical architecture second. The goal is not AI novelty in isolation. The goal is to make patient-controlled health information practically useful, explainable, and portable.

---

# Appendix material to convert into visuals

## Architecture diagram

```text
EHI Sources
  FHIR bundle | C-CDA | PDF | lab report | portal export
      ↓
Source Intake + Classification
      ↓
Extraction / Adapter Layer
      ↓
FHIR-Compatible Clinical Fact Graph
      ↓
Validation + Provenance + Harmonization
      ↓
Portable Evidence Workspace
      ↓
Web UI | CLI Review | Charts | Context Packets | AI Assistants | Handoffs
```

## Challenge criteria mapping

| Criterion | Atlas response |
|---|---|
| Relevance & problem alignment | Directly targets unusable Single Patient EHI exports. |
| Integration & scaling | Adapter model; FHIR-compatible core; multi-source harmonization. |
| Interpretability & ease of use | Five-facts design target, summaries, charts, citations, Data Lab. |
| Privacy/security/compliance | Synthetic demo data, patient-controlled sharing, evidence minimization, private deployment path. |
| AI innovation | Portable evidence workspace, transparent context packets, provenance-backed reasoning across agent systems. |

## Screenshots/mockups needed

1. Source Intake
2. Harmonized Record / source contributions
3. Clinical Overview / five facts
4. Assistant answer with citations and missing information
5. Methodology / Data Lab
6. Architecture diagram
7. Evaluation table
