# Data Aggregator Wireframes

Date: 2026-05-04

Purpose: clarify the relationship between Source Intake and Harmonized Record before making more UI changes.

## Core Framing

The current confusion is not just labels. The UI is mixing three concepts:

- Durable workspaces: Source Intake, Harmonized Record, Patient Context, Publish Readiness.
- Pipeline state: source added, prepared, merged, reviewed.
- User actions: upload, prepare pending sources, inspect provenance, resolve review items.

The wireframe direction below keeps the left navigation as durable workspaces and uses each page to show only the actions that belong there.

## Left Navigation

```text
Data Aggregator

  Overview
  Source Intake
    Upload and prepare source files

  Harmonized Record
    Merged record, review, provenance

  Patient Context
    Patient-reported context

  Publish Readiness
    Activation gates
```

No standalone Cleaning Queue. Review is a sub-area of Harmonized Record.

## Wireframe A: Source Intake

Source Intake should answer: "What did I add, and is each source prepared enough to feed harmonization?"

```text
┌──────────────────────────────────────────────────────────────────────────────┐
│ SOURCE INTAKE                                                               │
│ Add files, classify each source, and prepare them for harmonization.         │
│                                                                              │
│ [ Add files ]   [ Connect portal export ]                                    │
└──────────────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────────────┐
│ Collection                                                                   │
│ [ Uploaded session · 5cbc...                                      v ]        │
│ 2 files · 1 prepared PDF · 1 structured export · 0 needs preparation         │
└──────────────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────────────┐
│ Preparation Summary                                                          │
│                                                                              │
│ ┌───────────────┐ ┌───────────────┐ ┌───────────────┐ ┌───────────────┐      │
│ │ Files added   │ │ Needs context │ │ Needs prepare │ │ Ready to merge │      │
│ │ 2             │ │ 2             │ │ 0             │ │ 2             │      │
│ └───────────────┘ └───────────────┘ └───────────────┘ └───────────────┘      │
└──────────────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────────────┐
│ Source Files                                                   [ Prepare ]   │
│                                                                              │
│ File                         Type          Source context     Prep state      │
│ ───────────────────────────────────────────────────────────────────────────  │
│ functionhealth_results.pdf   PDF report    Missing            Prepared PDF    │
│ cedars-sinai.json            FHIR export   Missing            Prepared FHIR   │
│                                                                              │
│ Row detail drawer:                                                           │
│ - user description                                                           │
│ - source organization / portal                                               │
│ - likely clinical content                                                    │
│ - preparation log: OCR, JSON parse, extracted artifact path                  │
└──────────────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────────────┐
│ Next                                                                         │
│ All sources are prepared enough to merge.                                    │
│ [ Open Harmonized Record ]                                                   │
└──────────────────────────────────────────────────────────────────────────────┘
```

### Source Intake Notes

- Do not show Merge or Review as stepper items here.
- "Prepare" is intentionally broad: PDF extraction, FHIR envelope parsing, CSV normalization, XML/C-CDA conversion, image OCR.
- The primary table should be file-first, not fact-first.
- The button should only say "Prepare" when there is pending preparation. If everything is ready, the primary action should become "Open Harmonized Record."
- Missing file descriptions are not merge blockers, but should remain visible because they reduce downstream interpretability.

## Wireframe B: Harmonized Record

Harmonized Record should answer: "What did the prepared sources become, what needs review, and where did each fact come from?"

```text
┌──────────────────────────────────────────────────────────────────────────────┐
│ HARMONIZED RECORD                                                            │
│ Canonical record built from prepared sources.                                │
│                                                                              │
│ Collection [ Uploaded session · 5cbc...                             v ]      │
│                                                                              │
│ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐          │
│ │ Sources      │ │ Canonical    │ │ Shared facts │ │ Open review  │          │
│ │ 2            │ │ 206          │ │ 26           │ │ 1            │          │
│ └──────────────┘ └──────────────┘ └──────────────┘ └──────────────┘          │
└──────────────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────────────┐
│ Tabs:  Record  |  Review Queue  |  Source Contributions  |  Provenance       │
└──────────────────────────────────────────────────────────────────────────────┘

RECORD TAB
┌──────────────────────────────────────────────────────────────────────────────┐
│ Resource tabs: Labs | Conditions | Medications | Allergies | Immunizations   │
│                                                                              │
│ [x] Cross-source only   Search [____________________]                        │
│                                                                              │
│ Canonical fact                  Sources   Latest        Status               │
│ ───────────────────────────────────────────────────────────────────────────  │
│ Albumin                         2         4.6 g/dL      Shared               │
│ Alanine aminotransferase        2         26 U/L        Shared               │
│ ...                                                                          │
│                                                                              │
│ Right drawer on row click:                                                   │
│ - source measurements                                                        │
│ - confidence / conflict state                                                │
│ - document references                                                        │
└──────────────────────────────────────────────────────────────────────────────┘

REVIEW QUEUE TAB
┌──────────────────────────────────────────────────────────────────────────────┐
│ Review Queue                                                                 │
│ Only facts or sources needing human judgment.                                │
│                                                                              │
│ Type       Item                         Reason                 Action        │
│ ───────────────────────────────────────────────────────────────────────────  │
│ Lab        Example merged observation   same-day value spread  Resolve       │
│ Source     Example source               preparation failed     Re-prepare    │
│                                                                              │
│ Empty state: "No review items. This collection can proceed to publish checks."│
└──────────────────────────────────────────────────────────────────────────────┘

SOURCE CONTRIBUTIONS TAB
┌──────────────────────────────────────────────────────────────────────────────┐
│ Source Contributions                                                         │
│                                                                              │
│ Source file                    Unique   Shared   Raw   Prepared state        │
│ ───────────────────────────────────────────────────────────────────────────  │
│ functionhealth_results.pdf     32       26       58    Prepared PDF          │
│ cedars-sinai.json              181      26       416   Prepared FHIR         │
│                                                                              │
│ Row click: "What did this source contribute?"                               │
│ - Labs / conditions / medications / allergies / immunizations                │
└──────────────────────────────────────────────────────────────────────────────┘

PROVENANCE TAB
┌──────────────────────────────────────────────────────────────────────────────┐
│ Provenance                                                                   │
│                                                                              │
│ Select canonical fact [ Albumin                                      v ]     │
│                                                                              │
│ Canonical fact                                                               │
│    ├─ Function Health PDF, page/artifact reference                           │
│    └─ Cedars FHIR Observation reference                                      │
│                                                                              │
│ FHIR Provenance entities + source labels + harmonize activity                │
└──────────────────────────────────────────────────────────────────────────────┘
```

### Harmonized Record Notes

- Do not show Source Intake steps in the page header.
- Use tabs rather than stacked sections. The current page is too vertically busy because source contributions, review, and record tabs are all visible at once.
- The default tab should be Record.
- Review Queue is not a top-level route. It is a tab because review items are exceptions against the merged record.
- Source Contributions is where the current source table belongs.
- Provenance is where the reverse provenance walk belongs.

## Recommended Simplification

Use this page split:

```text
Source Intake
  Owns: upload, file metadata, preparation state, prepare action.
  Does not own: canonical facts, review queue, provenance graph.

Harmonized Record
  Owns: canonical facts, merge state, review queue, source contribution, provenance.
  Does not own: upload controls or generic file classification.
```

## Suggested Next UI Change

Before changing more styling, restructure Harmonized Record into four tabs:

1. Record
2. Review Queue
3. Source Contributions
4. Provenance

Then move the current sources table and reverse provenance walk into `Source Contributions`, leaving the Record tab much cleaner.
