"""
/api/corpus — corpus-level statistics across all patients.
"""

from __future__ import annotations

import csv
import io
import statistics
import zipfile
from collections import defaultdict

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from api.core.loader import list_patient_files, load_patient, patient_id_from_path
from api.models import (
    AllergyCriticalityBreakdown,
    AllergySubstanceEntry,
    CorpusStats,
    FieldCoverageItem,
    FieldCoverageResponse,
    ObservationDistribution,
    ObservationDistributionsResponse,
)

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


# ---------------------------------------------------------------------------
# Observation Distributions
# ---------------------------------------------------------------------------

def _percentile(sorted_values: list[float], pct: float) -> float:
    """Return the value at the given percentile (0–1) in a pre-sorted list."""
    n = len(sorted_values)
    if n == 0:
        return 0.0
    idx = int(n * pct)
    idx = max(0, min(idx, n - 1))
    return sorted_values[idx]


@router.get("/observation-distributions", response_model=ObservationDistributionsResponse)
def observation_distributions() -> ObservationDistributionsResponse:
    """
    Population-level lab value distributions for quantitative LOINC observations
    across all ~1,180 patient bundles.

    NOTE: First call loads all bundles (~60 s). Subsequent calls are fast due to
    the LRU cache in loader.py. Only LOINC codes with ≥20 data points are included.
    Results are capped at the top 30 codes by observation count, sorted descending.
    """
    files = list_patient_files()

    # values_by_code[loinc_code] = list of float values
    values_by_code: dict[str, list[float]] = defaultdict(list)
    # patients_by_code[loinc_code] = set of patient IDs with this code
    patients_by_code: dict[str, set[str]] = defaultdict(set)
    # metadata — store the most common display/unit per code
    display_by_code: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    unit_by_code: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))

    for path in files:
        patient_id = patient_id_from_path(path)
        result = load_patient(patient_id)
        if result is None:
            continue

        record, _ = result

        for obs in record.observations:
            if not obs.loinc_code:
                continue
            if obs.value_quantity is None:
                continue
            try:
                fval = float(obs.value_quantity)
            except (TypeError, ValueError):
                continue

            code = obs.loinc_code
            values_by_code[code].append(fval)
            patients_by_code[code].add(patient_id)
            if obs.display:
                display_by_code[code][obs.display] += 1
            if obs.value_unit:
                unit_by_code[code][obs.value_unit] += 1

    total_loinc_codes_found = len(values_by_code)

    # Filter to codes with ≥20 data points, then take top 30 by count
    qualifying = {
        code: vals
        for code, vals in values_by_code.items()
        if len(vals) >= 20
    }
    top_codes = sorted(qualifying.keys(), key=lambda c: len(qualifying[c]), reverse=True)[:30]

    distributions: list[ObservationDistribution] = []

    for code in top_codes:
        vals = qualifying[code]
        sorted_vals = sorted(vals)
        n = len(sorted_vals)

        val_min = sorted_vals[0]
        val_max = sorted_vals[-1]
        val_mean = sum(sorted_vals) / n
        val_median = statistics.median(sorted_vals)
        val_p10 = _percentile(sorted_vals, 0.10)
        val_p25 = _percentile(sorted_vals, 0.25)
        val_p75 = _percentile(sorted_vals, 0.75)
        val_p90 = _percentile(sorted_vals, 0.90)

        # 10-bucket histogram
        num_buckets = 10
        bucket_counts = [0] * num_buckets
        bucket_labels: list[str] = []

        if val_max > val_min:
            bucket_width = (val_max - val_min) / num_buckets
            for v in sorted_vals:
                idx = int((v - val_min) / bucket_width)
                idx = min(idx, num_buckets - 1)
                bucket_counts[idx] += 1
            for i in range(num_buckets):
                lo = val_min + i * bucket_width
                hi = val_min + (i + 1) * bucket_width
                bucket_labels.append(f"{lo:.2g}–{hi:.2g}")
        else:
            # All values identical — put everything in the first bucket
            bucket_counts[0] = n
            for i in range(num_buckets):
                bucket_labels.append(f"{val_min:.2g}")

        # Resolve most-common display name and unit
        display_name = (
            max(display_by_code[code], key=display_by_code[code].get)  # type: ignore[arg-type]
            if display_by_code[code]
            else code
        )
        unit = (
            max(unit_by_code[code], key=unit_by_code[code].get)  # type: ignore[arg-type]
            if unit_by_code[code]
            else ""
        )

        distributions.append(ObservationDistribution(
            loinc_code=code,
            display_name=display_name,
            unit=unit,
            count=n,
            patient_count=len(patients_by_code[code]),
            min=round(val_min, 4),
            max=round(val_max, 4),
            mean=round(val_mean, 4),
            median=round(float(val_median), 4),
            p10=round(val_p10, 4),
            p25=round(val_p25, 4),
            p75=round(val_p75, 4),
            p90=round(val_p90, 4),
            histogram=bucket_counts,
            bucket_labels=bucket_labels,
        ))

    return ObservationDistributionsResponse(
        distributions=distributions,
        total_loinc_codes_found=total_loinc_codes_found,
        loinc_codes_shown=len(distributions),
    )


