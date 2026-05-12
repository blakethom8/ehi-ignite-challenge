"""Ingest patient-voice FHIR bundles into the cross-source harmonizer.

The T1 adapter writes patient-voice FHIR resources to
``data/patient-context/<patient>/fhir/<session_id>.json``. This module
enumerates those bundles for a given patient and yields
:class:`~lib.harmonize.observations.SourceBundle` instances the existing
harmonizer can consume.

Resource-type mapping
---------------------

The harmonizer's per-resource matchers expect specific FHIR shapes:

- ``merge_medications`` reads ``MedicationRequest`` resources, but the
  patient-voice adapter emits ``MedicationStatement`` (the FHIR-correct
  shape for patient-asserted use). We convert here.
- ``merge_conditions``, ``merge_observations`` accept their native
  types directly.
- ``Goal`` has no merge target in Phase 1 and is skipped.

The conversion preserves ``meta.source`` so
``lib.harmonize.source_weights`` can identify patient-voice
contributors at merge time.

Identity / safety
-----------------

Bundles are filtered to entries whose ``subject.reference`` matches
``Patient/<patient_id>``. A bundle that contains resources for a
different patient (shouldn't happen, but guard anyway) is skipped at
the entry level — the rest of the bundle is still ingested.
"""

from __future__ import annotations

import json
import logging
import os
import re
from pathlib import Path
from typing import Any, Iterable

from lib.harmonize.observations import SourceBundle


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_STORE_ROOT = Path(
    os.getenv("PATIENT_CONTEXT_STORE_PATH", REPO_ROOT / "data" / "patient-context")
)


# Label surfaced on every patient-voice MedicationSource /
# ObservationSource. Matches the value emitted by the T1 adapter so the
# UI renders consistent chips regardless of which layer constructed the
# bundle.
PATIENT_VOICE_LABEL = "Patient (self-reported)"


_logger = logging.getLogger(__name__)


def _safe_id(value: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "-", value).strip(".-")
    return safe[:120] or "patient"


def patient_voice_source_bundles(
    patient_id: str,
    *,
    resource_type: str,
    store_root: Path | None = None,
) -> list[SourceBundle]:
    """Return SourceBundles of patient-voice resources for ``resource_type``.

    ``resource_type`` is the harmonizer's expected FHIR type
    (``"MedicationRequest"``, ``"Condition"``, ``"Observation"``).
    For ``MedicationRequest`` we convert the bundle's
    ``MedicationStatement`` entries; for the others we pass the
    entries through unchanged.

    Returns an empty list when no patient-voice FHIR is on disk for
    this patient, or when the patient-voice bundle contains nothing of
    the requested resource type.
    """
    if resource_type not in {"MedicationRequest", "Condition", "Observation"}:
        return []

    root = (store_root or DEFAULT_STORE_ROOT) / _safe_id(patient_id) / "fhir"
    if not root.exists():
        return []

    patient_ref = f"Patient/{patient_id}"
    bundles: list[SourceBundle] = []

    for bundle_path in sorted(root.glob("*.json")):
        try:
            payload = json.loads(bundle_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            _logger.warning("patient_voice bundle %s unreadable: %s", bundle_path, exc)
            continue
        if not isinstance(payload, dict) or payload.get("resourceType") != "Bundle":
            continue

        items = list(_resources_for_type(payload, resource_type, patient_ref=patient_ref))
        if not items:
            continue

        # Carry the bundle's meta.source through onto each resource
        # so the harmonizer's source-weight lookup can see it even on
        # resources that didn't already carry meta. Most do (the T1
        # adapter populates them), but be defensive.
        bundle_source = (payload.get("meta") or {}).get("source")
        if bundle_source:
            for r in items:
                meta = r.setdefault("meta", {})
                meta.setdefault("source", bundle_source)

        bundles.append(
            SourceBundle(
                label=PATIENT_VOICE_LABEL,
                observations=items,
                document_reference=None,
            )
        )

    return bundles


def _resources_for_type(
    bundle: dict[str, Any],
    resource_type: str,
    *,
    patient_ref: str,
) -> Iterable[dict[str, Any]]:
    """Yield resources of ``resource_type`` from a FHIR Bundle.

    Filters by ``subject.reference`` matching ``patient_ref`` for safety.
    Applies the MedicationStatement → MedicationRequest conversion.
    """
    for entry in bundle.get("entry") or []:
        if not isinstance(entry, dict):
            continue
        resource = entry.get("resource")
        if not isinstance(resource, dict):
            continue
        if not _subject_matches(resource, patient_ref):
            continue
        emitted_type = resource.get("resourceType")
        if resource_type == "MedicationRequest" and emitted_type == "MedicationStatement":
            yield _medication_statement_to_request(resource)
        elif emitted_type == resource_type:
            yield resource


def _subject_matches(resource: dict[str, Any], patient_ref: str) -> bool:
    subject = resource.get("subject") or {}
    ref = subject.get("reference")
    if not isinstance(ref, str):
        return False
    return ref == patient_ref


def _medication_statement_to_request(stmt: dict[str, Any]) -> dict[str, Any]:
    """Convert a patient-asserted MedicationStatement to MedicationRequest shape.

    Phase 1 adapter: keeps id, status, medicationCodeableConcept,
    subject, note, and meta intact. Maps ``dateAsserted`` →
    ``authoredOn`` so ``_extract_authored_on`` finds the right field.
    Drops ``informationSource`` (the harmonizer doesn't need it; the
    Provenance graph carries the patient identity via meta.source).

    A status of ``"stopped"`` carries through unchanged — both
    MedicationRequest and MedicationStatement use that value per FHIR.
    """
    return {
        "resourceType": "MedicationRequest",
        "id": stmt.get("id"),
        "status": stmt.get("status"),
        "medicationCodeableConcept": stmt.get("medicationCodeableConcept"),
        "subject": stmt.get("subject"),
        "authoredOn": stmt.get("dateAsserted"),
        "note": stmt.get("note"),
        "meta": stmt.get("meta"),
    }
