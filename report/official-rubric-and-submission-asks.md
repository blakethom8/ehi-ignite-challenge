# EHIgnite Challenge — Official Phase 1 Rubric & Submission Asks

_Source: `report/source-docs/EHIgnite-Official-Rules-1.pdf` downloaded from `ehignitechallenge.org/wp-content/uploads/2026/04/EHIgnite-Official-Rules-1.pdf` on 2026-05-08. Public website currently shows a later May 20 deadline; the official rules PDF says May 13. Verify final deadline in the portal before submission._

## 1. What they want you to submit

A complete **Phase 1 submission package** must include:

1. **Submission Entry Name**
2. **Submission Team Name**
3. **Team Lead Name and Email**
   - Team lead email should match the registration email.
4. **Submission Description**
   - No more than **1,000 characters**.
5. **Submission Narrative**
   - Uploaded as a **PDF** to `EHignitechallenge.org`.

## 2. Submission narrative format

The official rules require the narrative to be:

- **PDF format**
- **No longer than 10 pages**
- **One-inch margins**
- **Calibri font, 11-point or larger**
- **English**
- Must **not use HHS, ONC, or other federal logos**
- Must **not imply federal endorsement**

## 3. Required narrative sections

The Submission Narrative must include these sections:

### 1. Description of Solution and Problem Addressed

Describe how the solution addresses challenges in **single patient EHI exports**, including issues like:

- usability
- readability
- integration
- patient engagement
- clinician engagement
- actionability

### 2. Description of Submitting Individual, Team, or Entity

Include:

- background
- relevant experience
- interdisciplinary engagement, if any
- community engagement, if any
- relevant collaborators such as clinicians, patients, UX designers, health IT experts, etc.

### 3. Wireframe / Mockups

Include visual elements such as:

- screen views
- workflows
- UX/UI assets
- mockups of how users interact with the proposed solution

### 4. Technical Feasibility and Scalability

Describe:

- how the solution can be implemented
- how it integrates into workflows
- how it can scale across multiple EHRs
- how it can scale across care settings
- use of standards and interoperability approaches

### 5. Innovation

Highlight:

- novelty of the approach
- creative problem-solving
- unique use of technology
- how the solution makes EHI data actionable

### 6. Potential Impact

Explain:

- how the solution improves usability for patients, clinicians, and/or care teams
- expected benefits in real-world settings
- how it supports clinical care, care coordination, patient understanding, or related workflows

## 4. Required scenario/use-case coverage

Submissions must create a **usable, readable summary of relevant health information** based on the user and/or a particular scenario.

Participants must address **at least one** of these five scenarios:

### 1. Interactive Patient Tools

Enable patients to ask questions about their health data and receive understandable responses.

### 2. Customization for Clinical Domains

Build tools that allow customized queries and organizing exports by relevant domains.

### 3. Integration Across Settings

Create a solution that makes EHI exports more consumable and allows integration of EHI exports from multiple places of care.

### 4. Streamlined Payer Use Cases

Create a solution that allows easier and more streamlined sharing of information for insurance coverage using payer APIs.

### 5. Participant-Defined Use Case

Propose a unique solution that leverages single patient EHI exports to improve data usability and value beyond the outlined scenarios.

## 5. Phase 1 judging criteria

Total base score: **100 points**. Optional AI bonus: **up to 20 additional points**.

| Criterion | Points | What they are scoring |
|---|---:|---|
| **Relevance and Problem Alignment** | Up to 25 | Effectiveness in addressing EHI export usability challenges and solving real-world problems for patients/clinicians. |
| **Interpretability and Ease of Use** | Up to 40 | Novelty of approach, user-centered design, ease of use for end users, and potential to improve care coordination. |
| **Potential for Integration and Scaling** | Up to 20 | Practicality of implementation, use of consensus-based standards, scalability, and interoperability across multiple EHR systems. |
| **Privacy and Security Compliance** | Up to 15 | Adherence to HIPAA and other applicable laws; effectiveness in enabling customized privacy settings. |
| **Use of AI** | Optional, up to 20 bonus | Use of transparent, explainable AI or other advanced methods in compliance with privacy standards. |