# ---------------------------------------------------------------------------
# Allergy Criticality Breakdown
# ---------------------------------------------------------------------------

# Criticality severity order for "most severe wins" logic
_CRITICALITY_ORDER = {"high": 0, "low": 1, "unable-to-assess": 2, "unknown": 3}


@router.get("/allergies/criticality-breakdown", response_model=AllergyCriticalityBreakdown)
def allergy_criticality_breakdown() -> AllergyCriticalityBreakdown:
    """
    Population-level allergy criticality and category breakdown across all patients.

    Iterates all patient bundles, collecting AllergyRecord data to produce:
    - criticality_counts: tally of high / low / unable-to-assess / unknown
    - category_counts: tally of medication / food / environment / biologic
    - patients_with_high_criticality: patients with at least one "high" allergy
    - top_substances: top 10 substances by occurrence count

    NOTE: First call loads all bundles (~30–60 s). Subsequent calls are fast
    due to the LRU cache in loader.py.
    """
    files = list_patient_files()

    criticality_counts: dict[str, int] = defaultdict(int)
    category_counts: dict[str, int] = defaultdict(int)
    total_records = 0
    patients_with_allergies = 0
    patients_with_high = 0

    # substance -> {count, worst_criticality_order, worst_criticality_label}
    substance_data: dict[str, dict] = {}

    for path in files:
        patient_id = patient_id_from_path(path)
        result = load_patient(patient_id)
        if result is None:
            continue

        record, _ = result
        allergies = record.allergies
        if not allergies:
            continue

        patients_with_allergies += 1
        has_high = False

        for a in allergies:
            total_records += 1

            # Criticality
            crit = a.criticality.strip() if a.criticality else ""
            if crit not in ("high", "low", "unable-to-assess"):
                crit = "unknown"
            criticality_counts[crit] += 1
            if crit == "high":
                has_high = True

            # Categories — raw list of strings from the FHIR bundle
            for cat in a.categories:
                cat_clean = cat.strip().lower() if cat else "unknown"
                category_counts[cat_clean] += 1

            # Substance tracking
            substance = a.code.label()
            if not substance or substance == "Unknown":
                substance = "Unspecified"

            if substance not in substance_data:
                substance_data[substance] = {"count": 0, "worst_order": 99, "worst_label": "unknown"}

            substance_data[substance]["count"] += 1
            order = _CRITICALITY_ORDER.get(crit, 3)
            if order < substance_data[substance]["worst_order"]:
                substance_data[substance]["worst_order"] = order
                substance_data[substance]["worst_label"] = crit

        if has_high:
            patients_with_high += 1

    # Top 10 substances by count
    top_sorted = sorted(substance_data.items(), key=lambda x: -x[1]["count"])[:10]
    top_substances = [
        AllergySubstanceEntry(
            substance=name,
            count=data["count"],
            criticality=data["worst_label"],
        )
        for name, data in top_sorted
    ]

    return AllergyCriticalityBreakdown(
        criticality_counts=dict(criticality_counts),
        category_counts=dict(category_counts),
        total_allergy_records=total_records,
        patients_with_allergies=patients_with_allergies,
        patients_with_high_criticality=patients_with_high,
        top_substances=top_substances,
    )


# ---------------------------------------------------------------------------
# Export endpoint
# NOTE: This endpoint is slow on first call (~60s for the full 1,180-patient
# corpus because every bundle must be parsed from disk). Subsequent calls are
# fast because load_patient() uses an LRU cache. No request timeout is applied
# — the response streams once all CSVs are built in memory.
# ---------------------------------------------------------------------------

