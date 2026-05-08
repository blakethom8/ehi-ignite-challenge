"""MultiPassFHIRPipeline — schema-direct multi-pass extraction.

The architectural test. Replaces the bespoke ExtractionResult intermediate
format with per-resource-type passes that emit FHIR-shaped output directly.
Per ``docs/architecture/PDF-PROCESSOR.md`` decisions 1–4:

  1. **No intermediate format.** Each pass emits resources that go straight
     into a FHIR Bundle. Adding a new resource type = adding a new pass +
     its mini-schema; no changes to the pipeline core.

  2. **Multi-task → single-task.** The single-pass baseline asks one LLM
     call to handle Conditions, Symptoms (and implicitly nothing else).
     Multi-pass dispatches one focused call per FHIR resource type. Each
     prompt is targeted; each schema is small.

  3. **Pass 0 establishes document context.** Patient, encounter date,
     facility, ordering provider — extracted ONCE per PDF. Every per-
     resource pass receives that context so emitted resources carry
     consistent metadata even when source content spans pages.

  4. **Per-pass model selection.** Each ``ExtractionPass`` declares its
     backend + model. Cheap models for tabular passes (labs,
     immunizations); smarter models for narrative passes (conditions,
     allergies). The bake-off harness measures whether downgrading
     specific passes preserves F1.

What this pipeline ships today
-------------------------------
- Five resource passes: Conditions, Medications, AllergyIntolerance,
  Immunizations, Lab Observations. Procedures and Vitals are deferred
  until the eval harness scores them.
- Parallel dispatch via ThreadPoolExecutor (the AnthropicBackend is sync;
  asyncio bridging adds complexity for no real gain at 5–6 concurrent
  requests).
- Per-pass cache via the existing :class:`ExtractionCache`, keyed on
  (pdf_sha, pass_name, prompt_version, schema_version, backend/model).
"""

# Extension URL convention: https://ehi-atlas.example/fhir/StructureDefinition/...
# All new emissions in this file MUST use this base. The harmonize layer
# at lib/harmonize/provenance.py uses a different base
# (atlas.healthcaredataai.com) — those will migrate as part of T15.

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, Type

from pydantic import BaseModel, Field

from lib.extract.cache import CacheKey, ExtractionCache, hash_file
from lib.extract.layout import extract_layout, find_text_bbox
from lib.extract.pdf import VisionBackend, get_backend
from lib.extract.pipelines.base import (
    ExtractionPipeline,
    PipelineMetadata,
    register,
)


# ---------------------------------------------------------------------------
# Per-pass schemas (Pydantic) — small, focused, no discriminated unions
# ---------------------------------------------------------------------------


class DocumentContext(BaseModel):
    """Pass 0 output. Document-level metadata that propagates to every other pass.

    Extracted ONCE per PDF; cached as part of the pipeline's overall result.
    """

    document_type: Literal[
        "lab-report",
        "clinical-note",
        "discharge-summary",
        "imaging-report",
        "patient-summary",
        "other",
    ] = Field(..., description="Best guess at the document's primary type")
    patient_name: str | None = Field(None, description="Patient name as it appears")
    patient_dob: str | None = Field(None, description="Patient DOB ISO 8601 YYYY-MM-DD")
    encounter_date: str | None = Field(
        None, description="Date the document was issued / effective ISO 8601"
    )
    ordering_provider: str | None = None
    facility_name: str | None = Field(
        None,
        description="Lab name, hospital, clinic, or 'Patient Health Summary' for portal exports",
    )


class ConditionEntry(BaseModel):
    display: str = Field(..., description="Condition as it appears on the page")
    icd_10_cm_code: str | None = None
    snomed_ct_code: str | None = None
    onset_date: str | None = Field(None, description="ISO 8601 if mentioned")
    clinical_status: Literal[
        "active", "resolved", "remission", "recurrence", "relapse", "inactive"
    ] = "active"
    page: int | None = Field(None, description="1-indexed page number where this appeared")
    source_text: str | None = Field(
        None, description="Short verbatim phrase from the document (≤120 chars)"
    )


class ConditionExtraction(BaseModel):
    conditions: list[ConditionEntry] = Field(default_factory=list)


class MedicationEntry(BaseModel):
    display: str = Field(
        ...,
        description="Full medication name including dose form (e.g. 'Fluticasone propionate 50 mcg nasal spray')",
    )
    rxnorm_code: str | None = None
    dose: str | None = Field(None, description="Strength + units (e.g. '500 mg')")
    frequency: str | None = Field(None, description="Schedule (e.g. 'BID', 'once daily')")
    status: Literal[
        "active",
        "completed",
        "stopped",
        "on-hold",
        "cancelled",
        "draft",
        "unknown",
    ] = "active"
    page: int | None = None
    source_text: str | None = None


class MedicationExtraction(BaseModel):
    medications: list[MedicationEntry] = Field(default_factory=list)


class AllergyEntry(BaseModel):
    display: str = Field(..., description="Allergen as it appears (e.g. 'Penicillin', 'Peanuts')")
    snomed_ct_code: str | None = None
    reaction: str | None = Field(None, description="Reaction description if present")
    severity: Literal["mild", "moderate", "severe"] | None = None
    page: int | None = None
    source_text: str | None = None


class AllergyExtraction(BaseModel):
    allergies: list[AllergyEntry] = Field(default_factory=list)


class ImmunizationEntry(BaseModel):
    vaccine_display: str = Field(
        ..., description="Vaccine name (e.g. 'Influenza, QUAD, Preservative Free')"
    )
    cvx_code: str | None = None
    administration_date: str | None = Field(None, description="ISO 8601 if visible")
    page: int | None = None
    source_text: str | None = None


class ImmunizationExtraction(BaseModel):
    immunizations: list[ImmunizationEntry] = Field(default_factory=list)


class LabObservationEntry(BaseModel):
    test_name: str = Field(..., description="Test name as printed (e.g. 'Creatinine')")
    loinc_code: str | None = Field(
        None, description="LOINC code if confidently identified, else null"
    )
    value_quantity: float | None = None
    value_string: str | None = Field(
        None, description="Free-text value if non-numeric (e.g. 'Negative')"
    )
    unit: str | None = Field(None, description="UCUM unit if available")
    reference_range_low: float | None = None
    reference_range_high: float | None = None
    flag: Literal["H", "L", "N", "HH", "LL", "A"] | None = None
    effective_date: str | None = None
    page: int | None = None


class LabObservationExtraction(BaseModel):
    observations: list[LabObservationEntry] = Field(default_factory=list)


class VitalSignEntry(BaseModel):
    vital_type: Literal[
        "blood-pressure-systolic",
        "blood-pressure-diastolic",
        "heart-rate",
        "body-temperature",
        "respiratory-rate",
        "oxygen-saturation",
        "body-weight",
        "body-height",
        "bmi",
    ] = Field(..., description="Standardized vital-sign type")
    value: float | None = None
    unit: str | None = Field(None, description="UCUM unit if applicable")
    reference_range_low: float | None = None
    reference_range_high: float | None = None
    flag: Literal["H", "L", "N", "HH", "LL", "A"] | None = None
    effective_date: str | None = Field(None, description="ISO 8601 if printed")
    page: int | None = None
    source_text: str | None = None


class VitalSignExtraction(BaseModel):
    vital_signs: list[VitalSignEntry] = Field(default_factory=list)


class EncounterEntry(BaseModel):
    encounter_id: str | None = Field(
        None, description="Encounter ID if printed; otherwise the pipeline synthesizes a UUID"
    )
    status: Literal[
        "planned", "arrived", "triaged", "in-progress", "onleave", "finished", "cancelled"
    ] = "finished"
    class_code: Literal["AMB", "EMER", "IMP", "ACUTE", "NONAC", "OBSENC", "PRENC", "SS", "VR"] | None = Field(
        None,
        description="HL7 v3 ActCode for encounter class. AMB=Ambulatory (office visit), "
        "IMP=Inpatient, EMER=Emergency, ACUTE=Acute inpatient, OBSENC=Observation, etc."
    )
    type_display: str | None = Field(
        None, description="Encounter type as printed (e.g. 'Office Visit', 'Telehealth', 'Annual Physical')"
    )
    period_start: str | None = Field(None, description="ISO 8601; date or datetime")
    period_end: str | None = Field(None, description="ISO 8601; date or datetime")
    service_provider_display: str | None = Field(
        None, description="Name of the organization / facility / clinic that hosted this encounter"
    )
    participant_display: str | None = Field(
        None, description="Primary practitioner (name + role) for this encounter"
    )
    reason_text: str | None = Field(
        None, description="Reason for visit / chief complaint as narrative text"
    )
    page: int | None = None
    source_text: str | None = None


class EncounterExtraction(BaseModel):
    encounters: list[EncounterEntry] = Field(default_factory=list)


class PractitionerEntry(BaseModel):
    practitioner_id: str | None = Field(
        None, description="Practitioner ID if printed; otherwise pipeline synthesizes one"
    )
    npi: str | None = Field(
        None, description="10-digit NPI number if printed (digits only — strip dashes/spaces)"
    )
    display_name: str | None = Field(
        None, description="Full name as displayed (e.g. 'Steven Krems, MD')"
    )
    family_name: str | None = None
    given_names: list[str] = Field(default_factory=list)
    prefix: str | None = Field(None, description="Title prefix: Dr. / Mr. / Mrs.")
    suffix: str | None = Field(
        None, description="Credential suffix: MD, DO, NP, PA, RN, MD PhD, etc."
    )
    specialty: str | None = Field(
        None, description="Clinical specialty if mentioned (e.g. 'Allergy & Immunology')"
    )
    role: str | None = Field(
        None, description="Role in care: 'PCP', 'Attending', 'Supervising Physician', 'Authorizing'"
    )
    phone: str | None = None
    address_line: str | None = None
    city: str | None = None
    state: str | None = None
    postal_code: str | None = None
    page: int | None = None
    source_text: str | None = None


class PractitionerExtraction(BaseModel):
    practitioners: list[PractitionerEntry] = Field(default_factory=list)


class OrganizationEntry(BaseModel):
    organization_id: str | None = Field(
        None, description="Organization ID if printed; otherwise synthesized"
    )
    name: str | None = Field(..., description="Organization name as printed")
    type_code: Literal[
        "prov",     # Healthcare Provider (general)
        "dept",     # Department
        "team",     # Care team
        "ins",      # Insurance company
        "pay",      # Payer
        "edu",      # Educational institution
        "reli",     # Religious institution
        "crs",      # Clinical research sponsor
        "cg",       # Community group
        "bus",      # Non-healthcare business
        "other",
    ] | None = Field(
        None, description="HL7 organization-type code. 'prov' = generic healthcare provider; "
        "'dept' for sub-departments; 'pay' / 'ins' for insurance"
    )
    type_display: str | None = Field(
        None, description="Free-text type label (e.g. 'Allergy Clinic', 'Diagnostic Lab')"
    )
    phone: str | None = None
    fax: str | None = None
    address_line: str | None = None
    city: str | None = None
    state: str | None = None
    postal_code: str | None = None
    page: int | None = None
    source_text: str | None = None


class OrganizationExtraction(BaseModel):
    organizations: list[OrganizationEntry] = Field(default_factory=list)


class ClinicalNoteSection(BaseModel):
    title: str = Field(..., description="Section title as printed (e.g. 'Subjective', 'Physical Exam', 'Assessment and Plan', 'Plan')")
    loinc_code: str | None = Field(
        None, description="LOINC code for the section if known. Common: 10164-2 History of Present Illness, "
        "29545-1 Physical Examination, 51848-0 Evaluation note, 18776-5 Plan of treatment, 11329-0 Hx of past illness, "
        "10157-6 History of family member diseases."
    )
    narrative_text: str = Field(..., description="VERBATIM narrative text from this section. Do NOT summarize.")


