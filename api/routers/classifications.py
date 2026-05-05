"""
/api/classifications — patient classification categories and raw FHIR data.
"""

from __future__ import annotations

import base64
import json
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

from lib.fhir_parser.models import PatientRecord

from api.core.loader import load_patient, path_from_patient_id

router = APIRouter()

_REPO_ROOT = Path(__file__).parent.parent.parent
_CLASSIFICATIONS_PATH = _REPO_ROOT / "scripts" / "patient_classifications.json"

# Load classifications once at import time
_classifications: dict | None = None


def _load_classifications() -> dict:
    global _classifications
    if _classifications is None:
        if _CLASSIFICATIONS_PATH.exists():
            _classifications = json.loads(_CLASSIFICATIONS_PATH.read_text())
        else:
            _classifications = {"categories": {}, "population_stats": {}}
    return _classifications


@router.get("/classifications")
def get_classifications() -> dict:
    """Return patient classification categories with counts and best examples."""
    return _load_classifications()


@router.get("/patients/{patient_id}/fhir")
def get_raw_fhir(patient_id: str) -> JSONResponse:
    """Return the raw FHIR bundle JSON for a patient."""
    path = path_from_patient_id(patient_id)
    if path is not None:
        bundle = json.loads(path.read_text())
        return JSONResponse(content=bundle)

    loaded = load_patient(patient_id)
    if loaded is None:
        raise HTTPException(status_code=404, detail="Patient not found")
    bundle = _record_to_bundle(loaded[0])
    return JSONResponse(content=bundle)


def _iso(value) -> str | None:
    return value.isoformat() if value else None


def _coding(system: str, code: str, display: str) -> list[dict]:
    if not code and not display:
        return []
    return [{"system": system, "code": code, "display": display}]


