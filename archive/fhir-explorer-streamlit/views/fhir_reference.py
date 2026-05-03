"""
FHIR Reference — Educational page about FHIR R4 data structure and our parser.

Two tabs:
  1. FHIR Structure — what FHIR data looks like (bundle, resources, coding systems)
  2. Our Classifications — how our parser maps raw FHIR → typed models
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import streamlit as st

from ..parser.raw_loader import load_raw_resources, summarize_raw_resource

# ---------------------------------------------------------------------------
# Sample file for live examples (small patient, fast to load)
# ---------------------------------------------------------------------------

_DATA_DIR = Path(__file__).parent.parent.parent / "data" / "synthea-samples" / "synthea-r4-individual" / "fhir"


def _get_sample_file() -> Path | None:
    """Return a small sample patient file for live examples."""
    files = sorted(_DATA_DIR.glob("*.json"))
    if not files:
        return None
    # Pick the smallest file for fast loading
    return min(files, key=lambda f: f.stat().st_size)


# ---------------------------------------------------------------------------
# Static content — JSON skeletons and reference data
# ---------------------------------------------------------------------------

BUNDLE_SKELETON = """{
  "resourceType": "Bundle",
  "type": "transaction",
  "entry": [
    {
      "fullUrl": "urn:uuid:8799a4b0-1815-4963-a0da-cb91757a7692",
      "resource": {
        "resourceType": "Patient",
        "id": "8799a4b0-...",
        "name": [{ "given": ["Ahmad"], "family": "Nader" }],
        "gender": "male",
        "birthDate": "1991-04-21"
      },
      "request": { "method": "POST", "url": "Patient" }
    },
    {
      "fullUrl": "urn:uuid:9b3446ff-...",
      "resource": {
        "resourceType": "Encounter",
        "id": "9b3446ff-...",
        "status": "finished",
        "subject": { "reference": "urn:uuid:8799a4b0-..." }
      },
      "request": { "method": "POST", "url": "Encounter" }
    }
  ]
}"""

RESOURCE_SKELETONS: dict[str, dict] = {
    "Patient": {
        "skeleton": {
            "resourceType": "Patient",
            "id": "uuid",
            "text": {"status": "generated", "div": "<div>...</div>"},
            "extension": [
                {"url": "us-core-race", "extension": [{"url": "text", "valueString": "White"}]},
                {"url": "us-core-ethnicity", "extension": [{"url": "text", "valueString": "Not Hispanic"}]},
                {"url": "us-core-birthsex", "valueCode": "M"},
            ],
            "identifier": [
                {"type": {"coding": [{"code": "MR"}]}, "value": "medical-record-number"},
                {"type": {"coding": [{"code": "SS"}]}, "value": "999-50-7538"},
            ],
            "name": [{"use": "official", "family": "Nader710", "given": ["Ahmad985"], "prefix": ["Mr."]}],
            "gender": "male",
            "birthDate": "1991-04-21",
            "address": [{"city": "Boston", "state": "Massachusetts", "postalCode": "02108"}],
            "maritalStatus": {"coding": [{"code": "M"}]},
            "communication": [{"language": {"coding": [{"code": "en-US"}]}}],
        },
        "description": "The identity anchor. Contains demographics, identifiers (MRN, SSN), "
                        "and US Core extensions (race, ethnicity, birth sex). Every other resource "
                        "references back to this via `subject.reference`.",
        "coding_system": "N/A (identity, not coded)",
        "key_fields": [
            ("`name[].given` / `family`", "Patient name parts"),
            ("`gender`", "administrative gender"),
            ("`birthDate`", "date of birth (YYYY-MM-DD)"),
            ("`deceasedDateTime`", "date/time of death (if applicable)"),
            ("`extension[]`", "US Core race, ethnicity, birth sex"),
            ("`identifier[]`", "MRN, SSN, driver's license, etc."),
            ("`address[]`", "street, city, state, postal code + geolocation extension"),
            ("`maritalStatus`", "coded marital status"),
        ],
    },
    "Encounter": {
        "skeleton": {
            "resourceType": "Encounter",
            "id": "uuid",
            "status": "finished",
            "class": {"system": "http://terminology.hl7.org/CodeSystem/v3-ActCode", "code": "AMB"},
            "type": [{"coding": [{"system": "http://snomed.info/sct", "code": "162673000",
                                   "display": "General examination of patient"}]}],
            "subject": {"reference": "urn:uuid:<Patient-ID>", "display": "Mr. Ahmad985 Nader710"},
            "participant": [{"individual": {"reference": "urn:uuid:<Practitioner-ID>",
                                            "display": "Dr. Lorenzo669 Rempel203"}}],
            "period": {"start": "2010-06-20T08:02:17-04:00", "end": "2010-06-20T08:17:17-04:00"},
            "serviceProvider": {"reference": "urn:uuid:<Organization-ID>", "display": "PCP63533"},
        },
        "description": "A clinical visit — the temporal spine of the record. All clinical events "
                        "(observations, conditions, procedures, medications) link back to an Encounter.",
        "coding_system": "SNOMED CT for type; ActCode for class",
        "key_fields": [
            ("`status`", "`finished`, `in-progress`, `cancelled`"),
            ("`class.code`", "`AMB` (ambulatory), `IMP` (inpatient), `EMER` (emergency), `VR` (virtual)"),
            ("`type[].coding[]`", "SNOMED CT code describing the visit type"),
            ("`subject.reference`", "reference to Patient (the 'who')"),
            ("`period.start` / `end`", "when the visit occurred"),
            ("`participant[].individual`", "treating practitioner"),
            ("`serviceProvider`", "facility/organization"),
        ],
    },
    "Condition": {
        "skeleton": {
            "resourceType": "Condition",
            "id": "uuid",
            "clinicalStatus": {"coding": [{"system": "http://terminology.hl7.org/CodeSystem/condition-clinical",
                                            "code": "active"}]},
            "verificationStatus": {"coding": [{"system": "http://terminology.hl7.org/CodeSystem/condition-ver-status",
                                                "code": "confirmed"}]},
            "code": {"coding": [{"system": "http://snomed.info/sct", "code": "74400008",
                                  "display": "Appendicitis"}], "text": "Appendicitis"},
            "subject": {"reference": "urn:uuid:<Patient-ID>"},
            "encounter": {"reference": "urn:uuid:<Encounter-ID>"},
            "onsetDateTime": "2011-04-17T08:02:17-04:00",
            "recordedDate": "2011-04-17T08:02:17-04:00",
        },
        "description": "A diagnosis on the problem list. Uses SNOMED CT codes. "
                        "Has both clinicalStatus (active/resolved) and verificationStatus (confirmed/refuted).",
        "coding_system": "SNOMED CT",
        "key_fields": [
            ("`clinicalStatus.coding[0].code`", "`active`, `resolved`, `inactive`, `remission`, `recurrence`"),
            ("`verificationStatus.coding[0].code`", "`confirmed`, `unconfirmed`, `refuted`, `entered-in-error`"),
            ("`code.coding[]`", "SNOMED CT code for the diagnosis"),
            ("`onsetDateTime`", "when the condition started"),
            ("`abatementDateTime`", "when the condition resolved (if applicable)"),
            ("`subject` / `encounter`", "links to Patient and Encounter"),
        ],
    },
    "MedicationRequest": {
        "skeleton": {
            "resourceType": "MedicationRequest",
            "id": "uuid",
            "status": "active",
            "intent": "order",
            "medicationCodeableConcept": {
                "coding": [{"system": "http://www.nlm.nih.gov/research/umls/rxnorm",
                            "code": "314076", "display": "lisinopril 10 MG Oral Tablet"}],
                "text": "lisinopril 10 MG Oral Tablet",
            },
            "subject": {"reference": "urn:uuid:<Patient-ID>"},
            "encounter": {"reference": "urn:uuid:<Encounter-ID>"},
            "authoredOn": "1989-05-27T23:58:16-04:00",
            "requester": {"display": "Dr. Olevia458 Hermiston71"},
            "reasonReference": [{"reference": "Condition/<ID>", "display": "Essential hypertension"}],
            "dosageInstruction": [{"sequence": 1, "timing": {"repeat": {"frequency": 1,
                                  "period": 1, "periodUnit": "d"}}, "asNeededBoolean": False}],
        },
        "description": "A prescription order. Each refill or new order is a separate resource. "
                        "Uses RxNorm codes. Links to the Condition that justified the prescription.",
        "coding_system": "RxNorm",
        "key_fields": [
            ("`status`", "`active`, `stopped`, `completed`, `cancelled`, `on-hold`"),
            ("`medicationCodeableConcept.coding[]`", "RxNorm code for the drug"),
            ("`authoredOn`", "when the prescription was written"),
            ("`requester`", "prescribing practitioner"),
            ("`reasonReference[]`", "links to the Condition that justified this prescription"),
            ("`dosageInstruction[]`", "timing, frequency, route, as-needed flag"),
        ],
    },
    "Observation": {
        "skeleton": {
            "resourceType": "Observation",
            "id": "uuid",
            "status": "final",
            "category": [{"coding": [{"system": "http://terminology.hl7.org/CodeSystem/observation-category",
                                       "code": "vital-signs", "display": "vital-signs"}]}],
            "code": {"coding": [{"system": "http://loinc.org", "code": "8302-2",
                                  "display": "Body Height"}], "text": "Body Height"},
            "subject": {"reference": "urn:uuid:<Patient-ID>"},
            "encounter": {"reference": "urn:uuid:<Encounter-ID>"},
            "effectiveDateTime": "2010-06-20T08:02:17-04:00",
            "valueQuantity": {"value": 189.18, "unit": "cm",
                              "system": "http://unitsofmeasure.org", "code": "cm"},
        },
        "description": "A measured value — labs, vitals, social history, surveys. Uses LOINC codes. "
                        "Value can be a quantity (number + unit), a coded concept, a string, or "
                        "a set of components (e.g., blood pressure = systolic + diastolic).",
        "coding_system": "LOINC",
        "key_fields": [
            ("`status`", "`final`, `preliminary`, `entered-in-error`"),
            ("`category[].coding[0].code`", "`vital-signs`, `laboratory`, `social-history`, `survey`, `imaging`"),
            ("`code.coding[]`", "LOINC code identifying what was measured"),
            ("`effectiveDateTime`", "when the measurement was taken"),
            ("`valueQuantity`", "numeric result: `value` + `unit` (e.g., 189.18 cm)"),
            ("`valueCodeableConcept`", "coded result (e.g., 'Normal', 'Positive')"),
            ("`component[]`", "sub-observations (e.g., BP = systolic + diastolic)"),
        ],
    },
    "Procedure": {
        "skeleton": {
            "resourceType": "Procedure",
            "id": "uuid",
            "status": "completed",
            "code": {"coding": [{"system": "http://snomed.info/sct", "code": "430193006",
                                  "display": "Medication Reconciliation (procedure)"}]},
            "subject": {"reference": "urn:uuid:<Patient-ID>"},
            "encounter": {"reference": "urn:uuid:<Encounter-ID>"},
            "performedPeriod": {"start": "2022-06-22T12:31:08-04:00", "end": "2022-06-22T12:46:08-04:00"},
        },
        "description": "A clinical procedure — surgeries, reconciliations, screenings. "
                        "Uses SNOMED CT codes. Has a performed period (start/end) or a single dateTime.",
        "coding_system": "SNOMED CT",
        "key_fields": [
            ("`status`", "`completed`, `not-done`, `in-progress`"),
            ("`code.coding[]`", "SNOMED CT code for the procedure"),
            ("`performedPeriod`", "when the procedure occurred (start/end)"),
            ("`performedDateTime`", "alternative: single point in time"),
            ("`reasonCode[]`", "clinical reason for the procedure"),
        ],
    },
    "Immunization": {
        "skeleton": {
            "resourceType": "Immunization",
            "id": "uuid",
            "status": "completed",
            "vaccineCode": {"coding": [{"system": "http://hl7.org/fhir/sid/cvx", "code": "140",
                                         "display": "Influenza, seasonal, injectable, preservative free"}]},
            "patient": {"reference": "urn:uuid:<Patient-ID>"},
            "encounter": {"reference": "urn:uuid:<Encounter-ID>"},
            "occurrenceDateTime": "2010-06-20T08:02:17-04:00",
            "primarySource": True,
        },
        "description": "A vaccine administration. Uses CVX (CDC vaccine codes). "
                        "Note: uses `patient` not `subject` for the patient reference.",
        "coding_system": "CVX",
        "key_fields": [
            ("`status`", "`completed`, `entered-in-error`, `not-done`"),
            ("`vaccineCode.coding[]`", "CVX code for the vaccine"),
            ("`patient.reference`", "patient reference (note: `patient`, not `subject`)"),
            ("`occurrenceDateTime`", "when the vaccine was administered"),
            ("`primarySource`", "whether recorded directly from the vaccine provider"),
        ],
    },
    "AllergyIntolerance": {
        "skeleton": {
            "resourceType": "AllergyIntolerance",
            "id": "uuid",
            "clinicalStatus": {"coding": [{"code": "active"}]},
            "type": "allergy",
            "category": ["medication"],
            "criticality": "high",
            "code": {"coding": [{"system": "http://snomed.info/sct", "code": "387207008",
                                  "display": "Ibuprofen"}]},
            "patient": {"reference": "urn:uuid:<Patient-ID>"},
            "onsetDateTime": "2015-03-10",
            "recordedDate": "2015-03-10",
        },
        "description": "An allergy or intolerance. Can be drug, food, or environmental. "
                        "Uses `patient` (not `subject`). Includes criticality (low/high) and category.",
        "coding_system": "SNOMED CT",
        "key_fields": [
            ("`clinicalStatus`", "`active`, `inactive`, `resolved`"),
            ("`type`", "`allergy` or `intolerance`"),
            ("`category[]`", "`medication`, `food`, `environment`, `biologic`"),
            ("`criticality`", "`low`, `high`, `unable-to-assess`"),
            ("`code.coding[]`", "SNOMED CT code for the substance"),
            ("`patient.reference`", "patient reference"),
        ],
    },
    "DiagnosticReport": {
        "skeleton": {
            "resourceType": "DiagnosticReport",
            "id": "uuid",
            "status": "final",
            "category": [{"coding": [{"system": "http://loinc.org", "code": "34117-2",
                                       "display": "History and physical note"}]}],
            "code": {"coding": [{"system": "http://loinc.org", "code": "34117-2",
                                  "display": "History and physical note"}]},
            "subject": {"reference": "Patient/<ID>"},
            "encounter": {"reference": "Encounter/<ID>"},
            "effectiveDateTime": "2019-01-12T22:58:16-05:00",
            "result": [{"reference": "Observation/<ID>"}],
            "presentedForm": [{"contentType": "text/plain", "data": "<base64-encoded content>"}],
        },
        "description": "A clinical report — groups related Observations (via `result` references) "
                        "and may contain a narrative note in `presentedForm` (base64-encoded). "
                        "Uses LOINC codes for report type.",
        "coding_system": "LOINC",
        "key_fields": [
            ("`status`", "`final`, `preliminary`, `entered-in-error`"),
            ("`category[].coding[]`", "LOINC code for report type (H&P, progress note, etc.)"),
            ("`code.coding[]`", "LOINC code for the report"),
            ("`result[]`", "references to Observation resources this report groups"),
            ("`presentedForm[]`", "base64-encoded narrative document (absent in Synthea)"),
        ],
    },
}

CODING_SYSTEMS = [
    {
        "System": "SNOMED CT",
        "URI": "http://snomed.info/sct",
        "Codes": "Diagnoses, procedures, clinical findings",
        "Used By": "Condition, Procedure, AllergyIntolerance",
        "Example": "74400008 = Appendicitis",
    },
    {
        "System": "LOINC",
        "URI": "http://loinc.org",
        "Codes": "Labs, vitals, surveys, report types",
        "Used By": "Observation, DiagnosticReport",
        "Example": "8302-2 = Body Height",
    },
    {
        "System": "RxNorm",
        "URI": "http://www.nlm.nih.gov/research/umls/rxnorm",
        "Codes": "Medications and drug products",
        "Used By": "MedicationRequest",
        "Example": "314076 = lisinopril 10 MG",
    },
    {
        "System": "CVX",
        "URI": "http://hl7.org/fhir/sid/cvx",
        "Codes": "Vaccines (CDC vaccine codes)",
        "Used By": "Immunization",
        "Example": "140 = Influenza seasonal",
    },
    {
        "System": "ActCode",
        "URI": "http://terminology.hl7.org/CodeSystem/v3-ActCode",
        "Codes": "Encounter classification",
        "Used By": "Encounter (class field)",
        "Example": "AMB = Ambulatory, IMP = Inpatient",
    },
    {
        "System": "UCUM",
        "URI": "http://unitsofmeasure.org",
        "Codes": "Units of measure for lab/vital values",
        "Used By": "Observation (valueQuantity)",
        "Example": "cm, kg, mmHg, mg/dL",
    },
]

# ---------------------------------------------------------------------------
# Field mapping tables for the "Our Classifications" tab
# ---------------------------------------------------------------------------

FIELD_MAPPINGS: dict[str, dict] = {
    "Patient": {
        "maps": [
            ("resource.id", "patient_id", "UUID"),
            ("resource.name[0].given + family", "name", "Concatenated"),
            ("resource.gender", "gender", ""),
            ("resource.birthDate", "birth_date", "Parsed to date"),
            ("resource.deceasedDateTime", "deceased_date", "Also sets deceased=True"),
            ("resource.address[0]", "city, state, country, postal_code", "First address only"),
            ("resource.address[0].extension[geolocation]", "lat, lon", "Geolocation sub-extension"),
            ("resource.telecom[system=phone]", "phone", "First phone number"),
            ("resource.maritalStatus.coding[0].code", "marital_status", ""),
            ("resource.communication[0].language", "language", "Display text"),
            ("resource.identifier[type=MR]", "mrn", "Medical Record Number"),
            ("resource.identifier[type=SS]", "ssn", "Social Security Number"),
            ("extension[us-core-race]", "race", "Text sub-extension"),
            ("extension[us-core-ethnicity]", "ethnicity", "Text sub-extension"),
            ("extension[us-core-birthsex]", "birth_sex", "valueCode"),
            ("extension[disability-adjusted-life-years]", "daly", "Synthea-specific"),
            ("extension[quality-adjusted-life-years]", "qaly", "Synthea-specific"),
        ],
        "classification_logic": None,
        "model_name": "PatientSummary",
    },
    "Encounter": {
        "maps": [
            ("resource.id", "encounter_id", "UUID"),
            ("resource.status", "status", "finished, in-progress, cancelled"),
            ("resource.class.code", "class_code", "AMB, IMP, EMER, VR"),
            ("resource.type[0].coding[0].display", "encounter_type", "SNOMED display text"),
            ("resource.reasonCode[0].coding[0].display", "reason_display", ""),
            ("resource.period", "period (Period)", "start/end datetimes"),
            ("resource.subject.reference", "patient_id", "UUID stripped via strip_ref()"),
            ("resource.participant[0].individual.display", "practitioner_name", "First participant"),
            ("resource.serviceProvider.display", "provider_org", ""),
        ],
        "classification_logic": "Encounter class codes drive our visit categorization:\n"
                                 "- `AMB` = Ambulatory (routine clinic visit)\n"
                                 "- `IMP` = Inpatient (hospital admission)\n"
                                 "- `EMER` = Emergency department\n"
                                 "- `VR` = Virtual / telehealth\n\n"
                                 "Post-processing links observations, conditions, procedures, medications, "
                                 "etc. to encounters via their `encounter.reference` fields.",
        "model_name": "EncounterRecord",
    },
    "Condition": {
        "maps": [
            ("resource.id", "condition_id", "UUID"),
            ("resource.clinicalStatus.coding[0].code", "clinical_status", "active, resolved, inactive, remission"),
            ("resource.verificationStatus.coding[0].code", "verification_status", "confirmed, unconfirmed, refuted"),
            ("resource.code", "code (CodeableConcept)", "SNOMED CT system/code/display"),
            ("resource.subject.reference", "patient_id", "stripped UUID"),
            ("resource.encounter.reference", "encounter_id", "stripped UUID"),
            ("resource.onsetDateTime / onsetPeriod.start", "onset_dt", "Tries both patterns"),
            ("resource.abatementDateTime / abatementPeriod.start", "abatement_dt", "Tries both patterns"),
            ("resource.recordedDate", "recorded_dt", "When documented"),
        ],
        "classification_logic": "**`is_active` derivation:**\n\n"
                                 "```python\n"
                                 "is_active = (clinical_status == 'active') and (abatement_dt is None)\n"
                                 "```\n\n"
                                 "A condition is considered active only if its clinical status is explicitly "
                                 "'active' AND it has no abatement date. Resolved/inactive/remission conditions "
                                 "are all treated as not-active.",
        "model_name": "ConditionRecord",
    },
    "MedicationRequest": {
        "maps": [
            ("resource.id", "med_id", "UUID"),
            ("resource.status", "status", "active, stopped, completed, cancelled, on-hold"),
            ("resource.medicationCodeableConcept.coding[0]", "rxnorm_code, display", "RxNorm system"),
            ("resource.subject.reference", "patient_id", "stripped UUID"),
            ("resource.encounter.reference", "encounter_id", "stripped UUID"),
            ("resource.authoredOn", "authored_on", "When prescribed"),
            ("resource.requester.display", "requester", "Prescribing practitioner"),
            ("resource.dosageInstruction[0].asNeededBoolean", "as_needed", "Boolean"),
            ("resource.dosageInstruction[0] (text)", "dosage_text", "Free-text dosage"),
            ("resource.reasonCode[0].coding[0].display", "reason_display", "Clinical reason"),
        ],
        "classification_logic": "**Medication status determines current vs. historical:**\n"
                                 "- `active` / `on-hold` = currently prescribed\n"
                                 "- `stopped` = explicitly discontinued\n"
                                 "- `completed` = course finished (e.g., antibiotics)\n"
                                 "- `cancelled` = never filled\n\n"
                                 "Also handles `medicationReference` pattern (real EHRs) in addition "
                                 "to `medicationCodeableConcept` (Synthea pattern).",
        "model_name": "MedicationRecord",
    },
    "Observation": {
        "maps": [
            ("resource.id", "obs_id", "UUID"),
            ("resource.status", "status", "final, preliminary"),
            ("resource.category[0].coding[0].code", "category", "vital-signs, laboratory, survey, social-history"),
            ("resource.code.coding[0]", "loinc_code, display", "LOINC system"),
            ("resource.subject.reference", "patient_id", "stripped UUID"),
            ("resource.encounter.reference", "encounter_id", "stripped UUID"),
            ("resource.effectiveDateTime / effectivePeriod.start", "effective_dt", "Tries both"),
            ("resource.valueQuantity", "value_quantity, value_unit", "value_type = 'quantity'"),
            ("resource.valueCodeableConcept", "value_concept_display", "value_type = 'codeable_concept'"),
            ("resource.component[]", "components[]", "value_type = 'component'"),
        ],
        "classification_logic": "**Value type discrimination:** Exactly one value pattern is used:\n"
                                 "1. `valueQuantity` → numeric (e.g., 189.18 cm) → `value_type = 'quantity'`\n"
                                 "2. `valueCodeableConcept` → coded (e.g., 'Normal') → `value_type = 'codeable_concept'`\n"
                                 "3. `component[]` → multi-part (e.g., BP: systolic + diastolic) → `value_type = 'component'`\n"
                                 "4. None of the above → `value_type = 'none'`\n\n"
                                 "**Component observations** (like blood pressure) contain sub-observations, "
                                 "each with their own LOINC code and value.",
        "model_name": "ObservationRecord",
    },
    "Procedure": {
        "maps": [
            ("resource.id", "procedure_id", "UUID"),
            ("resource.status", "status", "completed, not-done, in-progress"),
            ("resource.code", "code (CodeableConcept)", "SNOMED CT"),
            ("resource.subject.reference", "patient_id", "stripped UUID"),
            ("resource.encounter.reference", "encounter_id", "stripped UUID"),
            ("resource.performedPeriod", "performed_period", "start/end"),
            ("resource.performedDateTime", "performed_period", "Wrapped as Period(start=dt)"),
            ("resource.reasonCode[0].coding[0].display", "reason_display", ""),
        ],
        "classification_logic": "Handles both `performedPeriod` (range) and `performedDateTime` "
                                 "(single point, wrapped into a Period with start only).",
        "model_name": "ProcedureRecord",
    },
    "Immunization": {
        "maps": [
            ("resource.id", "imm_id", "UUID"),
            ("resource.status", "status", "completed, entered-in-error, not-done"),
            ("resource.vaccineCode.coding[0]", "cvx_code, display", "CVX system"),
            ("resource.patient.reference", "patient_id", "Note: 'patient', not 'subject'"),
            ("resource.encounter.reference", "encounter_id", "stripped UUID"),
            ("resource.occurrenceDateTime", "occurrence_dt", "When administered"),
        ],
        "classification_logic": None,
        "model_name": "ImmunizationRecord",
    },
    "AllergyIntolerance": {
        "maps": [
            ("resource.id", "allergy_id", "UUID"),
            ("resource.clinicalStatus.coding[0].code", "clinical_status", "active, inactive, resolved"),
            ("resource.type", "allergy_type", "'allergy' or 'intolerance'"),
            ("resource.category[]", "categories", "medication, food, environment"),
            ("resource.criticality", "criticality", "low, high, unable-to-assess"),
            ("resource.code", "code (CodeableConcept)", "SNOMED CT"),
            ("resource.patient.reference", "patient_id", "Note: 'patient', not 'subject'"),
            ("resource.onsetDateTime", "onset_dt", ""),
            ("resource.recordedDate", "recorded_date", ""),
        ],
        "classification_logic": None,
        "model_name": "AllergyRecord",
    },
    "DiagnosticReport": {
        "maps": [
            ("resource.id", "report_id", "UUID"),
            ("resource.status", "status", "final, preliminary"),
            ("resource.category[0].coding[0]", "category", "LOINC report type code"),
            ("resource.code", "code (CodeableConcept)", "LOINC"),
            ("resource.subject.reference", "patient_id", "stripped UUID"),
            ("resource.encounter.reference", "encounter_id", "stripped UUID"),
            ("resource.effectiveDateTime / effectivePeriod.start", "effective_dt", ""),
            ("resource.result[].reference", "result_refs", "List of Observation UUIDs"),
            ("resource.presentedForm[0].data", "presented_form_text", "Base64-decoded; absent in Synthea"),
        ],
        "classification_logic": "The `result` array links to Observation resources that this report groups "
                                 "(e.g., a CBC panel groups hemoglobin, WBC, platelet observations). "
                                 "`presentedForm` contains base64-encoded clinical notes — present in real "
                                 "EHR exports but absent in Synthea data.",
        "model_name": "DiagnosticReportRecord",
    },
}

# Map resource types to the field name used for "live example" matching
_RESOURCE_TYPE_TO_FHIR_NAME = {
    "MedicationRequest": "MedicationRequest",
    "AllergyIntolerance": "AllergyIntolerance",
    "DiagnosticReport": "DiagnosticReport",
}


# ---------------------------------------------------------------------------
# Render
# ---------------------------------------------------------------------------

def render() -> None:
    st.title("FHIR Data Reference")
    st.markdown(
        "An interactive guide to the FHIR R4 data structure used in this project. "
        "Understand the raw JSON, coding systems, and how our parser transforms it."
    )

    tab_structure, tab_classifications = st.tabs(["FHIR Structure", "Our Classifications"])

    with tab_structure:
        _render_structure_tab()

    with tab_classifications:
        _render_classifications_tab()


# ---------------------------------------------------------------------------
# Tab 1: FHIR Structure
# ---------------------------------------------------------------------------

def _render_structure_tab() -> None:
    # --- Bundle structure ---
    st.subheader("Bundle Structure")
    st.markdown(
        "Every patient file is a **FHIR Bundle** — a JSON container wrapping all of a patient's "
        "clinical resources. The bundle has a `type` (usually `transaction`) and an `entry` array. "
        "Each entry contains a `fullUrl` (UUID reference), the `resource` object, and a `request` "
        "object (HTTP metadata for how this would be uploaded to an EHR)."
    )
    st.code(BUNDLE_SKELETON, language="json")

    st.markdown("---")

    # --- Coding systems ---
    st.subheader("Coding Systems")
    st.markdown(
        "FHIR uses standardized **coding systems** to represent clinical concepts. "
        "Every coded field has a `system` (URI identifying the vocabulary), "
        "a `code` (the actual code), and a `display` (human-readable label)."
    )
    st.markdown("```json\n"
                '{\n'
                '  "coding": [{\n'
                '    "system": "http://snomed.info/sct",\n'
                '    "code": "74400008",\n'
                '    "display": "Appendicitis"\n'
                '  }]\n'
                '}\n'
                "```")

    df_coding = pd.DataFrame(CODING_SYSTEMS)
    st.dataframe(df_coding, hide_index=True, width="stretch")

    st.markdown("---")

    # --- Resource types ---
    st.subheader("Resource Types")
    st.markdown(
        "Each `entry.resource` in the bundle has a `resourceType` field. "
        "Below are the 9 key clinical resource types with representative JSON structures."
    )

    for rtype, info in RESOURCE_SKELETONS.items():
        with st.expander(f"**{rtype}** — {info['coding_system']}"):
            col_json, col_desc = st.columns([3, 2])

            with col_json:
                st.markdown("**JSON Structure:**")
                st.code(json.dumps(info["skeleton"], indent=2), language="json")

            with col_desc:
                st.markdown(f"**Purpose:** {info['description']}")
                st.markdown("")
                st.markdown("**Key Fields:**")
                for field_path, field_desc in info["key_fields"]:
                    st.markdown(f"- {field_path} — {field_desc}")

    st.markdown("---")

    # --- Reference graph ---
    st.subheader("How Resources Reference Each Other")
    st.markdown(
        "Resources form a **reference graph** centered on Patient and Encounter. "
        "All references use the pattern `{\"reference\": \"urn:uuid:<ID>\"}` (in bundles) "
        "or `{\"reference\": \"<ResourceType>/<ID>\"}` (in bulk exports)."
    )

    st.markdown("""
