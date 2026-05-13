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
from lib.fhir_parser.extractors import extract_patient
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
    ProcedureRecord,
    DiagnosticReportRecord,
)

_DATA_DIR = _REPO_ROOT / "data" / "synthea-samples" / "synthea-r4-individual" / "fhir"

# Additional FHIR-bundle roots the loader treats as first-class patient sources.
# Each demo-profile persona under data/demo-profiles/<persona>/fhir/ contributes
# one or more bundles that the loader resolves alongside the Synthea corpus.
_EXTRA_DATA_DIRS: tuple[Path, ...] = (
    _REPO_ROOT / "data" / "demo-profiles" / "icu-mimic" / "fhir",
    _REPO_ROOT / "data" / "demo-profiles" / "oncology-breast-mcode" / "fhir",
    _REPO_ROOT / "data" / "demo-profiles" / "cardiac-coherent" / "fhir",
    _REPO_ROOT / "data" / "demo-profiles" / "polypharmacy-synthea" / "fhir",
)


def data_dir() -> Path:
    return _DATA_DIR


def _all_data_dirs() -> tuple[Path, ...]:
    return (_DATA_DIR, *_EXTRA_DATA_DIRS)


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


# Module-level cache: bare patient id → bundle Path.
# Populated lazily on first id-lookup miss; never cleared during process lifetime.
_pid_to_path: dict[str, Path] | None = None
_UUID_RE = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)


def _build_uuid_index() -> dict[str, Path]:
    """Build a map from FHIR Patient-resource id → bundle Path.

    Scans the Synthea corpus first (via the same fast strategies the loader has
    always used) and then walks each extra demo-profile FHIR root, where the
    Patient.id may be a non-UUID slug (e.g. ``cancer-patient-jenny-m``) and the
    filename stem is not a reliable identifier.
    """
    import json as _json

    index: dict[str, Path] = {}

    # Strategy 1 — Synthea corpus catalog (fast, real FHIR Patient ids).
    try:
        from lib.patient_catalog.corpus import load_corpus

        catalog = load_corpus(_DATA_DIR)
        for patient in catalog.patients:
            patient_id = (patient.patient_id or "").lower()
            file_name = patient.file_name or ""
            if patient_id and file_name:
                index[patient_id] = _DATA_DIR / Path(file_name).name
    except Exception:
        pass

    # Strategy 2 — legacy corpus cache.
    if not index:
        _CORPUS_CACHE = _REPO_ROOT / "fhir_explorer" / "catalog" / ".corpus_cache.json"
        if _CORPUS_CACHE.exists():
            try:
                with open(_CORPUS_CACHE) as _f:
                    cached = _json.load(_f)
                for p in cached.get("patients", []):
                    pid = p.get("patient_id", "").lower()
                    file_name = p.get("file_name", "")
                    if pid and file_name:
                        index[pid] = _DATA_DIR / Path(file_name).name
            except Exception:
                pass

    # Strategy 3 — filename-suffix UUIDs in the Synthea corpus.
    if not index:
        for path in _DATA_DIR.glob("*.json"):
            maybe_uuid = path.stem.rsplit("_", 1)[-1].lower()
            if _UUID_RE.match(maybe_uuid):
                index[maybe_uuid] = path

    # Strategy 4 — bundle scan over the Synthea corpus.
    if not index:
        for path in _DATA_DIR.glob("*.json"):
            try:
                with open(path) as _f:
                    bundle = _json.load(_f)
                for entry in bundle.get("entry", []):
                    resource = entry.get("resource", {})
                    if resource.get("resourceType") == "Patient":
                        pid = resource.get("id", "").lower()
                        if pid:
                            index[pid] = path
                        break
            except Exception:
                continue

    # ALWAYS scan the extra demo-profile roots — these are small (≤4 bundles
    # each) and may use non-UUID Patient ids, so the corpus catalog won't have
    # them. Bundle-scan is cheap on this tiny corpus.
    for root in _EXTRA_DATA_DIRS:
        if not root.exists():
            continue
        for path in root.glob("*.json"):
            try:
                with open(path) as _f:
                    bundle = _json.load(_f)
            except Exception:
                continue
            for entry in bundle.get("entry", []):
                resource = entry.get("resource", {})
                if resource.get("resourceType") == "Patient":
                    pid = (resource.get("id") or "").lower()
                    if pid:
                        index[pid] = path
                    break

    return index


