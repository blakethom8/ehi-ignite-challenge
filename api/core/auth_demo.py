"""Demo patient catalogue + alias resolution.

Holds the curated demo patient roster shipped with the application and the
small set of helpers that map alias ids (``demo-high-risk``, ``demo-aggregate-icu``,
…) onto the real Synthea / aggregate patient ids.

Imported by :mod:`api.core.auth_session` (for session-level demo allow-listing)
and re-exported through the :mod:`api.core.auth` facade.
"""

from __future__ import annotations

from dataclasses import dataclass

from fastapi import HTTPException

from api.auth_models import DemoPatientMetadata, DemoPatientOption


@dataclass(frozen=True)
class DemoPatientConfig:
    alias_id: str
    name: str
    actual_patient_id: str
    description: str
    short_journey: str
    care_setting: str
    clinical_focus: str
    complexity: str
    tags: tuple[str, ...]

    def to_option(self) -> DemoPatientOption:
        return DemoPatientOption(
            id=self.alias_id,
            name=self.name,
            description=self.description,
            short_journey=self.short_journey,
            metadata=DemoPatientMetadata(
                care_setting=self.care_setting,
                clinical_focus=self.clinical_focus,
                complexity=self.complexity,
                tags=list(self.tags),
            ),
        )


DEMO_PATIENTS: tuple[DemoPatientConfig, ...] = (
    DemoPatientConfig(
        alias_id="demo-high-risk",
        name="Demo Patient - Surgical Review",
        actual_patient_id="81e1b4cb-6817-4bdc-97cd-c1f3ac960345",
        description="Curated pre-op chart with cardiology, anticoagulation, heart-failure, stroke, and oncology context in one record.",
        short_journey="A 93-year-old man with coronary disease, atrial fibrillation, CHF, prior stroke, and prostate cancer who needs a fast surgical-safety review.",
        care_setting="Pre-op surgical review",
        clinical_focus="Medication safety and longitudinal risk review",
        complexity="high",
        tags=("FHIR-only", "Polypharmacy", "Peri-op", "Risk flags"),
    ),
    DemoPatientConfig(
        alias_id="demo-trial-match",
        name="Demo Patient - Trial Match",
        actual_patient_id="8143897c-e650-4e55-b08d-8306e2f424bb",
        description="Curated oncology referral chart with active cancer treatment, chronic disease burden, and trial-screening style review needs.",
        short_journey="A 95-year-old man with prostate neoplasm, CKD, coronary disease, diabetes, and active oncology treatment for referral and eligibility review.",
        care_setting="Specialty referral review",
        clinical_focus="Trial matching and evidence-backed referral prep",
        complexity="medium",
        tags=("FHIR-only", "Oncology", "Referral", "Trial matching"),
    ),
    DemoPatientConfig(
        alias_id="demo-med-access",
        name="Demo Patient - Medication Access",
        actual_patient_id="eec393be-2569-46db-a974-33d7c853d690",
        description="Curated longitudinal chart for polypharmacy, diabetes, CKD, chronic pain, and treatment-continuity review.",
        short_journey="A 91-year-old woman with diabetes, CKD, neuropathy, retinopathy, chronic pain, stroke history, and insulin plus oncology medications.",
        care_setting="Care coordination",
        clinical_focus="Medication access and ongoing treatment management",
        complexity="medium",
        tags=("FHIR-only", "Longitudinal", "Coverage", "Adherence"),
    ),
    # ─── Multi-source aggregation demos ──────────────────────────────────────
    # These four personas pair a structured FHIR baseline with a small fan of
    # pre-staged synthetic source documents (PDF discharge summaries, C-CDA
    # outside-provider exports, supplemental FHIR feeds from specialty clinics
    # / patient apps / device telemetry / home monitoring). They exist to
    # demonstrate the data-aggregation feature on real multi-source evidence
    # — each one ships with deliberate cross-source inconsistencies that the
    # harmonization pipeline is supposed to surface.
    # All four aliases share the demo-aggregate-* prefix so they can be
    # filtered or sunset as a group without touching the original Synthea
    # demos above.
    DemoPatientConfig(
        alias_id="demo-aggregate-icu",
        name="Demo Patient - Critical Care Aggregation",
        actual_patient_id="cb70e6ae-90b1-562b-8ab0-467c65d18d5e",
        description="Real (de-identified) MIMIC-IV ICU survivor — assembled from a structured FHIR baseline plus a discharge summary, anticoag clinic letter, pacemaker interrogation, sleep study, pre-op intake, outside oncology C-CDA, and Dana-Farber FHIR feed.",
        short_journey="A male in his 60s with CLL on active treatment, paroxysmal AFib with a Medtronic pacemaker, T2DM on insulin, OSA, and a prior TIA — chart assembled from seven distinct sources for a peri-operative review.",
        care_setting="Peri-operative / multi-source intake",
        clinical_focus="Multi-source data aggregation and reconciliation",
        complexity="high",
        tags=("Multi-source", "Real ICU data", "Polypharmacy", "Inconsistencies"),
    ),
    DemoPatientConfig(
        alias_id="demo-aggregate-oncology",
        name="Demo Patient - Oncology Aggregation",
        actual_patient_id="cancer-patient-jenny-m",
        description="Structured oncology chart (HL7 mCODE Jenny M) paired with a screening mammogram, biopsy pathology report, tumor board summary, genetic counseling letter, outside community-gynecologist C-CDA, and 8 weeks of patient-generated symptom-tracker FHIR data.",
        short_journey="A 55-year-old woman newly diagnosed with invasive ductal carcinoma — workup assembled from imaging, pathology, multidisciplinary review, genetic counseling, outside historical records, and a chemo symptom-tracker app.",
        care_setting="Specialty oncology workup",
        clinical_focus="Multi-source oncology assembly with mCODE staging",
        complexity="medium",
        tags=("Multi-source", "mCODE", "PGHD", "Family history"),
    ),
    DemoPatientConfig(
        alias_id="demo-aggregate-cardiac",
        name="Demo Patient - Cardiac Multimodal Aggregation",
        actual_patient_id="fec6d99f-1cfd-f397-e740-e3952410ea2a",
        description="Synthea Coherent CVD patient — a multimodal chart assembled from a 35 MB FHIR baseline, a cardiac MRI DICOM, simulated genomics, plus a cardiology post-arrest consult, stroke discharge summary, prostate pathology, oncology chemo plan, and Medtronic CareLink pacemaker telemetry FHIR feed.",
        short_journey="An elderly man, cardiac-arrest survivor with prior stroke and active prostate cancer on combined ADT + docetaxel — chart spans structured FHIR, imaging, genomics, and device telemetry.",
        care_setting="Complex cardiology / oncology coordination",
        clinical_focus="Multimodal aggregation across FHIR, imaging, genomics, and device feeds",
        complexity="high",
        tags=("Multi-source", "Multimodal", "DICOM", "Device telemetry"),
    ),
    DemoPatientConfig(
        alias_id="demo-aggregate-polypharmacy",
        name="Demo Patient - Polypharmacy Aggregation",
        actual_patient_id="b0f49c80-b59b-4df6-8292-40ce8b8f8612",
        description="Synthea polypharmacy patient — structured FHIR baseline plus a recent discharge summary, outpatient warfarin clinic letter, neurology dementia consult, colonoscopy + pathology, stale outside-PCP C-CDA, and 60 days of home-monitoring FHIR data from a connected BP cuff and glucometer.",
        short_journey="A 99-year-old woman with atrial fibrillation on warfarin, Alzheimer's on galantamine, and colorectal cancer on FOLFOX — chart assembled across hospital, anticoag clinic, neurology, GI, PCP, and home-monitoring sources.",
        care_setting="Geriatric polypharmacy / care coordination",
        clinical_focus="Cross-source medication safety and home-data harmonization",
        complexity="high",
        tags=("Multi-source", "Polypharmacy", "Home monitoring", "Stale outside data"),
    ),
)
DEMO_PATIENT_BY_ALIAS = {item.alias_id: item for item in DEMO_PATIENTS}


def demo_patient_options() -> list[DemoPatientOption]:
    return [item.to_option() for item in DEMO_PATIENTS]


def demo_patient_option(patient_id: str | None) -> DemoPatientOption | None:
    if patient_id is None:
        return None
    item = DEMO_PATIENT_BY_ALIAS.get(patient_id)
    return item.to_option() if item is not None else None


def is_demo_alias(patient_id: str) -> bool:
    return patient_id in DEMO_PATIENT_BY_ALIAS


def resolve_demo_patient_alias(patient_id: str) -> str:
    item = DEMO_PATIENT_BY_ALIAS.get(patient_id)
    if item is None:
        raise HTTPException(status_code=403, detail="Demo sessions can only access approved demo patients.")
    return item.actual_patient_id


def demo_patient_label(patient_id: str) -> str:
    item = DEMO_PATIENT_BY_ALIAS.get(patient_id)
    return item.name if item is not None else patient_id