```
                            Patient
                               |
                    subject.reference
                               |
         ┌─────────┬───────────┼───────────┬──────────┐
         |         |           |           |          |
    Encounter  AllergyInt  Immunization  Claim     EOB
         |
   encounter.reference
         |
    ┌────┼────┬──────────┬───────────┐
    |    |    |          |           |
  Obs  Cond  Proc  MedRequest  DiagReport
                      |              |
              reasonReference     result[]
                      |              |
                  Condition     Observation
```
    """)

    st.markdown(
        "**Key patterns:**\n"
        "- Almost every resource has a `subject` (or `patient`) reference to Patient\n"
        "- Most clinical resources have an `encounter` reference linking to the visit\n"
        "- `MedicationRequest.reasonReference` links to the Condition that justified the prescription\n"
        "- `DiagnosticReport.result[]` groups related Observations (e.g., a lab panel)\n"
        "- References use `urn:uuid:` prefix in bundles, `ResourceType/id` in bulk exports"
    )


# ---------------------------------------------------------------------------
# Tab 2: Our Classifications
# ---------------------------------------------------------------------------

def _render_classifications_tab() -> None:
    st.markdown(
        "How our parser (`fhir_explorer/parser/`) maps raw FHIR JSON fields "
        "into typed Python dataclasses. For each resource type, see which fields "
        "we extract, which we ignore, and any classification logic applied."
    )

    for rtype, info in FIELD_MAPPINGS.items():
        with st.expander(f"**{rtype}** → `{info['model_name']}`"):
            # Field mapping table
            st.markdown("**Field Mapping:**")
            rows = [{"FHIR Path": fhir, "Model Field": model, "Notes": notes}
                    for fhir, model, notes in info["maps"]]
            st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")

            # Classification logic
            if info.get("classification_logic"):
                st.markdown("")
                st.markdown("**Classification Logic:**")
                st.markdown(info["classification_logic"])

            # Live example
            st.markdown("")
            _render_live_example(rtype)


@st.cache_data(show_spinner=False)
def _load_sample_resources(_file_path: str) -> dict[str, list[dict]]:
    """Load raw resources from a sample file (cached)."""
    return load_raw_resources(_file_path)


def _render_live_example(resource_type: str) -> None:
    """Show a live raw JSON example from a sample patient file."""
    sample_file = _get_sample_file()
    if not sample_file:
        st.info("No sample data files found.")
        return

    resources = _load_sample_resources(str(sample_file))

    # Map resource type name to what appears in the bundle
    fhir_name = _RESOURCE_TYPE_TO_FHIR_NAME.get(resource_type, resource_type)
    examples = resources.get(fhir_name, [])
    if not examples:
        st.caption(f"No {resource_type} resources found in sample file.")
        return

    raw = examples[0]
    summary = summarize_raw_resource(fhir_name, raw)

    st.markdown(f"**Live Example** (from `{sample_file.name}` — {summary}):")

    col_raw, col_parsed = st.columns(2)
    with col_raw:
        st.markdown("*Raw FHIR JSON:*")
        st.code(json.dumps(raw, indent=2, default=str), language="json")

    with col_parsed:
        st.markdown(f"*Extracted → `{FIELD_MAPPINGS[resource_type]['model_name']}`*:")
        # Build a key-value display from the mapping
        extracted = {}
        for _fhir_path, model_field, _notes in FIELD_MAPPINGS[resource_type]["maps"]:
            value = _extract_display_value(raw, resource_type, model_field)
            if value is not None:
                extracted[model_field] = value

        if extracted:
            df = pd.DataFrame(
                [(k, str(v)) for k, v in extracted.items()],
                columns=["Field", "Extracted Value"],
            )
            st.dataframe(df, hide_index=True, width="stretch")
        else:
            st.caption("(could not extract preview)")


def _extract_display_value(raw: dict, resource_type: str, model_field: str) -> str | None:
    """Best-effort extraction of a model field value from raw FHIR for display purposes."""
    # Common ID fields
    if model_field in ("patient_id", "encounter_id", "condition_id", "med_id",
                       "obs_id", "procedure_id", "report_id", "imm_id",
                       "allergy_id", "study_id"):
        rid = raw.get("id", "")
        if model_field in ("patient_id",):
            ref = raw.get("subject", raw.get("patient", {})).get("reference", "")
            return ref.split(":")[-1][:20] if ref else None
        if model_field in ("encounter_id",):
            ref = raw.get("encounter", {}).get("reference", "")
            return ref.split(":")[-1][:20] if ref else None
        return rid[:20] if rid else None

    if model_field == "name":
        names = raw.get("name", [{}])
        if names:
            return " ".join(names[0].get("given", [])) + " " + names[0].get("family", "")
        return None

    if model_field == "gender":
        return raw.get("gender")

    if model_field in ("birth_date", "deceased_date"):
        return raw.get("birthDate") if "birth" in model_field else raw.get("deceasedDateTime")

    if model_field == "status":
        return raw.get("status")

    if model_field == "class_code":
        return raw.get("class", {}).get("code")

    if model_field == "encounter_type":
        types = raw.get("type", [])
        if types:
            codings = types[0].get("coding", [])
            return codings[0].get("display") if codings else None
        return None

    if model_field == "clinical_status":
        cc = raw.get("clinicalStatus", {})
        codings = cc.get("coding", [])
        return codings[0].get("code") if codings else None

    if model_field == "verification_status":
        cc = raw.get("verificationStatus", {})
        codings = cc.get("coding", [])
        return codings[0].get("code") if codings else None

    if model_field in ("code (CodeableConcept)",):
        code = raw.get("code", {})
        codings = code.get("coding", [])
        if codings:
            c = codings[0]
            return f"{c.get('system', '')}: {c.get('code', '')} ({c.get('display', '')})"
        return None

    if model_field in ("rxnorm_code, display",):
        med = raw.get("medicationCodeableConcept", {})
        codings = med.get("coding", [])
        if codings:
            return f"{codings[0].get('code', '')} — {codings[0].get('display', '')}"
        return None

    if model_field in ("loinc_code, display",):
        code = raw.get("code", {}).get("coding", [])
        if code:
            return f"{code[0].get('code', '')} — {code[0].get('display', '')}"
        return None

    if model_field in ("cvx_code, display",):
        vc = raw.get("vaccineCode", {}).get("coding", [])
        if vc:
            return f"{vc[0].get('code', '')} — {vc[0].get('display', '')}"
        return None

    if model_field == "category":
        cats = raw.get("category", [])
        if cats:
            codings = cats[0].get("coding", [])
            return codings[0].get("code") if codings else None
        return None

    if model_field == "authored_on":
        return raw.get("authoredOn")

    if model_field == "onset_dt":
        return raw.get("onsetDateTime") or (raw.get("onsetPeriod", {}) or {}).get("start")

    if model_field == "occurrence_dt":
        return raw.get("occurrenceDateTime")

    if model_field in ("period (Period)", "performed_period"):
        p = raw.get("period", raw.get("performedPeriod", {}))
        if p:
            return f"{p.get('start', '?')} — {p.get('end', '?')}"
        return None

    if model_field in ("value_quantity, value_unit",):
        vq = raw.get("valueQuantity", {})
        if vq:
            return f"{vq.get('value', '')} {vq.get('unit', '')}"
        return None

    if model_field == "is_active":
        cs = raw.get("clinicalStatus", {}).get("coding", [{}])[0].get("code", "") if raw.get("clinicalStatus") else ""
        abate = raw.get("abatementDateTime")
        return str(cs == "active" and abate is None)

    # Fallback: don't display
    return None