def path_from_patient_id(patient_id: str) -> Path | None:
    """Resolve a patient ID back to its file path.

    Accepts two ID shapes:
    1. Canonical filename stem (e.g. ``Shelly431_Corwin846_eec393be-…``) — fast
       direct lookup; tried against every known FHIR root.
    2. Bare Patient.id (UUID or slug) — resolved through the module-level
       index, built once on first miss; covers the Synthea corpus + the
       per-persona bundles under data/demo-profiles/.
    """
    global _pid_to_path

    # Shape 1: exact filename match across all known roots.
    for root in _all_data_dirs():
        candidate = root / f"{patient_id}.json"
        if candidate.exists():
            return candidate

    # Shape 2: Patient.id lookup via the lazily-built index.
    if _pid_to_path is None:
        _pid_to_path = _build_uuid_index()
    resolved = _pid_to_path.get(patient_id.lower())
    return resolved if resolved and resolved.exists() else None


def warm_patient_indexes() -> None:
    """Build lightweight lookup indexes that should be ready before traffic."""
    global _pid_to_path
    if _pid_to_path is None:
        _pid_to_path = _build_uuid_index()


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


def _numeric_value(value: Any) -> float | None:
    """Parse FHIR quantity values without treating free text as numeric."""
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if not isinstance(value, str):
        return None
    cleaned = value.strip().replace(",", "")
    if not cleaned:
        return None
    if not re.fullmatch(r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)", cleaned):
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def _safe_id(prefix: str, value: Any, index: int) -> str:
    raw = str(value or "").strip() or f"{prefix}-{index}"
    return re.sub(r"[^A-Za-z0-9_.-]+", "-", raw).strip(".-")[:160] or f"{prefix}-{index}"


def _source_display_label(label: Any, kind: str | None = None) -> str:
    """Turn upload/cache filenames into clinician-readable source labels."""
    raw = str(label or "").strip()
    if not raw:
        return "Published chart"
    cleaned = re.sub(r"^[0-9a-fA-F]{8,16}-", "", raw)
    cleaned = cleaned.removesuffix(".extracted.json")
    stem = Path(cleaned).stem
    lower = stem.lower().replace("_", "-")
    if "cedars" in lower:
        return "Cedars-Sinai"
    if "functionhealth" in lower or "function-health" in lower or "function" in lower:
        return "Function Health"
    if "quest" in lower:
        return "Quest Diagnostics"
    if "kaiser" in lower:
        return "Kaiser Permanente"
    if kind == "extracted-pdf":
        return re.sub(r"[-_]+", " ", stem).strip().title() or "PDF source"
    return re.sub(r"[-_]+", " ", stem).strip().title() or "Published chart"


def _source_event_type(source_label: str, resource_type: str) -> tuple[str, str, str]:
    """Describe a synthetic published-chart source event in clinical terms.

    Published workspace records do not always include first-class Encounter
    resources. When we synthesize timeline anchors for source facts, make the
    labels explain the source activity instead of implying a provider visit.
    """
    lower = source_label.lower()
    is_pdf = ".pdf" in lower or "function" in lower or "quest" in lower
    is_fhir = ".json" in lower or "fhir" in lower or "cedars" in lower
    if resource_type in {"Observation", "DiagnosticReport"}:
        if is_pdf:
            return ("Lab report source event", "Lab result imported from source document", "DOC")
        return ("Diagnostic source event", "Lab or diagnostic fact imported from source", "DOC")
    if resource_type == "Condition":
        return ("Problem list source event", "Condition imported from source record", "DOC")
    if resource_type == "MedicationRequest":
        return ("Medication list source event", "Medication imported from source record", "DOC")
    if resource_type == "Immunization":
        return ("Immunization source event", "Immunization imported from source record", "DOC")
    if resource_type == "Procedure":
        return ("Procedure source event", "Procedure imported from source record", "DOC")
    if is_fhir:
        return ("FHIR export source event", "Fact imported from structured FHIR export", "DOC")
    return ("Published chart source event", "Harmonized source fact", "DOC")