class ClinicalNoteEntry(BaseModel):
    note_id: str | None = Field(None, description="Note ID if printed; otherwise synthesized")
    note_type: Literal[
        "progress-note",
        "consult-note",
        "discharge-summary",
        "procedure-note",
        "history-and-physical",
        "patient-education",
        "telephone-encounter",
        "other",
    ] = "progress-note"
    note_type_loinc: str | None = Field(
        None, description="LOINC code for note type. Common: 11506-3 Progress note, "
        "11488-4 Consultation note, 18842-5 Discharge summary, 28570-0 Procedure note, "
        "34117-2 History and Physical."
    )
    title: str | None = Field(None, description="Note title as printed (e.g. 'Allergy & Immunology Progress Note')")
    author_name: str | None = None
    author_role: str | None = Field(None, description="Author credential / role (NP / MD / RN / etc.)")
    encounter_date: str | None = Field(None, description="ISO 8601; date the note was authored")
    sections: list[ClinicalNoteSection] = Field(default_factory=list, description="Ordered sections of the note")
    page_start: int | None = None
    page_end: int | None = None
    source_text: str | None = None


class ClinicalNoteExtraction(BaseModel):
    clinical_notes: list[ClinicalNoteEntry] = Field(default_factory=list)


class PatientEntry(BaseModel):
    patient_id: str | None = Field(
        None, description="Patient ID / MRN if printed (used as the FHIR Patient.id when present)"
    )
    family_name: str | None = None
    given_names: list[str] = Field(default_factory=list)
    prefix: str | None = None
    suffix: str | None = None
    nickname: str | None = Field(None, description="Preferred / used name (e.g. 'Blake' for 'Blake Thomson')")
    gender: Literal["male", "female", "other", "unknown"] | None = None
    birth_sex: Literal["M", "F", "UNK", "OTH"] | None = Field(
        None, description="US Core birthsex: M / F / UNK / OTH"
    )
    birth_date: str | None = Field(None, description="ISO 8601 YYYY-MM-DD")
    deceased_date: str | None = None
    # OMB race + ethnicity codes (US Core)
    race_text: str | None = Field(None, description="Race as printed (free text)")
    race_omb_code: str | None = Field(
        None,
        description="OMB race code: 1002-5 American Indian/Alaska Native, 2028-9 Asian, "
        "2054-5 Black/African American, 2076-8 Native Hawaiian/Pacific Islander, "
        "2106-3 White, 2131-1 Other"
    )
    ethnicity_text: str | None = None
    ethnicity_omb_code: str | None = Field(
        None,
        description="OMB ethnicity code: 2135-2 Hispanic or Latino, 2186-5 Not Hispanic or Latino"
    )
    marital_status: str | None = Field(
        None, description="Marital status as printed (e.g. 'Domestic Partner', 'Married', 'Single')"
    )
    language: str | None = Field(None, description="Preferred language as printed (e.g. 'English')")
    address_line: str | None = None
    city: str | None = None
    state: str | None = None
    postal_code: str | None = None
    country: str | None = None
    phone_home: str | None = None
    phone_mobile: str | None = None
    phone_work: str | None = None
    email: str | None = None
    page: int | None = None
    source_text: str | None = None


class PatientExtraction(BaseModel):
    patients: list[PatientEntry] = Field(
        default_factory=list,
        description="Usually 1; allow list to handle edge cases (e.g. multi-patient summaries)",
    )


class CoverageEntry(BaseModel):
    coverage_id: str | None = None
    status: Literal["active", "cancelled", "draft", "entered-in-error"] = "active"
    plan_type: str | None = Field(None, description="HMO / PPO / EPO / POS / Indemnity / etc.")
    payor_name: str | None = Field(None, description="Insurance company / payer (e.g. 'Blue Cross', 'Aetna')")
    plan_name: str | None = Field(None, description="Specific plan name (e.g. 'BLUE CROSS EMP VIVITY HMO CSPN')")
    member_id: str | None = Field(None, description="Member ID / Subscriber ID")
    subscriber_id: str | None = None
    group_id: str | None = None
    payer_id: str | None = Field(None, description="Payer ID (e.g. NAIC code)")
    relationship_to_subscriber: Literal["self", "spouse", "child", "common-law-spouse", "other"] | None = None
    effective_period_start: str | None = None
    effective_period_end: str | None = None
    page: int | None = None
    source_text: str | None = None


class CoverageExtraction(BaseModel):
    coverages: list[CoverageEntry] = Field(default_factory=list)


class SocialHistoryEntry(BaseModel):
    topic: Literal[
        "tobacco-use",
        "alcohol-use",
        "drug-use",
        "occupation",
        "phq-9",
        "phq-2",
        "depression-screen",
        "sex-assigned-at-birth",
        "legal-sex",
        "gender-identity",
        "sexual-orientation",
    ] = Field(..., description="Standardized social-history topic")
    value_string: str | None = Field(
        None, description="Categorical / text value (e.g. 'Never', 'Yes', 'Manager')"
    )
    value_quantity: float | None = Field(
        None, description="Numeric value (e.g. PHQ-9 score, drinks/week)"
    )
    unit: str | None = Field(None, description="UCUM unit if numeric")
    effective_date: str | None = None
    page: int | None = None
    source_text: str | None = None


class SocialHistoryExtraction(BaseModel):
    social_history: list[SocialHistoryEntry] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Pass definitions — declarative table of what runs and how
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ExtractionPass:
    """Declarative description of one extraction pass.

    Each pass has its own prompt, schema, prompt_version, schema_version,
    and backend. Adding a new fact type is a new ExtractionPass + a
    converter function.

    - prompt_version: bump for prompt-only changes. Cheap re-extract for
      this pass alone; other passes' caches unaffected. Track deltas in
      ``docs/architecture/PIPELINE-LOG.md``.
    - schema_version: bump when the BaseModel schema for this pass changes.
      Forces re-extract for this pass alone; other passes' caches unaffected.
      Both are per-pass — they do NOT invalidate other passes' caches.
    """

    name: str
    schema: Type[BaseModel]
    system_prompt: str
    prompt_version: str = "v1"
    schema_version: str = "v1"
    backend_name: str = "anthropic"
    model: str | None = None


_PASS_0_PROMPT = """You are reading a single medical document. Extract the
document's top-level metadata: what kind of document it is, who the patient
is, when it was issued, and which facility/lab/clinic produced it.

Be conservative. If a field isn't clearly visible, return null for that field.
The document_type field is required — pick the closest match from the enum."""


_CONDITIONS_PROMPT = """You are extracting EVERY clinical condition or
diagnosis recorded in this medical document. Be exhaustive.

A "condition" in FHIR includes ALL of these — extract each one:

  1. **Diseases / disorders** (e.g. 'Allergic rhinitis', 'Hyperlipidemia')
  2. **Symptoms** treated as diagnoses (e.g. 'Sinus congestion R09.81',
     'Pain R52', 'Sinus pressure J34.89')
  3. **Injuries** with episode-of-care codes (e.g. 'Sprain of left foot
     S93.602A', 'Closed fracture of phalanx S92.512S sequela')
  4. **Z-codes for encounters** — these ARE conditions in FHIR:
     - Z00.00 Annual physical exam
     - Z11.59 Special screening for viral disease
     - Z12.83 Screening exam for skin cancer
     - Z23 Need for vaccination
     - Z85.x History of cancer
     Treat every Z-code printed in the document as a condition entry.
  5. **R-codes** — symptoms-coded-as-findings. Always emit when a code
     is printed. Don't filter "this is just a symptom not a real diagnosis."
  6. **D-codes** for neoplasms / lesions, including benign (e.g. D22.9
     multiple nevi, D49.2 skin neoplasm, L82.1 seborrheic keratoses)
  7. **Resolved conditions** (mark clinical_status=resolved)
  8. **Past medical history** entries, including remote ones

Sources to scan in chart-export documents:
  - Problem list / Active Problems
  - Past Medical History
  - Encounter Diagnoses / Visit Diagnoses (PER ENCOUNTER — yes, the
    same condition appearing in 4 visits should be emitted, but only
    ONCE; we'll dedupe by code)
  - Reason for Visit / Chief Complaint coded with an ICD code
  - Health maintenance / preventive care items with Z-codes
  - Surgical history (the underlying condition, e.g. 'Appendectomy
    2015' → only emit appendicitis if document explicitly codes it)

Rules:
- Extract every UNIQUE condition. If the same code appears multiple times
  (problem list + 3 encounter diagnoses), emit it ONCE.
- Different codes for related conditions are SEPARATE entries (e.g.
  J30.1 'Allergic rhinitis due to pollen' and J30.81 'Allergic rhinitis
  due to dust mite' are two different facts — emit both).
- Include ICD-10-CM and SNOMED-CT codes ONLY when printed in the document.
  Never fabricate. Null is correct when no code is shown.
- Use the display name VERBATIM from the document.
- clinical_status: 'active' by default; 'resolved' if document says so.
- Set page to the 1-indexed page where the condition first appeared.
- Include source_text: ≤120 char verbatim excerpt.
- Skip conditions in family history attributed only to RELATIVES.

A typical comprehensive chart export has 10–30 distinct conditions.
If you return fewer than 8 from a multi-page chart, you're probably
under-extracting — re-scan for Z-codes, R-codes, and encounter-level
diagnoses you may have skipped."""


_MEDICATIONS_PROMPT = """You are extracting medications from a medical document.

Rules:
- Extract every medication mentioned in current/active med lists, prescription
  records, or inpatient admin lists.
- Use the full medication name including dose form (e.g. "fluticasone propionate
  50 mcg nasal spray", not just "fluticasone").
- Include RxNorm code only if printed on the document. Don't fabricate.
- Include dose (strength) and frequency when stated.
- Status defaults to active; mark completed/stopped/cancelled only when explicit.
- Skip medications that are merely mentioned in narrative ("the patient was
  previously on X") unless the document treats them as part of the structured
  med list.
- If no medications are present, return an empty list."""


_ALLERGIES_PROMPT = """You are extracting allergies and intolerances from a
medical document.

Rules:
- Extract every allergen explicitly listed in an allergy section.
- Include "No Known Allergies" / "NKDA" / similar — that's still an
  AllergyIntolerance entry with display="No Known Allergies".
- Include reaction and severity when stated.
- Include SNOMED-CT code only if printed on the document.
- If the document has no allergy section at all (vs "no known allergies"),
  return an empty list."""


_IMMUNIZATIONS_PROMPT = """You are extracting immunizations/vaccines from a
medical document.

Rules:
- Extract every vaccine administration explicitly recorded.
- Use the vaccine name as printed (e.g. "Influenza, QUAD, Preservative Free").
- Include CVX code only if printed.
- administration_date should be ISO 8601 (YYYY-MM-DD) if a date is shown.
- Don't extract vaccines merely recommended or counseled-on but not given.
- If no immunization section is present, return an empty list."""


_LAB_OBSERVATIONS_PROMPT = """You are extracting individual lab/diagnostic
results from a medical document.

Rules:
- Extract every result row in detailed-results tables. Include the test name,
  numeric value (or string value for non-numeric like "Negative"), unit,
  reference range, and flag (H/L/N/HH/LL/A).
- LOINC codes only if printed on the document.
- effective_date is the date the lab was performed, if stated. Often this
  is at the document level; in that case set it to the document_date supplied
  via context.
- Do NOT extract narrative text or summary statements about labs ("kidney
  function was normal") — only extract structured result rows.
- If no lab tables are present (e.g. this is a pure clinical note), return
  an empty list."""


