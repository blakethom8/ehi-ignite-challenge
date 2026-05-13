# Extraction Pipeline — Data Model Reference

> What comes out of `multipass-fhir` at each stage. Walks through the **three layers** of data the pipeline produces and shows where cross-resource reconciliation (common date / encounter / patient) actually happens. Includes a worked end-to-end example with real JSON.

---

## TL;DR — the three layers

```
┌──────────────────────────────────────────────────────────────────────────┐
│                                                                          │
│   PDF + DocumentContext (Pass 0)                                         │
│        │                                                                 │
│        ▼                                                                 │
│   ┌─────────────────────────────────────────────────────────────┐       │
│   │  Layer 1: Pass output (Pydantic)                            │       │
│   │                                                             │       │
│   │  Each pass returns an `XExtraction` containing list[XEntry]│       │
│   │  Independent — no cross-references between passes           │       │
│   │                                                             │       │
│   │  Examples:                                                  │       │
│   │   - LabObservationExtraction(observations=[...])            │       │
│   │   - ConditionExtraction(conditions=[...])                   │       │
│   │   - VitalSignExtraction(vital_signs=[...])                  │       │
│   └─────────────────────────────────────────────────────────────┘       │
│        │                                                                 │
│        ▼ (per-builder transform)                                         │
│   ┌─────────────────────────────────────────────────────────────┐       │
│   │  Layer 2: FHIR resource dicts (per builder)                 │       │
│   │                                                             │       │
│   │  _X_to_fhir(entry, common_meta, ...) → dict                 │       │
│   │  Every resource: subject = Patient/<placeholder>            │       │
│   │  Every resource: meta.extension carries provenance          │       │
│   │  Cross-references NOT yet wired                             │       │
│   └─────────────────────────────────────────────────────────────┘       │
│        │                                                                 │
│        ▼ (post-passes — the reconciliation layer)                        │
│   ┌─────────────────────────────────────────────────────────────┐       │
│   │  Layer 3: Merged FHIR Bundle                                │       │
│   │                                                             │       │
│   │  _assign_encounter_references — wires resources to Encounter│       │
│   │  _rewrite_patient_references  — Patient/unknown → real id   │       │
│   │  + LOINC matcher, interpretation, clinical-category etc.    │       │
│   │                                                             │       │
│   │  Output: a single FHIR Bundle of `type: document`           │       │
│   │  with cross-references resolved                             │       │
│   └─────────────────────────────────────────────────────────────┘       │
│                                                                          │
└──────────────────────────────────────────────────────────────────────────┘
```

**The headline answer to "where do common date / encounter / patient live?":**

| Question | Answer | Where in the code |
|---|---|---|
| Common **date** across resources | `DocumentContext.encounter_date` is the per-pass fallback when an entry has no date of its own | Set in each `_X_to_fhir` builder via `doc_context.encounter_date` fallback |
| Common **encounter** | Post-pass `_assign_encounter_references` wires `encounter: Reference(...)` after all passes return | `lib/extract/pipelines/multipass_fhir.py` |
| Common **patient** | Post-pass `_rewrite_patient_references` rewrites `Patient/<placeholder>` to the actual extracted Patient.id | `lib/extract/pipelines/multipass_fhir.py` |

**Pydantic schemas are intentionally simple** — they capture only what one pass extracts in isolation. Cross-resource reconciliation is deterministic post-processing. This separation lets each pass be a single focused LLM call without inter-pass awareness.

---

## Layer 1 — Pass output (Pydantic)

### The pattern

Every pass follows the same shape:

```python
class XEntry(BaseModel):
    # Per-fact fields (display, value, unit, code, dates, etc.)
    page: int | None = None        # 1-indexed page where this fact appeared
    source_text: str | None = None  # short verbatim phrase for bbox lookup


class XExtraction(BaseModel):
    items: list[XEntry] = Field(default_factory=list)
```

### What's NOT in the Pydantic schemas

- ❌ **No subject reference.** No `patient_id` field on per-resource entries.
- ❌ **No encounter reference.** No `encounter_id` field tying labs to a visit.
- ❌ **No cross-pass linkage.** A `MedicationEntry` doesn't know about any `Condition` or `Encounter` extracted by other passes.
- ❌ **No FHIR-shape fields.** `meta.extension`, `category`, `coding[]` are added by the FHIR builders, not present in the Pydantic layer.

