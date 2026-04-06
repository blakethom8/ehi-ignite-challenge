"""
/api/corpus — corpus-level statistics across all patients.
"""

from __future__ import annotations

from collections import defaultdict

from fastapi import APIRouter

from api.core.loader import list_patient_files, load_patient, patient_id_from_path
from api.models import CorpusStats, FieldCoverageItem, FieldCoverageResponse

router = APIRouter(prefix="/corpus", tags=["corpus"])


@router.get("/stats", response_model=CorpusStats)
def corpus_stats() -> CorpusStats:
    """
    Aggregate statistics across the entire patient corpus.

    NOTE: This endpoint loads all patient bundles on first call. For a corpus
    of ~1,180 patients this will be slow (~30–60 s) the first time. Subsequent
    calls are fast because load_patient() uses an LRU cache. Consider calling
    this endpoint at startup or after a warm-up delay in production.
    """
    files = list_patient_files()

    gender_breakdown: dict[str, int] = defaultdict(int)
    complexity_tier_breakdown: dict[str, int] = defaultdict(int)
    total_age: float = 0.0
    total_encounters: int = 0
    total_resources: int = 0
    total_active_conditions: int = 0
    total_active_meds: int = 0
    loaded_count: int = 0

    for path in files:
        patient_id = patient_id_from_path(path)
        result = load_patient(patient_id)
        if result is None:
            continue

        _, stats = result
        loaded_count += 1

        gender_breakdown[stats.gender or "unknown"] += 1
        complexity_tier_breakdown[stats.complexity_tier] += 1
        total_age += stats.age_years
        total_encounters += stats.encounter_count
        total_resources += stats.total_resources
        total_active_conditions += stats.active_condition_count
        total_active_meds += stats.active_med_count

    n = loaded_count or 1  # avoid division by zero

    return CorpusStats(
        total_patients=loaded_count,
        gender_breakdown=dict(gender_breakdown),
        complexity_tier_breakdown=dict(complexity_tier_breakdown),
        avg_age=round(total_age / n, 2),
        avg_encounter_count=round(total_encounters / n, 2),
        avg_active_condition_count=round(total_active_conditions / n, 2),
        avg_active_med_count=round(total_active_meds / n, 2),
        total_encounters=total_encounters,
        total_resources=total_resources,
    )


def _coverage_label(pct: float) -> str:
    if pct >= 95:
        return "Always"
    if pct >= 70:
        return "Usually"
    if pct >= 30:
        return "Sometimes"
    return "Rarely"


