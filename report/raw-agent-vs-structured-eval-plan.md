# Evaluation Plan — Raw Agent vs Structured Evidence Workspace

Date: 2026-05-08

## Why this matters

A major assumption behind EHI Atlas is that structured, curated clinical evidence performs better than asking a general-purpose agent to read raw records directly.

This is not a trivial assumption. Modern coding/agent tools can already read multiple PDFs, extract facts, write summaries, and generate reports. If EHI Atlas cannot outperform that baseline on traceability, consistency, usability, or safety, then the added structure is architectural overhead rather than product value.

So we should test it directly.

## Core hypothesis

> A structured, provenance-backed EHI workspace will produce more reliable, traceable, interpretable, and reusable outputs than a raw general-purpose agent working directly over the same PDFs and exports.

Shorter:

> Prepared evidence beats raw agent reading.

## Competing approaches

### Baseline A — Raw agent over files

Give Claude Code / Claude / another strong agent the raw files:

- PDFs
- C-CDA XML
- FHIR exports
- lab reports
- portal downloads

Ask it to answer user-facing clinical questions directly.

The agent can inspect files and reason, but it does not get a prebuilt harmonized fact graph, source contribution table, provenance model, or deterministic validation layer.

### Approach B — EHI Atlas structured workspace

Run the same sources through Atlas:

1. Source Intake
2. Extraction/adapters
3. FHIR-compatible fact graph
4. Provenance attachment
5. Harmonization / deduplication
6. Conflict and missing-information detection
7. Assistant over bounded evidence packet
8. Summary/chart/handoff generation

## What we expect to be better

Atlas does not need to beat a raw agent on every dimension. It needs to be clearly better on dimensions that matter for patient/clinical trust.

### 1. Traceability

Question:

> Can every important claim be traced to a source file, page/resource, and extracted fact?

Expected advantage:

Atlas should win because provenance is part of the data model, not reconstructed after the answer.

### 2. Consistency

Question:

> If the same record is queried multiple times, are facts represented consistently?

Expected advantage:

Atlas should win because facts are normalized once and reused. A raw agent may re-parse and phrase facts differently each time.

### 3. Cross-source deduplication

Question:

> Can the system tell whether two sources contain the same medication/lab/condition versus distinct facts?

Expected advantage:

Atlas should win because harmonization and source contribution are explicit system functions.

### 4. Missing-information disclosure

Question:

> Does the output clearly state what is missing or unknown?

Expected advantage:

Atlas should win if absence and coverage are first-class concepts in the workspace.

### 5. Reusability

Question:

> Can the extracted facts power multiple downstream views: summary, chart, Q&A, handoff, conflict review?

Expected advantage:

Atlas should win because facts become reusable objects. A raw agent answer is usually a one-off artifact.

### 6. Human reviewability

Question:

> Can a human reviewer inspect the intermediate state and correct errors?

Expected advantage:

Atlas should win because it has source intake, harmonized record, review queue, and provenance surfaces.

### 7. Chartability / structured computation

Question:

> Can the system reliably plot labs over time or compute medication status from structured data?

Expected advantage:

Atlas should win because chart data comes from typed Observations / medications rather than prose extraction.

## Where raw agents may beat Atlas

We should be honest. Raw agents may be better at:

- quick narrative summarization
- broad semantic synthesis from messy notes
- spotting surprising facts outside current schemas
- one-off exploratory analysis
- adapting to unknown document types before an adapter exists

This means the benchmark should not assume structure wins everywhere. It should identify where structure wins and where agentic reading remains valuable.

## Test records

Start with records already available in the repo/lab:

1. **Corrected lab report PDF**
   - `data/aggregation-uploads/smoke-codex-upload-2026/9ae6d3aee5a7-corrected-lab-report.pdf`
   - Has Opus gold output.
   - Good for lab extraction, provenance, chartability.

2. **Synthetic multi-source collection**
   - `synthea-demo` / aggregation upload collection.
   - Good for harmonization, source contribution, deduplication.

3. **Cedars-style health summary / chart PDF if available**
   - Good for narrative + structured mixed content.
   - Good stress test for raw agent vs structured pipeline.

4. **Function Health or lab-direct PDF if available and safe**
   - Good for out-of-network / non-TEFCA records.
   - Avoid committing PHI.

## Evaluation questions

Use realistic tasks, not generic extraction prompts.

