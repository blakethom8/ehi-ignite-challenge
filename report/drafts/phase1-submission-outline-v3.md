# EHIgnite Phase 1 Submission Outline v3

Purpose: produce a 10-page narrative PDF that is visibly aligned to the official required sections while still reading like one coherent story.

This version incorporates three changes:

1. Make the required submission sections obvious to the judges.
2. Reserve roughly the first 3 pages for product overview and problem/solution framing.
3. Frame Atlas against the real benchmark: strong general-purpose agents can do well on clean records, but Atlas is designed to outperform them on portability, patient ownership, scale, provenance, reconciliation, repeatability, and multi-source usability.

---

## Recommended document strategy

- Use the official section names directly in page headers or subheads.
- Keep the first page as the executive summary the user requested.
- Make Pages 1-3 the product overview block.
- Use fewer card layouts and more text density.
- Limit visuals to 5-6 high-value screenshots/diagrams.
- Keep every technical claim tied to one scoring category: interpretability, integration/scaling, privacy, or AI transparency.

## Core framing

Primary claim:

> Atlas turns fragmented Single Patient EHI exports into a structured, source-backed clinical record that is easier for patients, clinicians, and AI systems to use safely.

Benchmark claim:

> Frontier agents can already summarize clean medical PDFs surprisingly well. Atlas is not being built because those models are useless; it is being built because production healthcare record review requires a patient-owned, portable record layer with source reconciliation, provenance, chart-ready structure, repeatability, and scalable handling of diverse records.

Concise problem statement:

> The challenge is no longer only getting access to records. The challenge is making records usable when they arrive in high volume, across many formats, from many settings, for real decisions.

## Language to tighten

Reduce:

- repeated “patient-owned portable evidence workspace” phrasing on every page
- language that sounds like Atlas is mainly a future platform thesis
- broad “AI-ready” statements without concrete workflow value

Prefer:

- “structured, source-backed patient record”
- “harmonized clinical summary and review environment”
- “cited summaries, chart-ready data, and source contribution tracking”
- “bounded evidence for AI”

Keep “patient-owned” and “portable,” but use them selectively where they matter most:

- Executive Summary
- Privacy / sharing
- benchmark comparison against raw-agent workflows
- Closing paragraph

Important nuance:

- do not de-emphasize patient ownership or portability as product differences
- do avoid repeating the same exact phrase so often that it starts to sound abstract
- connect ownership and portability to concrete user value:
  - the patient can carry forward a usable record, not restart from raw files in each new tool
  - the same prepared record can support summaries, handoffs, charts, and multiple AI systems
  - the structured workspace remains valuable even when the preferred model or interface changes

---

## Page-by-page outline

## Page 1 — Executive Summary

Required section coverage:

- Description of Solution and Problem Addressed

Goal:

- Give judges a fast, high-confidence summary of what Atlas is, what problem it solves, and why it matters.

Structure:

- Title
- 2 short paragraphs:
  - raw EHI exports are available but still hard to use
  - Atlas organizes fragmented records into structured, cited, reviewable clinical information
- “What has shipped” box updated to current state
- Small “Scenarios addressed” line:
  - Integration Across Settings
  - Customization for Clinical Domains
  - Interactive Patient Tools

Suggested headline:

> EHI Atlas turns fragmented patient exports into a patient-owned, portable, source-backed record for summaries, chart review, and explainable AI assistance.

What to show:

- one small product screenshot or one small architecture thumbnail, not a full-page card grid

## Page 2 — Description of Solution and Problem Addressed: Problem Statement

Required section coverage:

- Description of Solution and Problem Addressed

Goal:

- Make the pain points concrete and tied directly to the rubric.
- Use this as the single central page that buckets the major problem statements clearly.

Narrative points:

- single-patient exports are technically available but practically hard to read
- records arrive as FHIR, C-CDA, PDFs, portal downloads, and scans
- users need answers, not folders
- clinicians need summaries that show where claims came from
- the problem gets worse with many documents, many settings, and repeated review

Recommended framing:

- start with the problem statements we already use in the report
- include a short benchmark-aware paragraph informed by the Claude Code experience
- make clear that the problem is not “LLMs cannot read records”
- make clear that the real challenge is consistency and usability across high-volume, diverse, multi-source data

Recommended subsection structure:

### Bucket 1: Access does not equal usability

- patients can download records but still cannot easily understand what matters
- clinicians still spend time re-reading exports and reconstructing histories

