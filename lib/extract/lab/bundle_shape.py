"""Bundle-shape scoring — structural-quality assertions on a FHIR Bundle.

Captures things F1 doesn't:
  - Patient uniqueness (should be exactly 1 for single-patient PDFs)
  - Encounter linkage rate (fraction of encounter-scopable resources
    with encounter ref)
  - Practitioner NPI coverage (canonical US identifier)
  - LOINC resolution rate (post-pass effectiveness)
  - Duplicate NPIs (same practitioner extracted twice)
  - Orphaned subject/encounter references (pointing at nonexistent ids)

Used by LAB-T03's run command to write bundle_shape.json into each
run directory; LAB-T04 reads it for compare; LAB-T06 reports it.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict, field
from typing import Any


# Resources whose `subject` should reference Patient
_SUBJECT_TYPES = {
    "Observation", "Condition", "MedicationRequest", "Encounter",
    "DiagnosticReport", "AllergyIntolerance", "DocumentReference",
    "Composition", "Procedure",
}
# Resources whose `patient` (not `subject`) should reference Patient
_PATIENT_FIELD_TYPES = {"Immunization"}
# Resources whose `beneficiary` should reference Patient
_BENEFICIARY_TYPES = {"Coverage"}
# Resources that should carry an `encounter` reference when an encounter exists
_ENCOUNTER_LINKABLE = {
    "Observation", "Condition", "MedicationRequest", "Procedure",
    "Immunization", "AllergyIntolerance", "DiagnosticReport", "Composition",
}


@dataclass(frozen=True)
class BundleShapeReport:
    # Counts
    total_entries: int
    patient_count: int
    encounter_count: int
    practitioner_count: int
    organization_count: int
    document_reference_count: int
    composition_count: int

    # Linkage / coverage rates (0.0–1.0)
    encounter_link_rate: float           # fraction of _ENCOUNTER_LINKABLE resources with encounter ref
    patient_link_rate: float             # fraction of subject/patient/beneficiary refs that resolve to the actual Patient.id
    practitioner_npi_rate: float         # fraction of Practitioners with NPI identifier
    loinc_resolution_rate: float         # fraction of Observations with at least one LOINC coding entry
    interpretation_rate: float           # fraction of numeric Observations (with valueQuantity + referenceRange) that have an interpretation
    clinical_category_rate: float        # fraction of Observations with the clinical-category extension
    note_encounter_link_rate: float      # fraction of DocumentReferences with context.encounter set

    # Structural anomalies (lists of offenders)
    duplicate_practitioner_npis: list[str] = field(default_factory=list)
    orphaned_subject_references: list[str] = field(default_factory=list)
    orphaned_encounter_references: list[str] = field(default_factory=list)
    multiple_patients_warning: bool = False  # patient_count > 1


def score_bundle_shape(bundle: dict) -> BundleShapeReport:
    """Score a FHIR Bundle on structural quality. No mutation."""
    entries = bundle.get("entry", []) or []
    resources = [e.get("resource", {}) for e in entries]

    # Index by id and type
    patients = [r for r in resources if r.get("resourceType") == "Patient"]
    encounters = [r for r in resources if r.get("resourceType") == "Encounter"]
    practitioners = [r for r in resources if r.get("resourceType") == "Practitioner"]
    organizations = [r for r in resources if r.get("resourceType") == "Organization"]
    document_references = [r for r in resources if r.get("resourceType") == "DocumentReference"]
    compositions = [r for r in resources if r.get("resourceType") == "Composition"]
    observations = [r for r in resources if r.get("resourceType") == "Observation"]

    patient_ids = {r.get("id") for r in patients if r.get("id")}
    encounter_ids = {r.get("id") for r in encounters if r.get("id")}

    # Encounter linkage
    encounter_linkable = [r for r in resources if r.get("resourceType") in _ENCOUNTER_LINKABLE]
    encounter_link_count = sum(
        1 for r in encounter_linkable
        if _has_encounter_ref(r)
    )
    encounter_link_rate = encounter_link_count / len(encounter_linkable) if encounter_linkable else 0.0

    # Patient linkage
    subject_bearing = [
        r for r in resources
        if r.get("resourceType") in (_SUBJECT_TYPES | _PATIENT_FIELD_TYPES | _BENEFICIARY_TYPES)
    ]
    if subject_bearing and patient_ids:
        valid_links = sum(
            1 for r in subject_bearing
            if _patient_ref_matches(r, patient_ids)
        )
        patient_link_rate = valid_links / len(subject_bearing)
    else:
        patient_link_rate = 0.0

    # Practitioner NPI rate
    if practitioners:
        with_npi = sum(1 for p in practitioners if _practitioner_has_npi(p))
        practitioner_npi_rate = with_npi / len(practitioners)
    else:
        practitioner_npi_rate = 0.0

    # LOINC resolution rate
    if observations:
        with_loinc = sum(
            1 for o in observations
            if any("loinc" in (c.get("system", "") or "").lower()
                   for c in (o.get("code", {}).get("coding") or []))
        )
        loinc_resolution_rate = with_loinc / len(observations)
    else:
        loinc_resolution_rate = 0.0

    # Interpretation rate (only count Observations with both value and ref range)
    interp_eligible = [
        o for o in observations
        if "valueQuantity" in o and o.get("referenceRange")
    ]
    if interp_eligible:
        with_interp = sum(1 for o in interp_eligible if o.get("interpretation"))
        interpretation_rate = with_interp / len(interp_eligible)
    else:
        interpretation_rate = 0.0

    # Clinical-category rate
    if observations:
        with_cat = sum(
            1 for o in observations
            if any("clinical-category" in (e.get("url") or "")
                   for e in (o.get("meta", {}).get("extension") or []))
        )
        clinical_category_rate = with_cat / len(observations)
    else:
        clinical_category_rate = 0.0

    # Note -> encounter link rate
    if document_references:
        with_enc = sum(
            1 for d in document_references
            if d.get("context", {}).get("encounter")
        )
        note_encounter_link_rate = with_enc / len(document_references)
    else:
        note_encounter_link_rate = 0.0

    # Duplicate NPIs
    npi_counts: dict[str, int] = {}
    for p in practitioners:
        for ident in p.get("identifier") or []:
            if "npi" in (ident.get("system", "") or "").lower():
                npi = ident.get("value")
                if npi:
                    npi_counts[npi] = npi_counts.get(npi, 0) + 1
    duplicate_npis = [npi for npi, count in npi_counts.items() if count > 1]

    # Orphaned subject references
    orphaned_subjects: list[str] = []
    for r in subject_bearing:
        ref_value = _extract_patient_ref(r)
        if ref_value and ref_value.startswith("Patient/"):
            target_id = ref_value.split("/", 1)[1]
            if target_id not in patient_ids and target_id != "unknown":
                orphaned_subjects.append(ref_value)

    # Orphaned encounter references
    orphaned_encounters: list[str] = []
    for r in encounter_linkable:
        enc_ref = (r.get("encounter") or {}).get("reference")
        if not enc_ref and r.get("resourceType") == "DocumentReference":
            ctx = r.get("context") or {}
            enc_list = ctx.get("encounter") or []
            if enc_list:
                enc_ref = enc_list[0].get("reference")
        if enc_ref and enc_ref.startswith("Encounter/"):
            target_id = enc_ref.split("/", 1)[1]
            if target_id not in encounter_ids:
                orphaned_encounters.append(enc_ref)

    return BundleShapeReport(
        total_entries=len(entries),
        patient_count=len(patients),
        encounter_count=len(encounters),
        practitioner_count=len(practitioners),
        organization_count=len(organizations),
        document_reference_count=len(document_references),
        composition_count=len(compositions),
        encounter_link_rate=round(encounter_link_rate, 4),
        patient_link_rate=round(patient_link_rate, 4),
        practitioner_npi_rate=round(practitioner_npi_rate, 4),
        loinc_resolution_rate=round(loinc_resolution_rate, 4),
        interpretation_rate=round(interpretation_rate, 4),
        clinical_category_rate=round(clinical_category_rate, 4),
        note_encounter_link_rate=round(note_encounter_link_rate, 4),
        duplicate_practitioner_npis=duplicate_npis,
        orphaned_subject_references=orphaned_subjects,
        orphaned_encounter_references=orphaned_encounters,
        multiple_patients_warning=len(patients) > 1,
    )


def _has_encounter_ref(resource: dict) -> bool:
    if (resource.get("encounter") or {}).get("reference"):
        return True
    # DocumentReference uses context.encounter[]
    if resource.get("resourceType") == "DocumentReference":
        ctx = resource.get("context") or {}
        return bool(ctx.get("encounter"))
    return False


def _extract_patient_ref(resource: dict) -> str | None:
    rt = resource.get("resourceType")
    if rt in _SUBJECT_TYPES:
        return (resource.get("subject") or {}).get("reference")
    if rt in _PATIENT_FIELD_TYPES:
        return (resource.get("patient") or {}).get("reference")
    if rt in _BENEFICIARY_TYPES:
        return (resource.get("beneficiary") or {}).get("reference")
    return None


def _patient_ref_matches(resource: dict, patient_ids: set[str]) -> bool:
    ref_value = _extract_patient_ref(resource)
    if not ref_value or not ref_value.startswith("Patient/"):
        return False
    target_id = ref_value.split("/", 1)[1]
    return target_id in patient_ids


def _practitioner_has_npi(practitioner: dict) -> bool:
    for ident in practitioner.get("identifier") or []:
        if "npi" in (ident.get("system", "") or "").lower():
            if ident.get("value"):
                return True
    return False