### Patient-facing

1. What are the five most important things in this record for me to understand?
2. What changed recently?
3. What should I ask my doctor about?
4. What information appears to be missing?
5. Which facts came from which source?

### Clinician/care-team-facing

1. Summarize active medications, allergies, key conditions, and recent abnormal labs.
2. Identify duplicated or conflicting facts across sources.
3. Generate a one-page handoff for a specialist visit.
4. Chart kidney/liver/metabolic labs over time.
5. List evidence behind each safety concern.

## Scoring rubric

Score each answer 1–5 on each dimension.

| Dimension | 1 | 3 | 5 |
|---|---|---|---|
| Correctness | Major factual errors | Mostly correct with gaps | Accurate against gold/source review |
| Completeness | Misses key facts | Captures obvious facts | Captures key facts and relevant absences |
| Traceability | No citations | Some citations | Every important claim traceable |
| Interpretability | Hard to use | Readable but generic | Clear, actionable, user-centered |
| Cross-source reasoning | Treats files separately | Some merge logic | Explicit dedup/conflict/source contribution |
| Missing-info handling | Silent gaps | Some caveats | Specific missing/unknown items surfaced |
| Reusability | One-off prose | Some structured output | Facts reusable for charts/Q&A/handoff |
| Reviewability | No intermediate state | Some extracted notes | Inspectable/correctable facts and provenance |

## Quantitative extraction metrics where possible

For labs/vitals and other structured facts:

- precision
- recall
- F1
- missing key fields
- extra/hallucinated facts
- unit/date correctness
- source locator correctness
- duplicate handling
- latency
- cost

## Suggested first experiment

### Experiment 1 — Lab PDF: raw agent vs structured extraction

Input:

- corrected lab report PDF
- Opus gold output

Tasks:

1. Extract all labs with value, unit, reference range, flag, date, and source page.
2. Identify abnormal results.
3. Produce a patient-friendly summary.
4. Produce a machine-readable table suitable for charting.

Compare:

- Raw Claude/Claude Code over the PDF
- `multipass-fhir`
- `medgemma-ollama`
- existing Opus gold

Win condition for Atlas:

- higher or equal extraction F1 than raw agent
- better source traceability
- better machine-readable output
- better chart-ready structure

### Experiment 2 — Multi-source harmonization

Input:

- one FHIR export
- one PDF/lab report
- one C-CDA or synthetic equivalent

Tasks:

1. Identify shared facts across sources.
2. Identify unique facts from each source.
3. Identify conflicts or ambiguous duplicates.
4. Produce a one-page handoff with citations.

Compare:

- Raw agent over all files
- Atlas harmonized record + assistant

Win condition for Atlas:

- clearer source contribution table
- better deduplication
- fewer unsupported claims
- more inspectable intermediate state

## How to phrase this in the report

We should not say we already proved this unless we run the benchmark.

Safe language:

> Our design hypothesis is that patient records become more usable and trustworthy when clinical facts are structured, harmonized, and provenance-backed before AI assistance begins. Phase 1 prototype work focuses on building and testing that evidence layer against the simpler baseline of direct AI summarization over raw exports.

Stronger language after evaluation:

> In early tests, the structured evidence workflow improved traceability and reuse compared with direct raw-document prompting, especially for source-backed summaries, chart generation, and cross-source deduplication.

## Report implication

This evaluation plan should become part of the Technical Feasibility / Innovation section.

The honest claim:

> We are not assuming that AI alone solves EHI usability. We are testing whether a curated, provenance-backed workspace produces better and more transparent outputs than raw agentic document reading.

That is a mature claim and should read well to judges.

## Portability nuance

The point of the benchmark is not to prove that Atlas's own assistant is always better than Claude or another frontier model. The more important claim is that structured evidence makes capable agents better.

A useful evaluation variant is:

1. Claude over raw PDFs/exports.
2. Claude over Atlas-generated evidence packets, provenance tables, and structured facts.
3. Atlas assistant over the same prepared evidence.

If Claude performs better with Atlas's prepared workspace than with raw files, that supports the core product thesis: the value is the patient-owned evidence environment, not the particular model sitting on top.

This should be reflected in the report:

> EHI Atlas is designed to improve the performance, transparency, and portability of many agent systems by giving them a structured, provenance-backed workspace. Our own assistant is one implementation; the evidence layer is the durable patient-owned asset.