_VITAL_SIGNS_PROMPT = """You are extracting vital-sign measurements from a
medical document.

Rules:
- Extract vital signs from any "Vital Signs" / "Last Filed Vital Signs" /
  "Last Vital Signs" table or row in the document.
- For Blood Pressure (e.g. "119/71"), emit TWO entries:
  one with vital_type="blood-pressure-systolic" value=119,
  one with vital_type="blood-pressure-diastolic" value=71.
- Use UCUM units: mm[Hg] for blood pressure, /min for heart rate and
  respiratory rate, Cel for Celsius, %{Saturation} for O2 sat, kg for
  weight, cm for height, kg/m2 for BMI.
- effective_date is the date the vital was taken if shown; ISO 8601.
- Don't extract vitals merely referenced in narrative without a value.
- If no vital-signs section is present, return an empty list."""


_ENCOUNTERS_PROMPT = """You are extracting clinical encounters / visits / appointments
from a medical document.

Rules:
- Extract every distinct encounter explicitly recorded — office visits, telehealth
  visits, hospitalizations, ER visits, procedure visits, follow-ups.
- Use ISO 8601 dates. If only a date is shown (no time), use that as period_start
  with no period_end. If date + time are shown, include the time portion.
- class_code mapping (HL7 v3 ActCode):
    AMB     = Ambulatory office visit, telehealth, urgent care
    IMP     = Inpatient hospitalization
    EMER    = Emergency department visit
    ACUTE   = Acute inpatient
    OBSENC  = Observation stay
    PRENC   = Pre-admission encounter
    SS      = Short-stay
    VR      = Virtual / telehealth (use when explicitly virtual)
- type_display: the narrative type as printed (e.g. "Office Visit", "Annual Physical",
  "Allergy Follow-up", "Wellness Visit", "Hospital Discharge").
- service_provider_display: the organization / clinic / hospital that hosted the visit
  (e.g. "Beverly Hills Allergy", "Cedars-Sinai Health System").
- participant_display: the primary practitioner (e.g. "Ani Shirvanian, NP",
  "Steven Krems, MD"). One name per encounter — capture the lead provider.
- reason_text: chief complaint / reason for visit as a short phrase if printed.
- Do not synthesize encounters from medication orders or lab orders alone.
- If no encounter records are present (e.g. lab-only PDF), return empty list."""


_PRACTITIONERS_PROMPT = """You are extracting practitioners / providers / clinicians
mentioned in a medical document.

Rules:
- Extract every distinct practitioner — physicians, nurse practitioners,
  physician assistants, supervising providers, authorizing providers,
  pathologists, radiologists.
- Distinguish first-time mentions from repeated references — emit ONE entry
  per unique practitioner. If the same name appears multiple times in the
  document with different roles (e.g. "Ani Shirvanian, NP" appears as
  Attending in one encounter and as Care Team member elsewhere), emit one
  entry capturing the highest-fidelity role description.
- Capture NPI if printed. NPIs are 10-digit numbers, often labeled "NPI:"
  or appearing under a provider's name.
- Capture suffix credentials carefully: "MD" / "DO" / "NP" / "PA" / "RN" /
  "MD, PhD" / etc. These go in `suffix`, not in `display_name`.
- Capture specialty if mentioned in narrative (e.g. "Board certified in
  Allergy & Immunology" → specialty="Allergy & Immunology").
- Capture role if context makes it clear: PCP / Attending / Supervising /
  Authorizing / Performing / Ordering. Do not guess if not stated.
- Capture practice address from any "Suite", "Office Phone", or formal
  address block adjacent to the name.
- If only a display name is shown without a clear practitioner context
  (e.g. a name buried in narrative), still emit it — name alone is enough.
- If no practitioners are present, return empty list."""


_ORGANIZATIONS_PROMPT = """You are extracting healthcare organizations / facilities /
labs / hospitals / clinics mentioned in a medical document.

Rules:
- Extract every distinct healthcare organization. Examples:
    - Health systems / hospitals: "Cedars-Sinai Health System", "Mayo Clinic"
    - Clinics: "Beverly Hills Allergy", "Beverly Hills Allergy & Immunology"
    - Labs: "Quest Diagnostics", "Quest Diagnostics-West Hills", "LabCorp"
    - Pathology departments: "CEDARS-SINAI MED CTR DEPT OF PATHOLOGY"
    - Imaging centers
    - Pharmacies (when named as the dispensing org, not the brand)
    - Insurance / payers: "BLUE CROSS", "Aetna", "Humana"
- Emit one entry per unique organization. If the same name appears multiple
  times in the document with different roles (e.g. "Quest Diagnostics" as
  a performing org and as a contact org), emit one entry.
- type_code mapping (HL7 organization-type):
    prov  = generic healthcare provider (hospital, clinic, lab — most cases)
    dept  = a department within a larger org ("DEPT OF PATHOLOGY")
    pay   = payer / insurance company (Blue Cross, Aetna)
    ins   = insurance product
    other = anything not clearly fitting above
  Default to 'prov' when in doubt.
- type_display: a more specific narrative label (e.g. "Allergy Clinic",
  "Diagnostic Lab", "Hospital", "Insurance Company").
- Capture phone, fax, full address when printed.
- Be careful: don't extract individual practitioners' personal addresses
  (those go to the Practitioner pass). Only extract addresses tied to the
  organization itself.
- If no organizations are mentioned, return empty list."""


_CLINICAL_NOTES_PROMPT = """You are extracting long-form narrative clinical notes
from a medical document.

What counts as a clinical note:
- Progress notes (SOAP-format or narrative)
- Consult notes
- Discharge summaries
- Procedure notes
- History & Physical (H&P) entries
- Patient education paragraphs that read as continuous narrative

Rules:
- Extract every distinct narrative note. Each note becomes ONE
  ClinicalNoteEntry; its internal sections (Subjective, Objective,
  Assessment, Plan, etc.) become entries in the `sections` list.
- Preserve section structure when present. Common section titles:
    Subjective, Objective, Physical Exam, Assessment, Plan,
    Assessment and Plan, History of Present Illness, Reason for Visit,
    Patient Education, Plan of Treatment, Reason for Follow up,
    Past Medical History, Review of Systems, Allergies (when narrative).
- For each section: capture the title verbatim and the FULL narrative
  text. Do NOT summarize, paraphrase, or shorten. The point of this
  pass is to preserve narrative fidelity.
- LOINC codes for note types (use these when confident):
    11506-3 = Progress note
    11488-4 = Consultation note
    18842-5 = Discharge summary
    28570-0 = Procedure note
    34117-2 = History and Physical
- LOINC codes for sections (use these when confident):
    10164-2 = History of Present Illness (Subjective / HPI)
    29545-1 = Physical Examination (Objective / Physical Exam)
    51848-0 = Evaluation note (Assessment)
    18776-5 = Plan of treatment (Plan)
    51847-2 = Evaluation + Plan note (combined A&P)
- Capture author_name + author_role separately (e.g. "Ani Shirvanian"
  + "NP", or "Steven Krems" + "MD"). Strip the credential from the name.
- encounter_date: ISO 8601 if visible. Use the note's authored/signed date.
- page_start / page_end: 1-indexed page numbers spanning the note.
- Multi-page notes ARE allowed — capture the full continuous narrative
  even if it spans pages.
- Do NOT extract structured-table content here (vital signs, labs,
  medications, immunizations have their own passes).
- Do NOT extract administrative text (insurance, demographics,
  document headers/footers).
- If no narrative notes are present (e.g. lab-only PDF), return empty list."""


_COVERAGE_PROMPT = """You are extracting insurance / coverage / payer information
from a medical document.

Rules:
- Extract every distinct insurance plan / coverage record. A patient may have
  primary + secondary coverage; emit one entry per plan.
- payor_name: the insurance company (e.g. "Blue Cross Blue Shield", "Aetna",
  "Humana", "Medicare", "Medicaid"). Strip the specific plan suffix.
- plan_name: the full plan name as printed (e.g. "BLUE CROSS EMP VIVITY HMO CSPN").
- plan_type: HMO / PPO / EPO / POS / Indemnity / Medicare / Medicaid / etc.
- member_id and subscriber_id: capture both if shown. They're often the same
  but distinguish when the patient is a dependent on someone else's plan.
- group_id: employer group ID if shown.
- relationship_to_subscriber: 'self' if the patient IS the subscriber, else
  spouse / child / common-law-spouse / other.
- Dates ISO 8601. effective_period_start/end if printed (e.g. "Effective 01/01/2026-Present").
- Do NOT extract historical-only / cancelled coverages unless explicitly listed
  with end dates.
- If no insurance information is present, return empty list."""


_PATIENT_DEMOGRAPHICS_PROMPT = """You are extracting patient demographic information
from a medical document.

Rules:
- Extract the primary patient's demographics. Most documents describe ONE patient;
  emit one PatientEntry. If the document covers multiple patients (rare), emit
  one entry per distinct patient.
- patient_id: capture MRN / Medical Record Number / Patient ID if printed.
- gender: lowercase ("male" / "female" / "other" / "unknown").
- birth_sex: US Core uses single-letter codes. "Legal Sex Male" / "Sex Assigned at
  Birth Male" → "M". Female → "F". Unknown / not on file → "UNK". Other → "OTH".
- birth_date: ISO 8601 (YYYY-MM-DD).
- race_text: capture as printed (e.g. "White", "Black or African American",
  "Asian", "American Indian or Alaska Native").
- race_omb_code: map to OMB code if confident:
    1002-5 = American Indian or Alaska Native
    2028-9 = Asian
    2054-5 = Black or African American
    2076-8 = Native Hawaiian or Other Pacific Islander
    2106-3 = White
    2131-1 = Other Race
- ethnicity_text: capture as printed (e.g. "Not Hispanic or Latino", "Hispanic or Latino").
- ethnicity_omb_code: map to OMB code if confident:
    2135-2 = Hispanic or Latino
    2186-5 = Not Hispanic or Latino
- marital_status: capture as printed (don't translate Domestic Partner → other terms).
- language: preferred spoken / written language as printed.
- Capture multiple phone numbers if labeled (Home / Mobile / Work).
- Capture address from the primary "Patient Address" block.
- Do NOT extract demographics of other people mentioned in the document
  (practitioners, emergency contacts, family). Those are not the patient.
- If no patient demographics block is present, return empty list."""


_PASSES: list[ExtractionPass] = [
    ExtractionPass(
        name="conditions",
        schema=ConditionExtraction,
        system_prompt=_CONDITIONS_PROMPT,
        # v3 (2026-05-03): explicit Z/R/S/D-code enumeration with concrete
        # examples. v2 (section enumeration) helped but model still skipped
        # encounter-level diagnoses and screening Z-codes. v3 adds
        # "extract every printed ICD code" with example codes for each
        # category — should pull recall from 0.16 toward 0.6+ on Cedars.
        prompt_version="v3",
    ),
    ExtractionPass(
        name="medications",
        schema=MedicationExtraction,
        system_prompt=_MEDICATIONS_PROMPT,
        prompt_version="v1",
    ),
    ExtractionPass(
        name="allergies",
        schema=AllergyExtraction,
        system_prompt=_ALLERGIES_PROMPT,
        prompt_version="v1",
    ),
    ExtractionPass(
        name="immunizations",
        schema=ImmunizationExtraction,
        system_prompt=_IMMUNIZATIONS_PROMPT,
        prompt_version="v1",
    ),
    ExtractionPass(
        name="lab_observations",
        schema=LabObservationExtraction,
        system_prompt=_LAB_OBSERVATIONS_PROMPT,
        prompt_version="v1",
    ),
    ExtractionPass(
        name="vital_signs",
        schema=VitalSignExtraction,
        system_prompt=_VITAL_SIGNS_PROMPT,
        prompt_version="v1",
        schema_version="v1",
    ),
    ExtractionPass(
        name="encounter",
        schema=EncounterExtraction,
        system_prompt=_ENCOUNTERS_PROMPT,
        prompt_version="v1",
        schema_version="v1",
    ),
    ExtractionPass(
        name="practitioner",
        schema=PractitionerExtraction,
        system_prompt=_PRACTITIONERS_PROMPT,
        prompt_version="v1",
        schema_version="v1",
    ),
    ExtractionPass(
        name="organization",
        schema=OrganizationExtraction,
        system_prompt=_ORGANIZATIONS_PROMPT,
        prompt_version="v1",
        schema_version="v1",
    ),
    ExtractionPass(
        name="clinical_notes",
        schema=ClinicalNoteExtraction,
        system_prompt=_CLINICAL_NOTES_PROMPT,
        prompt_version="v1",
        schema_version="v1",
    ),
    ExtractionPass(
        name="patient_demographics",
        schema=PatientExtraction,
        system_prompt=_PATIENT_DEMOGRAPHICS_PROMPT,
        prompt_version="v1",
        schema_version="v1",
    ),
    ExtractionPass(
        name="coverage",
        schema=CoverageExtraction,
        system_prompt=_COVERAGE_PROMPT,
        prompt_version="v1",
        schema_version="v1",
    ),
]


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------


