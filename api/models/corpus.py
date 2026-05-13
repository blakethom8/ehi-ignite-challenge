"""
Corpus-level response models — aggregate statistics across the patient
corpus (gender / complexity breakdowns, lab-value distributions, allergy
criticality, field coverage profiling).

Consumed by `api/routers/corpus.py`.
"""

from __future__ import annotations

from pydantic import BaseModel


# ---------------------------------------------------------------------------
# Corpus Stats
# ---------------------------------------------------------------------------

class CorpusStats(BaseModel):
    total_patients: int
    gender_breakdown: dict[str, int]
    complexity_tier_breakdown: dict[str, int]
    avg_age: float
    avg_encounter_count: float
    avg_active_condition_count: float
    avg_active_med_count: float
    total_encounters: int
    total_resources: int


# ---------------------------------------------------------------------------
# Observation Distributions (corpus-level lab value distributions)
# ---------------------------------------------------------------------------

class ObservationDistribution(BaseModel):
    loinc_code: str
    display_name: str
    unit: str
    count: int
    patient_count: int
    min: float
    max: float
    mean: float
    median: float
    p10: float
    p25: float
    p75: float
    p90: float
    histogram: list[int]
    bucket_labels: list[str]


class ObservationDistributionsResponse(BaseModel):
    distributions: list[ObservationDistribution]
    total_loinc_codes_found: int
    loinc_codes_shown: int


# ---------------------------------------------------------------------------
# Allergy Criticality Breakdown (corpus-level)
# ---------------------------------------------------------------------------

class AllergySubstanceEntry(BaseModel):
    substance: str
    count: int
    criticality: str  # most severe criticality seen for this substance


class AllergyCriticalityBreakdown(BaseModel):
    criticality_counts: dict[str, int]    # {"high": 45, "low": 120, ...}
    category_counts: dict[str, int]       # {"medication": 234, "food": 45, ...}
    total_allergy_records: int
    patients_with_allergies: int
    patients_with_high_criticality: int   # at least one "high" allergy
    top_substances: list[AllergySubstanceEntry]  # top 10 by count


# ---------------------------------------------------------------------------
# Field Coverage Profiler
# ---------------------------------------------------------------------------

class FieldCoverageItem(BaseModel):
    field_path: str          # e.g. "patient.birth_date", "condition.onset_dt"
    resource_type: str       # e.g. "Patient", "Condition"
    present_count: int       # how many patients have this field non-null/non-empty
    total_count: int         # total patients checked
    coverage_pct: float      # present_count / total_count * 100
    coverage_label: str      # "Always" (>=95%), "Usually" (70-94%), "Sometimes" (30-69%), "Rarely" (<30%)


class FieldCoverageResponse(BaseModel):
    total_patients: int
    fields: list[FieldCoverageItem]  # sorted by resource_type, then coverage_pct descending
