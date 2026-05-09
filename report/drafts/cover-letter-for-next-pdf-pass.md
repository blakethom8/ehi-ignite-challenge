# Cover Letter / Direction for Next PDF Pass

This is a working note to guide the next version of the EHIgnite Phase 1 PDF. It is not necessarily part of the official submission, but it captures the framing changes we want the PDF to reflect.

---

## Draft cover note

The next version of the EHI Atlas submission should present the product as an interpretable, patient-owned synthesis layer for fragmented health records. The first draft captured the technical architecture, but the final competition narrative should lean more heavily into the challenge rubric: usability, readability, interpretability, care coordination, privacy, and real-world impact.

The central message should be that EHI Atlas helps patients and care teams move from record access to record ownership. TEFCA, QHINs, EHR networks, portals, and C-CDA exports are making it increasingly possible for records to move or be downloaded. But movement and possession are not the same as understanding. Patients still end up with point-in-time pulls, large XML documents, PDFs, lab reports, duplicate facts, missing information, and scattered context. EHI Atlas focuses on the next layer: giving patients a living workspace where records from many sources can be organized, harmonized, explained, and shared for a purpose.

The PDF should avoid sounding like an AI harness pitch. AI is part of the solution, but only after the record has been structured. The stronger claim is that EHI Atlas creates the prepared evidence environment that makes both humans and AI more effective. FHIR-compatible schemas matter because they give clinical facts a consistent shape across source types. Provenance matters because users need to know where facts came from. Harmonization matters because patients and clinicians need one understandable view across many sources. AI then becomes useful as an assistant over this evidence layer, not as a substitute for the layer itself.

The final PDF should therefore be more text-forward and less card-heavy. Cards and diagrams can still help, but the submission should read like a serious concept paper: clear paragraphs, explicit rubric alignment, a few high-value visuals, and direct language about what the product does for patients, clinicians, and care teams.

---

## Report tone target

Professional, clear, and sober.

Avoid:

- overly slick AI-startup language
- too many callout boxes
- “universal model harness” language as the main pitch
- implying FHIR or AI alone solves the problem
- overexplaining TEFCA mechanics

Use:

- direct product language
- patient ownership language
- interpretability and usability language
- standards-aware but not standards-obsessed framing
- honest AI limitations and guardrails

## Revised title/subtitle options

### Option A

**EHI Atlas: A Patient-Owned Synthesis Layer for Fragmented Health Records**

Subtitle:

> Turning Single Patient EHI exports into an interpretable, source-backed workspace for summaries, charts, conflicts, and handoffs.

### Option B

**EHI Atlas: Making Patient EHI Understandable and Actionable**

Subtitle:

> A source-backed record workspace that harmonizes PDFs, C-CDAs, FHIR bundles, and portal exports before AI assistance begins.

### Option C

**EHI Atlas: From Record Access to Record Ownership**

Subtitle:

> Helping patients organize, understand, and share fragmented health records through a consistent, provenance-backed evidence layer.

Current favorite: **Option A**.

## Proposed executive opening

Patients increasingly have the right to access their health information, and national interoperability efforts are improving the movement of records across systems. But access and movement do not automatically create understanding. A patient who changes jobs, moves out of state, switches insurance, seeks a second opinion, or helps an aging parent may still face a scattered folder of C-CDA files, PDFs, lab reports, portal downloads, and incomplete exports. The burden of interpretation remains with the patient, caregiver, or receiving clinician.

EHI Atlas is designed for the layer after record movement: patient-owned synthesis. It turns fragmented Single Patient EHI exports into an interpretable, source-backed record workspace. The system ingests records from many source types, maps them into a consistent FHIR-compatible evidence structure, preserves provenance, identifies duplicates and conflicts, surfaces missing information, and creates purpose-specific summaries, charts, and handoffs. AI assists by reasoning over prepared evidence; it does not replace the evidence layer.

## Proposed main sections for final PDF