_PROMPT_VERSION = "multipass-v0.1.0"
_SCHEMA_VERSION = "multipass-v0.1.0"

def _stable_encounter_id(e: "EncounterEntry", doc_context: "DocumentContext") -> str:
    """Stable, deterministic encounter ID from (date + provider + service)."""
    import hashlib

    parts = [
        e.period_start or doc_context.encounter_date or "no-date",
        e.participant_display or "no-provider",
        e.service_provider_display or "no-org",
        e.type_display or "no-type",
    ]
    seed = "|".join(parts)
    return f"enc-{hashlib.sha1(seed.encode()).hexdigest()[:12]}"


def _stable_practitioner_id(p: "PractitionerEntry") -> str:
    """Stable, deterministic ID. Prefers NPI when present (the canonical
    practitioner identifier in US healthcare); falls back to SHA1 of
    (display_name|family|given) for un-NPI'd practitioners."""
    import hashlib

    if p.npi:
        return f"prac-npi-{p.npi}"
    seed_parts = [
        p.display_name or "",
        p.family_name or "",
        "|".join(p.given_names),
        p.prefix or "",
        p.suffix or "",
    ]
    seed = "|".join(seed_parts)
    return f"prac-{hashlib.sha1(seed.encode()).hexdigest()[:12]}"


def _stable_organization_id(o: "OrganizationEntry") -> str:
    """Stable ID derived from normalized name + city + state. Same inputs
    yield same ID across re-extractions."""
    import hashlib
    name = (o.name or "").lower().strip()
    city = (o.city or "").lower().strip()
    state = (o.state or "").lower().strip()
    seed = f"{name}|{city}|{state}"
    return f"org-{hashlib.sha1(seed.encode()).hexdigest()[:12]}"


def _stable_clinical_note_id(n: "ClinicalNoteEntry", doc_context: "DocumentContext") -> str:
    """Stable, deterministic note ID from (title|author|date|page_start).
    Same inputs across re-extractions always yield the same ID."""
    import hashlib
    parts = [
        n.title or n.note_type,
        n.author_name or "no-author",
        n.encounter_date or doc_context.encounter_date or "no-date",
        str(n.page_start or 0),
    ]
    seed = "|".join(parts)
    return f"note-{hashlib.sha1(seed.encode()).hexdigest()[:12]}"


def _stable_patient_id(p: "PatientEntry", doc_context: "DocumentContext") -> str:
    """Stable patient ID derived from MRN if present, else from name + DOB.
    The FHIR Patient.id thus matches across re-extractions of the same patient."""
    import hashlib
    if p.patient_id:
        # Sanitize MRN for use as FHIR id (alphanumeric + dash)
        sanitized = "".join(c if c.isalnum() else "-" for c in p.patient_id)
        return f"pat-mrn-{sanitized}"
    seed_parts = [
        p.family_name or "",
        "|".join(p.given_names),
        p.birth_date or doc_context.patient_dob or "",
    ]
    seed = "|".join(seed_parts)
    return f"pat-{hashlib.sha1(seed.encode()).hexdigest()[:12]}"


def _stable_coverage_id(c: "CoverageEntry") -> str:
    """Stable, deterministic coverage ID from (payor|member|plan)."""
    import hashlib

    parts = [
        c.payor_name or "no-payor",
        c.member_id or c.subscriber_id or "no-member",
        c.plan_name or "no-plan",
    ]
    seed = "|".join(parts)
    return f"cov-{hashlib.sha1(seed.encode()).hexdigest()[:12]}"


# OMB code → display lookup tables
_OMB_RACE_DISPLAY = {
    "1002-5": "American Indian or Alaska Native",
    "2028-9": "Asian",
    "2054-5": "Black or African American",
    "2076-8": "Native Hawaiian or Other Pacific Islander",
    "2106-3": "White",
    "2131-1": "Other Race",
}
_OMB_ETHNICITY_DISPLAY = {
    "2135-2": "Hispanic or Latino",
    "2186-5": "Not Hispanic or Latino",
}


_VITAL_LOINC_MAP: dict[str, tuple[str, str]] = {
    "blood-pressure-systolic": ("8480-6", "Systolic blood pressure"),
    "blood-pressure-diastolic": ("8462-4", "Diastolic blood pressure"),
    "heart-rate": ("8867-4", "Heart rate"),
    "body-temperature": ("8310-5", "Body temperature"),
    "respiratory-rate": ("9279-1", "Respiratory rate"),
    "oxygen-saturation": ("2708-6", "Oxygen saturation in Arterial blood"),
    "body-weight": ("29463-7", "Body weight"),
    "body-height": ("8302-2", "Body height"),
    "bmi": ("39156-5", "Body mass index (BMI)"),
}


