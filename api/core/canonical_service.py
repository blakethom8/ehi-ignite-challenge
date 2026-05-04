"""Canonical patient workspace read facade.

The physical sources can be Synthea bundles, uploaded FHIR pulls, parsed PDFs,
or future off-server stores. This module presents the application-level summary
as one patient workspace so downstream screens do not need to know that detail.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from api.core import harmonize_service
from api.core.loader import load_patient
from api.models import CanonicalPatientSummary, CanonicalSourceSummary


PREPARED_STATUSES = {"structured", "extracted"}
NEEDS_PREPARATION_STATUSES = {
    "unparsed_structured",
    "pending_extraction",
    "empty_extraction",
    "missing",
}


def _date_from_resource(resource: dict[str, Any]) -> str | None:
    for key in (
        "effectiveDateTime",
        "onsetDateTime",
        "authoredOn",
        "occurrenceDateTime",
        "recordedDate",
        "issued",
    ):
        value = resource.get(key)
        if isinstance(value, str) and value:
            return value[:10]
    period = resource.get("period")
    if isinstance(period, dict):
        start = period.get("start")
        if isinstance(start, str) and start:
            return start[:10]
    return None


def _resource_date_span(resources_by_source: dict[str, dict[str, list[dict]]]) -> tuple[str | None, str | None]:
    dates: list[str] = []
    for resources_by_type in resources_by_source.values():
        for resources in resources_by_type.values():
            dates.extend(date for resource in resources if (date := _date_from_resource(resource)))
    if not dates:
        return None, None
    return min(dates), max(dates)


def _format_dt(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date().isoformat()
    return str(value)[:10]


def canonical_patient_summary(patient_id: str) -> CanonicalPatientSummary:
    workspace_id = harmonize_service.workspace_collection_id(patient_id)
    collection = harmonize_service.patient_workspace_collection(patient_id)
    manifest = harmonize_service.collection_source_manifest(workspace_id) if collection else []
    manifest = manifest or []
    resources = harmonize_service.load_collection_resources(workspace_id) if collection else {}

    resource_counts: dict[str, int] = {}
    for resources_by_type in resources.values():
        for resource_type, typed_resources in resources_by_type.items():
            resource_counts[resource_type] = resource_counts.get(resource_type, 0) + len(typed_resources)

    patient_name = patient_id
    encounter_count = resource_counts.get("Encounter", 0)
    date_start, date_end = _resource_date_span(resources)
    fallback_modes: list[str] = []

    loaded = load_patient(patient_id)
    if loaded is not None:
        _record, stats = loaded
        patient_name = stats.name
        encounter_count = stats.encounter_count
        date_start = _format_dt(stats.earliest_encounter_dt) or date_start
        date_end = _format_dt(stats.latest_encounter_dt) or date_end
        fallback_modes.append("synthea-baseline")

    prepared_source_count = sum(1 for source in manifest if source["status"] in PREPARED_STATUSES)
    needs_preparation_count = sum(1 for source in manifest if source["status"] in NEEDS_PREPARATION_STATUSES)
    observation_conflicts = 0
    if collection is not None:
        observation_conflicts = sum(1 for item in harmonize_service.merged_observations(workspace_id) if item.has_conflict)

    if any(source["kind"] == "extracted-pdf" for source in manifest):
        fallback_modes.append("uploaded-pdf-extractions")
    if any(source["kind"] == "fhir-pull" and source["id"] != "synthea-fhir" for source in manifest):
        fallback_modes.append("uploaded-fhir-pulls")

    return CanonicalPatientSummary(
        patient_id=patient_id,
        patient_name=patient_name,
        workspace_id=workspace_id,
        source_count=len(manifest),
        prepared_source_count=prepared_source_count,
        needs_preparation_count=needs_preparation_count,
        total_resources=sum(resource_counts.values()),
        canonical_observation_count=resource_counts.get("Observation", 0),
        canonical_condition_count=resource_counts.get("Condition", 0),
        canonical_medication_count=resource_counts.get("MedicationRequest", 0) + resource_counts.get("Medication", 0),
        canonical_allergy_count=resource_counts.get("AllergyIntolerance", 0),
        canonical_immunization_count=resource_counts.get("Immunization", 0),
        encounter_count=encounter_count,
        review_item_count=needs_preparation_count + observation_conflicts,
        date_start=date_start,
        date_end=date_end,
        storage_mode="server-local-workspace",
        storage_description=(
            "Prototype workspace storage on the application server. Downstream "
            "screens read this canonical facade so source files can later move "
            "to cloud storage, patient-controlled vaults, or partner systems."
        ),
        sources=[CanonicalSourceSummary(**source) for source in manifest],
        fallback_modes=fallback_modes,
    )