This is intentional. Each pass is a single LLM call with a focused prompt; making the schema cross-aware would force the model to think across resource types and degrade extraction quality.

### What IS in every pass's prompt

Every per-resource pass receives a **`context_suffix`** appended to its system prompt, derived from the Pass 0 output:

```
Document context (extracted in Pass 0; carry into every emitted resource):
  - document_type: lab-report
  - patient_name: Blake Thomson
  - patient_dob: 1993-06-16
  - encounter_date: 2026-04-22
  - ordering_provider: Steven Krems, MD
  - facility_name: Quest Diagnostics-West Hills
```

So the model knows the "who" and "when" — but each per-resource entry only carries fact-specific dates if they're explicitly different from the document encounter date.

### The 13 specialist passes — schema names

| Pass name | Pydantic schema | Entry list field |
|---|---|---|
| `conditions` | `ConditionExtraction` | `conditions: list[ConditionEntry]` |
| `medications` | `MedicationExtraction` | `medications: list[MedicationEntry]` |
| `allergies` | `AllergyExtraction` | `allergies: list[AllergyEntry]` |
| `immunizations` | `ImmunizationExtraction` | `immunizations: list[ImmunizationEntry]` |
| `lab_observations` | `LabObservationExtraction` | `observations: list[LabObservationEntry]` |
| `vital_signs` | `VitalSignExtraction` | `vital_signs: list[VitalSignEntry]` |
| `encounter` | `EncounterExtraction` | `encounters: list[EncounterEntry]` |
| `practitioner` | `PractitionerExtraction` | `practitioners: list[PractitionerEntry]` |
| `organization` | `OrganizationExtraction` | `organizations: list[OrganizationEntry]` |
| `clinical_notes` | `ClinicalNoteExtraction` | `clinical_notes: list[ClinicalNoteEntry]` |
| `patient_demographics` | `PatientExtraction` | `patients: list[PatientEntry]` |
| `coverage` | `CoverageExtraction` | `coverages: list[CoverageEntry]` |
| `social_history` | `SocialHistoryExtraction` | `social_history: list[SocialHistoryEntry]` |

Plus Pass 0:
- `document_context` → `DocumentContext` (default pipeline)
- `document_map` → `DocumentMap` (scout pipeline)

### Field summaries — what each entry captures

