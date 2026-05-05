"""
Patient loader — wraps fhir_explorer parser for use by the API layer.

Parsed bundles are cached in-memory (LRU, 30 patients) so repeated requests
to the same patient don't re-parse from disk.
"""

from __future__ import annotations

import json
import re
import sys
from collections import defaultdict
from functools import lru_cache
from datetime import datetime, timezone
from typing import Any
from pathlib import Path

# Ensure repo root is on path so fhir_explorer imports work
_REPO_ROOT = Path(__file__).parent.parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from lib.fhir_parser.bundle_parser import parse_bundle
from lib.patient_catalog.single_patient import compute_patient_stats, PatientStats
from lib.fhir_parser.models import (
    AllergyRecord,
    CodeableConcept,
    ConditionRecord,
    EncounterRecord,
    ImmunizationRecord,
    MedicationRecord,
    ObservationRecord,
    PatientRecord,
    PatientSummary,
    Period,
)

_DATA_DIR = _REPO_ROOT / "data" / "synthea-samples" / "synthea-r4-individual" / "fhir"


def data_dir() -> Path:
    return _DATA_DIR


def list_patient_files() -> list[Path]:
    """Return sorted list of all FHIR bundle JSON files."""
    return sorted(_DATA_DIR.glob("*.json"))


def patient_display_name(path: Path) -> str:
    """Extract a readable name from the filename stem."""
    parts = path.stem.split("_")
    if len(parts) >= 2:
        first = re.sub(r"\d+", "", parts[0]).strip()
        last = re.sub(r"\d+", "", parts[1]).strip()
        return f"{first} {last}"
    return path.stem


def patient_id_from_path(path: Path) -> str:
    """Use the filename stem (without .json) as the stable patient ID."""
    return path.stem


# Module-level cache: bare UUID → canonical filename stem.
# Populated lazily on first UUID-lookup miss; never cleared during process lifetime.
_uuid_to_stem: dict[str, str] | None = None
_UUID_RE = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)


def _build_uuid_index() -> dict[str, str]:
    """Build a map from FHIR Patient-resource id → canonical filename stem.

    Strategies, in preference order:
    1. Use the corpus catalog mapping from FHIR Patient id → filename.
    2. Read the legacy corpus cache if present.
    3. Use the UUID suffix embedded in the Synthea filename stem as a fallback.
    4. Scan each JSON file and extract the Patient resource id by reading
       bundle entries until the first Patient resource is found (slower but
       works without a corpus cache).
    """
    import json as _json

    index: dict[str, str] = {}

    # Strategy 1: use the same compact corpus catalog that backs /api/patients.
    # It stores the real FHIR Patient resource id, which can differ from the
    # UUID suffix embedded in the Synthea filename.
    try:
        from lib.patient_catalog.corpus import load_corpus

        catalog = load_corpus(_DATA_DIR)
        for patient in catalog.patients:
            patient_id = (patient.patient_id or "").lower()
            file_name = patient.file_name or ""
            if patient_id and file_name:
                index[patient_id] = Path(file_name).stem
        if index:
            return index
    except Exception:
        pass

    # Strategy 2: use legacy corpus cache if present
    _CORPUS_CACHE = _REPO_ROOT / "fhir_explorer" / "catalog" / ".corpus_cache.json"
    if _CORPUS_CACHE.exists():
        try:
            with open(_CORPUS_CACHE) as _f:
                cached = _json.load(_f)
            for p in cached.get("patients", []):
                pid = p.get("patient_id", "").lower()
                file_name = p.get("file_name", "")
                if pid and file_name:
                    stem = Path(file_name).stem
                    index[pid] = stem
            if index:
                return index
        except Exception:
            pass

    # Strategy 3: many Synthea filenames also end with a UUID. This does not
    # always match the FHIR Patient id, but it is cheap and useful as fallback.
    for path in _DATA_DIR.glob("*.json"):
        stem = path.stem
        maybe_uuid = stem.rsplit("_", 1)[-1].lower()
        if _UUID_RE.match(maybe_uuid):
            index[maybe_uuid] = stem
    if index:
        return index

    # Strategy 4: scan bundles for Patient resource id
    for path in _DATA_DIR.glob("*.json"):
        stem = path.stem
        try:
            with open(path) as _f:
                bundle = _json.load(_f)
            for entry in bundle.get("entry", []):
                resource = entry.get("resource", {})
                if resource.get("resourceType") == "Patient":
                    pid = resource.get("id", "").lower()
                    if pid:
                        index[pid] = stem
                    break  # Only need the first Patient entry
        except Exception:
            continue

    return index


