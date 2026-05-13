"""Patient Context session → FHIR Bundle.

Public entry point: :func:`session_to_fhir_bundle`. Accepts a dumped
``PatientContextSessionResponse`` (i.e. ``session.model_dump(mode='json')``)
and returns a FHIR R4 Bundle (``type='collection'``) ready for ingest by
``lib.harmonize``.

Worked examples for each emitted resource type live in
``docs/architecture/context/LLM-CONTEXT-AUGMENTATION-PLAN.md`` §3.1.

Atlas extension URLs used by emitted resources:

- ``http://atlas.healthcaredataai.com/fhir/StructureDefinition/source-label``
- ``http://atlas.healthcaredataai.com/fhir/StructureDefinition/source-locator``

Identification convention:
``id = "pv-<session_id>-<turn_id>-<seq>"``. ``seq`` is always ``"0"`` for
single-resource turns; the field exists so a future classifier that
emits multiple resources per turn (e.g. ``"started fish oil and stopped
lisinopril"``) can disambiguate.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping

from .classifier import (
    FakeTurnClassifier,
    TurnClassification,
    TurnClassifier,
)


SOURCE_LABEL_URL = "http://atlas.healthcaredataai.com/fhir/StructureDefinition/source-label"
SOURCE_LOCATOR_URL = "http://atlas.healthcaredataai.com/fhir/StructureDefinition/source-locator"

PATIENT_VOICE_CODE_SYSTEM = (
    "http://atlas.healthcaredataai.com/fhir/CodeSystem/patient-voice"
)

# Patient self-report is the source label we surface in the UI and on
# every Provenance entity originating from the patient.
PATIENT_VOICE_SOURCE_LABEL = "Patient (self-reported)"


def session_to_fhir_bundle(
    session_dict: Mapping[str, Any],
    *,
    classifier: TurnClassifier | None = None,
    today_iso: str | None = None,
) -> dict[str, Any]:
    """Convert a patient-context session into a FHIR ``collection`` Bundle.

    Parameters
    ----------
    session_dict:
        ``PatientContextSessionResponse.model_dump(mode='json')``. Must
        carry ``session_id``, ``patient_id``, ``turns`` and ``gap_cards``.
    classifier:
        Optional turn classifier. Defaults to a :class:`FakeTurnClassifier`
        that returns ``kind='generic'`` for every turn — convenient for
        unit tests that don't need real classification. Production
        callers pass :class:`HaikuTurnClassifier`.
    today_iso:
        ISO-8601 date string the classifier uses for relative-time
        phrases ("3 weeks ago"). Defaults to today (UTC).

    Returns
    -------
    A FHIR R4 Bundle dict with ``resourceType='Bundle'`` and
    ``type='collection'``. The ``entry`` list contains one FHIR resource
    per patient turn (assistant turns are ignored). Bundle is empty
    (``entry=[]``) when the session has no patient turns.
    """
    session_id = str(session_dict["session_id"])
    patient_id = str(session_dict["patient_id"])
    turns = list(session_dict.get("turns", []) or [])
    gaps = {g["id"]: g for g in (session_dict.get("gap_cards") or []) if isinstance(g, dict)}
    cls = classifier or FakeTurnClassifier()
    today = today_iso or datetime.now(timezone.utc).date().isoformat()

    patient_ref = f"Patient/{patient_id}"
    source_meta_uri = f"patient-context://{session_id}"

    entries: list[dict[str, Any]] = []
    for turn in turns:
        if not isinstance(turn, Mapping):
            continue
        if turn.get("role") != "patient":
            continue
        turn_id = str(turn.get("id") or "")
        content = str(turn.get("content") or "").strip()
        if not turn_id or not content:
            continue
        gap_id = turn.get("linked_gap_id")
        gap = gaps.get(gap_id) if isinstance(gap_id, str) else None
        gap_title = (gap or {}).get("title", "")
        gap_prompt = (gap or {}).get("prompt", "")
        created_at = _parse_iso(turn.get("created_at"))

        classification = cls.classify(
            turn_id=turn_id,
            turn_content=content,
            gap_title=gap_title,
            gap_prompt=gap_prompt,
            today_iso=today,
        )

        resource = _resource_for_classification(
            classification=classification,
            session_id=session_id,
            turn_id=turn_id,
            gap_id=gap_id if isinstance(gap_id, str) else None,
            patient_ref=patient_ref,
            source_meta_uri=source_meta_uri,
            turn_content=content,
            turn_created_at=created_at,
        )
        if resource is not None:
            entries.append({"resource": resource})

    return {
        "resourceType": "Bundle",
        "type": "collection",
        "meta": {"source": source_meta_uri},
        "entry": entries,
    }


# ---------------------------------------------------------------------------
# Per-kind resource builders
# ---------------------------------------------------------------------------


def _resource_for_classification(
    *,
    classification: TurnClassification,
    session_id: str,
    turn_id: str,
    gap_id: str | None,
    patient_ref: str,
    source_meta_uri: str,
    turn_content: str,
    turn_created_at: datetime,
) -> dict[str, Any] | None:
    seq = 0
    resource_id = f"pv-{session_id}-{turn_id}-{seq}"
    locator = _source_locator(session_id=session_id, turn_id=turn_id, gap_id=gap_id)
    meta = _meta(source_meta_uri=source_meta_uri, locator=locator)

    if classification.kind == "med_statement":
        if not classification.drug_text or not classification.status:
            return _generic_observation(
                resource_id=resource_id,
                patient_ref=patient_ref,
                meta=meta,
                turn_content=turn_content,
                turn_created_at=turn_created_at,
            )
        med: dict[str, Any] = {
            "resourceType": "MedicationStatement",
            "id": resource_id,
            "status": classification.status,
            "medicationCodeableConcept": {"text": classification.drug_text},
            "subject": {"reference": patient_ref},
            "informationSource": {"reference": patient_ref},
            "dateAsserted": _iso_with_tz(turn_created_at),
            "note": [{"text": turn_content}],
            "meta": meta,
        }
        if classification.status == "stopped" and classification.effective_end_iso:
            med["effectivePeriod"] = {"end": classification.effective_end_iso}
        return med

    if classification.kind == "condition":
        if not classification.condition_text:
            return _generic_observation(
                resource_id=resource_id,
                patient_ref=patient_ref,
                meta=meta,
                turn_content=turn_content,
                turn_created_at=turn_created_at,
            )
        condition: dict[str, Any] = {
            "resourceType": "Condition",
            "id": resource_id,
            "verificationStatus": {
                "coding": [
                    {
                        "system": "http://terminology.hl7.org/CodeSystem/condition-ver-status",
                        "code": "unconfirmed",
                    }
                ]
            },
            "code": {"text": classification.condition_text},
            "subject": {"reference": patient_ref},
            "recorder": {"reference": patient_ref},
            "note": [{"text": turn_content}],
            "meta": meta,
        }
        if classification.onset_period:
            start, end = classification.onset_period
            condition["onsetPeriod"] = {"start": start, "end": end}
        return condition

    if classification.kind == "goal":
        if not classification.goal_text:
            return _generic_observation(
                resource_id=resource_id,
                patient_ref=patient_ref,
                meta=meta,
                turn_content=turn_content,
                turn_created_at=turn_created_at,
            )
        return {
            "resourceType": "Goal",
            "id": resource_id,
            "lifecycleStatus": "active",
            "description": {"text": classification.goal_text},
            "subject": {"reference": patient_ref},
            "expressedBy": {"reference": patient_ref},
            "note": [{"text": turn_content}],
            "meta": meta,
        }

    # generic fallback
    return _generic_observation(
        resource_id=resource_id,
        patient_ref=patient_ref,
        meta=meta,
        turn_content=turn_content,
        turn_created_at=turn_created_at,
    )


def _generic_observation(
    *,
    resource_id: str,
    patient_ref: str,
    meta: dict[str, Any],
    turn_content: str,
    turn_created_at: datetime,
) -> dict[str, Any]:
    return {
        "resourceType": "Observation",
        "id": resource_id,
        "status": "final",
        "code": {
            "coding": [
                {"system": PATIENT_VOICE_CODE_SYSTEM, "code": "patient-claim"}
            ]
        },
        "category": [
            {
                "coding": [
                    {
                        "system": "http://terminology.hl7.org/CodeSystem/observation-category",
                        "code": "survey",
                    }
                ]
            }
        ],
        "subject": {"reference": patient_ref},
        "effectiveDateTime": _iso_with_tz(turn_created_at),
        "valueString": turn_content,
        "meta": meta,
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _meta(*, source_meta_uri: str, locator: str) -> dict[str, Any]:
    return {
        "source": source_meta_uri,
        "extension": [
            {"url": SOURCE_LABEL_URL, "valueString": PATIENT_VOICE_SOURCE_LABEL},
            {"url": SOURCE_LOCATOR_URL, "valueString": locator},
        ],
    }


def _source_locator(*, session_id: str, turn_id: str, gap_id: str | None) -> str:
    parts = [f"session={session_id}", f"turn={turn_id}"]
    if gap_id:
        parts.append(f"gap={gap_id}")
    return ";".join(parts)


def _parse_iso(value: Any) -> datetime:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value
    if isinstance(value, str):
        cleaned = value.replace("Z", "+00:00")
        try:
            parsed = datetime.fromisoformat(cleaned)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed
        except ValueError:
            pass
    return datetime.now(timezone.utc)


def _iso_with_tz(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()