def _source_practitioner_label(display_source: str, resource_type: str) -> str:
    if resource_type in {"Observation", "DiagnosticReport"}:
        return f"{display_source} lab / diagnostic records"
    if resource_type == "MedicationRequest":
        return f"{display_source} medication records"
    if resource_type == "Condition":
        return f"{display_source} problem list"
    if resource_type == "Immunization":
        return f"{display_source} immunization records"
    return f"{display_source} source records"


def _first_clean_label(*values: Any) -> str:
    for value in values:
        if isinstance(value, list):
            for item in value:
                label = _first_clean_label(item)
                if label:
                    return label
            continue
        label = str(value or "").strip()
        if label:
            return label
    return ""


def _labels_from_artifact(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    labels = []
    for item in value:
        label = str(item or "").strip()
        if label and label not in labels:
            labels.append(label)
    return labels


def _artifact_provider_site(
    artifact: dict[str, Any],
    source_id: str,
) -> tuple[str, str]:
    """Return (site/organization, practitioner/provider) for a clinical artifact."""
    source_label = _source_display_label(artifact.get("source_label") or source_id)
    participant = _first_clean_label(
        _labels_from_artifact(artifact.get("practitioner_labels")),
        _labels_from_artifact(artifact.get("participant_labels")),
    )
    performer_practitioner = _first_clean_label(
        _labels_from_artifact(artifact.get("performer_practitioner_labels")),
        _labels_from_artifact(artifact.get("results_interpreter_practitioner_labels")),
    )
    performer_organization = _first_clean_label(
        _labels_from_artifact(artifact.get("performer_organization_labels")),
        _labels_from_artifact(artifact.get("results_interpreter_organization_labels")),
    )
    author_practitioner = _first_clean_label(_labels_from_artifact(artifact.get("author_practitioner_labels")))
    author_organization = _first_clean_label(_labels_from_artifact(artifact.get("author_organization_labels")))
    provider = _first_clean_label(
        participant,
        performer_practitioner,
        author_practitioner,
        artifact.get("practitioner"),
    )
    site = _first_clean_label(
        artifact.get("site"),
        artifact.get("service_provider"),
        _labels_from_artifact(artifact.get("location_labels")),
        performer_organization,
        author_organization,
        artifact.get("provider"),
        source_label,
    )
    if provider == site:
        provider = ""
    return site, provider


def _collection_patient_summary(
    collection_id: str,
    patient_id: str,
    file_path: str,
    fallback_name: str,
) -> PatientSummary:
    """Promote the first Patient resource from upload sources into the facade.

    Published workspace charts keep their stable workspace id, but should still
    surface real demographics from an uploaded FHIR export when present.
    """
    summary = PatientSummary(
        patient_id=patient_id,
        file_path=file_path,
        name=fallback_name,
        gender="workspace",
    )
    try:
        from api.core import harmonize_service

        resources_by_source = harmonize_service.load_collection_resources(collection_id)
    except Exception:
        return summary
    for resources in resources_by_source.values():
        for patient in resources.get("Patient", []):
            if not isinstance(patient, dict):
                continue
            parsed = extract_patient(patient, file_path=file_path)
            parsed.patient_id = patient_id
            parsed.file_path = file_path
            if not parsed.name:
                parsed.name = fallback_name
            return parsed
    return summary


def _summary_has_demographics(summary: PatientSummary) -> bool:
    """True when a summary contains real demographics, not only workspace chrome."""
    return bool(
        summary.birth_date
        or summary.race
        or summary.ethnicity
        or summary.language
        or summary.marital_status
        or summary.city
        or summary.state
        or (summary.gender and summary.gender != "workspace")
    )


def _patient_summary_from_artifacts(
    artifacts: dict[str, Any],
    patient_id: str,
    file_path: str,
    fallback_name: str,
) -> PatientSummary | None:
    """Promote Patient resources embedded in a persisted run artifact."""
    patients = artifacts.get("patients")
    if not isinstance(patients, list):
        return None
    for item in patients:
        if not isinstance(item, dict):
            continue
        resource = item.get("resource")
        if not isinstance(resource, dict):
            continue
        parsed = extract_patient(resource, file_path=file_path)
        parsed.patient_id = patient_id
        parsed.file_path = file_path
        if not parsed.name:
            parsed.name = fallback_name
        return parsed
    return None


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
    site_label: str | None = None,
    provider_label: str | None = None,
) -> str | None:
    if event_dt is None:
        return None
    display_source = _source_display_label(source_label)
    display_site = _first_clean_label(site_label, display_source)
    display_provider = _first_clean_label(
        provider_label,
        _source_practitioner_label(display_site, resource_type),
    )
    key = (display_site, event_dt.date().isoformat())
    encounter = encounter_by_key.get(key)
    if encounter is None:
        encounter_id = _safe_id("enc", f"published-{key[0]}-{key[1]}", len(encounter_by_key))
        event_type, reason_display, class_code = _source_event_type(source_label, resource_type)
        encounter = EncounterRecord(
            encounter_id=encounter_id,
            patient_id=record.summary.patient_id,
            status="finished",
            class_code=class_code,
            encounter_type=event_type,
            reason_display=reason_display,
            period=Period(start=event_dt, end=event_dt),
            provider_org=display_site,
            practitioner_name=display_provider,
        )
        encounter_by_key[key] = encounter
        record.encounters.append(encounter)
    return _link_resource_to_encounter(encounter, resource_type, resource_id)