def path_from_patient_id(patient_id: str) -> Path | None:
    """Resolve a patient ID back to its file path.

    Accepts two ID shapes:
    1. Canonical filename stem (e.g. ``Shelly431_Corwin846_eec393be-…``) — fast
       direct lookup.
    2. Bare UUID (e.g. ``eec393be-2569-46db-a974-33d7c853d690``) — resolved
       through the module-level UUID index, built once on first miss.
    """
    global _uuid_to_stem

    # Shape 1: exact filename match
    candidate = _DATA_DIR / f"{patient_id}.json"
    if candidate.exists():
        return candidate

    # Shape 2: bare UUID — build index on first use then look up
    if _uuid_to_stem is None:
        _uuid_to_stem = _build_uuid_index()
    stem = _uuid_to_stem.get(patient_id.lower())
    if stem is None:
        return None
    resolved = _DATA_DIR / f"{stem}.json"
    return resolved if resolved.exists() else None


def warm_patient_indexes() -> None:
    """Build lightweight lookup indexes that should be ready before traffic."""
    global _uuid_to_stem
    if _uuid_to_stem is None:
        _uuid_to_stem = _build_uuid_index()


def _parse_dt(value: Any) -> datetime | None:
    """Parse FHIR-ish date strings into naive UTC datetimes.

    The legacy parsed Synthea models generally compare naive datetimes. Published
    harmonization artifacts may contain offset-aware timestamps from uploaded
    FHIR exports, so normalize here before feeding the shared patient endpoints.
    """
    if not value or not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        try:
            parsed = datetime.fromisoformat(f"{value}T00:00:00")
        except ValueError:
            return None
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
    return parsed


def _safe_id(prefix: str, value: Any, index: int) -> str:
    raw = str(value or "").strip() or f"{prefix}-{index}"
    return re.sub(r"[^A-Za-z0-9_.-]+", "-", raw).strip(".-")[:160] or f"{prefix}-{index}"


def _best_source_date(sources: list[dict[str, Any]], field: str) -> datetime | None:
    dates = [_parse_dt(source.get(field)) for source in sources]
    present = [dt for dt in dates if dt is not None]
    return max(present) if present else None


def _add_encounter(
    record: PatientRecord,
    encounter_by_key: dict[tuple[str, str], EncounterRecord],
    source_label: str,
    event_dt: datetime | None,
    resource_type: str,
    resource_id: str,
) -> str | None:
    if event_dt is None:
        return None
    key = (source_label or "Published chart", event_dt.date().isoformat())
    encounter = encounter_by_key.get(key)
    if encounter is None:
        encounter_id = _safe_id("enc", f"published-{key[0]}-{key[1]}", len(encounter_by_key))
        encounter = EncounterRecord(
            encounter_id=encounter_id,
            patient_id=record.summary.patient_id,
            status="finished",
            class_code="DOC",
            encounter_type="Published chart source event",
            reason_display="Harmonized source fact",
            period=Period(start=event_dt, end=event_dt),
            provider_org=source_label or "Published chart",
        )
        encounter_by_key[key] = encounter
        record.encounters.append(encounter)
    if resource_type == "Observation":
        encounter.linked_observations.append(resource_id)
    elif resource_type == "Condition":
        encounter.linked_conditions.append(resource_id)
    elif resource_type == "MedicationRequest":
        encounter.linked_medications.append(resource_id)
    elif resource_type == "Immunization":
        encounter.linked_immunizations.append(resource_id)
    return encounter.encounter_id


def _load_active_published_run(patient_id: str) -> dict[str, Any] | None:
    """Return the active published harmonization run for a selected patient id."""
    from api.core import harmonization_runs, harmonize_service, published_charts

    collection_ids = [harmonize_service.workspace_collection_id(patient_id)]
    if patient_id.startswith("workspace-"):
        # Backward-compatible upload collection id used before the patient
        # workspace wrapper became the canonical downstream read target.
        collection_ids.append(f"upload-{patient_id}")

    for collection_id in dict.fromkeys(collection_ids):
        active = published_charts.state(collection_id).get("active_snapshot")
        if not active:
            continue
        artifact_path = active.get("artifact_path")
        if isinstance(artifact_path, str):
            path = Path(artifact_path)
            if path.exists():
                try:
                    return json.loads(path.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError):
                    pass
        run_id = active.get("run_id")
        if isinstance(run_id, str):
            run = harmonization_runs.get_run(collection_id, run_id)
            if run is not None:
                return run
    return None