@register
class MultiPassFHIRPipeline:
    """Schema-direct multi-pass extraction. See module docstring for the *why*."""

    metadata = PipelineMetadata(
        name="multipass-fhir",
        description=(
            "Document-context pass + 5 per-resource-type passes (parallel). "
            "Each pass emits FHIR-shaped output directly. Eliminates the "
            "ExtractedClinicalNote schema-gap that was the dominant failure "
            "mode of single-pass-vision."
        ),
        architecture="multipass-vision",
        primary_backends=["anthropic"],  # default; per-pass override possible
        estimated_cost_per_pdf_usd=0.30,  # 6 calls × ~$0.05 each, rough
    )

    def __init__(
        self,
        *,
        patient_id: str = "unknown",
        backend_name: str = "anthropic",
        model: str | None = None,
        pass_overrides: dict[str, dict[str, str]] | None = None,
        max_workers: int = 6,
    ) -> None:
        """Construct a MultiPassFHIRPipeline.

        Args:
            patient_id: Patient FHIR ID for emitted resources.
            backend_name: Default backend for every pass when no override.
            model: Default model for every pass when no override.
            pass_overrides: Per-pass backend/model overrides. Format:
                ``{"pass_name": {"backend": "gemma-google-ai-studio",
                                 "model": "gemma-4-31b-it"}, ...}``.
                Used to test "cheap models for tabular passes" hypotheses
                without subclassing. Pass names match the ``name`` field
                in :data:`_PASSES`.
            max_workers: Concurrency for the per-resource passes. Default 6.
        """
        self._patient_id = patient_id
        self._backend_name = backend_name
        self._model = model
        self._pass_overrides = pass_overrides or {}
        self._max_workers = max_workers
        self._cache = ExtractionCache()

    def extract(
        self,
        pdf_path: Path,
        *,
        skip_cache: bool = False,
    ) -> dict[str, Any]:
        """Run document-context pass + per-resource passes in parallel; merge to Bundle."""
        pdf_bytes = pdf_path.read_bytes()
        pdf_hash = hash_file(pdf_path)

        # Pass 0 — document context
        doc_context = self._run_pass(
            pass_name="document_context",
            schema=DocumentContext,
            system_prompt=_PASS_0_PROMPT,
            pdf_bytes=pdf_bytes,
            pdf_hash=pdf_hash,
            skip_cache=skip_cache,
            extra_user_text=None,
        )

        # Build context-augmented prompt suffix for the rest of the passes
        context_suffix = (
            f"\n\n--- DOCUMENT CONTEXT (provided to ensure consistency across "
            f"resources) ---\n"
            f"document_type: {doc_context.document_type}\n"
            f"patient_name: {doc_context.patient_name}\n"
            f"patient_dob: {doc_context.patient_dob}\n"
            f"encounter_date: {doc_context.encounter_date}\n"
            f"ordering_provider: {doc_context.ordering_provider}\n"
            f"facility_name: {doc_context.facility_name}\n"
            f"--- end context ---"
        )

        # Per-resource passes — parallel
        per_pass_outputs: dict[str, BaseModel] = {}
        with ThreadPoolExecutor(max_workers=self._max_workers) as pool:
            futures = {
                pool.submit(
                    self._run_pass,
                    pass_name=p.name,
                    schema=p.schema,
                    system_prompt=p.system_prompt + context_suffix,
                    pdf_bytes=pdf_bytes,
                    pdf_hash=pdf_hash,
                    skip_cache=skip_cache,
                    extra_user_text=None,
                    prompt_version=p.prompt_version,
                    schema_version=p.schema_version,
                ): p
                for p in _PASSES
            }
            for future in as_completed(futures):
                p = futures[future]
                try:
                    per_pass_outputs[p.name] = future.result()
                except Exception as e:
                    # Per-pass failure is captured but doesn't kill the pipeline.
                    # Empty output for that pass; pipeline still emits a
                    # partial Bundle. The bake-off cell will reflect lower
                    # recall but completes successfully.
                    per_pass_outputs[p.name] = p.schema()  # empty instance
                    print(f"[multipass-fhir] pass {p.name!r} failed: {type(e).__name__}: {e}")

        # Merger — convert per-pass outputs to FHIR resources, build Bundle
        layout = self._safe_extract_layout(pdf_path)
        bundle = self._merge_to_bundle(
            doc_context=doc_context,
            per_pass=per_pass_outputs,
            pdf_path=pdf_path,
            layout=layout,
        )
        return bundle

    # ------------------------------------------------------------------
    # Pass machinery
    # ------------------------------------------------------------------

    def _run_pass(
        self,
        *,
        pass_name: str,
        schema: Type[BaseModel],
        system_prompt: str,
        pdf_bytes: bytes,
        pdf_hash: str,
        skip_cache: bool,
        extra_user_text: str | None,
        prompt_version: str = "v1",
        schema_version: str = "v1",
    ) -> BaseModel:
        """Execute one pass with caching + validation."""
        # Per-pass override resolution: pipeline ctor accepts a dict of
        # {pass_name: {backend, model}} that overrides the defaults.
        # Unspecified passes fall through to the pipeline's default backend.
        override = self._pass_overrides.get(pass_name, {})
        backend_name = override.get("backend") or self._backend_name
        model = override.get("model") or self._model
        backend = get_backend(name=backend_name, model=model)
        cache_model_id = f"multipass-fhir/{pass_name}/{backend.name}/{backend.model}"
        # Per-pass prompt + schema versions: bumping either for one pass only
        # invalidates that pass's cache, not the others.
        full_prompt_version = f"{_PROMPT_VERSION}/{pass_name}@{prompt_version}#{schema_version}"
        key = CacheKey(
            file_sha256=pdf_hash,
            prompt_version=full_prompt_version,
            schema_version=_SCHEMA_VERSION,
            model_name=cache_model_id,
        )

        if not skip_cache:
            cached = self._cache.get(key)
            if cached is not None:
                try:
                    return schema.model_validate(cached)
                except Exception:
                    # Cached entry doesn't validate against current schema —
                    # treat as miss and re-extract.
                    pass

        # Apply the same coercions extract_from_pdf uses, in case backends
        # emit string-wrapped sub-objects or extra envelope keys.
        from lib.extract.pdf import (
            _coerce_stringified_subobjects,
            _unwrap_extraction_envelope,
        )

        # One retry on validation failure. Anthropic's API occasionally
        # returns an empty tool_use input under concurrent load (we hit this
        # in the K.4 → Move A bake-off — same prompt + PDF + model that
        # worked moments earlier returned `{}`). A single retry is cheap
        # insurance; persistent failures still surface as exceptions.
        last_error: Exception | None = None
        for attempt in range(2):
            try:
                raw = backend.extract(
                    pdf_bytes=pdf_bytes,
                    system_prompt=system_prompt,
                    schema_json=schema.model_json_schema(),
                )
                raw = _coerce_stringified_subobjects(raw)
                raw = _unwrap_extraction_envelope(raw)
                validated = schema.model_validate(raw)
                self._cache.put(key, raw)
                return validated
            except Exception as e:
                last_error = e
                if attempt == 0:
                    # Brief pause before retry helps with rate-limit smoothing
                    import time

                    time.sleep(1.5)
                    continue
                raise
        # Should never reach here — the loop either returns or raises
        raise RuntimeError(f"_run_pass exhausted retries: {last_error}")

    def _safe_extract_layout(self, pdf_path: Path):
        """Return DocumentLayout or None if the PDF has no extractable text layer."""
        try:
            return extract_layout(pdf_path)
        except Exception:
            return None

    # ------------------------------------------------------------------
    # Per-pass FHIR converters
    # ------------------------------------------------------------------

    def _assign_encounter_references(self, entries: list[dict[str, Any]]) -> None:
        """Mutate entries in place to add encounter references on encounter-
        scopable resources.

        Strategies (in order of preference per resource):
        1. Single-encounter shortcut: one Encounter in bundle → link everything.
        2. Date + author match: for DocumentReference / Composition, match on
           (date, author display) since notes have explicit authorship.
        3. Date match: fall back to day-precision date match for resources with
           a date field.

        Resources NOT linked: Patient, Practitioner, Organization, Coverage,
        Encounter (self).
        """
        encounters = [
            e["resource"] for e in entries
            if e["resource"].get("resourceType") == "Encounter"
        ]
        if not encounters:
            return

        # Build day-precision date → list of encounters map (multiple encounters
        # can share a date)
        enc_by_date: dict[str, list[dict[str, Any]]] = {}
        for enc in encounters:
            period = enc.get("period") or {}
            start = period.get("start") or ""
            if start:
                day = start[:10]
                enc_by_date.setdefault(day, []).append(enc)

        single_encounter_id = encounters[0]["id"] if len(encounters) == 1 else None

        LINKABLE_VIA_ENCOUNTER_FIELD = {
            "Observation",
            "Condition",
            "MedicationRequest",
            "Procedure",
            "Immunization",
            "AllergyIntolerance",
            "DiagnosticReport",
            "Composition",
        }
        DATE_FIELDS = {
            "Observation": "effectiveDateTime",
            "Condition": "onsetDateTime",
            "MedicationRequest": "authoredOn",
            "Procedure": "performedDateTime",
            "Immunization": "occurrenceDateTime",
            "AllergyIntolerance": "recordedDate",
            "DiagnosticReport": "effectiveDateTime",
            "Composition": "date",
            "DocumentReference": "date",
        }

        def _match_encounter_for(resource: dict[str, Any]) -> str | None:
            """Return matched encounter ID or None."""
            rt = resource.get("resourceType")

            # Strategy 1: single-encounter shortcut
            if single_encounter_id is not None:
                return single_encounter_id

            # Strategy 2: date + author match (DocumentReference / Composition only)
            author_display = None
            if rt in ("DocumentReference", "Composition"):
                authors = resource.get("author") or []
                if authors:
                    author_display = (authors[0].get("display") or "").strip()

            date_field = DATE_FIELDS.get(rt)
            date_value = resource.get(date_field) if date_field else None
            if not date_value:
                return None
            day = date_value[:10]
            candidates = enc_by_date.get(day) or []
            if not candidates:
                return None
            if len(candidates) == 1:
                return candidates[0]["id"]
            # Multiple encounters on the same day — author match if available
            if author_display:
                for c in candidates:
                    participants = c.get("participant") or []
                    for p in participants:
                        individual = (p.get("individual") or {}).get("display") or ""
                        if individual.strip() and individual.strip() in author_display:
                            return c["id"]
                        if author_display in individual.strip():
                            return c["id"]
            # Fallback: first candidate
            return candidates[0]["id"]

        for entry in entries:
            resource = entry["resource"]
            rt = resource.get("resourceType")

            if rt == "DocumentReference":
                # Skip if already linked
                ctx = resource.get("context") or {}
                if ctx.get("encounter"):
                    continue
                matched = _match_encounter_for(resource)
                if matched:
                    resource.setdefault("context", {})
                    resource["context"]["encounter"] = [{"reference": f"Encounter/{matched}"}]
                continue

            if rt in LINKABLE_VIA_ENCOUNTER_FIELD:
                if "encounter" in resource:
                    continue
                matched = _match_encounter_for(resource)
                if matched:
                    resource["encounter"] = {"reference": f"Encounter/{matched}"}
                continue

            # Other resources (Patient, Practitioner, Organization, Coverage,
            # Encounter itself) are not linked.

    def _rewrite_patient_references(self, entries: list[dict[str, Any]]) -> None:
        """If a Patient resource exists in the bundle, rewrite every other
        resource's subject/patient reference to point at the real Patient.id.

        Mutates entries in place. Idempotent: re-running on an already-rewritten
        bundle has no effect.

        No-op if zero or multiple Patient resources are present (multiple is
        rare and ambiguous; we don't pick).
        """
        patients = [
            e["resource"] for e in entries
            if e["resource"].get("resourceType") == "Patient"
        ]
        if len(patients) != 1:
            return  # zero or ambiguous

        target_id = patients[0]["id"]
        target_ref = f"Patient/{target_id}"

        # Resource types that carry a ``subject: Reference(Patient/...)`` field.
        # Per FHIR R4: Observation, Condition, Procedure, MedicationRequest,
        # Encounter, DiagnosticReport, AllergyIntolerance, DocumentReference,
        # Composition (and more).
        SUBJECT_TYPES = {
            "Observation",
            "Condition",
            "MedicationRequest",
            "Encounter",
            "DiagnosticReport",
            "AllergyIntolerance",
            "DocumentReference",
            "Composition",
            "Procedure",
        }

        for entry in entries:
            resource = entry["resource"]
            rt = resource.get("resourceType")

            if rt == "Patient":
                continue  # the patient itself

            # subject-field path
            if rt in SUBJECT_TYPES:
                subj = resource.get("subject")
                if isinstance(subj, dict):
                    ref = subj.get("reference") or ""
                    if ref.startswith("Patient/") and ref != target_ref:
                        subj["reference"] = target_ref

            # Immunization uses ``patient`` (not ``subject``) per _immunization_to_fhir
            if rt == "Immunization":
                pat = resource.get("patient")
                if isinstance(pat, dict):
                    ref = pat.get("reference") or ""
                    if ref.startswith("Patient/") and ref != target_ref:
                        pat["reference"] = target_ref

            # Coverage uses ``beneficiary``
            if rt == "Coverage":
                ben = resource.get("beneficiary")
                if isinstance(ben, dict):
                    ref = ben.get("reference") or ""
                    if ref.startswith("Patient/") and ref != target_ref:
                        ben["reference"] = target_ref

    def _merge_to_bundle(
        self,
        *,
        doc_context: DocumentContext,
        per_pass: dict[str, BaseModel],
        pdf_path: Path,
        layout: Any,  # DocumentLayout | None
    ) -> dict[str, Any]:
        """Convert per-pass outputs into a single FHIR Bundle dict."""
        entries: list[dict[str, Any]] = []
        source_attachment_id = pdf_path.stem
        common_meta_template = self._common_meta_template(doc_context, source_attachment_id)

        # Conditions
        cond_extraction: ConditionExtraction = per_pass.get("conditions") or ConditionExtraction()
        for c in cond_extraction.conditions:
            entries.append({"resource": self._condition_to_fhir(c, common_meta_template, layout)})

        # Medications
        med_extraction: MedicationExtraction = per_pass.get("medications") or MedicationExtraction()
        for m in med_extraction.medications:
            entries.append({"resource": self._medication_to_fhir(m, common_meta_template, layout)})

        # Allergies
        allergy_extraction: AllergyExtraction = per_pass.get("allergies") or AllergyExtraction()
        for a in allergy_extraction.allergies:
            entries.append({"resource": self._allergy_to_fhir(a, common_meta_template, layout)})

        # Immunizations
        imm_extraction: ImmunizationExtraction = per_pass.get("immunizations") or ImmunizationExtraction()
        for i in imm_extraction.immunizations:
            entries.append({"resource": self._immunization_to_fhir(i, common_meta_template, layout)})

        # Lab Observations + LOINC + interpretation + clinical-category post-passes
        obs_extraction: LabObservationExtraction = per_pass.get("lab_observations") or LabObservationExtraction()
        loinc_sources = self._apply_loinc_post_pass(obs_extraction)
        interp_sources = self._apply_interpretation_post_pass(obs_extraction)
        clinical_categories = self._lookup_clinical_categories(obs_extraction)
        for o in obs_extraction.observations:
            entries.append(
                {
                    "resource": self._lab_observation_to_fhir(
                        o,
                        common_meta_template,
                        layout,
                        doc_context,
                        loinc_resolution_source=loinc_sources.get(id(o)),
                        interpretation_source=interp_sources.get(id(o)),
                        clinical_category=clinical_categories.get(id(o)),
                    )
                }
            )

        # Vital Signs
        vs_extraction: VitalSignExtraction = per_pass.get("vital_signs") or VitalSignExtraction()
        for vs in vs_extraction.vital_signs:
            entries.append(
                {"resource": self._vital_sign_to_fhir(vs, common_meta_template, layout, doc_context)}
            )

        # Encounters
        enc_extraction: EncounterExtraction = per_pass.get("encounter") or EncounterExtraction()
        for e in enc_extraction.encounters:
            entries.append(
                {"resource": self._encounter_to_fhir(e, common_meta_template, layout, doc_context)}
            )

        # Practitioners
        prac_extraction: PractitionerExtraction = per_pass.get("practitioner") or PractitionerExtraction()
        for p in prac_extraction.practitioners:
            entries.append(
                {"resource": self._practitioner_to_fhir(p, common_meta_template, layout, doc_context)}
            )

        # Organizations
        org_extraction: OrganizationExtraction = per_pass.get("organization") or OrganizationExtraction()
        for o in org_extraction.organizations:
            entries.append(
                {"resource": self._organization_to_fhir(o, common_meta_template, layout, doc_context)}
            )

        # Clinical Notes — emits paired DocumentReference + Composition per note
        notes_extraction: ClinicalNoteExtraction = per_pass.get("clinical_notes") or ClinicalNoteExtraction()
        for n in notes_extraction.clinical_notes:
            for resource in self._clinical_note_to_fhir_resources(n, common_meta_template, layout, doc_context):
                entries.append({"resource": resource})

        # Patient Demographics
        patient_extraction: PatientExtraction = per_pass.get("patient_demographics") or PatientExtraction()
        for p in patient_extraction.patients:
            entries.append(
                {"resource": self._patient_to_fhir(p, common_meta_template, layout, doc_context)}
            )

        # Coverage
        coverage_extraction: CoverageExtraction = per_pass.get("coverage") or CoverageExtraction()
        for c in coverage_extraction.coverages:
            entries.append(
                {"resource": self._coverage_to_fhir(c, common_meta_template, layout, doc_context)}
            )

        # Post-pass: wire encounter references onto encounter-scopable resources
        self._assign_encounter_references(entries)

        # Post-pass: rewrite Patient/unknown (or any stale patient_id) to the
        # real Patient.id emitted by the patient_demographics pass (T10).
        self._rewrite_patient_references(entries)

        bundle: dict[str, Any] = {
            "resourceType": "Bundle",
            "type": "document",
            "entry": entries,
            "meta": {
                "source": f"extracted://{doc_context.document_type}/{source_attachment_id}",
                "extension": [
                    {
                        "url": "https://ehi-atlas.example/fhir/StructureDefinition/extraction-pipeline",
                        "valueString": MultiPassFHIRPipeline.metadata.name,
                    },
                    {
                        "url": "https://ehi-atlas.example/fhir/StructureDefinition/extraction-prompt-version",
                        "valueString": _PROMPT_VERSION,
                    },
                    {
                        "url": "https://ehi-atlas.example/fhir/StructureDefinition/document-context",
                        "valueString": doc_context.model_dump_json(),
                    },
                ],
            },
        }
        return bundle

    def _common_meta_template(
        self,
        doc_context: DocumentContext,
        source_attachment_id: str,
    ) -> dict[str, Any]:
        """Build a meta-extension template every emitted resource carries."""
        backend_id = f"{self._backend_name}/{self._model or 'default'}"
        return {
            "source": f"extracted://{doc_context.document_type}/{source_attachment_id}",
            "extension": [
                {
                    "url": "https://ehi-atlas.example/fhir/StructureDefinition/extraction-model",
                    "valueString": backend_id,
                },
                {
                    "url": "https://ehi-atlas.example/fhir/StructureDefinition/extraction-prompt-version",
                    "valueString": _PROMPT_VERSION,
                },
                {
                    "url": "https://ehi-atlas.example/fhir/StructureDefinition/source-attachment",
                    "valueString": source_attachment_id,
                },
            ],
        }

    def _bbox_locator_for(
        self,
        anchor_text: str | None,
        page: int | None,
        layout,
    ) -> str | None:
        """Look up a bbox via pdfplumber for a given anchor text + page."""
        if not anchor_text or not layout:
            return None
        try:
            result = find_text_bbox(layout, anchor_text, page=page)
        except Exception:
            return None
        if result is None:
            return None
        bbox = result.to_schemas_bbox()
        return bbox.to_locator_string()

    def _add_bbox_to_meta(
        self,
        meta: dict[str, Any],
        bbox_locator: str | None,
    ) -> dict[str, Any]:
        if not bbox_locator:
            return meta
        meta = {**meta, "extension": [*meta.get("extension", [])]}
        meta["extension"].append(
            {
                "url": "https://ehi-atlas.example/fhir/StructureDefinition/source-locator",
                "valueString": bbox_locator,
            }
        )
        return meta

    def _condition_to_fhir(
        self,
        c: ConditionEntry,
        common_meta: dict[str, Any],
        layout,
    ) -> dict[str, Any]:
        bbox_locator = self._bbox_locator_for(c.source_text or c.display, c.page, layout)
        codings: list[dict[str, Any]] = []
        if c.icd_10_cm_code:
            codings.append({"system": "http://hl7.org/fhir/sid/icd-10-cm", "code": c.icd_10_cm_code})
        if c.snomed_ct_code:
            codings.append({"system": "http://snomed.info/sct", "code": c.snomed_ct_code})
        resource: dict[str, Any] = {
            "resourceType": "Condition",
            "subject": {"reference": f"Patient/{self._patient_id}"},
            "clinicalStatus": {
                "coding": [
                    {
                        "system": "http://terminology.hl7.org/CodeSystem/condition-clinical",
                        "code": c.clinical_status,
                    }
                ]
            },
            "code": {"text": c.display, **({"coding": codings} if codings else {})},
            "meta": self._add_bbox_to_meta(common_meta, bbox_locator),
        }
        if c.onset_date:
            resource["onsetDateTime"] = c.onset_date
        if c.source_text:
            resource["note"] = [{"text": c.source_text}]
        return resource

    def _medication_to_fhir(
        self,
        m: MedicationEntry,
        common_meta: dict[str, Any],
        layout,
    ) -> dict[str, Any]:
        bbox_locator = self._bbox_locator_for(m.display, m.page, layout)
        codings: list[dict[str, Any]] = []
        if m.rxnorm_code:
            codings.append(
                {"system": "http://www.nlm.nih.gov/research/umls/rxnorm", "code": m.rxnorm_code}
            )
        resource: dict[str, Any] = {
            "resourceType": "MedicationRequest",
            "subject": {"reference": f"Patient/{self._patient_id}"},
            "status": m.status,
            "intent": "order",
            "medicationCodeableConcept": {
                "text": m.display,
                **({"coding": codings} if codings else {}),
            },
            "meta": self._add_bbox_to_meta(common_meta, bbox_locator),
        }
        if m.dose or m.frequency:
            instruction: dict[str, Any] = {}
            if m.dose:
                instruction["text"] = (
                    f"{m.dose}" + (f" {m.frequency}" if m.frequency else "")
                )
            elif m.frequency:
                instruction["text"] = m.frequency
            resource["dosageInstruction"] = [instruction]
        return resource

    def _allergy_to_fhir(
        self,
        a: AllergyEntry,
        common_meta: dict[str, Any],
        layout,
    ) -> dict[str, Any]:
        bbox_locator = self._bbox_locator_for(a.display, a.page, layout)
        codings: list[dict[str, Any]] = []
        if a.snomed_ct_code:
            codings.append({"system": "http://snomed.info/sct", "code": a.snomed_ct_code})
        resource: dict[str, Any] = {
            "resourceType": "AllergyIntolerance",
            "patient": {"reference": f"Patient/{self._patient_id}"},
            "code": {"text": a.display, **({"coding": codings} if codings else {})},
            "meta": self._add_bbox_to_meta(common_meta, bbox_locator),
        }
        if a.severity:
            resource["criticality"] = (
                "high" if a.severity == "severe" else "low" if a.severity == "mild" else "unable-to-assess"
            )
        if a.reaction:
            resource["reaction"] = [{"description": a.reaction}]
        return resource

    def _immunization_to_fhir(
        self,
        imm: ImmunizationEntry,
        common_meta: dict[str, Any],
        layout,
    ) -> dict[str, Any]:
        bbox_locator = self._bbox_locator_for(imm.vaccine_display, imm.page, layout)
        codings: list[dict[str, Any]] = []
        if imm.cvx_code:
            codings.append({"system": "http://hl7.org/fhir/sid/cvx", "code": imm.cvx_code})
        resource: dict[str, Any] = {
            "resourceType": "Immunization",
            "patient": {"reference": f"Patient/{self._patient_id}"},
            "status": "completed",
            "vaccineCode": {
                "text": imm.vaccine_display,
                **({"coding": codings} if codings else {}),
            },
            "meta": self._add_bbox_to_meta(common_meta, bbox_locator),
        }
        if imm.administration_date:
            resource["occurrenceDateTime"] = imm.administration_date
        return resource

    def _apply_loinc_post_pass(
        self,
        obs_extraction: "LabObservationExtraction",
    ) -> dict[int, str]:
        """Resolve missing LOINC codes via the curated lookup table.

        For each LabObservationEntry without a loinc_code, calls the matcher.
        On hit, mutates the entry to populate loinc_code. Returns a dict mapping
        ``id(entry) → resolution_source`` where source is one of:

        - ``"manual"`` — extraction emitted a code already (no change)
        - ``"lookup-table-exact"`` / ``"lookup-table-alias"`` / ``"lookup-table-fuzzy"``
            — post-pass resolved via the matcher (match_type appended)
        - ``"unmatched"`` — post-pass tried but found no candidate

        No external calls. Safe to call repeatedly (idempotent for already-coded
        entries).
        """
        # Lazy import to avoid pulling the table at module load time.
        from lib.extract.terminology.loinc_matcher import match_loinc

        sources: dict[int, str] = {}
        for o in obs_extraction.observations:
            if o.loinc_code:
                sources[id(o)] = "manual"
                continue
            unit_hint = o.unit
            result = match_loinc(o.test_name, unit_hint)
            if result is None:
                sources[id(o)] = "unmatched"
                continue
            o.loinc_code = result.code
            sources[id(o)] = f"lookup-table-{result.match_type}"
        return sources

    def _apply_interpretation_post_pass(
        self,
        obs_extraction: "LabObservationExtraction",
    ) -> dict[int, str]:
        """Derive interpretation flag (H / L / N) from value vs reference range.

        For each LabObservationEntry without an extraction-emitted flag but with
        both a numeric value and at least one reference-range bound, compute
        interpretation. Returns a dict mapping ``id(entry) → source``:

        - ``"printed"`` — extraction emitted a flag (no change)
        - ``"computed"`` — post-pass derived flag from numeric comparison
        - ``"unknown"`` — couldn't compute (no value, or no range)

        FHIR v3-ObservationInterpretation codes used:
        - ``"H"`` — high (above reference_range_high)
        - ``"L"`` — low (below reference_range_low)
        - ``"N"`` — normal (within range)

        Mutates entries in place by populating ``o.flag``.
        """
        sources: dict[int, str] = {}
        for o in obs_extraction.observations:
            if o.flag is not None:
                sources[id(o)] = "printed"
                continue
            if o.value_quantity is None:
                sources[id(o)] = "unknown"
                continue
            low = o.reference_range_low
            high = o.reference_range_high
            if low is None and high is None:
                sources[id(o)] = "unknown"
                continue
            value = o.value_quantity
            if low is not None and value < low:
                o.flag = "L"
            elif high is not None and value > high:
                o.flag = "H"
            else:
                o.flag = "N"
            sources[id(o)] = "computed"
        return sources

    def _lookup_clinical_categories(
        self,
        obs_extraction: "LabObservationExtraction",
    ) -> dict[int, str]:
        """For each Observation with a resolved LOINC code, look up the clinical
        category (Metabolic / Kidney / Liver / Blood / Heart / Urine / etc.)
        from the curated reference table.

        Must run AFTER ``_apply_loinc_post_pass`` so codes are populated.
        Returns a dict mapping ``id(entry) → category`` for entries that have
        a category match. Entries without a LOINC code or with a code missing
        from the category table are simply absent from the dict.
        """
        from lib.extract.terminology.loinc_matcher import lookup_clinical_category

        categories: dict[int, str] = {}
        for o in obs_extraction.observations:
            if not o.loinc_code:
                continue
            cat = lookup_clinical_category(o.loinc_code)
            if cat is not None:
                categories[id(o)] = cat
        return categories

    def _lab_observation_to_fhir(
        self,
        o: LabObservationEntry,
        common_meta: dict[str, Any],
        layout,
        doc_context: DocumentContext,
        loinc_resolution_source: str | None = None,
        interpretation_source: str | None = None,
        clinical_category: str | None = None,
    ) -> dict[str, Any]:
        bbox_locator = self._bbox_locator_for(o.test_name, o.page, layout)
        codings: list[dict[str, Any]] = []
        if o.loinc_code:
            codings.append({"system": "http://loinc.org", "code": o.loinc_code})
        meta = self._add_bbox_to_meta(common_meta, bbox_locator)
        if loinc_resolution_source or interpretation_source or clinical_category:
            meta = {**meta, "extension": [*meta.get("extension", [])]}
        if loinc_resolution_source:
            meta["extension"].append(
                {
                    "url": "https://ehi-atlas.example/fhir/StructureDefinition/loinc-resolution",
                    "valueString": loinc_resolution_source,
                }
            )
        if interpretation_source:
            meta["extension"].append(
                {
                    "url": "https://ehi-atlas.example/fhir/StructureDefinition/interpretation-source",
                    "valueString": interpretation_source,
                }
            )
        if clinical_category:
            meta["extension"].append(
                {
                    "url": "https://ehi-atlas.example/fhir/StructureDefinition/clinical-category",
                    "valueString": clinical_category,
                }
            )
        resource: dict[str, Any] = {
            "resourceType": "Observation",
            "subject": {"reference": f"Patient/{self._patient_id}"},
            "status": "final",
            "category": [
                {
                    "coding": [
                        {
                            "system": "http://terminology.hl7.org/CodeSystem/observation-category",
                            "code": "laboratory",
                            "display": "Laboratory",
                        }
                    ]
                }
            ],
            "code": {"text": o.test_name, **({"coding": codings} if codings else {})},
            "meta": meta,
        }
        if o.value_quantity is not None:
            resource["valueQuantity"] = {
                "value": o.value_quantity,
                "unit": o.unit or "",
                "system": "http://unitsofmeasure.org",
                "code": o.unit or "",
            }
        elif o.value_string is not None:
            resource["valueString"] = o.value_string
        if o.reference_range_low is not None or o.reference_range_high is not None:
            rr: dict[str, Any] = {}
            if o.reference_range_low is not None:
                rr["low"] = {"value": o.reference_range_low, "unit": o.unit or ""}
            if o.reference_range_high is not None:
                rr["high"] = {"value": o.reference_range_high, "unit": o.unit or ""}
            resource["referenceRange"] = [rr]
        if o.flag:
            resource["interpretation"] = [
                {
                    "coding": [
                        {
                            "system": "http://terminology.hl7.org/CodeSystem/v3-ObservationInterpretation",
                            "code": o.flag,
                        }
                    ]
                }
            ]
        if o.effective_date:
            resource["effectiveDateTime"] = o.effective_date
        elif doc_context.encounter_date:
            resource["effectiveDateTime"] = doc_context.encounter_date
        return resource

    def _vital_sign_to_fhir(
        self,
        vs: VitalSignEntry,
        common_meta: dict[str, Any],
        layout,
        doc_context: DocumentContext,
    ) -> dict[str, Any]:
        bbox_locator = self._bbox_locator_for(vs.source_text, vs.page, layout)
        loinc_code, loinc_display = _VITAL_LOINC_MAP[vs.vital_type]
        resource: dict[str, Any] = {
            "resourceType": "Observation",
            "subject": {"reference": f"Patient/{self._patient_id}"},
            "status": "final",
            "category": [
                {
                    "coding": [
                        {
                            "system": "http://terminology.hl7.org/CodeSystem/observation-category",
                            "code": "vital-signs",
                            "display": "Vital Signs",
                        }
                    ]
                }
            ],
            "code": {
                "text": loinc_display,
                "coding": [{"system": "http://loinc.org", "code": loinc_code, "display": loinc_display}],
            },
            "meta": self._add_bbox_to_meta(common_meta, bbox_locator),
        }
        if vs.value is not None:
            resource["valueQuantity"] = {
                "value": vs.value,
                "unit": vs.unit or "",
                "system": "http://unitsofmeasure.org",
                "code": vs.unit or "",
            }
        if vs.reference_range_low is not None or vs.reference_range_high is not None:
            rr: dict[str, Any] = {}
            if vs.reference_range_low is not None:
                rr["low"] = {"value": vs.reference_range_low, "unit": vs.unit or ""}
            if vs.reference_range_high is not None:
                rr["high"] = {"value": vs.reference_range_high, "unit": vs.unit or ""}
            resource["referenceRange"] = [rr]
        if vs.flag:
            resource["interpretation"] = [
                {
                    "coding": [
                        {
                            "system": "http://terminology.hl7.org/CodeSystem/v3-ObservationInterpretation",
                            "code": vs.flag,
                        }
                    ]
                }
            ]
        if vs.effective_date:
            resource["effectiveDateTime"] = vs.effective_date
        elif doc_context.encounter_date:
            resource["effectiveDateTime"] = doc_context.encounter_date
        return resource

    def _encounter_to_fhir(
        self,
        e: EncounterEntry,
        common_meta: dict[str, Any],
        layout: Any,
        doc_context: DocumentContext,
    ) -> dict[str, Any]:
        bbox_locator = self._bbox_locator_for(e.source_text, e.page, layout)
        encounter_id = e.encounter_id or _stable_encounter_id(e, doc_context)
        resource: dict[str, Any] = {
            "resourceType": "Encounter",
            "id": encounter_id,
            "subject": {"reference": f"Patient/{self._patient_id}"},
            "status": e.status,
            "meta": self._add_bbox_to_meta(common_meta, bbox_locator),
        }
        if e.class_code:
            resource["class"] = {
                "system": "http://terminology.hl7.org/CodeSystem/v3-ActCode",
                "code": e.class_code,
            }
        if e.type_display:
            resource["type"] = [{"text": e.type_display}]
        if e.period_start or e.period_end:
            period: dict[str, Any] = {}
            if e.period_start:
                period["start"] = e.period_start
            if e.period_end:
                period["end"] = e.period_end
            resource["period"] = period
        if e.participant_display:
            resource["participant"] = [
                {"individual": {"display": e.participant_display}}
            ]
        if e.service_provider_display:
            resource["serviceProvider"] = {"display": e.service_provider_display}
        if e.reason_text:
            resource["reasonCode"] = [{"text": e.reason_text}]
        return resource

    def _practitioner_to_fhir(
        self,
        p: PractitionerEntry,
        common_meta: dict[str, Any],
        layout: Any,
        doc_context: DocumentContext,
    ) -> dict[str, Any]:
        bbox_locator = self._bbox_locator_for(p.source_text, p.page, layout)
        practitioner_id = p.practitioner_id or _stable_practitioner_id(p)
        resource: dict[str, Any] = {
            "resourceType": "Practitioner",
            "id": practitioner_id,
            "active": True,
            "meta": self._add_bbox_to_meta(common_meta, bbox_locator),
        }
        # Identifier (NPI)
        if p.npi:
            resource["identifier"] = [
                {
                    "system": "http://hl7.org/fhir/sid/us-npi",
                    "value": p.npi,
                }
            ]
        # Name
        name_part: dict[str, Any] = {}
        if p.family_name:
            name_part["family"] = p.family_name
        if p.given_names:
            name_part["given"] = list(p.given_names)
        if p.prefix:
            name_part["prefix"] = [p.prefix]
        if p.suffix:
            name_part["suffix"] = [p.suffix]
        if p.display_name and not name_part:
            # Display-only fallback when we can't decompose
            name_part["text"] = p.display_name
        if name_part:
            if p.display_name and "text" not in name_part:
                name_part["text"] = p.display_name
            resource["name"] = [name_part]
        # Telecom
        if p.phone:
            resource["telecom"] = [
                {"system": "phone", "value": p.phone, "use": "work"}
            ]
        # Address
        if p.address_line or p.city or p.state or p.postal_code:
            addr: dict[str, Any] = {}
            if p.address_line:
                addr["line"] = [p.address_line]
            if p.city:
                addr["city"] = p.city
            if p.state:
                addr["state"] = p.state
            if p.postal_code:
                addr["postalCode"] = p.postal_code
            resource["address"] = [addr]
        # Specialty + role go in extensions (since FHIR R4 Practitioner doesn't
        # natively carry specialty — that's PractitionerRole's job; we keep it
        # here for now and migrate to PractitionerRole in a future task).
        extensions = []
        if p.specialty:
            extensions.append(
                {
                    "url": "https://ehi-atlas.example/fhir/StructureDefinition/practitioner-specialty",
                    "valueString": p.specialty,
                }
            )
        if p.role:
            extensions.append(
                {
                    "url": "https://ehi-atlas.example/fhir/StructureDefinition/practitioner-role",
                    "valueString": p.role,
                }
            )
        if extensions:
            resource_extension_list = resource["meta"].get("extension", [])
            resource["meta"] = {**resource["meta"], "extension": [*resource_extension_list, *extensions]}
        return resource

    def _organization_to_fhir(
        self,
        o: OrganizationEntry,
        common_meta: dict[str, Any],
        layout: Any,
        doc_context: DocumentContext,
    ) -> dict[str, Any]:
        bbox_locator = self._bbox_locator_for(o.source_text, o.page, layout)
        organization_id = o.organization_id or _stable_organization_id(o)
        resource: dict[str, Any] = {
            "resourceType": "Organization",
            "id": organization_id,
            "active": True,
            "name": o.name,
            "meta": self._add_bbox_to_meta(common_meta, bbox_locator),
        }
        if o.type_code:
            type_coding: dict[str, Any] = {
                "system": "http://terminology.hl7.org/CodeSystem/organization-type",
                "code": o.type_code,
            }
            type_entry: dict[str, Any] = {"coding": [type_coding]}
            if o.type_display:
                type_entry["text"] = o.type_display
            resource["type"] = [type_entry]
        elif o.type_display:
            # No code, but we have a free-text type
            resource["type"] = [{"text": o.type_display}]
        # Telecom
        telecom = []
        if o.phone:
            telecom.append({"system": "phone", "value": o.phone, "use": "work"})
        if o.fax:
            telecom.append({"system": "fax", "value": o.fax, "use": "work"})
        if telecom:
            resource["telecom"] = telecom
        # Address
        if o.address_line or o.city or o.state or o.postal_code:
            addr: dict[str, Any] = {}
            if o.address_line:
                addr["line"] = [o.address_line]
            if o.city:
                addr["city"] = o.city
            if o.state:
                addr["state"] = o.state
            if o.postal_code:
                addr["postalCode"] = o.postal_code
            resource["address"] = [addr]
        return resource

    def _clinical_note_to_fhir_resources(
        self,
        n: ClinicalNoteEntry,
        common_meta: dict[str, Any],
        layout: Any,
        doc_context: DocumentContext,
    ) -> list[dict[str, Any]]:
        """Returns a list of TWO FHIR resources: a DocumentReference (narrative
        container) and a Composition (sectioned structure). Both are linked
        via shared identifier."""
        import base64

        bbox_locator = self._bbox_locator_for(n.source_text, n.page_start, layout)
        note_id = n.note_id or _stable_clinical_note_id(n, doc_context)
        base_meta = self._add_bbox_to_meta(common_meta, bbox_locator)

        note_date = n.encounter_date or doc_context.encounter_date

        # Build joined narrative for DocumentReference attachment
        full_text_parts: list[str] = []
        if n.title:
            full_text_parts.append(n.title)
        for section in n.sections:
            full_text_parts.append(f"\n\n{section.title}\n{section.narrative_text}")
        full_text = "\n".join(full_text_parts).strip()

        # Type coding for both resources
        if n.note_type_loinc:
            type_coding = {
                "system": "http://loinc.org",
                "code": n.note_type_loinc,
                "display": n.note_type.replace("-", " ").title(),
            }
        else:
            # Default mappings if model didn't emit a code
            DEFAULT_TYPE_LOINC: dict[str, tuple[str, str]] = {
                "progress-note": ("11506-3", "Progress note"),
                "consult-note": ("11488-4", "Consultation note"),
                "discharge-summary": ("18842-5", "Discharge summary"),
                "procedure-note": ("28570-0", "Procedure note"),
                "history-and-physical": ("34117-2", "History and Physical"),
                "patient-education": ("11506-3", "Progress note"),  # closest
                "telephone-encounter": ("28615-3", "Telephone encounter note"),
                "other": ("11506-3", "Progress note"),
            }
            code, display = DEFAULT_TYPE_LOINC[n.note_type]
            type_coding = {"system": "http://loinc.org", "code": code, "display": display}

        # 1. DocumentReference — narrative container
        encoded = base64.b64encode(full_text.encode("utf-8")).decode("ascii") if full_text else ""
        doc_ref: dict[str, Any] = {
            "resourceType": "DocumentReference",
            "id": f"docref-{note_id}",
            "status": "current",
            "type": {"coding": [type_coding], "text": n.title or n.note_type},
            "subject": {"reference": f"Patient/{self._patient_id}"},
            "content": [
                {
                    "attachment": {
                        "contentType": "text/plain",
                        "data": encoded,
                        **({"title": n.title} if n.title else {}),
                    }
                }
            ],
            "meta": base_meta,
        }
        if note_date:
            doc_ref["date"] = note_date
        if n.author_name:
            doc_ref["author"] = [{"display": n.author_name + (f", {n.author_role}" if n.author_role else "")}]

        # 2. Composition — sectioned structure
        composition: dict[str, Any] = {
            "resourceType": "Composition",
            "id": f"comp-{note_id}",
            "status": "final",
            "type": {"coding": [type_coding], "text": n.title or n.note_type},
            "subject": {"reference": f"Patient/{self._patient_id}"},
            "title": n.title or "Clinical Note",
            "meta": base_meta,
        }
        if note_date:
            composition["date"] = note_date
        if n.author_name:
            composition["author"] = [{"display": n.author_name + (f", {n.author_role}" if n.author_role else "")}]
        sections_out: list[dict[str, Any]] = []
        for section in n.sections:
            section_dict: dict[str, Any] = {
                "title": section.title,
                "text": {
                    "status": "additional",
                    "div": f'<div xmlns="http://www.w3.org/1999/xhtml">{section.narrative_text}</div>',
                },
            }
            if section.loinc_code:
                section_dict["code"] = {
                    "coding": [
                        {
                            "system": "http://loinc.org",
                            "code": section.loinc_code,
                        }
                    ]
                }
            sections_out.append(section_dict)
        if sections_out:
            composition["section"] = sections_out

        return [doc_ref, composition]

    def _patient_to_fhir(
        self,
        p: PatientEntry,
        common_meta: dict[str, Any],
        layout: Any,
        doc_context: DocumentContext,
    ) -> dict[str, Any]:
        bbox_locator = self._bbox_locator_for(p.source_text, p.page, layout)
        patient_id = _stable_patient_id(p, doc_context)
        base_meta = self._add_bbox_to_meta(common_meta, bbox_locator)
        resource: dict[str, Any] = {
            "resourceType": "Patient",
            "id": patient_id,
            "active": True,
            "meta": base_meta,
        }

        # US Core extensions
        extensions: list[dict[str, Any]] = []
        if p.race_omb_code or p.race_text:
            race_ext_inner: list[dict[str, Any]] = []
            if p.race_omb_code:
                race_ext_inner.append({
                    "url": "ombCategory",
                    "valueCoding": {
                        "system": "urn:oid:2.16.840.1.113883.6.238",
                        "code": p.race_omb_code,
                        "display": _OMB_RACE_DISPLAY.get(p.race_omb_code, p.race_text or ""),
                    },
                })
            if p.race_text:
                race_ext_inner.append({"url": "text", "valueString": p.race_text})
            extensions.append({
                "url": "http://hl7.org/fhir/us/core/StructureDefinition/us-core-race",
                "extension": race_ext_inner,
            })
        if p.ethnicity_omb_code or p.ethnicity_text:
            eth_ext_inner: list[dict[str, Any]] = []
            if p.ethnicity_omb_code:
                eth_ext_inner.append({
                    "url": "ombCategory",
                    "valueCoding": {
                        "system": "urn:oid:2.16.840.1.113883.6.238",
                        "code": p.ethnicity_omb_code,
                        "display": _OMB_ETHNICITY_DISPLAY.get(p.ethnicity_omb_code, p.ethnicity_text or ""),
                    },
                })
            if p.ethnicity_text:
                eth_ext_inner.append({"url": "text", "valueString": p.ethnicity_text})
            extensions.append({
                "url": "http://hl7.org/fhir/us/core/StructureDefinition/us-core-ethnicity",
                "extension": eth_ext_inner,
            })
        if p.birth_sex:
            extensions.append({
                "url": "http://hl7.org/fhir/us/core/StructureDefinition/us-core-birthsex",
                "valueCode": p.birth_sex,
            })
        if extensions:
            resource["extension"] = extensions

        # Identifier (MRN)
        if p.patient_id:
            resource["identifier"] = [
                {
                    "type": {
                        "coding": [
                            {
                                "system": "http://terminology.hl7.org/CodeSystem/v2-0203",
                                "code": "MR",
                                "display": "Medical Record Number",
                            }
                        ]
                    },
                    "value": p.patient_id,
                }
            ]

        # Name
        name_part: dict[str, Any] = {}
        if p.family_name:
            name_part["family"] = p.family_name
        if p.given_names:
            name_part["given"] = list(p.given_names)
        if p.prefix:
            name_part["prefix"] = [p.prefix]
        if p.suffix:
            name_part["suffix"] = [p.suffix]
        if name_part:
            resource["name"] = [name_part]
            if p.nickname:
                resource["name"].append({"use": "usual", "given": [p.nickname]})

        if p.gender:
            resource["gender"] = p.gender
        if p.birth_date:
            resource["birthDate"] = p.birth_date
        if p.deceased_date:
            resource["deceasedDateTime"] = p.deceased_date

        # Address
        if p.address_line or p.city or p.state or p.postal_code:
            addr: dict[str, Any] = {"use": "home"}
            if p.address_line:
                addr["line"] = [p.address_line]
            if p.city:
                addr["city"] = p.city
            if p.state:
                addr["state"] = p.state
            if p.postal_code:
                addr["postalCode"] = p.postal_code
            if p.country:
                addr["country"] = p.country
            resource["address"] = [addr]

        # Telecom
        telecom: list[dict[str, Any]] = []
        if p.phone_home:
            telecom.append({"system": "phone", "value": p.phone_home, "use": "home"})
        if p.phone_mobile:
            telecom.append({"system": "phone", "value": p.phone_mobile, "use": "mobile"})
        if p.phone_work:
            telecom.append({"system": "phone", "value": p.phone_work, "use": "work"})
        if p.email:
            telecom.append({"system": "email", "value": p.email})
        if telecom:
            resource["telecom"] = telecom

        # Communication / language
        if p.language:
            resource["communication"] = [
                {"language": {"text": p.language}, "preferred": True}
            ]

        # Marital status
        if p.marital_status:
            resource["maritalStatus"] = {"text": p.marital_status}

        return resource

    def _coverage_to_fhir(
        self,
        c: CoverageEntry,
        common_meta: dict[str, Any],
        layout: Any,
        doc_context: DocumentContext,
    ) -> dict[str, Any]:
        bbox_locator = self._bbox_locator_for(c.source_text, c.page, layout)
        coverage_id = c.coverage_id or _stable_coverage_id(c)
        base_meta = self._add_bbox_to_meta(common_meta, bbox_locator)
        resource: dict[str, Any] = {
            "resourceType": "Coverage",
            "id": coverage_id,
            "status": c.status,
            "beneficiary": {"reference": f"Patient/{self._patient_id}"},
            "meta": base_meta,
        }
        # Type (plan type)
        if c.plan_type:
            resource["type"] = {
                "coding": [
                    {
                        "system": "http://terminology.hl7.org/CodeSystem/v3-ActCode",
                        "code": c.plan_type.upper() if c.plan_type.upper() in ("HMO", "PPO", "EPO", "POS") else "OTH",
                        "display": c.plan_type,
                    }
                ],
                "text": c.plan_type,
            }
        # Identifiers (member ID, group ID)
        identifiers = []
        if c.member_id:
            identifiers.append({"type": {"text": "Member ID"}, "value": c.member_id})
        if c.group_id:
            identifiers.append({"type": {"text": "Group ID"}, "value": c.group_id})
        if c.subscriber_id and c.subscriber_id != c.member_id:
            identifiers.append({"type": {"text": "Subscriber ID"}, "value": c.subscriber_id})
        if identifiers:
            resource["identifier"] = identifiers
        # subscriberId convenience field
        if c.subscriber_id:
            resource["subscriberId"] = c.subscriber_id
        # Payor (display-only reference; org resolution is T14's job)
        payor_entries = []
        if c.payor_name:
            payor_entries.append({"display": c.payor_name})
        if payor_entries:
            resource["payor"] = payor_entries
        # Relationship
        if c.relationship_to_subscriber:
            resource["relationship"] = {
                "coding": [
                    {
                        "system": "http://terminology.hl7.org/CodeSystem/subscriber-relationship",
                        "code": c.relationship_to_subscriber,
                    }
                ]
            }
        # Period
        if c.effective_period_start or c.effective_period_end:
            period: dict[str, Any] = {}
            if c.effective_period_start:
                period["start"] = c.effective_period_start
            if c.effective_period_end:
                period["end"] = c.effective_period_end
            resource["period"] = period
        # class[] for plan name + group
        classes = []
        if c.plan_name:
            classes.append({
                "type": {"coding": [{"system": "http://terminology.hl7.org/CodeSystem/coverage-class", "code": "plan"}]},
                "value": c.plan_name,
                "name": c.plan_name,
            })
        if c.group_id:
            classes.append({
                "type": {"coding": [{"system": "http://terminology.hl7.org/CodeSystem/coverage-class", "code": "group"}]},
                "value": c.group_id,
            })
        if classes:
            resource["class"] = classes
        return resource