### Bucket 2: Multi-source records do not assemble themselves

- the same patient record is scattered across different systems and formats
- duplicate, conflicting, or partial facts require reconciliation

### Bucket 3: Generic file reading does not create a durable record

- frontier models can summarize clean documents well
- they do not automatically produce a patient-owned, portable, reusable clinical record layer
- each new tool or reviewer may need to start over from the raw files

Suggested benchmark paragraph:

> Our own testing with Claude Code reinforced an important point: strong models can already perform impressive one-off review of clean records. That raises the bar for Atlas. The question is not whether an LLM can read a document once. The question is whether a patient-owned, structured record layer can outperform generic harnesses when data is large, mixed-format, repeatedly used, and expected to remain traceable.

Recommended subsection:

### Pain points we are solving

- fragmented records across providers and care settings
- duplicate or conflicting facts across sources
- hard-to-chart labs and medication histories
- weak provenance in ordinary summaries
- repeated manual effort every time a new tool or clinician reviews the record

## Page 3 — Description of Solution and Problem Addressed: Proposed Solution

Required section coverage:

- Description of Solution and Problem Addressed
- Innovation

Goal:

- Explain the solution clearly at a high level before later wireframe pages go deeper into the application surfaces.

Narrative points:

- present Atlas as a two-pronged solution
- explain the data-layer solution first
- explain the application-layer solution second
- position benchmark comparison as part of how we will validate the architecture

Recommended subsection structure:

### Prong 1: Data aggregation and portable structured output

- ingest FHIR bundles, C-CDA, PDFs, and portal exports
- harmonize and prepare the record
- produce canonical facts with provenance
- create exportable FHIR-compatible and portable outputs ready for use in other environments

### Prong 2: Application experiences over the prepared record

- Caspian for guided review
- Plugins for scoped workflows
- FHIR Charts for structured chart views
- Export package for downstream use outside the core app

Recommended explanation:

> Atlas is not only an interface and not only a converter. It combines a patient-owned data preparation layer with application surfaces built on top of that layer.

Suggested inset or callout:

> Atlas first creates the patient-owned, portable record layer. Caspian, plugins, FHIR Charts, and export packages are downstream environments built on that shared record.

Optional alternate callout:

> A frontier model can answer questions about a file. Atlas is designed to give the patient a portable, reusable record that does not have to be rebuilt from scratch in each new tool.

Visual:

- use the Atlas Data Flow visual from the main page as a key early figure
- caption idea:
  - “Atlas harmonizes multiple source types into canonical facts and a portable bundle, then supports multiple downstream environments including Caspian, plug-ins, chart views, and export.”

Benchmark note to include near the bottom:

- we should run a direct comparison test against Claude Code and Codex-style raw-file harnesses
- success criteria should emphasize provenance, repeatability, cross-source reasoning, and exportable structured output

---

## Page 4 — Wireframes/Mockups: Product Workflow

Required section coverage:

- Wireframe/Mockups
- Description of Solution and Problem Addressed

Goal:

- Show the end-to-end user workflow clearly and simply.
- Move from high-level solution framing into concrete product surfaces.

Recommended flow:

1. Source Intake
2. Harmonized Record
3. Clinical Summary / Safety Review
4. Assistant / Q&A
5. Shareable packet or handoff

What to show:

- 2 screenshots maximum, likely Source Intake and Harmonized Record
- short captions that explain the user value, not the UI chrome

Rubric message:

> Atlas does not ask the user to browse raw files. It turns them into an interpretable workflow.

## Page 5 — Wireframes/Mockups: Usability and Interpretability

Required section coverage:

- Wireframe/Mockups
- Potential Impact

Goal:

- Win the 40-point interpretability category with concrete interface proof.

Narrative points:

- high-signal summaries first
- drilldown to source evidence second
- explicit missing-information disclosure
- trend and chart views from structured facts
- source contribution and conflict review

Best visuals:

- Clinical Summary or Safety Panel
- Assistant with evidence/citation context

Suggested callout:

> The interface answers the question first, then shows the evidence.

---

## Page 6 — Technical Feasibility and Scalability: Data Pipeline

Required section coverage:

- Technical Feasibility and Scalability

Goal:

- Explain implementation without overloading the reader with architecture detail.

Narrative points:

- source-specific adapters for FHIR, C-CDA, PDFs, and portal exports
- common FHIR-compatible fact layer
- deterministic harmonization before AI explanation
- provenance attached to extracted facts
- same structure supports summaries, charts, and assistants