1. **Executive Summary: From Record Access to Record Ownership**
2. **Problem: The Exchange Moves Data, But Not Meaning**
3. **Solution: A Patient-Owned Synthesis Workspace**
4. **User Workflow and Mockups**
   - Source Intake
   - Harmonized Record
   - Patient Context
   - Purpose-Specific Handoff
   - Assistant / Q&A
5. **Technical Approach: Consistent Evidence Structure Across Source Types**
   - PDFs, C-CDA, FHIR bundles, portal exports
   - FHIR-compatible internal facts
   - provenance, harmonization, validation
6. **Interpretability and Ease of Use**
   - readable summaries
   - charts/trends
   - conflict/source contribution view
   - missing information
7. **AI as Assistance Over Prepared Evidence**
   - bounded context packets
   - cited answers
   - transparent/explainable AI
8. **Privacy, Security, and Patient Control**
9. **Scalability, Impact, and Team**

## Paragraphs to include or adapt

### TEFCA complementarity

National interoperability efforts such as TEFCA are improving the movement of records across networks. But moving records does not automatically make them understandable. Even when exchange succeeds, patients and clinicians can still receive large C-CDA documents, fragmented exports, duplicate facts, and source-specific record dumps. The exchange moves data; it does not necessarily move meaning. EHI Atlas complements exchange infrastructure by focusing on the next layer: patient-owned synthesis.

### Patient ownership

A provider-mediated, point-in-time pull does not give a person a living workspace for their clinical history. EHI Atlas is designed as that patient-owned layer: a place to gather records, reconcile them, add context, understand changes, identify missing information, and create a shareable packet for a specific need.

### C-CDA stance

Atlas treats C-CDA as an important source input, not the final intelligence layer. C-CDA packages clinical history in a document-centric format; Atlas converts it, along with FHIR bundles, PDFs, lab reports, and portal exports, into a common clinical evidence structure before summarization, charting, or AI assistance begins.

### AI stance

The product should make the record usable before AI enters the loop. When the assistant is used, it receives a bounded evidence packet assembled from validated clinical facts. This keeps responses more explainable and less dependent on a model re-parsing every raw document from scratch.

## Visual direction

Reduce the number of card blocks. Use fewer, stronger visuals:

1. One architecture diagram: Sources → Evidence Structure → Workspace → Outputs.
2. One workflow mockup: Source Intake / Harmonized Record.
3. One output mockup: patient-owned summary or handoff.
4. One assistant example showing citations and missing information.
5. One rubric alignment table.

The final PDF should feel more like a polished white paper / proposal and less like a landing page.

## Rubric reminders

The report should explicitly call out each scoring area:

- **Relevance and Problem Alignment:** patient access is not enough; EHI exports are still hard to use.
- **Interpretability and Ease of Use:** source-backed workspace, readable summaries, charts, conflicts, missing information, purpose-specific handoffs.
- **Integration and Scaling:** source adapters, FHIR-compatible internal evidence structure, standards-aware design.
- **Privacy and Security:** patient-controlled sharing, scoped packets, provenance, minimum necessary evidence for AI.
- **AI Bonus:** transparent AI over prepared evidence, not black-box raw document summarization.


## Portability and CLI/tooling addition

The next PDF should make clear that EHI Atlas is not trying to prove that “our agent beats Claude” in isolation. The stronger claim is that a patient-owned evidence workspace makes any capable agent or review tool better. Claude, local models, future clinical agents, deterministic chart builders, and command-line tools can all use the same structured facts, provenance, source contribution state, and missing-information signals.

A CLI is a useful way to make that portability concrete. It shows that the workspace is not trapped inside a web UI or a single assistant. Potential commands:

```bash
atlas sources list
atlas facts search "creatinine"
atlas facts timeline --loinc 2160-0
atlas provenance show observation/abc123
atlas conflicts list
atlas summary build --audience patient --purpose second-opinion
atlas packet export --purpose preop-review --format markdown
atlas agent context --question "What changed recently?"
```

This supports the patient ownership story: the patient owns a portable evidence environment that can be inspected, exported, shared, and used by different tools over time.