# ---------------------------------------------------------------------------
# Mixed-backend variant — Move B experiment
# ---------------------------------------------------------------------------


@register
class MultiPassFHIRGemmaTabularPipeline(MultiPassFHIRPipeline):
    """multipass-fhir variant: Claude for narrative passes, Gemma 4 31B for
    tabular passes (medications, immunizations, lab observations).

    Hypothesis from PDF-PROCESSOR.md decision 4: tabular extraction is
    Gemma's strength. If F1 holds while cost drops 50–70%, this becomes
    the new default.
    """

    metadata = PipelineMetadata(
        name="multipass-fhir-gemma-tabular",
        description=(
            "Same as multipass-fhir, but tabular passes (medications, "
            "immunizations, lab observations) run on Gemma 4 31B while "
            "narrative passes (conditions, allergies, document_context) "
            "stay on Claude. Cost-optimization experiment per decision 4."
        ),
        architecture="multipass-vision",
        primary_backends=["anthropic", "gemma-google-ai-studio"],
        estimated_cost_per_pdf_usd=0.12,  # rough — narrative passes Claude, tabular Gemma
    )

    def __init__(
        self,
        *,
        patient_id: str = "unknown",
        max_workers: int = 6,
    ) -> None:
        super().__init__(
            patient_id=patient_id,
            backend_name="anthropic",
            model=None,  # default Claude Opus
            max_workers=max_workers,
            pass_overrides={
                "medications": {
                    "backend": "gemma-google-ai-studio",
                    "model": "gemma-4-31b-it",
                },
                "immunizations": {
                    "backend": "gemma-google-ai-studio",
                    "model": "gemma-4-31b-it",
                },
                "lab_observations": {
                    "backend": "gemma-google-ai-studio",
                    "model": "gemma-4-31b-it",
                },
            },
        )