@router.get("/field-coverage", response_model=FieldCoverageResponse)
def field_coverage() -> FieldCoverageResponse:
    """
    Field coverage profiler — shows which FHIR fields are always/sometimes/rarely
    populated across the entire patient corpus.

    For Patient-level fields: counts patients where the field is truthy.
    For sub-resource fields (Condition, Medication, Observation, Encounter):
      computes per-patient ratio (# resources with field / total resources of that type),
      then counts patients where ratio > 0.5 (i.e. majority of their records have the field).

    NOTE: First call loads all bundles (~30-60 s). Subsequent calls are fast due to LRU cache.
    """
    files = list_patient_files()

    # Accumulators — keyed by field_path
    # Patient-level: count patients with field present
    patient_present: dict[str, int] = defaultdict(int)

    # Sub-resource level: count patients where >50% of their resources have the field
    sub_present: dict[str, int] = defaultdict(int)

    loaded_count = 0

    for path in files:
        patient_id = patient_id_from_path(path)
        result = load_patient(patient_id)
        if result is None:
            continue

        record, _ = result
        s = record.summary
        loaded_count += 1

        # ------------------------------------------------------------------
        # Patient-level fields
        # ------------------------------------------------------------------
        if s.birth_date is not None:
            patient_present["patient.birth_date"] += 1
        if s.gender:
            patient_present["patient.gender"] += 1
        if s.race:
            patient_present["patient.race"] += 1
        if s.ethnicity:
            patient_present["patient.ethnicity"] += 1
        if s.language:
            patient_present["patient.language"] += 1
        if s.marital_status:
            patient_present["patient.marital_status"] += 1
        if s.city:
            patient_present["patient.city"] += 1
        if s.state:
            patient_present["patient.state"] += 1

        # ------------------------------------------------------------------
        # Condition fields
        # ------------------------------------------------------------------
        conditions = record.conditions
        n_cond = len(conditions)
        if n_cond > 0:
            onset_ratio = sum(1 for c in conditions if c.onset_dt is not None) / n_cond
            if onset_ratio > 0.5:
                sub_present["condition.onset_dt"] += 1

            # abatement_dt: only meaningful on resolved conditions
            resolved = [c for c in conditions if not c.is_active]
            n_resolved = len(resolved)
            if n_resolved > 0:
                abat_ratio = sum(1 for c in resolved if c.abatement_dt is not None) / n_resolved
                if abat_ratio > 0.5:
                    sub_present["condition.abatement_dt"] += 1
            else:
                # No resolved conditions — treat as not present for this patient
                pass

        # ------------------------------------------------------------------
        # Medication fields
        # ------------------------------------------------------------------
        meds = record.medications
        n_meds = len(meds)
        if n_meds > 0:
            authored_ratio = sum(1 for m in meds if m.authored_on is not None) / n_meds
            rxnorm_ratio = sum(1 for m in meds if m.rxnorm_code) / n_meds
            dosage_ratio = sum(1 for m in meds if m.dosage_text) / n_meds

            if authored_ratio > 0.5:
                sub_present["medication.authored_on"] += 1
            if rxnorm_ratio > 0.5:
                sub_present["medication.rxnorm_code"] += 1
            if dosage_ratio > 0.5:
                sub_present["medication.dosage_text"] += 1

        # ------------------------------------------------------------------
        # Observation fields
        # ------------------------------------------------------------------
        obs = record.observations
        n_obs = len(obs)
        if n_obs > 0:
            loinc_ratio = sum(1 for o in obs if o.loinc_code) / n_obs
            eff_dt_ratio = sum(1 for o in obs if o.effective_dt is not None) / n_obs

            # value_quantity: only check quantity-type observations
            qty_obs = [o for o in obs if o.value_type == "quantity"]
            n_qty = len(qty_obs)
            if n_qty > 0:
                vq_ratio = sum(1 for o in qty_obs if o.value_quantity is not None) / n_qty
                if vq_ratio > 0.5:
                    sub_present["observation.value_quantity"] += 1

            if loinc_ratio > 0.5:
                sub_present["observation.loinc_code"] += 1
            if eff_dt_ratio > 0.5:
                sub_present["observation.effective_dt"] += 1

        # ------------------------------------------------------------------
        # Encounter fields
        # ------------------------------------------------------------------
        encs = record.encounters
        n_encs = len(encs)
        if n_encs > 0:
            period_start_ratio = sum(1 for e in encs if e.period.start is not None) / n_encs
            period_end_ratio = sum(1 for e in encs if e.period.end is not None) / n_encs
            class_ratio = sum(1 for e in encs if e.class_code) / n_encs
            org_ratio = sum(1 for e in encs if e.provider_org) / n_encs
            prac_ratio = sum(1 for e in encs if e.practitioner_name) / n_encs

            if period_start_ratio > 0.5:
                sub_present["encounter.period.start"] += 1
            if period_end_ratio > 0.5:
                sub_present["encounter.period.end"] += 1
            if class_ratio > 0.5:
                sub_present["encounter.class_code"] += 1
            if org_ratio > 0.5:
                sub_present["encounter.provider_org"] += 1
            if prac_ratio > 0.5:
                sub_present["encounter.practitioner_name"] += 1

    total = loaded_count or 1  # avoid division by zero

    # ------------------------------------------------------------------
    # Build FieldCoverageItem list
    # ------------------------------------------------------------------
    RESOURCE_TYPE_MAP: dict[str, str] = {
        "patient.birth_date": "Patient",
        "patient.gender": "Patient",
        "patient.race": "Patient",
        "patient.ethnicity": "Patient",
        "patient.language": "Patient",
        "patient.marital_status": "Patient",
        "patient.city": "Patient",
        "patient.state": "Patient",
        "condition.onset_dt": "Condition",
        "condition.abatement_dt": "Condition",
        "medication.authored_on": "Medication",
        "medication.rxnorm_code": "Medication",
        "medication.dosage_text": "Medication",
        "observation.loinc_code": "Observation",
        "observation.value_quantity": "Observation",
        "observation.effective_dt": "Observation",
        "encounter.period.start": "Encounter",
        "encounter.period.end": "Encounter",
        "encounter.class_code": "Encounter",
        "encounter.provider_org": "Encounter",
        "encounter.practitioner_name": "Encounter",
    }

    all_counts: dict[str, int] = {**patient_present, **sub_present}

    items: list[FieldCoverageItem] = []
    for field_path, resource_type in RESOURCE_TYPE_MAP.items():
        present_count = all_counts.get(field_path, 0)
        coverage_pct = round(present_count / total * 100, 1)
        items.append(FieldCoverageItem(
            field_path=field_path,
            resource_type=resource_type,
            present_count=present_count,
            total_count=loaded_count,
            coverage_pct=coverage_pct,
            coverage_label=_coverage_label(coverage_pct),
        ))

    # Sort: resource_type alphabetically, then coverage_pct descending
    items.sort(key=lambda x: (x.resource_type, -x.coverage_pct))

    return FieldCoverageResponse(
        total_patients=loaded_count,
        fields=items,
    )