@router.get("/export")
def export_corpus(format: str = "csv", limit: int = 0) -> StreamingResponse:
    """
    Download normalized tabular data from the full patient corpus as a ZIP
    file containing one CSV per resource type.

    Query params:
      - format: "csv" (default). Reserved for future "json" support.
      - limit: if non-zero, export only this many patients (useful for testing).
               When 0, export all patients in the corpus.

    Returns:
      application/zip — filename "ehi-export.zip"
    """
    files = list_patient_files()
    if limit > 0:
        files = files[:limit]

    # ── StringIO buffers — one per table ────────────────────────────────────
    patients_buf = io.StringIO()
    encounters_buf = io.StringIO()
    conditions_buf = io.StringIO()
    medications_buf = io.StringIO()
    observations_buf = io.StringIO()
    procedures_buf = io.StringIO()

    # ── CSV writers ──────────────────────────────────────────────────────────
    patients_writer = csv.DictWriter(patients_buf, fieldnames=[
        "id", "name", "age_years", "gender", "birth_date",
        "city", "state", "complexity_tier",
        "total_resources", "encounter_count",
        "active_condition_count", "active_med_count",
    ])
    patients_writer.writeheader()

    encounters_writer = csv.DictWriter(encounters_buf, fieldnames=[
        "patient_id", "encounter_id", "date", "class_code",
        "encounter_type", "reason_display", "duration_hours", "provider_org",
    ])
    encounters_writer.writeheader()

    conditions_writer = csv.DictWriter(conditions_buf, fieldnames=[
        "patient_id", "condition_id", "display", "clinical_status",
        "onset_date", "category",
    ])
    conditions_writer.writeheader()

    medications_writer = csv.DictWriter(medications_buf, fieldnames=[
        "patient_id", "medication_id", "display", "status",
        "authored_date", "rxnorm_code",
    ])
    medications_writer.writeheader()

    observations_writer = csv.DictWriter(observations_buf, fieldnames=[
        "patient_id", "loinc_code", "display", "value", "unit",
        "date", "category",
    ])
    observations_writer.writeheader()

    procedures_writer = csv.DictWriter(procedures_buf, fieldnames=[
        "patient_id", "procedure_id", "display", "status",
        "performed_date", "reason_display",
    ])
    procedures_writer.writeheader()

    # ── Iterate patients once, filling all tables simultaneously ─────────────
    for path in files:
        patient_id = patient_id_from_path(path)
        result = load_patient(patient_id)
        if result is None:
            continue

        record, stats = result
        s = record.summary

        # patients.csv
        patients_writer.writerow({
            "id": s.patient_id,
            "name": s.name,
            "age_years": round(s.age_years, 1),
            "gender": s.gender,
            "birth_date": s.birth_date.isoformat() if s.birth_date else "",
            "city": s.city,
            "state": s.state,
            "complexity_tier": stats.complexity_tier,
            "total_resources": stats.total_resources,
            "encounter_count": stats.encounter_count,
            "active_condition_count": stats.active_condition_count,
            "active_med_count": stats.active_med_count,
        })

        # encounters.csv
        for enc in record.encounters:
            date_str = enc.period.start.date().isoformat() if enc.period.start else ""
            duration_hours = ""
            if enc.period.start and enc.period.end:
                delta = enc.period.end - enc.period.start
                duration_hours = round(delta.total_seconds() / 3600, 2)
            encounters_writer.writerow({
                "patient_id": enc.patient_id,
                "encounter_id": enc.encounter_id,
                "date": date_str,
                "class_code": enc.class_code,
                "encounter_type": enc.encounter_type,
                "reason_display": enc.reason_display,
                "duration_hours": duration_hours,
                "provider_org": enc.provider_org,
            })

        # conditions.csv
        for cond in record.conditions:
            onset_str = cond.onset_dt.date().isoformat() if cond.onset_dt else ""
            conditions_writer.writerow({
                "patient_id": cond.patient_id,
                "condition_id": cond.condition_id,
                "display": cond.code.label(),
                "clinical_status": cond.clinical_status,
                "onset_date": onset_str,
                "category": "",  # not stored on ConditionRecord — left blank
            })

        # medications.csv
        for med in record.medications:
            authored_str = med.authored_on.date().isoformat() if med.authored_on else ""
            medications_writer.writerow({
                "patient_id": med.patient_id,
                "medication_id": med.med_id,
                "display": med.display,
                "status": med.status,
                "authored_date": authored_str,
                "rxnorm_code": med.rxnorm_code,
            })

        # observations.csv
        for obs in record.observations:
            date_str = obs.effective_dt.date().isoformat() if obs.effective_dt else ""
            value = ""
            unit = ""
            if obs.value_type == "quantity":
                value = obs.value_quantity if obs.value_quantity is not None else ""
                unit = obs.value_unit
            elif obs.value_type == "codeable_concept":
                value = obs.value_concept_display or ""
            observations_writer.writerow({
                "patient_id": obs.patient_id,
                "loinc_code": obs.loinc_code,
                "display": obs.display,
                "value": value,
                "unit": unit,
                "date": date_str,
                "category": obs.category,
            })

        # procedures.csv
        for proc in record.procedures:
            performed_str = ""
            if proc.performed_period and proc.performed_period.start:
                performed_str = proc.performed_period.start.date().isoformat()
            procedures_writer.writerow({
                "patient_id": proc.patient_id,
                "procedure_id": proc.procedure_id,
                "display": proc.code.label(),
                "status": proc.status,
                "performed_date": performed_str,
                "reason_display": proc.reason_display,
            })

    # ── Pack all CSVs into a ZIP in memory ───────────────────────────────────
    zip_buf = io.BytesIO()
    with zipfile.ZipFile(zip_buf, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("patients.csv", patients_buf.getvalue())
        zf.writestr("encounters.csv", encounters_buf.getvalue())
        zf.writestr("conditions.csv", conditions_buf.getvalue())
        zf.writestr("medications.csv", medications_buf.getvalue())
        zf.writestr("observations.csv", observations_buf.getvalue())
        zf.writestr("procedures.csv", procedures_buf.getvalue())

    zip_buf.seek(0)

    return StreamingResponse(
        zip_buf,
        media_type="application/zip",
        headers={"Content-Disposition": 'attachment; filename="ehi-export.zip"'},
    )