## 6. Deadlines and prize structure from official rules PDF

### Phase 1: Concept & Design

- Submission period begins: **February 23, 2026, 10:00 AM EST**
- Submission period ends in official rules PDF: **May 13, 2026, 11:59 PM PST**
- Winner announcement: **June 2026**
- HHS may select up to **9 submissions**
- Each Phase 1 winner may receive up to **$10,000**

### Phase 2: Prototype Development

- Submission period begins: **June 23, 2026, 10:00 AM EST**
- Submission period ends: **March 24, 2027, 11:59 PM PST**
- Winner announcement: **May 2027**

### Total prize pool

- Total cash prizes: **$490,000**
- Phase 2 first place: **$250,000**
- Phase 2 second place: **$100,000**
- Phase 2 third place: **$30,000**
- Most Innovative Use of AI: **$20,000**

## 7. Eligibility notes

To be eligible, a participant must have registered as an individual, team, or entity.

High-level requirements from the rules:

- Private entities must be incorporated in and maintain a primary place of business in the United States.
- Individuals/groups must be U.S. citizens or permanent residents and at least 18 years old.
- Federal entities and Federal employees acting within scope of employment are not eligible.
- HHS employees acting in a personal capacity are not eligible.
- Participants may not use Federal funds from a grant award, cooperative agreement, or contract to develop submissions.

## 8. What this means for our EHI Atlas report

### Must-have content

Our PDF needs to explicitly cover:

1. **Problem**: raw Single Patient EHI exports are technically available but not usable/readable/actionable.
2. **Solution**: EHI Atlas converts fragmented sources into a FHIR-compatible, provenance-backed clinical fact graph.
3. **Team**: Blake's relevant healthcare data strategy background + current prototyping work.
4. **Wireframes/mockups**: Source Intake, Harmonized Record, Assistant, Data Lab/methodology, output summary/handoff.
5. **Technical feasibility**: adapters, PDF-to-FHIR, FHIR R4, provenance, deterministic harmonization, model-flexible LLM harness.
6. **Scalability**: add new data sources as adapters; scale across EHRs/care settings through standards-aligned core.
7. **Innovation**: FHIR-grounded LLM harness; evidence packets; transparent AI; local/specialized model testing.
8. **Impact**: patients/caregivers understand records; clinicians get cited summaries; care teams coordinate across settings.
9. **Privacy/security**: synthetic data, minimum necessary evidence packets, patient-controlled sharing, HIPAA-aware deployment path.

### Scenarios we should claim

Primary:

- **Integration Across Settings**

Secondary:

- **Customization for Clinical Domains**
- **Interactive Patient Tools**

Optional framing:

- **Participant-Defined Use Case**: AI-ready patient fact graph / trustworthy clinical evidence layer.

### Highest-scoring rubric target

The biggest category is **Interpretability and Ease of Use — up to 40 points**. Our report should not over-index on architecture at the expense of usability. Every technical claim should tie back to:

- readable summaries
- cited answers
- charts/trends
- source provenance
- missing information
- care coordination
- patient/clinician comprehension

### AI bonus target

The AI bonus is specifically about **transparent, explainable AI** in compliance with privacy standards. Our language should emphasize:

- constrained LLM tools
- bounded evidence packets
- source-backed outputs
- missing-information disclosure
- deterministic validation before model reasoning
- no unrestricted raw-record dumping into the model by default

## 9. Current gap in our generated PDF draft

The existing draft PDF is 8 pages, but it currently uses smaller margins than official requirements. Official rules say **one-inch margins**. Before submission, regenerate the PDF with:

- one-inch margins
- Calibri 11-point or larger
- no more than 10 pages
- no federal logos
- PDF format

