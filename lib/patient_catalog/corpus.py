"""
Corpus index over all patient files.

Builds a compact PatientIndex for each patient (not a full PatientRecord)
and caches to .corpus_cache.json. Cache is invalidated if any file changes.
First build takes ~5–10s for 1,180 patients; subsequent loads are instant.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Callable

from ..fhir_parser.bundle_parser import parse_bundle
from ..patient_catalog.single_patient import compute_patient_stats


CACHE_FILE = Path(__file__).parent / ".corpus_cache.json"


@dataclass
class PatientIndex:
    file_path: str
    file_name: str
    patient_id: str
    patient_name: str
    gender: str
    age_years: float
    is_deceased: bool
    city: str
    state: str
    race: str
    total_resources: int
    condition_count: int
    active_condition_count: int
    med_count: int
    active_med_count: int
    encounter_count: int
    years_of_history: float
    earliest_encounter: str    # ISO date string
    latest_encounter: str      # ISO date string
    has_allergies: bool
    allergy_labels: list[str]
    insurer: str
    unique_loinc_count: int
    immunization_count: int
    complexity_score: float
    complexity_tier: str
    top_conditions: list[str]  # display names of up to 3 conditions
    resource_type_counts: dict[str, int] = field(default_factory=dict)
    file_mtime: float = 0.0


@dataclass
class CorpusCatalog:
    patient_count: int
    total_resources: int
    global_resource_type_counts: dict[str, int]
    patients: list[PatientIndex]
    cache_generated_at: float
    cache_file_count: int


def build_corpus(
    data_dir: Path,
    progress_callback: Callable[[int, int, str], None] | None = None,
) -> CorpusCatalog:
    """
    Scan all patient JSON files in data_dir and build a CorpusCatalog.

    Args:
        data_dir: Directory containing patient bundle JSON files.
        progress_callback: Optional fn(current, total, patient_name) for progress reporting.

    Returns:
        CorpusCatalog with one PatientIndex per patient.
    """
    files = sorted(data_dir.glob("*.json"))
    patients: list[PatientIndex] = []
    global_counts: dict[str, int] = {}

    for i, fp in enumerate(files):
        try:
            record = parse_bundle(fp)
            stats = compute_patient_stats(record)

            insurer = ""
            if record.claims:
                insurer = record.claims[0].insurer or ""

            top_conditions = [
                c.display
                for c in stats.condition_catalog
                if c.is_active
            ][:3]
            if not top_conditions:
                top_conditions = [c.display for c in stats.condition_catalog][:3]

            earliest = stats.earliest_encounter_dt.strftime("%Y-%m-%d") if stats.earliest_encounter_dt else ""
            latest = stats.latest_encounter_dt.strftime("%Y-%m-%d") if stats.latest_encounter_dt else ""

            idx = PatientIndex(
                file_path=str(fp),
                file_name=fp.name,
                patient_id=record.summary.patient_id,
                patient_name=stats.name,
                gender=stats.gender,
                age_years=stats.age_years,
                is_deceased=stats.is_deceased,
                city=stats.city,
                state=stats.state,
                race=stats.race,
                total_resources=stats.total_resources,
                condition_count=stats.active_condition_count + stats.resolved_condition_count,
                active_condition_count=stats.active_condition_count,
                med_count=stats.total_med_count,
                active_med_count=stats.active_med_count,
                encounter_count=stats.encounter_count,
                years_of_history=stats.years_of_history,
                earliest_encounter=earliest,
                latest_encounter=latest,
                has_allergies=stats.allergy_count > 0,
                allergy_labels=stats.allergy_labels,
                insurer=insurer,
                unique_loinc_count=stats.unique_loinc_count,
                immunization_count=stats.immunization_count,
                complexity_score=stats.complexity_score,
                complexity_tier=stats.complexity_tier,
                top_conditions=top_conditions,
                resource_type_counts=record.resource_type_counts,
                file_mtime=os.path.getmtime(fp),
            )
            patients.append(idx)

            # Accumulate global resource type counts
            for rtype, cnt in record.resource_type_counts.items():
                global_counts[rtype] = global_counts.get(rtype, 0) + cnt

            if progress_callback:
                progress_callback(i + 1, len(files), stats.name)

        except Exception as e:
            if progress_callback:
                progress_callback(i + 1, len(files), f"ERROR: {fp.name}: {e}")

    return CorpusCatalog(
        patient_count=len(patients),
        total_resources=sum(global_counts.values()),
        global_resource_type_counts=global_counts,
        patients=patients,
        cache_generated_at=time.time(),
        cache_file_count=len(files),
    )


def _needs_rebuild(data_dir: Path) -> bool:
    """Check if the cache is missing or stale."""
    if not CACHE_FILE.exists():
        return True
    try:
        with open(CACHE_FILE) as f:
            cached = json.load(f)
        cached_at = cached.get("cache_generated_at", 0)
        files = list(data_dir.glob("*.json"))
        # Rebuild if file count changed
        if len(files) != cached.get("cache_file_count", 0):
            return True
        # Rebuild if any file is newer than cache
        for fp in files:
            if os.path.getmtime(fp) > cached_at:
                return True
        return False
    except Exception:
        return True


def load_corpus(
    data_dir: Path,
    progress_callback: Callable[[int, int, str], None] | None = None,
) -> CorpusCatalog:
    """Load corpus from cache if fresh, otherwise rebuild and save."""
    if not _needs_rebuild(data_dir):
        try:
            with open(CACHE_FILE) as f:
                data = json.load(f)
            patients = [PatientIndex(**p) for p in data["patients"]]
            return CorpusCatalog(
                patient_count=data["patient_count"],
                total_resources=data["total_resources"],
                global_resource_type_counts=data["global_resource_type_counts"],
                patients=patients,
                cache_generated_at=data["cache_generated_at"],
                cache_file_count=data["cache_file_count"],
            )
        except Exception:
            pass  # Fall through to rebuild

    catalog = build_corpus(data_dir, progress_callback)

    # Save cache
    try:
        cache_data = {
            "patient_count": catalog.patient_count,
            "total_resources": catalog.total_resources,
            "global_resource_type_counts": catalog.global_resource_type_counts,
            "cache_generated_at": catalog.cache_generated_at,
            "cache_file_count": catalog.cache_file_count,
            "patients": [asdict(p) for p in catalog.patients],
        }
        with open(CACHE_FILE, "w") as f:
            json.dump(cache_data, f)
    except Exception:
        pass  # Cache write failure is non-fatal

    return catalog
