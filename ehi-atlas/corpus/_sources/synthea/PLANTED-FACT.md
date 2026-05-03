# Planted Fact — Artifact 4

> This file documents the deliberate free-text extraction artifact planted in the synthesized clinical note for the showcase patient. Per the EXECUTION-PLAN: "Honesty about construction beats fake naturalism."

---

## What was planted

A symptom report of exertional chest tightness with onset in November, embedded naturally into the Subjective section of a pulmonology / thoracic oncology follow-up progress note.

This is clinically plausible for the patient's known conditions (COPD, GOLD Stage II; non-small cell lung cancer, stage IA2) and is the kind of symptom that would commonly appear in free-text notes but NOT be represented as a discrete FHIR Observation or Condition resource in a Synthea-generated bundle.

---

## Where in the note

**File:** `synthesized-clinical-note/progress-note-2026-01-15.txt`  
**Section:** SUBJECTIVE (second paragraph)

Exact paragraph:

> He mentions that he first noticed occasional chest tightness on exertion since approximately November of last year. He describes it as a mild pressure sensation, not pleuritic, occurring mainly when he walks more than a few blocks or climbs two flights of stairs. It resolves quickly with rest. He has not had any exertional syncope, orthopnea, or worsening nocturnal dyspnea. He denies hemoptysis since the index bronchoscopy.

The planted fact also echoes in the Assessment section, paragraph 2 (COPD), where the clinician writes:

> The chest tightness on exertion, present since November, is most consistent with ventilatory limitation from obstructive physiology in the setting of the underlying lung mass.

---

## Exact phrases the Layer 3 extractor should latch onto

Primary target phrase (Subjective):

```
occasional chest tightness on exertion since approximately November of last year
```

Secondary confirmation phrase (Assessment):

```
chest tightness on exertion, present since November
```

Both appear in the same document. The extractor should treat the Subjective instance as the symptom-report anchor and the Assessment mention as corroboration that the clinician attributed it to a specific condition.

---

## Expected Layer 3 extraction output

The LLM extractor (task 3.x, Stage 3) should lift this free-text fact into a FHIR resource with:

**Resource type:** `Condition` (or `Observation` if using the symptom-as-observation pattern — prefer `Condition` for clinical presentation of a reportable symptom)

**Suggested fields:**

| Field | Value |
|---|---|
| `resourceType` | `Condition` |
| `clinicalStatus` | `active` (as of note date 2026-01-15) |
| `category` | `symptom` (SNOMED 418799008 "Symptom") |
| `code.coding[0].system` | `http://snomed.info/sct` |
| `code.coding[0].code` | `230145002` (Difficulty breathing on exertion) or `29857009` (Chest pain) or more specifically `23924001` (Tight chest) |
| `code.coding[0].display` | "Chest tightness on exertion" |
| `subject` | `Patient/Rhett759_Rohan584_cd64ff18-472b-4d58-b73c-2a04a2bf3e61` |
| `onsetDateTime` | `2025-11` (approximate — the note says "since approximately November of last year"; note is dated 2026-01-15) |
| `recordedDate` | `2026-01-15` |
| `note[0].text` | "Patient reports occasional chest tightness on exertion since approximately November of last year. Mild pressure sensation, not pleuritic, exertional, self-resolving with rest." |
| `meta.extension[extraction-model]` | the model that ran the extraction |
| `meta.extension[extraction-confidence]` | confidence score (expected ≥ 0.90 given clear symptom language) |
| `meta.extension[extraction-prompt-version]` | frozen prompt version |
| `meta.extension[source-attachment]` | `Binary/synthesized-progress-note-rhett759-2026-01-15-binary` |
| `meta.tag[source-tag]` | `extracted` |
| `meta.tag[lifecycle]` | `extracted` |

---

## Why this fact was chosen

1. **Clinically plausible.** Exertional chest tightness is a common symptom in both moderate COPD (ventilatory limitation) and early-stage lung cancer. A real clinician would record it exactly this way — as a patient report in Subjective, with a clinical interpretation in Assessment.

2. **Not in the structured data.** Synthea does not generate this as a discrete Condition or Observation. It exists only in the free-text note. This creates a clean before/after: without the extractor, this symptom is invisible; with it, it appears as a Provenance-tracked Condition in the gold tier.

3. **Has a clear onset date.** "Since approximately November of last year" gives the extractor a dateable onset (`2025-11`). This matters for temporal alignment (Layer 3 task 3.4) and for the Sources panel showing when the symptom was first reported vs when it was first extracted.

4. **Supports multiple diagnostic interpretations.** The Assessment attributes it to COPD physiology but acknowledges that cardiac etiology has not been ruled out. This ambiguity is realistic and gives the LLM-narrator a meaningful thing to say about provenance and diagnostic confidence.

---

## Source files

| File | Description |
|---|---|
| `synthesized-clinical-note/progress-note-2026-01-15.txt` | Plaintext progress note (the source attachment) |
| `synthesized-clinical-note/DocumentReference.json` | FHIR R4 DocumentReference pointing to the Binary |
| `synthesized-clinical-note/Binary.json` | FHIR R4 Binary with base64-encoded note text |

---

## Bronze staging note

These three files are added to the bronze tier alongside the original Synthea bundle for this patient at task 1.12. They are NOT modifications to the Synthea bundle file. The bronze-staging manifest should reference them as:

```json
{
  "source": "constructed://synthesized-clinical-note/2026-01-15",
  "artifact": "4",
  "description": "Synthesized clinical note with planted chest-tightness symptom fact (Artifact 4)",
  "files": [
    "synthesized-clinical-note/DocumentReference.json",
    "synthesized-clinical-note/Binary.json",
    "synthesized-clinical-note/progress-note-2026-01-15.txt"
  ]
}
```

---

*Created: 2026-04-29 — task 1.10 (sub:sonnet)*