Keep this line explicit:

> C-CDA and PDFs are supported inputs. They are not the final reasoning layer.

Possible figure:

- compact pipeline diagram or table

## Page 7 — Technical Feasibility and Scalability: Benchmark, Evaluation, and Scale

Required section coverage:

- Technical Feasibility and Scalability
- Innovation

Goal:

- Show that Atlas is being built and judged against real alternatives, not just described conceptually.

Narrative points:

- benchmark against raw-agent-over-files workflows
- explain expected wins:
  - traceability
  - consistency
  - cross-source deduplication
  - chart-ready output
  - missing-information disclosure
- mention current prototype assets:
  - FHIR corpus
  - PDF extraction pipeline
  - local model experiments
  - workspace package / agent comparison plan

Best visual:

- compact comparison table instead of a large screenshot

Suggested claim:

> The test is not whether a frontier model can summarize one clean record. The test is whether a patient-owned, portable, provenance-backed workflow performs better when records are numerous, mixed-format, and reused across tasks.

---

## Page 8 — Innovation

Required section coverage:

- Innovation

Goal:

- State clearly what is actually novel.

Recommended innovation points:

1. structured clinical evidence before model reasoning
2. provenance-backed facts instead of black-box summarization
3. harmonization across formats and settings
4. bounded evidence packets for explainable AI
5. reusable outputs across summaries, charts, handoffs, and future agents

Good one-sentence version:

> Atlas combines standards-based health data structuring with constrained AI reasoning so that the patient record becomes portable, readable, reviewable, and reusable.

Avoid:

- sounding like the novelty is simply “we use AI”
- overexplaining FHIR as a standard in the abstract

---

## Page 9 — Potential Impact

Required section coverage:

- Potential Impact

Goal:

- Show practical value for real users and care settings.

Narrative points:

- patients and caregivers get understandable summaries
- clinicians get faster chart review and better handoffs
- care teams can compare information across settings
- structured outputs support follow-up questions, charting, and care coordination
- this design is more scalable than one-off document summaries

Suggested framing:

- patient impact
- clinician impact
- ecosystem impact

Keep impact concrete:

- fewer repeated interpretations
- easier second opinions
- better pre-visit preparation
- more transparent AI assistance

---

## Page 10 — Description of Submitting Individual, Team or Entity + Closing

Required section coverage:

- Description of Submitting Individual, Team or Entity

Goal:

- Close with credibility and a concise restatement of why this team can build it.

Narrative points:

- Blake background and healthcare-data context
- prototyping work already completed
- clinician-informed design direction
- interdisciplinary angle: product, health IT, data, UX, AI

Small closing paragraph:

> Atlas is designed to make patient records not just accessible, but usable: structured enough for software, transparent enough for clinicians, and understandable enough for patients.

Optional final box:

- official section checklist to reassure judges all requirements were covered

---

## Recommended visual plan

Use 5-6 visuals total:

1. small overview visual on Page 1
2. benchmark or workflow diagram on Page 3
3. Source Intake screenshot on Page 4
4. Harmonized Record or source contribution screenshot on Page 4 or 5
5. Clinical Summary or Safety Panel screenshot on Page 5
6. assistant or evaluation table on Page 7 or 8

If space gets tight, remove visuals before removing explanatory prose.

## Recommended section mapping for transparency

To make the narrative sections obvious, use these exact labels in the document:

- Description of Solution and Problem Addressed
- Wireframes/Mockups
- Technical Feasibility and Scalability
- Innovation
- Potential Impact
- Description of Submitting Individual, Team or Entity

These can appear as page headers or bold section bars inside the page flow.

## What to cut or compress from the current draft

- long philosophical passages about ownership if they are not tied to workflow
- repeated comparisons between “workspace” and “chatbot” across multiple pages
- generic background on interoperability policy
- long lists of future interfaces such as CLI, agents, exports, unless directly relevant to scoring

Keep those ideas, but compress them into proof-oriented sentences.

## Suggested writing stance for the final report

Confident but honest:

- do not claim generic agents fail at everything
- do claim they are not enough for scalable, auditable healthcare record review
- do show that Atlas is a stronger substrate for repeated, multi-source, explainable use

Best concise positioning line:

> General-purpose AI can read records. Atlas is designed to turn them into a patient-owned, portable record that humans and AI can trust, reuse, and verify.