def _link_resource_to_encounter(
    encounter: EncounterRecord,
    resource_type: str,
    resource_id: str,
) -> str:
    if resource_type == "Observation":
        _append_unique(encounter.linked_observations, resource_id)
    elif resource_type == "Condition":
        _append_unique(encounter.linked_conditions, resource_id)
    elif resource_type == "MedicationRequest":
        _append_unique(encounter.linked_medications, resource_id)
    elif resource_type == "Immunization":
        _append_unique(encounter.linked_immunizations, resource_id)
    elif resource_type == "Procedure":
        _append_unique(encounter.linked_procedures, resource_id)
    elif resource_type == "DiagnosticReport":
        _append_unique(encounter.linked_diagnostic_reports, resource_id)
    return encounter.encounter_id


def _append_unique(items: list[str], value: str) -> None:
    if value and value not in items:
        items.append(value)


def _artifact_source_id(source: dict[str, Any], source_lookup: dict[str, str]) -> str:
    explicit = source.get("source_id")
    if explicit:
        return str(explicit)
    document_reference = source.get("document_reference")
    if isinstance(document_reference, str) and document_reference in source_lookup:
        return source_lookup[document_reference]
    source_label = source.get("source_label")
    if isinstance(source_label, str) and source_label in source_lookup:
        return source_lookup[source_label]
    return ""


def _dated_artifact_encounter(
    artifact_encounter_by_date: dict[tuple[str, str], EncounterRecord],
    source_id: str,
    event_dt: datetime | None,
) -> EncounterRecord | None:
    if not source_id or event_dt is None:
        return None
    return artifact_encounter_by_date.get((source_id, event_dt.date().isoformat()))


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


def load_active_published_run(patient_id: str) -> dict[str, Any] | None:
    """Public read helper for the active published harmonization artifact."""
    return _load_active_published_run(patient_id)