| Resource | Key fields | Notes |
|---|---|---|
| **Condition** | display, icd_10_cm_code, snomed_ct_code, onset_date, clinical_status | LOINC not used (it's for observations); SNOMED + ICD-10 are the condition coding systems |
| **Medication** | display, rxnorm_code, dose, frequency, status | RxNorm code only if printed; dose/freq as text |
| **Allergy** | display, snomed_ct_code, reaction, severity | "No known allergies" emits as a single entry with appropriate fields |
| **Immunization** | vaccine_display, cvx_code, administration_date | CVX is the vaccine code system |
| **LabObservation** | test_name, loinc_code, value_quantity / value_string, unit, reference_range_low/high, flag, effective_date | flag is `H/L/N/HH/LL/A` per FHIR v3-ObservationInterpretation |
| **VitalSign** | vital_type (Literal), value, unit, reference_range, flag, effective_date | vital_type is the Literal that maps to LOINC in the builder |
| **Encounter** | status, class_code, type_display, period_start/end, service_provider_display, participant_display, reason_text | class_code is HL7 v3 ActCode (AMB / IMP / EMER / VR) |
| **Practitioner** | npi, family/given/prefix/suffix, specialty, role, address, telecom | NPI is the canonical US identifier — used as the stable id when present |
| **Organization** | name, type_code, type_display, phone, fax, address | type_code is HL7 organization-type (prov / dept / pay / ins / other) |
| **ClinicalNote** | note_type, title, author_name, author_role, encounter_date, sections (list of `ClinicalNoteSection`) | Each section has title, loinc_code, narrative_text |
| **Patient** | family/given/prefix/suffix, gender, birth_sex, birth_date, race_omb_code, ethnicity_omb_code, marital_status, language, address, phones, email, mrn | birth_sex / race / ethnicity carry US Core OMB codes |
| **Coverage** | status, plan_type, payor_name, plan_name, member_id, group_id, relationship_to_subscriber, effective_period_start/end | |
| **SocialHistory** | topic (Literal), value_string / value_quantity, unit, effective_date | topic is the Literal that maps to LOINC in the builder |

---

## Layer 2 — FHIR resource dicts (per-builder output)

Each pass output flows through a `_X_to_fhir` builder method that converts the Pydantic entry into a FHIR resource dict.

### What each builder always does

1. Sets `resourceType` (Observation / Condition / Encounter / etc.)
2. Sets `subject: {"reference": f"Patient/{self._patient_id}"}` — the placeholder, rewritten in Layer 3
3. Looks up the bbox via `_bbox_locator_for(source_text, page, layout)` and adds it to `meta.extension`
4. Threads `common_meta` (extraction-pipeline / extraction-prompt-version / source-attachment / extraction-model) through every resource
5. Falls back to `doc_context.encounter_date` for `effectiveDateTime` / `onsetDateTime` / `authoredOn` when the entry doesn't have its own

### What each builder optionally does

- Maps Pydantic enums to FHIR codings (e.g., `vital_type` → LOINC code via `_VITAL_LOINC_MAP`, `topic` → LOINC via `_SOCIAL_HISTORY_LOINC_MAP`)
- Generates a **stable, content-addressed id** for resources where one wasn't printed (`_stable_encounter_id`, `_stable_practitioner_id`, etc.)
- Emits special category coding (`vital-signs`, `social-history`, `survey`) when applicable

### What NO builder does

- Does NOT set `encounter` references (T06 post-pass handles this)
- Does NOT rewrite the `subject` placeholder (T10 post-pass handles this)
- Does NOT resolve LOINC codes that the Pydantic entry left null (T03 post-pass handles this)
- Does NOT compute interpretation flags (T06 post-pass handles this)
- Does NOT attach clinical-category extensions (T07 post-pass handles this)

---

## Layer 3 — Merged Bundle (post-passes)

After all per-resource builders finish, `_merge_to_bundle` runs **post-passes in this order**:

1. **LOINC matcher post-pass** (`_apply_loinc_post_pass`) — for Observations without a LOINC code, looks up the display name in the curated table; populates `loinc_code` field on the entry.
2. **Interpretation post-pass** (`_apply_interpretation_post_pass`) — for Observations with both `value_quantity` and `referenceRange` but no `flag`, computes H/L/N from numeric comparison.
3. **Clinical category post-pass** (`_lookup_clinical_categories`) — for Observations with a resolved LOINC, attaches a `clinical-category` extension (Metabolic / Kidney / Liver / etc.).
4. **Encounter linkage post-pass** (`_assign_encounter_references`) — adds `encounter: Reference(Encounter/<id>)` to scopable resources using:
    - **Single-encounter shortcut**: if exactly 1 Encounter in bundle → link everything to it
    - **Date-match fallback**: multi-encounter, match by day-precision date
    - **Author-match for notes**: when same-day encounters share a date, prefer the one whose `participant.individual.display` matches the note's `author[0].display`
5. **Patient reference rewrite** (`_rewrite_patient_references`) — if exactly 1 Patient resource exists, rewrites every other resource's `Patient/<placeholder>` reference to the actual `Patient.id`. No-op when 0 or 2+ Patients exist (ambiguous).

After post-passes, the entries are wrapped into a Bundle with `type: "document"` and bundle-level `meta.extension` carrying `extraction-pipeline`, `extraction-prompt-version`, and `document-context` (the Pass 0 output as JSON).

---

## Worked example — a synthetic 3-page PDF

To make this concrete, here's the data flow for a hypothetical small PDF with:
- Page 1: Patient demographics + 1 active condition + 1 medication
- Page 2: Vital signs + 2 lab observations
- Page 3: A short progress note from a 2026-04-22 office visit

### Pass 0 output — `DocumentContext`

```json
{
  "document_type": "patient-summary",
  "patient_name": "Blake Thomson",
  "patient_dob": "1993-06-16",
  "encounter_date": "2026-04-22",
  "ordering_provider": "Ani Shirvanian, NP",
  "facility_name": "Beverly Hills Allergy"
}
```

This propagates as `context_suffix` to every per-resource pass.

### Layer 1 — Per-pass Pydantic outputs

#### `ConditionExtraction`

```json
{
  "conditions": [
    {
      "display": "Allergic rhinitis due to American house dust mite",
      "icd_10_cm_code": "J30.81",
      "snomed_ct_code": "232353008",
      "onset_date": null,
      "clinical_status": "active",
      "page": 1,
      "source_text": "Allergic rhinitis due to American house dust mite"
    }
  ]
}
```

Note: `onset_date` is null because the page didn't print one. The builder will fall back to `doc_context.encounter_date`.

#### `MedicationExtraction`

```json
{
  "medications": [
    {
      "display": "Fluticasone propionate 50 mcg nasal spray",
      "rxnorm_code": null,
      "dose": "50 mcg/actuation",
      "frequency": "2 sprays in both nostrils daily",
      "status": "active",
      "page": 1,
      "source_text": "fluticasone propionate (FLONASE) 50 mcg/actuation nasal spray"
    }
  ]
}
```

#### `VitalSignExtraction`

```json
{
  "vital_signs": [
    {"vital_type": "blood-pressure-systolic", "value": 119, "unit": "mm[Hg]", "effective_date": "2026-04-22", "page": 2},
    {"vital_type": "blood-pressure-diastolic", "value": 71, "unit": "mm[Hg]", "effective_date": "2026-04-22", "page": 2},
    {"vital_type": "heart-rate", "value": 58, "unit": "/min", "effective_date": "2026-04-22", "page": 2},
    {"vital_type": "body-weight", "value": 95.7, "unit": "kg", "effective_date": "2026-04-22", "page": 2}
  ]
}
```

Note BP emits as **two entries** (systolic + diastolic) per the prompt — separate FHIR Observations, both clinically codable.

#### `LabObservationExtraction`

```json
{
  "observations": [
    {
      "test_name": "Glucose",
      "loinc_code": null,
      "value_quantity": 115,
      "unit": "mg/dL",
      "reference_range_low": 65,
      "reference_range_high": 99,
      "flag": "H",
      "effective_date": null,
      "page": 2
    },
    {
      "test_name": "Hemoglobin A1c",
      "loinc_code": null,
      "value_quantity": 5.2,
      "unit": "%",
      "reference_range_low": null,
      "reference_range_high": 5.7,
      "flag": null,
      "effective_date": null,
      "page": 2
    }
  ]
}
```

`loinc_code: null` — the prompt says "LOINC codes only if printed on the document." The PDF doesn't print them. The post-pass will resolve via the curated table.

#### `EncounterExtraction`

```json
{
  "encounters": [
    {
      "encounter_id": null,
      "status": "finished",
      "class_code": "AMB",
      "type_display": "Office Visit",
      "period_start": "2026-04-22T14:15:00",
      "period_end": null,
      "service_provider_display": "Beverly Hills Allergy",
      "participant_display": "Ani Shirvanian, NP",
      "reason_text": "Allergy follow-up",
      "page": 3,
      "source_text": "04/22/2026 Office Visit Beverly Hills Allergy"
    }
  ]
}
```

#### `ClinicalNoteExtraction`

```json
{
  "clinical_notes": [
    {
      "note_id": null,
      "note_type": "progress-note",
      "note_type_loinc": "11506-3",
      "title": "Allergy & Immunology Progress Note",
      "author_name": "Ani Shirvanian",
      "author_role": "NP",
      "encounter_date": "2026-04-22",
      "sections": [
        {
          "title": "Subjective",
          "loinc_code": "10164-2",
          "narrative_text": "32 yo male with persistent sinus pressure, nasal drip, and itchy eyes for 6 months..."
        },
        {
          "title": "Assessment and Plan",
          "loinc_code": "51847-2",
          "narrative_text": "Allergic rhinitis. Plan: continue Flonase, add Astelin BID. Patient education on epipen use."
        }
      ],
      "page_start": 3,
      "page_end": 3,
      "source_text": "Allergy & Immunology Progress Note"
    }
  ]
}
```

#### `PatientExtraction`

```json
{
  "patients": [
    {
      "patient_id": "33224600",
      "family_name": "Thomson",
      "given_names": ["Blake"],
      "gender": "male",
      "birth_sex": "M",
      "birth_date": "1993-06-16",
      "race_omb_code": "2106-3",
      "race_text": "White",
      "ethnicity_omb_code": "2186-5",
      "ethnicity_text": "Not Hispanic or Latino",
      "address_line": "231 BAY ST APT 5",
      "city": "Santa Monica",
      "state": "CA",
      "postal_code": "90405",
      "phone_mobile": "615-720-2002",
      "email": "blakethomson8@gmail.com",
      "page": 1
    }
  ]
}
```

### Layer 2 — Per-builder FHIR resources (BEFORE post-passes)

Each pass output becomes one or more FHIR resource dicts via its `_X_to_fhir` method. Here's the lab observation for Glucose **before** any post-passes run:

```json
{
  "resourceType": "Observation",
  "subject": {"reference": "Patient/unknown"},
  "status": "final",
  "category": [{
    "coding": [{
      "system": "http://terminology.hl7.org/CodeSystem/observation-category",
      "code": "laboratory",
      "display": "Laboratory"
    }]
  }],
  "code": {"text": "Glucose"},
  "valueQuantity": {"value": 115, "unit": "mg/dL", "system": "http://unitsofmeasure.org", "code": "mg/dL"},
  "referenceRange": [{"low": {"value": 65, "unit": "mg/dL"}, "high": {"value": 99, "unit": "mg/dL"}}],
  "interpretation": [{
    "coding": [{
      "system": "http://terminology.hl7.org/CodeSystem/v3-ObservationInterpretation",
      "code": "H"
    }]
  }],
  "effectiveDateTime": "2026-04-22",
  "meta": {
    "source": "extracted://patient-summary/<source-attachment-id>",
    "extension": [
      {"url": "https://ehi-atlas.example/fhir/StructureDefinition/extraction-model", "valueString": "anthropic/default"},
      {"url": "https://ehi-atlas.example/fhir/StructureDefinition/extraction-prompt-version", "valueString": "multipass-v0.1.0"},
      {"url": "https://ehi-atlas.example/fhir/StructureDefinition/source-attachment", "valueString": "<id>"},
      {"url": "https://ehi-atlas.example/fhir/StructureDefinition/source-locator", "valueString": "page=2;bbox=72,508,540,524"}
    ]
  }
}
```

Things to note about this snapshot:

- ✅ The H flag was extracted by the model (it's printed on the page)
- ✅ The reference range was extracted as numeric low/high
- ✅ The effectiveDateTime fell back to `doc_context.encounter_date` because `effective_date` was null on the Pydantic entry
- ❌ No LOINC code in `code.coding[]` yet — the prompt didn't extract it (PDF doesn't print)
- ❌ No `clinical-category` extension yet — depends on LOINC
- ❌ No `loinc-resolution` extension yet — added by the post-pass
- ❌ `subject` is `Patient/unknown` — the placeholder

### Layer 3 — Same Glucose Observation AFTER post-passes

```json
{
  "resourceType": "Observation",
  "subject": {"reference": "Patient/pat-mrn-33224600"},
  "encounter": {"reference": "Encounter/enc-a3b2c1d4e5f6"},
  "status": "final",
  "category": [{
    "coding": [{
      "system": "http://terminology.hl7.org/CodeSystem/observation-category",
      "code": "laboratory",
      "display": "Laboratory"
    }]
  }],
  "code": {
    "text": "Glucose",
    "coding": [{"system": "http://loinc.org", "code": "2345-7"}]
  },
  "valueQuantity": {"value": 115, "unit": "mg/dL", "system": "http://unitsofmeasure.org", "code": "mg/dL"},
  "referenceRange": [{"low": {"value": 65, "unit": "mg/dL"}, "high": {"value": 99, "unit": "mg/dL"}}],
  "interpretation": [{
    "coding": [{
      "system": "http://terminology.hl7.org/CodeSystem/v3-ObservationInterpretation",
      "code": "H"
    }]
  }],
  "effectiveDateTime": "2026-04-22",
  "meta": {
    "source": "extracted://patient-summary/<source-attachment-id>",
    "extension": [
      {"url": ".../extraction-model", "valueString": "anthropic/default"},
      {"url": ".../extraction-prompt-version", "valueString": "multipass-v0.1.0"},
      {"url": ".../source-attachment", "valueString": "<id>"},
      {"url": ".../source-locator", "valueString": "page=2;bbox=72,508,540,524"},
      {"url": ".../loinc-resolution", "valueString": "lookup-table-exact"},
      {"url": ".../interpretation-source", "valueString": "printed"},
      {"url": ".../clinical-category", "valueString": "Metabolic"}
    ]
  }
}
```

**The diff:**
- `subject.reference` rewrote `Patient/unknown` → `Patient/pat-mrn-33224600` (post-pass T10)
- `encounter.reference` added: `Encounter/enc-a3b2c1d4e5f6` (post-pass T06; single-encounter shortcut)
- `code.coding[]` populated with LOINC `2345-7` (post-pass T03)
- Three new meta extensions: `loinc-resolution`, `interpretation-source`, `clinical-category`

This is the FINAL shape that lands in the FHIR Bundle.

### Layer 3 — Full merged Bundle (top-level structure)

```json
{
  "resourceType": "Bundle",
  "type": "document",
  "entry": [
    {"resource": {"resourceType": "Patient", "id": "pat-mrn-33224600", ...}},
    {"resource": {"resourceType": "Condition", ...}},
    {"resource": {"resourceType": "MedicationRequest", ...}},
    {"resource": {"resourceType": "Observation", ...}},  // Glucose (above)
    {"resource": {"resourceType": "Observation", ...}},  // HbA1c
    {"resource": {"resourceType": "Observation", ...}},  // BP systolic
    {"resource": {"resourceType": "Observation", ...}},  // BP diastolic
    {"resource": {"resourceType": "Observation", ...}},  // heart rate
    {"resource": {"resourceType": "Observation", ...}},  // body weight
    {"resource": {"resourceType": "Encounter", "id": "enc-a3b2c1d4e5f6", ...}},
    {"resource": {"resourceType": "Practitioner", "id": "prac-...", ...}},
    {"resource": {"resourceType": "Organization", "id": "org-...", ...}},
    {"resource": {"resourceType": "DocumentReference", "id": "docref-note-...", ...}},
    {"resource": {"resourceType": "Composition", "id": "comp-note-...", ...}}
  ],
  "meta": {
    "source": "extracted://patient-summary/<source-attachment-id>",
    "extension": [
      {"url": ".../extraction-pipeline", "valueString": "multipass-fhir"},
      {"url": ".../extraction-prompt-version", "valueString": "multipass-v0.1.0"},
      {"url": ".../document-context", "valueString": "{\"document_type\":\"patient-summary\",...}"}
    ]
  }
}
```

A handful of cross-references that now resolve because of the post-pass layer:

- All 5 vital-sign Observations + 2 lab Observations + Condition + MedicationRequest + ClinicalNote (Composition + DocumentReference) carry **`subject: Patient/pat-mrn-33224600`** → unified patient identity
- All 5 vital-sign Observations + 2 lab Observations + Condition + MedicationRequest carry **`encounter: Encounter/enc-a3b2c1d4e5f6`** → unified encounter linkage (via single-encounter shortcut)
- DocumentReference carries `context.encounter[0].reference: Encounter/enc-a3b2c1d4e5f6` (T08)
- Composition carries `encounter.reference: Encounter/enc-a3b2c1d4e5f6` (T08)

**This is the wedge — the cross-resource graph is consistent across the whole bundle.** A downstream consumer (`api/routers/patients.py:encounter_detail`) can iterate the bundle and group by encounter; every Observation, Condition, etc. ties back correctly.

---

## Stable IDs — why re-extraction is deterministic

Each resource type has a `_stable_<thing>_id` helper (module-level in `multipass_fhir.py`). The IDs are content-addressed:

| Resource | ID derivation | Format |
|---|---|---|
| Patient | MRN if present; else SHA1 of (family\|given\|dob) | `pat-mrn-{mrn}` or `pat-{12-hex}` |
| Encounter | SHA1 of (date\|provider\|org\|type) | `enc-{12-hex}` |
| Practitioner | NPI if present; else SHA1 of (name parts) | `prac-npi-{npi}` or `prac-{12-hex}` |
| Organization | SHA1 of (name\|city\|state) | `org-{12-hex}` |
| Coverage | SHA1 of (payor\|member\|plan) | `cov-{12-hex}` |
| ClinicalNote → DocumentReference + Composition | SHA1 of (title\|author\|date\|page_start), shared between the two paired resources | `docref-note-{12-hex}` + `comp-note-{12-hex}` |

**Implication:** re-extracting the same PDF (or extracting the same content from a different PDF) yields the same IDs. Cross-source merging (the harmonize layer) can deduplicate cleanly without UUID generation or merge keys.

---

## Cache key — how prompts and schemas version independently

Per-pass cache key string (see `_run_pass` in `multipass_fhir.py`):

```
{global_prefix}/{pass_name}@{prompt_version}#{schema_version}
```

Example: `multipass-v0.1.0/vital_signs@v1#v1`

- Bumping `prompt_version` for one pass invalidates only that pass's cache.
- Bumping `schema_version` for one pass invalidates only that pass's cache.
- Bumping the global `_SCHEMA_VERSION` constant invalidates everything (last-resort).

Adding a new pass to `_PASSES` doesn't invalidate existing cache entries — the new pass simply has no cache entries yet and extracts on first use.

---

## Reading guide for the source

If you want to see this in code, the reading order that maps to the layer model:

```
1. Pydantic schemas              → lines ~63–600
   (DocumentContext, ConditionEntry, ..., SocialHistoryEntry)

2. Stable-ID helpers + LOINC maps  → lines ~600–700
   (_stable_*_id, _VITAL_LOINC_MAP, _SOCIAL_HISTORY_LOINC_MAP, _OMB_*)

3. Prompt constants              → lines ~700–900
   (_PASS_0_PROMPT, _CONDITIONS_PROMPT, ..., _SOCIAL_HISTORY_PROMPT)

4. _PASSES list                  → lines ~900–1000
   (Declarative pass registry; add new passes here)

5. MultiPassFHIRPipeline class   → lines ~1000–1700
   - extract() method                        ← Pass 0 + dispatch loop
   - _merge_to_bundle()                       ← entry-emission loops
   - _apply_loinc_post_pass()                 ← post-pass 1
   - _apply_interpretation_post_pass()        ← post-pass 2
   - _lookup_clinical_categories()            ← post-pass 3
   - _assign_encounter_references()           ← post-pass 4
   - _rewrite_patient_references()            ← post-pass 5
   - _<thing>_to_fhir() builder methods       ← per-resource builders

6. Variant subclasses            → lines ~1700–end
   (MultiPassFHIRGemmaTabularPipeline, MultiPassFHIRScoutPipeline)
```

---

## Quick reference — common questions

### "How does the model know which encounter a lab belongs to?"

It doesn't, at extraction time. The model extracts the lab as an isolated `LabObservationEntry` with optional `effective_date`. Encounter linkage is wired in `_assign_encounter_references` (post-pass 4) via:
1. Single-encounter shortcut (1 Encounter in bundle → all linked there)
2. Date match (multi-encounter, day precision)
3. Author match for clinical notes (when same-day encounters are ambiguous)

### "What if the PDF spans multiple encounters?"

The model extracts every Encounter into the `EncounterExtraction.encounters` list. Post-pass 4 then date-matches each Observation/Condition/etc. to the correct encounter. If a fact's date doesn't match any encounter, no encounter linkage is added (rather than guessing).

### "Why is the same fact emitted with `subject: Patient/unknown` and then rewritten?"

To keep each builder method context-free. The builder doesn't need to know whether the Patient pass extracted a real Patient or not. Post-pass 5 (`_rewrite_patient_references`) handles the rewriting after all passes return. If no Patient resource is in the bundle (e.g., lab-only PDF), the rewrite is skipped and references remain `Patient/unknown` — honest about what we know.

### "Where do `meta.extension` URLs come from?"

All custom URLs use the convention `https://ehi-atlas.example/fhir/StructureDefinition/<name>`. The list is documented as a comment at the top of `multipass_fhir.py`. The harmonize layer at `lib/harmonize/provenance.py` uses a different base (`atlas.healthcaredataai.com`) — those will migrate as they're touched.

### "How do I know which fields a downstream consumer relies on?"

`api/core/harmonize_service.py` iterates the Bundle entries and consumes specific fields per `resourceType`. The audit captured in `docs/daily/2026-05-07-ClaudeCode.md` Entry 7 (extraction-expansion plan) documents the per-resource consumption surface.

---

*Last updated: 2026-05-07. Source of truth for the data model is `lib/extract/pipelines/multipass_fhir.py` itself; this doc walks through it.*
