# EHI Atlas — Strategy Scratchpad

Purpose: working space for ideas that should inform the submission but may not all fit inside the 10-page PDF. Use this to iterate on framing, metaphors, positioning, and report language before deciding what belongs in the final narrative.

## Current north star

> EHI Atlas is a patient-owned synthesis layer for fragmented health records.

A slightly fuller version:

> EHI Atlas turns fragmented Single Patient EHI exports into an interpretable, source-backed record workspace. Patients can gather records from EHR exports, C-CDAs, PDFs, portals, labs, and non-network sources; harmonize them into a consistent evidence structure; preserve provenance; add patient context; and generate purpose-specific summaries, charts, and handoffs when they choose to share.

## Core thesis

We should not pitch this as primarily a FHIR app or an AI harness. Those are important architectural choices, but the competition is asking for usability, readability, actionability, and interpretation.

The product thesis is:

> We make EHI understandable before making it intelligent.

The architecture thesis is:

> A consistent FHIR-compatible evidence structure gives facts a stable shape across source types, which makes summaries, charts, provenance, review workflows, and AI assistance safer and easier to interpret.

The AI thesis is:

> AI is useful because it operates over prepared evidence, not because it magically understands every raw document.

## Three-layer market framing

### 1. Record movement

Examples:

- TEFCA
- QHINs
- EHR network exchange
- provider-mediated pulls
- point-of-care document retrieval

Question answered:

> Can the record move from system A to system B?

Important nuance:

TEFCA and related networks are valuable infrastructure. We are not competing with them. Their success creates more records to synthesize.

### 2. Record possession

Examples:

- patient portal downloads
- Apple Health / patient-facing APIs
- C-CDA files
- PDFs
- lab portal reports
- exported zip files

Question answered:

> Can the patient get a copy?

Important nuance:

Possession is not the same as usability. A folder of XML, PDFs, portal documents, and lab reports still leaves the patient with the work of interpretation.

### 3. Record ownership and action

This is EHI Atlas.

Question answered:

> Can the patient organize, understand, update, share, and act on their record?

Capabilities:

- gather multi-source records
- normalize into consistent clinical facts
- preserve provenance
- identify duplicates and conflicts
- show what each source contributed
- surface missing information
- add patient/caregiver context
- produce purpose-specific summaries and handoffs
- support AI assistance over prepared evidence

## TEFCA complementarity paragraph

Draft language:

> National interoperability efforts such as TEFCA are improving the movement of records across networks. But moving records does not automatically make them understandable. Even when exchange succeeds, patients and clinicians can still receive large C-CDA documents, fragmented exports, duplicate facts, and source-specific record dumps. The exchange moves data; it does not necessarily move meaning. EHI Atlas complements exchange infrastructure by focusing on the next layer: patient-owned synthesis. It ingests records from both network and non-network sources, harmonizes duplicate or conflicting facts, preserves provenance, and presents an interpretable workspace where patients, clinicians, and care teams can understand what matters.

Shorter version:

> TEFCA helps records move. EHI Atlas helps patients own and use them.

## Patient ownership framing

The report should draw a distinction between access and ownership.

Access:

- patient can download a record
- provider can pull a record at point of care
- app can request records through an authorized connection

Ownership/action:

- patient has a living workspace
- patient can add context
- patient can identify gaps
- patient can create a purpose-specific summary
- patient can share selectively
- record persists across jobs, insurance changes, states, care systems, and life events

Draft paragraph:

> A provider-mediated, point-in-time pull does not give a person a living workspace for their clinical history. EHI Atlas is designed as that patient-owned layer: a place to gather records, reconcile them, add context, understand changes, and create a shareable packet for a specific need.

## HR / life transition analogy

Potential analogy:

> Healthcare lacks the equivalent of a personal HR file for clinical life. When people switch jobs, move states, change insurance, care for aging parents, seek a second opinion, or prepare for surgery, their history is scattered across institutions and portals. EHI Atlas creates the patient-owned record workspace that travels with them.

Use carefully. It is relatable, but should not become the main metaphor.

## C-CDA stance

Do not sound anti-C-CDA. The correct stance:

- C-CDA is a valuable exchange artifact.
- It is common today and must be supported.
- It is document-centric, not ideal as the intelligence layer.
- We ingest C-CDA, but we do not rely on AI to reason directly over C-CDA every time.
- We convert it into consistent facts first.

Draft language:

> Atlas treats C-CDA as an important source input, not the final intelligence layer. C-CDA packages clinical history in a document-centric format; Atlas converts it, along with FHIR bundles, PDFs, lab reports, and portal exports, into a common clinical evidence structure before summarization, charting, or AI assistance begins.

## Rubric alignment priority

The report should be less architecture-first and more rubric-first.

### Interpretability and Ease of Use — 40 pts

This should dominate the narrative.

Evidence to emphasize:

- readable summaries
- source-backed charts
- provenance drilldown
- source contribution view
- duplicate/conflict review
- missing information surfaced explicitly
- patient/caregiver context
- purpose-specific handoffs

### Relevance and Problem Alignment — 25 pts

Tie directly to Single Patient EHI exports.

- exported data is available but not usable
- point-in-time pulls do not create a patient-owned workspace
- raw files do not answer patient/clinician questions

### Integration and Scaling — 20 pts

Tie to source adapters and standards.

- PDFs, C-CDA, FHIR bundles, portal downloads
- FHIR-compatible internal structure
- new source types become adapters
- works across care settings because the output structure is consistent

### Privacy and Security — 15 pts

Tie to patient control and minimum necessary evidence.

- patient-owned sharing
- scope-specific handoffs
- provenance
- synthetic demo data
- private deployment path
- AI sees bounded evidence packets

### AI Bonus — 20 pts

Make AI an outcome of good structure.

- explainable AI because evidence is already structured
- bounded context packets
- source-backed answers
- missing information disclosure
- no raw-record dumping by default

## Things to avoid

- Overclaiming TEFCA access.
- Saying FHIR is the pitch.
- Framing as “universal model layer.”
- Making it look like a chatbot wrapper.
- Too many cards/callouts that make the PDF look AI-generated.
- Too much QHIN / XCA / XCPD detail in the formal submission.
- Suggesting C-CDA is bad or obsolete.

## Strong phrases to reuse

- “We make EHI understandable before making it intelligent.”
- “TEFCA helps records move. EHI Atlas helps patients own and use them.”
- “The exchange moves data; it does not necessarily move meaning.”
- “C-CDA is an input, not the intelligence layer.”
- “Patient-owned synthesis layer.”
- “An interpretable record workspace.”
- “Source-specific at the edge, consistent at the core.”
- “AI operates over prepared evidence.”
- “A living workspace for clinical history.”
- “Purpose-specific summaries and handoffs.”

## Open questions

- What is the strongest primary use case for the final PDF: moving states/jobs, second opinion, caregiver coordination, pre-op review, or general longitudinal patient workspace?
- Should the PDF use “EHI Atlas” or a more human product name?
- How much should we mention TEFCA in a 10-page submission? Current recommendation: one concise paragraph, not a dedicated section.
- Should the patient-owned angle appear in the title/subtitle?
- What screenshots best prove interpretability rather than architecture?

## Hard assumption to test: prepared evidence vs raw agent reading

Blake identified a critical assumption: Atlas must be better than simply asking Claude Code or another strong agent to read a folder of PDFs and generate a summary.

This should be treated as an evaluation hypothesis, not an untested claim.

Hypothesis:

> A curated, provenance-backed evidence workspace produces more reliable, traceable, interpretable, and reusable outputs than a raw general-purpose agent operating directly over the same documents.

Why structure should win:

- provenance is attached before generation
- facts are normalized once and reused
- cross-source deduplication is explicit
- charts are generated from typed observations
- missing information can be represented as a first-class signal
- human reviewers can inspect and correct intermediate facts

Where raw agents may win:

- quick narrative synthesis
- flexible exploration of unknown document types
- noticing facts outside the current schema

Report-safe language:

> Our design hypothesis is that AI becomes more trustworthy when it operates over prepared clinical evidence rather than re-parsing raw exports for every question. Phase 1 prototype work is structured to test that hypothesis against direct raw-document agent baselines.

See: `report/raw-agent-vs-structured-eval-plan.md`.