def _record_from_published_run(patient_id: str, run: dict[str, Any]) -> tuple[PatientRecord, PatientStats]:
    """Convert a published harmonization artifact into the shared PatientRecord shape.

    This is intentionally a read facade, not a new parser. It lets existing
    downstream modules consume the published canonical chart without knowing
    whether the source was Synthea, an uploaded FHIR export, or PDF extraction.
    """
    collection_name = str(run.get("collection_name") or patient_id)
    display_name = collection_name.removesuffix(" — patient workspace")
    record = PatientRecord(
        summary=PatientSummary(
            patient_id=patient_id,
            file_path=str(run.get("artifact_path") or ""),
            name=display_name,
            gender="workspace",
        )
    )
    encounter_by_key: dict[tuple[str, str], EncounterRecord] = {}
    candidate = run.get("candidate_record") if isinstance(run.get("candidate_record"), dict) else {}

    for obs_idx, obs in enumerate(candidate.get("observations") or []):
        if not isinstance(obs, dict):
            continue
        sources = [s for s in obs.get("sources") or [] if isinstance(s, dict)]
        if not sources and isinstance(obs.get("latest"), dict):
            sources = [obs["latest"]]
        if not sources:
            sources = [{}]
        for source_idx, source in enumerate(sources):
            effective_dt = _parse_dt(source.get("effective_date") or (obs.get("latest") or {}).get("effective_date"))
            raw_value = source.get("value", (obs.get("latest") or {}).get("value"))
            unit = source.get("unit") or obs.get("canonical_unit") or (obs.get("latest") or {}).get("unit") or ""
            obs_id = _safe_id(
                "obs",
                source.get("source_observation_ref") or f"{obs.get('merged_ref')}-{source_idx}",
                obs_idx,
            )
            value_quantity = float(raw_value) if isinstance(raw_value, (int, float)) else None
            record_obs = ObservationRecord(
                obs_id=obs_id,
                patient_id=patient_id,
                status="final",
                category="laboratory" if obs.get("loinc_code") else "unknown",
                loinc_code=str(obs.get("loinc_code") or ""),
                display=str(obs.get("canonical_name") or "Observation"),
                effective_dt=effective_dt,
                value_type="quantity" if value_quantity is not None else ("codeable_concept" if raw_value else "none"),
                value_quantity=value_quantity,
                value_unit=str(unit),
                value_concept_display=None if value_quantity is not None else (str(raw_value) if raw_value is not None else None),
            )
            record_obs.encounter_id = _add_encounter(
                record,
                encounter_by_key,
                str(source.get("source_label") or "Published chart"),
                effective_dt,
                "Observation",
                obs_id,
            )
            record.observations.append(record_obs)

    for idx, condition in enumerate(candidate.get("conditions") or []):
        if not isinstance(condition, dict):
            continue
        sources = [s for s in condition.get("sources") or [] if isinstance(s, dict)]
        onset_dt = _best_source_date(sources, "onset_date")
        source = sources[0] if sources else {}
        condition_id = _safe_id("condition", condition.get("merged_ref"), idx)
        condition_record = ConditionRecord(
            condition_id=condition_id,
            patient_id=patient_id,
            clinical_status=str(source.get("clinical_status") or ("active" if condition.get("is_active") else "resolved")),
            verification_status="confirmed",
            code=CodeableConcept(
                system="http://snomed.info/sct" if condition.get("snomed") else "",
                code=str(condition.get("snomed") or condition.get("icd10") or condition.get("icd9") or ""),
                display=str(condition.get("canonical_name") or source.get("display") or "Condition"),
            ),
            onset_dt=onset_dt,
            is_active=bool(condition.get("is_active")),
        )
        condition_record.encounter_id = _add_encounter(
            record,
            encounter_by_key,
            str(source.get("source_label") or "Published chart"),
            onset_dt,
            "Condition",
            condition_id,
        )
        record.conditions.append(condition_record)

    for idx, medication in enumerate(candidate.get("medications") or []):
        if not isinstance(medication, dict):
            continue
        sources = [s for s in medication.get("sources") or [] if isinstance(s, dict)]
        authored_on = _best_source_date(sources, "authored_on")
        source = sources[0] if sources else {}
        rxnorm_codes = medication.get("rxnorm_codes") if isinstance(medication.get("rxnorm_codes"), list) else []
        med_id = _safe_id("med", medication.get("merged_ref"), idx)
        medication_record = MedicationRecord(
            med_id=med_id,
            patient_id=patient_id,
            status=str(source.get("status") or ("active" if medication.get("is_active") else "completed")),
            rxnorm_code=str(rxnorm_codes[0]) if rxnorm_codes else "",
            display=str(medication.get("canonical_name") or source.get("display") or "Medication"),
            authored_on=authored_on,
        )
        medication_record.encounter_id = _add_encounter(
            record,
            encounter_by_key,
            str(source.get("source_label") or "Published chart"),
            authored_on,
            "MedicationRequest",
            med_id,
        )
        record.medications.append(medication_record)

    for idx, allergy in enumerate(candidate.get("allergies") or []):
        if not isinstance(allergy, dict):
            continue
        sources = [s for s in allergy.get("sources") or [] if isinstance(s, dict)]
        recorded_dt = _best_source_date(sources, "recorded_date")
        source = sources[0] if sources else {}
        record.allergies.append(
            AllergyRecord(
                allergy_id=_safe_id("allergy", allergy.get("merged_ref"), idx),
                patient_id=patient_id,
                clinical_status=str(source.get("clinical_status") or ("active" if allergy.get("is_active") else "inactive")),
                criticality=str(allergy.get("highest_criticality") or source.get("criticality") or ""),
                code=CodeableConcept(
                    system="http://snomed.info/sct" if allergy.get("snomed") else "",
                    code=str(allergy.get("snomed") or allergy.get("rxnorm") or ""),
                    display=str(allergy.get("canonical_name") or source.get("display") or "Allergy"),
                ),
                recorded_date=recorded_dt,
            )
        )

    for idx, immunization in enumerate(candidate.get("immunizations") or []):
        if not isinstance(immunization, dict):
            continue
        sources = [s for s in immunization.get("sources") or [] if isinstance(s, dict)]
        occurrence_dt = _parse_dt(immunization.get("occurrence_date")) or _best_source_date(sources, "occurrence_date")
        source = sources[0] if sources else {}
        imm_id = _safe_id("imm", immunization.get("merged_ref"), idx)
        imm_record = ImmunizationRecord(
            imm_id=imm_id,
            patient_id=patient_id,
            status=str(source.get("status") or "completed"),
            cvx_code=str(immunization.get("cvx") or source.get("cvx") or ""),
            display=str(immunization.get("canonical_name") or source.get("display") or "Immunization"),
            occurrence_dt=occurrence_dt,
        )
        imm_record.encounter_id = _add_encounter(
            record,
            encounter_by_key,
            str(source.get("source_label") or "Published chart"),
            occurrence_dt,
            "Immunization",
            imm_id,
        )
        record.immunizations.append(imm_record)

    record.encounter_index = {enc.encounter_id: enc for enc in record.encounters}
    record.obs_index = {obs.obs_id: obs for obs in record.observations}
    record.obs_by_encounter = defaultdict(list)
    record.obs_by_loinc = defaultdict(list)
    for obs in record.observations:
        if obs.encounter_id:
            record.obs_by_encounter[obs.encounter_id].append(obs.obs_id)
        if obs.loinc_code:
            record.obs_by_loinc[obs.loinc_code].append(obs.obs_id)
    record.obs_by_encounter = dict(record.obs_by_encounter)
    record.obs_by_loinc = dict(record.obs_by_loinc)
    record.resource_type_counts = {
        "Patient": 1,
        "Encounter": len(record.encounters),
        "Observation": len(record.observations),
        "Condition": len(record.conditions),
        "MedicationRequest": len(record.medications),
        "AllergyIntolerance": len(record.allergies),
        "Immunization": len(record.immunizations),
    }
    record.resource_type_counts = {key: value for key, value in record.resource_type_counts.items() if value > 0}
    record.parse_warnings.append("Loaded from active published harmonization snapshot.")
    return record, compute_patient_stats(record)


@lru_cache(maxsize=30)
def _cached_load(canonical_stem: str) -> tuple[PatientRecord, PatientStats]:
    """Parse bundle and compute stats. Cached by canonical filename stem."""
    path = _DATA_DIR / f"{canonical_stem}.json"
    record = parse_bundle(str(path))
    stats = compute_patient_stats(record)
    return record, stats


def load_patient(patient_id: str) -> tuple[PatientRecord, PatientStats] | None:
    """Load and parse a patient bundle by ID. Returns None if not found. Cached.

    Accepts both the canonical filename stem and a bare resource UUID — both
    resolve to the same ``_cached_load`` entry via the canonical stem so the
    LRU cache is never double-populated for the same physical patient.
    """
    published_run = _load_active_published_run(patient_id)
    if published_run is not None:
        return _record_from_published_run(patient_id, published_run)

    path = path_from_patient_id(patient_id)
    if path is None:
        return None
    # Always use the canonical stem as the cache key so bare-UUID and
    # filename-stem callers share the same cached entry.
    return _cached_load(path.stem)
