# Podcast Insights — FHIR / EHI Product Positioning

*Created: 2026-04-05*  
*Sources: Out of the FHIR podcast episode pages + follow-up product discussion*

---

## Why This File Exists

We reviewed several episodes of **Out of the FHIR** and used them to sharpen product direction for the EHI Ignite Challenge. These were not transcript-level deep dives; they were used to pressure-test positioning, workflow, and target user decisions.

This file captures the strategic conclusions worth preserving for future build sessions.

---

## Episodes Reviewed

### Episode 21 — Pooja Babbrah
**Theme:** Pharmacy as an underrated interoperability player

Key takeaway:
- Pharmacy is not a sidecar to interoperability. It is one of the most important ways to turn fragmented health records into clinically useful information.

### Episode 18 — Michael Westover
**Theme:** Payer-provider exchange, informatics, value-based care

Key takeaway:
- The opportunity is not limited to one provider's chart view. Cross-boundary data exchange matters, especially for care coordination and value-based workflows.

### Episode 22 — Chris Hutchins
**Theme:** COVID, data, and the coming AI reckoning in healthcare

Key takeaway:
- Healthcare did not lack data. It lacked urgency and usable delivery. The real product opportunity is compressing time-to-understanding.

### Episode 24 — HIMSS 2026 Roundup
**Theme:** Skepticism toward generic “AI-first” messaging

Key takeaway:
- The market is already full of vague AI positioning. A generic AI-for-EHR product story is weak. The product needs a concrete workflow and a sharp value proposition.

---

## Core Strategic Conclusions

## 1) Do not build a generic FHIR browser
That path is too shallow and too crowded.

Weak framing:
- AI-powered EHR insights
- next-generation FHIR browser
- interoperability assistant

These all sound plausible and boring.

Better framing:
- **patient journey intelligence**
- **clinical briefing engine**
- **medication-centered clinical intelligence**
- **evidence-backed care summary**

The product should not feel like a record viewer. It should feel like a system that tells a clinician what matters now.

---

## 2) The best initial wedge is medication-centered intelligence
Medication history is one of the strongest ways to reconstruct the patient story.

Why medication is a strong wedge:
- longitudinal
- clinically actionable
- safety-critical
- cross-setting
- often fragmented
- directly relevant to high-stakes decisions

Medication data can reveal:
- disease burden
- treatment progression
- active risk factors
- care fragmentation
- recent clinical instability
- reconciliation complexity

This is stronger than a generic summary because it is immediately useful in real workflows.

---

## 3) Start doctor-first, not patient-first
The primary user should be a **doctor or care team member**, not the patient.

Why:
- the pain is sharper
- the use case is more urgent
- the workflow is more defensible
- the value is easier to demonstrate in a competition setting

Best initial user:
- surgeon / specialist / peri-op reviewer / clinician doing high-speed chart review

Secondary users later:
- memory-care intake team
- geriatric care team
- discharge / transition-of-care team
- payer care manager
- patient / caregiver simplified summary

Patient-facing can be an output later, but it should not be the first product surface.

---

## 4) The real product value is time-to-understanding
A recurring theme across the podcast insights is that healthcare already has massive data volume. The problem is not access alone. The problem is turning fragmented data into understanding quickly enough to matter.

This suggests the product value proposition should sound like:

> Clinicians don’t need more records. They need the right 5 facts in 30 seconds.

That is much stronger than saying:
- we summarize EHR data
- we use AI to unlock insights
- we help patients understand their records

The product should optimize for **decision speed + evidence-backed confidence**.

---

## 5) Pharmacy and payer angles are both important, but they are different surfaces
### Pharmacy angle
At the individual level, pharmacy is best thought of as a lens into the patient's longitudinal story.

A strong pharmacy layer should capture:
- active meds grouped by class / indication / risk
- medication episodes (start, stop, restart, dose change)
- new starts / abrupt stops / switches / escalation
- high-risk med classes
- polypharmacy burden
- likely reconciliation complexity

### Payer angle
Payer workflows are valid, but the UI is different.

A payer-oriented interface is less likely to be a deep clinical chart summary and more likely to be:
- action queue
- patient summary
- risk flags
- care gaps
- next-best action
- care management workflow

This means one normalized intelligence layer can support multiple views, but the first UI should stay focused.

---

## 6) Memory care / geriatric intake is a promising secondary use case
A medication-centered patient journey view also maps surprisingly well to memory care.

Potential value:
- polypharmacy burden
- fall-risk or confusion-associated medications
- psych meds / sedatives / anticholinergics
- hospitalization timeline
- caregiver-friendly intake summary
- complexity of regimen and longitudinal context

This could become a strong second workflow after the initial clinician-facing build.

---

## Product UI Direction

### The interface should feel like:
- a clinical briefing
- a timeline
- a risk dashboard
- evidence-backed Q&A

### It should not feel like:
- a giant EMR clone
- a patient portal
- a chat-only assistant
- a raw FHIR resource browser

### Suggested UI sections
1. **Summary header**
   - patient basics
   - key diagnoses
   - allergies
   - reason for review

2. **What matters now** panel
   - blood thinners
   - immunosuppressants
   - recent hospitalization
   - active risk flags
   - major recent changes

3. **Medication timeline**
   - starts/stops
   - dose changes
   - class highlighting
   - risk overlay

4. **Question-driven answers**
   - Is this patient on blood thinners?
   - Any medications affecting anesthesia?
   - Any recent major changes?
   - What matters for memory / fall risk?

5. **Evidence drawer**
   - provenance
   - encounter source
   - medication source
   - dates
   - confidence

---

## Recommended Positioning Language

### Strong lines worth keeping
- **Clinicians don’t need more records. They need the right 5 facts in 30 seconds.**
- **Don’t build a FHIR browser. Build a patient-journey intelligence layer.**
- **Healthcare doesn’t lack data. It lacks workflow-ready understanding.**

### Weaker language to avoid
- AI-powered interoperability
- FHIR-based patient record explorer
- next-generation healthcare assistant
- generic patient summary platform

---

## Best Current Product Framing

If we had to summarize the current direction in one sentence:

> Build a doctor-first, medication-centered patient journey intelligence layer that turns fragmented FHIR/EHI data into fast, evidence-backed clinical understanding.

That is the current north star.

---

## Potential Build Sequence

### Phase 1 / challenge demo
- clinician-first
- medication timeline
- what-matters-now panel
- question-driven answers
- evidence drawer

### Phase 2
- memory care / geriatric intake adaptation
- caregiver-friendly summary output

### Phase 3
- payer care-manager surface
- action queue / next-best action workflow

---

## Related Internal Notes
- `~/Chief/20-projects/ehi-ignite-challenge/meeting-notes/2026-04-04-out-of-the-fhir-pooja-babbrah-pharmacy-interoperability.md`
- `~/Chief/20-projects/ehi-ignite-challenge/meeting-notes/2026-04-04-out-of-the-fhir-additional-episodes-synthesis.md`
- `~/Chief/20-projects/ehi-ignite-challenge/research/resources-and-links.md`

---

## Bottom Line

The podcast review pushed us toward a sharper conclusion:

- generic AI + FHIR is weak
- medication-centered workflow intelligence is strong
- doctor-first is the right first user
- patient/caregiver and payer views can come later from the same intelligence layer

This should be the starting point for the next Claude Code build session.
