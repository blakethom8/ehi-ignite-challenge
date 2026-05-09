# Framing Memo — Interpretability First, AI Harness Second

Date: 2026-05-08

## Blake's critique

The current report language risks leaning too hard into the AI harness / universal model layer idea. That architecture is real, but the competition rubric heavily rewards **interpretability and ease of use**. The strongest submission should not sound like we are mainly building a model orchestration system.

The better framing:

> We are building an interpretable patient record workspace that gives patients, clinicians, and care teams a consistent, source-backed view of fragmented EHI. The AI harness is powerful because the workspace has already structured the evidence.

## Core reframing

### Old emphasis

```text
Fragmented EHI → FHIR fact graph → LLM harness → AI summaries
```

This is technically correct, but it foregrounds the model layer.

### Better emphasis

```text
Fragmented EHI → interpretable patient workspace → source-backed summaries, charts, and handoffs
                              ↓
                     AI operates over prepared evidence
```

The user-facing value is not “any model can plug in.” The user-facing value is:

- one coherent record across sources
- every fact has provenance
- conflicts are visible
- missing information is explicit
- summaries are readable
- charts are generated from structured facts
- AI explanations cite the same evidence a human can inspect

## New primary thesis

> EHI Atlas turns fragmented patient exports into an interpretable, source-backed record workspace. A FHIR-compatible data structure gives every clinical fact a consistent shape across PDFs, C-CDAs, FHIR bundles, and portal downloads, while provenance and harmonization make the record understandable, auditable, and usable. AI assists by reasoning over this prepared evidence layer — not by replacing it.

## Short version

> We make EHI understandable before we make it intelligent.

## One-liner options

1. **EHI Atlas makes fragmented patient records interpretable: one source-backed workspace for summaries, charts, conflicts, and handoffs.**
2. **We turn messy EHI exports into a consistent, provenance-backed record that humans can understand and AI can safely assist with.**
3. **Before AI can help patients understand their records, the records need a usable evidence structure. EHI Atlas builds that structure.**
4. **Our core product is not a chatbot. It is an interpretable patient record workspace with AI layered over structured evidence.**

## Language hierarchy for the report

### Lead with interpretability / ease of use

Use first:

- readable patient record
- interpretable record workspace
- source-backed summaries
- clear charts and trends
- source contribution view
- missing information made explicit
- conflict detection
- patient/clinician handoff
- usable record layer

### Then explain the technical substrate

Use second:

- FHIR-compatible fact graph
- flexible schemas across source types
- provenance and harmonization
- adapters for PDFs, C-CDAs, FHIR bundles, and portal downloads
- consistent clinical fact structure

### Then explain AI

Use third:

- AI assistant reasons over prepared evidence
- constrained evidence packets
- source-backed Q&A
- model-flexible harness
- transparent/explainable AI

## Replace / soften phrases

| Too AI-harness-forward | Better competition language |
|---|---|
| FHIR-grounded AI harness | Interpretable EHI workspace with a FHIR-compatible evidence layer |
| Universal model layer | Consistent clinical fact structure across source types |
| Any model can plug in | AI tools can reason over prepared evidence instead of re-parsing every document |
| Language model harness behind FHIR | Source-backed record workspace; AI is one interface on top |
| Model-flexible agent layer | Standards-aligned evidence layer that supports multiple summarization and analysis tools |
| LLM reasoning layer | Assistant that explains, cites, and surfaces missing information |

## Revised architecture story

The report should describe three layers:

### 1. Usability layer — what users experience

- Source Intake
- Harmonized Record
- Patient Context
- Summaries and charts
- Cited Q&A
- Care handoffs
- Review queue for conflicts and missing information

This is what earns the 40-point interpretability/ease-of-use category.

### 2. Evidence layer — why the app is trustworthy

- consistent clinical fact schema
- FHIR-compatible resources
- source references
- provenance
- harmonization
- deduplication
- conflict detection
- validation

This is the backbone.

### 3. AI assistance layer — how intelligence is added safely

- bounded evidence packets
- retrieval over structured facts
- cited explanations
- missing-information disclosure
- model flexibility

This is the bonus, not the whole product.

## Stronger paragraph for the report

EHI Atlas is not primarily an AI chatbot for medical records. It is an interpretable patient record workspace. The platform first converts fragmented exports into a consistent, source-backed clinical fact structure that can be read by humans and used by software. Patients and care teams can see what each source contributed, where facts agree or conflict, what information is missing, and how key measures change over time. AI then becomes safer and more useful because it works inside this prepared evidence environment rather than trying to parse every raw document from scratch.

## How this answers the rubric

The rubric's largest category is **Interpretability and Ease of Use — 40 points**. The submission should therefore make the judge feel:

> “I can see how a patient or clinician would actually use this.”

Not just:

> “This is an elegant architecture for AI agents.”

Our FHIR/flexible-schema architecture matters because it supports interpretability:

- consistent labels and types make the UI predictable
- provenance makes summaries auditable
- harmonization makes multi-source records understandable
- validation makes facts safer to reuse
- AI can cite evidence instead of hallucinating

## Revised report priority

1. Start with the user problem and interpretation gap.
2. Show the product workspace.
3. Explain the source-backed evidence layer.
4. Explain FHIR-compatible schemas as the mechanism.
5. Explain AI as an assistant over prepared evidence.
6. Close with transparency, privacy, and scalability.

