# Reference Review Find-in-PDF

## Purpose

Reference Review needs a trustworthy bridge between an extracted FHIR fact and the source PDF region that supports, contradicts, or fails to support it.

The interaction target is:

1. Reviewer selects a fact.
2. System moves to the most likely PDF page.
3. System highlights one or more candidate evidence regions.
4. Reviewer confirms, rejects, or annotates the connection.
5. Confirmed connections become review evidence, not just UI state.

This is not the same as publishing ground truth. A locator match is candidate evidence until a human accepts it.

## Product Language

Use these terms consistently:

- **Extracted fact**: a candidate FHIR resource or resource-level fact emitted by a pipeline.
- **Candidate evidence region**: a PDF page and normalized bbox that may support the fact.
- **Confirmed evidence region**: a candidate region accepted by the reviewer.
- **Unsupported fact**: an extracted fact Blake decides is not supported by the PDF.
- **Reviewed reference bundle**: accepted and edited resources published as the benchmark answer key.

Avoid saying the locator “proved” a fact. The locator finds likely evidence; the reviewer decides.

## Current Implementation

Backend module:

- `api/core/pdf_fact_locator.py`

Router endpoints:

- `GET /api/ground-truth-review/runs/{run_id}/pdf/pages`
- `GET /api/ground-truth-review/runs/{run_id}/pdf/pages/{page_number}.png`
- `GET /api/ground-truth-review/runs/{run_id}/pdf/search?q=...`
- `GET /api/ground-truth-review/runs/{run_id}/locate-fact?resource_ref=...`

Frontend:

- `app/src/pages/GroundTruthReview/ReferenceReview.tsx`

The locator currently uses `pdfplumber` text extraction. It builds a query from the selected fact:

- display text
- value
- date
- status
- first few codes

It then scans PDF words in sliding windows and returns normalized page bboxes. The PDF pane renders pages as PNG images via `pypdfium2`; highlight overlays use normalized bbox coordinates over those page images.

## Locator Result Contract

Each match returns:

```json
{
  "page_number": 3,
  "bbox": { "x": 0.024, "y": 0.364, "width": 0.243, "height": 0.017 },
  "text": "Method Time Performed At Pathologist Signature Egg White (F001) IgE <0.10",
  "score": 0.825,
  "confidence": "high",
  "matched_terms": ["egg", "f001", "ige"],
  "strategy": "heuristic-text-v1"
}
```

Coordinates are normalized to the original PDF page coordinate space:

- `x`, `y`: top-left origin
- `width`, `height`: normalized dimensions
- all values range from `0` to `1`

The UI can draw the same bbox on any rendered image size by multiplying by the displayed page width and height.

## Review State Contract

Confirmed locator evidence should be persisted as `PdfAnnotation` records in the review session:

```json
{
  "annotation_id": "annotation-...",
  "page_number": 3,
  "bbox": { "x": 0.024, "y": 0.364, "width": 0.243, "height": 0.017 },
  "annotation_type": "supports_fact",
  "linked_resource_ref": "Observation/o1",
  "note": "Reviewer confirmed this line supports the extracted lab value.",
  "created_at": "...",
  "updated_at": "..."
}
```

Fact decisions should link to annotations through `linked_annotation_ids`.

This separation matters:

- Locator results are disposable suggestions.
- Annotations are durable review evidence.
- Decisions are reviewer judgments about extracted facts.

## UI Model

Reference Review should feel like synchronized work surfaces:

- **Source PDF pane**: rendered page images, zoom, page navigation, candidate/confirmed overlays.
- **Extracted facts pane**: readable fact table, filters, search, fact selection, locator trigger.
- **Fact detail pane**: decision workflow, notes, JSON edit, best candidate evidence, confirmed annotations.

Pane behavior:

- Panes remain in fixed order: PDF, facts, detail.
- Panes are independently collapsible.
- Separators are draggable.
- Collapsing a pane removes it from layout; reopening restores it.
- Locator results should always reopen the PDF pane if it is collapsed.

## Agent Direction

The next version should add a narrow locator agent, not a general chart-review agent.

Agent input:

- source PDF page images and/or text words
- selected fact summary
- extracted resource JSON
- current heuristic candidates
- reviewer intent: `find_support`, `find_contradiction`, or `find_missing`

Agent output must be structured:

```json
{
  "resource_ref": "Observation/o1",
  "answer": "found" ,
  "regions": [
    {
      "page_number": 3,
      "bbox": { "x": 0.024, "y": 0.364, "width": 0.243, "height": 0.017 },
      "evidence_text": "Egg White (F001) IgE <0.10",
      "relationship": "supports_fact",
      "confidence": "high",
      "rationale": "The PDF row contains the same test name and value."
    }
  ],
  "warnings": []
}
```

The agent must not directly change review decisions. It proposes regions; Blake confirms them.

## Implementation Roadmap

### Phase 1: Locator MVP

Shipped:

- Render PDF pages as images.
- Extract PDF text with word bboxes.
- Find candidate regions from selected facts.
- Navigate to best match page.
- Draw candidate overlays.
- Show confidence, score, matched terms, strategy.

### Phase 2: Confirmed Evidence

Build next:

- Click a candidate highlight to select it.
- `Confirm supports fact` creates a `PdfAnnotation`.
- `Confirm contradiction` creates a contradiction annotation.
- Fact decisions link to annotation ids.
- Confirmed overlays render differently from candidate overlays.
- Draft save persists annotations.

### Phase 3: Manual Region Creation

Build after confirmed evidence:

- Click-drag on PDF page creates a normalized bbox.
- User chooses annotation type.
- User links region to selected fact or creates a missing-fact stub.
- Store region with page number, bbox, note, and linked resource ref.

### Phase 4: Locator Agent

Build when heuristic limits are clear:

- Agent reranks heuristic candidates.
- Agent can inspect page images for scanned PDFs or layout-heavy sections.
- Agent returns structured candidate regions only.
- UI shows `heuristic`, `agent`, and `reviewer-confirmed` provenance separately.

### Phase 5: Pipeline Provenance

Longer term:

- Extraction pipelines emit source locators during extraction.
- Review UI shows pipeline-provided regions first.
- Locator agent is used to validate, repair, or find missing provenance.
- Evaluation can score both extracted facts and source-grounding quality.

## Design Principle

The core problem is shared attention between agent and reviewer.

The UI and locator must always agree on:

- selected fact
- current PDF page
- candidate regions
- confirmed annotations
- confidence/provenance of each region

When the user says “find this,” every subsystem should point at the same fact and the same PDF state.