def _record_to_bundle(record: PatientRecord) -> dict:
    """Serialize a loader PatientRecord facade into a minimal FHIR-ish bundle.

    Uploaded workspaces do not have one original portal-export JSON file after
    publish; the published harmonized chart is the durable source. This keeps the
    raw FHIR explorer tab usable by exposing the same canonical resources the
    downstream chart views read.
    """
    patient_id = record.summary.patient_id
    entries: list[dict] = [
        {
            "resource": {
                "resourceType": "Patient",
                "id": patient_id,
                "name": [{"text": record.summary.name}] if record.summary.name else [],
                "gender": record.summary.gender or "unknown",
                "birthDate": record.summary.birth_date.isoformat() if record.summary.birth_date else None,
            }
        }
    ]

    for enc in record.encounters:
        entries.append(
            {
                "resource": {
                    "resourceType": "Encounter",
                    "id": enc.encounter_id,
                    "status": enc.status or "finished",
                    "class": {"code": enc.class_code or "DOC"},
                    "type": [{"text": enc.encounter_type}] if enc.encounter_type else [],
                    "reasonCode": [{"text": enc.reason_display}] if enc.reason_display else [],
                    "subject": {"reference": f"Patient/{patient_id}"},
                    "period": {"start": _iso(enc.period.start), "end": _iso(enc.period.end)},
                    "serviceProvider": {"display": enc.provider_org} if enc.provider_org else None,
                }
            }
        )

    for obs in record.observations:
        resource = {
            "resourceType": "Observation",
            "id": obs.obs_id,
            "status": obs.status or "final",
            "category": [{"text": obs.category}] if obs.category else [],
            "code": {
                "coding": _coding("http://loinc.org", obs.loinc_code, obs.display),
                "text": obs.display,
            },
            "subject": {"reference": f"Patient/{patient_id}"},
            "effectiveDateTime": _iso(obs.effective_dt),
            "encounter": {"reference": f"Encounter/{obs.encounter_id}"} if obs.encounter_id else None,
        }
        if obs.value_quantity is not None:
            resource["valueQuantity"] = {"value": obs.value_quantity, "unit": obs.value_unit}
        elif obs.value_concept_display:
            resource["valueCodeableConcept"] = {"text": obs.value_concept_display}
        entries.append({"resource": resource})

    for condition in record.conditions:
        entries.append(
            {
                "resource": {
                    "resourceType": "Condition",
                    "id": condition.condition_id,
                    "clinicalStatus": {"text": condition.clinical_status},
                    "verificationStatus": {"text": condition.verification_status},
                    "code": {
                        "coding": _coding(condition.code.system, condition.code.code, condition.code.display),
                        "text": condition.code.label(),
                    },
                    "subject": {"reference": f"Patient/{patient_id}"},
                    "encounter": {"reference": f"Encounter/{condition.encounter_id}"} if condition.encounter_id else None,
                    "onsetDateTime": _iso(condition.onset_dt),
                    "abatementDateTime": _iso(condition.abatement_dt),
                    "recordedDate": _iso(condition.recorded_dt),
                }
            }
        )

    for medication in record.medications:
        entries.append(
            {
                "resource": {
                    "resourceType": "MedicationRequest",
                    "id": medication.med_id,
                    "status": medication.status or "unknown",
                    "intent": "order",
                    "medicationCodeableConcept": {
                        "coding": _coding("http://www.nlm.nih.gov/research/umls/rxnorm", medication.rxnorm_code, medication.display),
                        "text": medication.display,
                    },
                    "subject": {"reference": f"Patient/{patient_id}"},
                    "encounter": {"reference": f"Encounter/{medication.encounter_id}"} if medication.encounter_id else None,
                    "authoredOn": _iso(medication.authored_on),
                    "dosageInstruction": [{"text": medication.dosage_text}] if medication.dosage_text else [],
                }
            }
        )

    for allergy in record.allergies:
        entries.append(
            {
                "resource": {
                    "resourceType": "AllergyIntolerance",
                    "id": allergy.allergy_id,
                    "clinicalStatus": {"text": allergy.clinical_status},
                    "type": allergy.allergy_type or None,
                    "category": allergy.categories,
                    "criticality": allergy.criticality or None,
                    "code": {
                        "coding": _coding(allergy.code.system, allergy.code.code, allergy.code.display),
                        "text": allergy.code.label(),
                    },
                    "patient": {"reference": f"Patient/{patient_id}"},
                    "onsetDateTime": _iso(allergy.onset_dt),
                    "recordedDate": _iso(allergy.recorded_date),
                }
            }
        )

    for immunization in record.immunizations:
        entries.append(
            {
                "resource": {
                    "resourceType": "Immunization",
                    "id": immunization.imm_id,
                    "status": immunization.status or "completed",
                    "vaccineCode": {
                        "coding": _coding("http://hl7.org/fhir/sid/cvx", immunization.cvx_code, immunization.display),
                        "text": immunization.display,
                    },
                    "patient": {"reference": f"Patient/{patient_id}"},
                    "occurrenceDateTime": _iso(immunization.occurrence_dt),
                }
            }
        )

    for procedure in record.procedures:
        period = procedure.performed_period
        entries.append(
            {
                "resource": {
                    "resourceType": "Procedure",
                    "id": procedure.procedure_id,
                    "status": procedure.status or "completed",
                    "code": {
                        "coding": _coding(procedure.code.system, procedure.code.code, procedure.code.display),
                        "text": procedure.code.label(),
                    },
                    "subject": {"reference": f"Patient/{patient_id}"},
                    "encounter": {"reference": f"Encounter/{procedure.encounter_id}"} if procedure.encounter_id else None,
                    "performedPeriod": {
                        "start": _iso(period.start) if period else None,
                        "end": _iso(period.end) if period else None,
                    },
                    "reasonCode": [{"text": procedure.reason_display}] if procedure.reason_display else [],
                }
            }
        )

    for report in record.diagnostic_reports:
        resource = {
            "resourceType": "DiagnosticReport",
            "id": report.report_id,
            "status": report.status or "final",
            "category": [{"text": report.category}] if report.category else [],
            "code": {
                "coding": _coding(report.code.system, report.code.code, report.code.display),
                "text": report.code.label(),
            },
            "subject": {"reference": f"Patient/{patient_id}"},
            "encounter": {"reference": f"Encounter/{report.encounter_id}"} if report.encounter_id else None,
            "effectiveDateTime": _iso(report.effective_dt),
            "result": [{"reference": f"Observation/{ref}"} for ref in report.result_refs],
        }
        if report.has_presented_form and report.presented_form_text:
            resource["presentedForm"] = [
                {
                    "contentType": "text/plain",
                    "data": base64.b64encode(report.presented_form_text.encode("utf-8")).decode("ascii"),
                }
            ]
        entries.append({"resource": resource})

    for entry in entries:
        resource = entry.get("resource", {})
        for key in [key for key, value in resource.items() if value is None]:
            resource.pop(key, None)

    return {
        "resourceType": "Bundle",
        "type": "collection",
        "id": f"published-{patient_id}",
        "entry": entries,
    }