def _record_from_published_run(patient_id: str, run: dict[str, Any]) -> tuple[PatientRecord, PatientStats]:
    """Convert a published harmonization artifact into the shared PatientRecord shape.

    This is intentionally a read facade, not a new parser. It lets existing
    downstream modules consume the published canonical chart without knowing
    whether the source was Synthea, an uploaded FHIR export, or PDF extraction.
    """
    collection_name = str(run.get("collection_name") or patient_id)
    display_name = collection_name.removesuffix(" — patient workspace")
    collection_id = str(run.get("collection_id") or "")
    artifact_path = str(run.get("artifact_path") or "")
    candidate = run.get("candidate_record") if isinstance(run.get("candidate_record"), dict) else {}
    artifacts = candidate.get("clinical_artifacts") if isinstance(candidate.get("clinical_artifacts"), dict) else {}
    summary = _collection_patient_summary(
        collection_id,
        patient_id,
        artifact_path,
        display_name,
    )
    if not _summary_has_demographics(summary):
        summary = _patient_summary_from_artifacts(artifacts, patient_id, artifact_path, display_name) or summary
    record = PatientRecord(summary=summary)
    encounter_by_key: dict[tuple[str, str], EncounterRecord] = {}
    artifact_encounter_by_key: dict[tuple[str, str], EncounterRecord] = {}
    artifact_encounter_by_date: dict[tuple[str, str], EncounterRecord] = {}
    observation_artifact_by_key: dict[tuple[str, str], dict[str, Any]] = {}
    observation_artifact_by_ref: dict[tuple[str, str], dict[str, Any]] = {}
    source_lookup: dict[str, str] = {}
    source_provider_lookup: dict[str, tuple[str, str]] = {}

    for doc in artifacts.get("documents") or []:
        if not isinstance(doc, dict):
            continue
        source_id = str(doc.get("source_id") or "")
        if not source_id:
            continue
        document_reference = doc.get("document_reference")
        if isinstance(document_reference, str) and document_reference:
            source_lookup[document_reference] = source_id
        source_label = doc.get("source_label")
        if isinstance(source_label, str) and source_label:
            source_lookup[source_label] = source_id
        source_provider_lookup[source_id] = _artifact_provider_site(doc, source_id)

    for idx, enc in enumerate(artifacts.get("encounters") or []):
        if not isinstance(enc, dict):
            continue
        source_id = str(enc.get("source_id") or "")
        raw_id = str(enc.get("id") or "")
        encounter_id = _safe_id("enc", f"{source_id}-{raw_id}", idx)
        start = _parse_dt(enc.get("period_start"))
        end = _parse_dt(enc.get("period_end")) or start
        site, provider = _artifact_provider_site(enc, source_id)
        encounter_record = EncounterRecord(
            encounter_id=encounter_id,
            patient_id=patient_id,
            status=str(enc.get("status") or "finished"),
            class_code=str(enc.get("class_code") or "DOC"),
            encounter_type=str(enc.get("type") or "Source encounter"),
            reason_display=str(enc.get("reason") or ""),
            period=Period(start=start, end=end),
            provider_org=site,
            practitioner_name=provider,
        )
        record.encounters.append(encounter_record)
        if raw_id:
            artifact_encounter_by_key[(source_id, raw_id)] = encounter_record
        if source_id and start:
            artifact_encounter_by_date.setdefault(
                (source_id, start.date().isoformat()),
                encounter_record,
            )

    for observation_artifact in artifacts.get("observations") or []:
        if not isinstance(observation_artifact, dict):
            continue
        source_id = str(observation_artifact.get("source_id") or "")
        raw_id = str(observation_artifact.get("id") or "")
        if not source_id or not raw_id:
            continue
        observation_artifact_by_key[(source_id, raw_id)] = observation_artifact
        observation_artifact_by_ref[(source_id, f"Observation/{raw_id}")] = observation_artifact

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
            value_quantity = _numeric_value(raw_value)
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
                reference_low=_numeric_value(source.get("reference_low")),
                reference_high=_numeric_value(source.get("reference_high")),
                reference_unit=str(source.get("reference_unit") or unit or ""),
            )
            source_id = _artifact_source_id(source, source_lookup)
            source_ref = str(source.get("source_observation_ref") or "")
            observation_artifact = observation_artifact_by_ref.get((source_id, source_ref))
            if observation_artifact is None and source_ref.startswith("Observation/"):
                observation_artifact = observation_artifact_by_key.get((source_id, source_ref.rsplit("/", 1)[-1]))
            artifact_encounter = None
            raw_encounter_id = str((observation_artifact or {}).get("encounter_id") or "")
            if raw_encounter_id:
                artifact_encounter = artifact_encounter_by_key.get((source_id, raw_encounter_id))
            if artifact_encounter is None:
                artifact_encounter = _dated_artifact_encounter(
                    artifact_encounter_by_date,
                    source_id,
                    effective_dt,
                )
            if artifact_encounter is not None:
                record_obs.encounter_id = _link_resource_to_encounter(
                    artifact_encounter,
                    "Observation",
                    obs_id,
                )
            else:
                site, provider = ("", "")
                if observation_artifact is not None:
                    site, provider = _artifact_provider_site(observation_artifact, source_id)
                if not site and not provider:
                    site, provider = source_provider_lookup.get(source_id, ("", ""))
                record_obs.encounter_id = _add_encounter(
                    record,
                    encounter_by_key,
                    str(source.get("source_label") or "Published chart"),
                    effective_dt,
                    "Observation",
                    obs_id,
                    site_label=site,
                    provider_label=provider,
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
        source_id = _artifact_source_id(source, source_lookup)
        artifact_encounter = _dated_artifact_encounter(
            artifact_encounter_by_date,
            source_id,
            onset_dt,
        )
        if artifact_encounter is not None:
            condition_record.encounter_id = _link_resource_to_encounter(
                artifact_encounter,
                "Condition",
                condition_id,
            )
        else:
            condition_record.encounter_id = _add_encounter(
                record,
                encounter_by_key,
                str(source.get("source_label") or "Published chart"),
                onset_dt,
                "Condition",
                condition_id,
                site_label=source_provider_lookup.get(source_id, ("", ""))[0],
                provider_label=source_provider_lookup.get(source_id, ("", ""))[1],
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
        source_id = _artifact_source_id(source, source_lookup)
        artifact_encounter = _dated_artifact_encounter(
            artifact_encounter_by_date,
            source_id,
            authored_on,
        )
        if artifact_encounter is not None:
            medication_record.encounter_id = _link_resource_to_encounter(
                artifact_encounter,
                "MedicationRequest",
                med_id,
            )
        else:
            medication_record.encounter_id = _add_encounter(
                record,
                encounter_by_key,
                str(source.get("source_label") or "Published chart"),
                authored_on,
                "MedicationRequest",
                med_id,
                site_label=source_provider_lookup.get(source_id, ("", ""))[0],
                provider_label=source_provider_lookup.get(source_id, ("", ""))[1],
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
        source_id = _artifact_source_id(source, source_lookup)
        artifact_encounter = _dated_artifact_encounter(
            artifact_encounter_by_date,
            source_id,
            occurrence_dt,
        )
        if artifact_encounter is not None:
            imm_record.encounter_id = _link_resource_to_encounter(
                artifact_encounter,
                "Immunization",
                imm_id,
            )
        else:
            imm_record.encounter_id = _add_encounter(
                record,
                encounter_by_key,
                str(source.get("source_label") or "Published chart"),
                occurrence_dt,
                "Immunization",
                imm_id,
                site_label=source_provider_lookup.get(source_id, ("", ""))[0],
                provider_label=source_provider_lookup.get(source_id, ("", ""))[1],
            )
        record.immunizations.append(imm_record)

    for idx, procedure in enumerate(artifacts.get("procedures") or []):
        if not isinstance(procedure, dict):
            continue
        start = _parse_dt(procedure.get("performed_start"))
        end = _parse_dt(procedure.get("performed_end")) or start
        procedure_id = _safe_id("procedure", f"{procedure.get('source_id')}-{procedure.get('id')}", idx)
        procedure_record = ProcedureRecord(
            procedure_id=procedure_id,
            patient_id=patient_id,
            status=str(procedure.get("status") or "completed"),
            code=CodeableConcept(
                system=str(procedure.get("system") or ""),
                code=str(procedure.get("code") or ""),
                display=str(procedure.get("display") or "Procedure"),
            ),
            performed_period=Period(start=start, end=end),
            reason_display=str(procedure.get("reason") or ""),
        )
        source_id = str(procedure.get("source_id") or "")
        encounter = artifact_encounter_by_key.get((source_id, str(procedure.get("encounter_id") or "")))
        if encounter is None:
            encounter = _dated_artifact_encounter(artifact_encounter_by_date, source_id, start)
        if encounter is not None:
            procedure_record.encounter_id = _link_resource_to_encounter(
                encounter,
                "Procedure",
                procedure_id,
            )
        else:
            site, provider = _artifact_provider_site(procedure, source_id)
            procedure_record.encounter_id = _add_encounter(
                record,
                encounter_by_key,
                str(procedure.get("source_label") or "Published chart"),
                start,
                "Procedure",
                procedure_id,
                site_label=site,
                provider_label=provider,
            )
        record.procedures.append(procedure_record)

    for idx, report in enumerate(artifacts.get("diagnostic_reports") or []):
        if not isinstance(report, dict):
            continue
        effective_dt = _parse_dt(report.get("effective_date"))
        report_id = _safe_id("diagnostic-report", f"{report.get('source_id')}-{report.get('id')}", idx)
        result_refs = [str(ref) for ref in report.get("result_refs") or [] if ref]
        diagnostic_report = DiagnosticReportRecord(
            report_id=report_id,
            patient_id=patient_id,
            category=str(report.get("category") or ""),
            status=str(report.get("status") or "final"),
            code=CodeableConcept(
                system=str(report.get("system") or ""),
                code=str(report.get("code") or ""),
                display=str(report.get("display") or "Diagnostic report"),
            ),
            effective_dt=effective_dt,
            result_refs=result_refs,
            has_presented_form=bool(report.get("has_presented_form")),
            presented_form_text=str(report.get("presented_form_text") or ""),
        )
        source_id = str(report.get("source_id") or "")
        encounter = artifact_encounter_by_key.get((source_id, str(report.get("encounter_id") or "")))
        if encounter is None:
            encounter = _dated_artifact_encounter(artifact_encounter_by_date, source_id, effective_dt)
        if encounter is not None:
            diagnostic_report.encounter_id = _link_resource_to_encounter(
                encounter,
                "DiagnosticReport",
                report_id,
            )
        else:
            site, provider = _artifact_provider_site(report, source_id)
            diagnostic_report.encounter_id = _add_encounter(
                record,
                encounter_by_key,
                str(report.get("source_label") or "Published chart"),
                effective_dt,
                "DiagnosticReport",
                report_id,
                site_label=site,
                provider_label=provider,
            )
        record.diagnostic_reports.append(diagnostic_report)

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
        "Procedure": len(record.procedures),
        "DiagnosticReport": len(record.diagnostic_reports),
        "AllergyIntolerance": len(record.allergies),
        "Immunization": len(record.immunizations),
    }
    record.resource_type_counts = {key: value for key, value in record.resource_type_counts.items() if value > 0}
    record.parse_warnings.append("Loaded from active published harmonization snapshot.")
    return record, compute_patient_stats(record)


@lru_cache(maxsize=30)
def _cached_load(path_str: str) -> tuple[PatientRecord, PatientStats]:
    """Parse bundle and compute stats. Cached by the bundle's absolute path
    so the same physical file resolves to the same cache entry regardless of
    which patient-id shape the caller used."""
    record = parse_bundle(path_str)
    stats = compute_patient_stats(record)
    return record, stats


def load_patient(patient_id: str) -> tuple[PatientRecord, PatientStats] | None:
    """Load and parse a patient bundle by ID. Returns None if not found. Cached.

    Accepts both the canonical filename stem and a bare Patient.id — both
    resolve to the same ``_cached_load`` entry via the bundle's absolute path
    so the LRU cache is never double-populated for the same physical patient.
    """
    published_run = _load_active_published_run(patient_id)
    if published_run is not None:
        return _record_from_published_run(patient_id, published_run)

    path = path_from_patient_id(patient_id)
    if path is None:
        return None
    return _cached_load(str(path))
