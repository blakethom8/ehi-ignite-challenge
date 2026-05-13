"""Anchor package compiler.

Given a verified manifest and a raw patient record, compile the
scope-limited, redacted, signed slice the plugin will see.
"""

from __future__ import annotations

import json
import uuid
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from api.core.auth import DEMO_PATIENT_BY_ALIAS
from api.core.loader import path_from_patient_id
from api.settings import get_settings
from api.trust.keys import REPO_ROOT, atlas_keypair
from api.trust.models import AnchorPackage, PluginManifest
from api.trust.redactions import apply_preset
from api.trust.signatures import SignatureError, sign_object, verify_object


SCHEMA_VERSION = "1.0.0"


class AnchorError(Exception):
    pass


class AnchorExpired(AnchorError):
    pass


class OutOfScope(AnchorError):
    pass


# ============================================================
# Raw patient record (v1 fixture)
# ============================================================

# Hollister is the canonical sample patient in the existing Atlas fixtures.
# v2 wires this to the real FHIR loader (`lib/fhir_parser`).
DEFAULT_PATIENT_PATH = REPO_ROOT / "data" / "plugins" / "_patient-fixture.json"


def _hollister_record() -> dict:
    """Fixture for the demo patient. Replaced by FHIR loader in v2."""
    return {
        "patientId": "8.4127.881",
        "name": "M. Hollister",
        "mrn": "8.4127.881",
        "dob": "1957-08-04",
        "demographics": {
            "age": 68,
            "sex": "F",
            "geography": {"zip": "94110", "city": "San Francisco", "state": "CA"},
        },
        "diagnoses": {
            "active": [
                {
                    "code": "C92.10",
                    "system": "ICD-10",
                    "display": "Chronic myeloid leukemia, BCR-ABL positive, in chronic phase",
                    "onsetYear": 2022,
                },
                {
                    "code": "I48.91",
                    "system": "ICD-10",
                    "display": "Unspecified atrial fibrillation",
                    "onsetYear": 2019,
                },
                {
                    "code": "E03.9",
                    "system": "ICD-10",
                    "display": "Hypothyroidism, unspecified",
                    "onsetYear": 2019,
                },
            ],
            "history": [
                {"code": "K40.20", "display": "Inguinal hernia", "onsetYear": 2024},
                {"code": "E11.9", "display": "Type 2 diabetes mellitus, well-controlled", "onsetYear": 2014},
            ],
        },
        "medications": {
            "active": [
                {"rxnorm": "1364430", "display": "apixaban 5 MG Oral Tablet", "dose": "5 mg BID", "startDate": "2023-06-14"},
                {"rxnorm": "860975", "display": "metformin 500 MG Oral Tablet", "dose": "500 mg BID", "startDate": "2014-04-01"},
                {"rxnorm": "966222", "display": "levothyroxine 100 MCG Oral Tablet", "dose": "100 mcg daily", "startDate": "2019-02-10"},
            ],
            "history": [
                {"rxnorm": "835603", "display": "imatinib 400 MG Oral Tablet", "discontinuedDate": "2024-05-20", "reason": "intolerance"},
            ],
        },
        "allergies": [
            {"substance": "penicillin", "reaction": "rash", "severity": "moderate"},
        ],
        "biomarkers": [
            {"marker": "BCR-ABL1 (t9;22)", "status": "positive", "method": "FISH", "lastTested": "2024-11-04"},
        ],
        "labs": {
            "recent": [
                {"code": "26464-8", "system": "LOINC", "display": "Leukocytes [#/volume] in Blood", "value": 6.8, "unit": "10^9/L", "date": "2026-04-22"},
                {"code": "718-7", "system": "LOINC", "display": "Hemoglobin [Mass/volume] in Blood", "value": 12.4, "unit": "g/dL", "date": "2026-04-22"},
                {"code": "3016-3", "system": "LOINC", "display": "Thyrotropin [Units/volume] in Serum or Plasma", "value": 0.2, "unit": "mIU/L", "date": "2026-04-22"},
                {"code": "3024-7", "system": "LOINC", "display": "Thyroxine (T4) free in Serum or Plasma", "value": 1.6, "unit": "ng/dL", "date": "2026-04-22"},
            ],
        },
        "encounters": {
            "recent": [
                {"id": "Enc/2026-04-22", "type": "follow-up", "provider": "Patel, A.", "date": "2026-04-22"},
                {"id": "Enc/2026-04-18", "type": "anesthesia consult", "provider": "Chen, R.", "date": "2026-04-18"},
            ],
        },
        "performance-status": {"scale": "ECOG", "value": 1, "date": "2026-04-18"},
    }


def _demo_high_risk_record() -> dict:
    return {
        "patientId": "81e1b4cb-6817-4bdc-97cd-c1f3ac960345",
        "name": "Demo Patient - Surgical Review",
        "mrn": "demo-high-risk",
        "dob": "1932-11-14",
        "demographics": {
            "age": 93,
            "sex": "M",
            "geography": {"zip": "02108", "city": "Boston", "state": "MA"},
        },
        "diagnoses": {
            "active": [
                {"code": "I25.10", "system": "ICD-10", "display": "Coronary Heart Disease", "onsetYear": 1992},
                {"code": "I48.91", "system": "ICD-10", "display": "Atrial fibrillation", "onsetYear": 2019},
                {"code": "I50.9", "system": "ICD-10", "display": "Heart failure", "onsetYear": 2021},
                {"code": "I63.9", "system": "ICD-10", "display": "Prior ischemic stroke", "onsetYear": 2020},
                {"code": "C61", "system": "ICD-10", "display": "Prostate cancer", "onsetYear": 2023},
            ],
            "history": [
                {"code": "K40.90", "display": "Inguinal hernia", "onsetYear": 2025},
                {"code": "E11.22", "display": "Type 2 diabetes mellitus with diabetic chronic kidney disease", "onsetYear": 2013},
            ],
        },
        "medications": {
            "active": [
                {"rxnorm": "1364430", "display": "apixaban 5 MG Oral Tablet", "dose": "5 mg BID", "startDate": "2023-06-14"},
                {"rxnorm": "860975", "display": "metformin 500 MG Oral Tablet", "dose": "500 mg BID", "startDate": "2014-04-01"},
                {"rxnorm": "617320", "display": "furosemide 20 MG Oral Tablet", "dose": "20 mg daily", "startDate": "2021-03-20"},
            ],
            "history": [
                {"rxnorm": "83367", "display": "warfarin sodium 5 MG Oral Tablet", "discontinuedDate": "2023-06-13", "reason": "switched to DOAC"},
            ],
        },
        "allergies": [
            {"substance": "penicillin", "reaction": "rash", "severity": "moderate"},
        ],
        "biomarkers": [
            {"marker": "PSA", "status": "elevated", "method": "serum", "lastTested": "2026-04-02"},
        ],
        "labs": {
            "recent": [
                {"code": "718-7", "system": "LOINC", "display": "Hemoglobin [Mass/volume] in Blood", "value": 11.9, "unit": "g/dL", "date": "2026-04-22"},
                {"code": "33914-3", "system": "LOINC", "display": "Glomerular filtration rate/1.73 sq M.predicted", "value": 44, "unit": "mL/min/1.73m2", "date": "2026-04-22"},
                {"code": "6301-6", "system": "LOINC", "display": "INR in Platelet poor plasma by Coagulation assay", "value": 1.3, "unit": "", "date": "2026-04-22"},
            ],
        },
        "encounters": {
            "recent": [
                {"id": "Enc/2026-04-22", "type": "pre-op review", "provider": "M. Gibber, MD", "date": "2026-04-22"},
                {"id": "Enc/2026-04-18", "type": "cardiology clearance", "provider": "Patel, A.", "date": "2026-04-18"},
            ],
        },
        "performance-status": {"scale": "ECOG", "value": 2, "date": "2026-04-18"},
    }


def _demo_trial_match_record() -> dict:
    return {
        "patientId": "8143897c-e650-4e55-b08d-8306e2f424bb",
        "name": "Demo Patient - Trial Match",
        "mrn": "demo-trial-match",
        "dob": "1931-09-18",
        "demographics": {
            "age": 95,
            "sex": "M",
            "geography": {"zip": "02332", "city": "Duxbury", "state": "MA"},
        },
        "diagnoses": {
            "active": [
                {"code": "C61", "system": "ICD-10", "display": "Prostate neoplasm", "onsetYear": 2022},
                {"code": "N18.9", "system": "ICD-10", "display": "Chronic kidney disease", "onsetYear": 2019},
                {"code": "I25.10", "system": "ICD-10", "display": "Coronary Heart Disease", "onsetYear": 1992},
                {"code": "E11.22", "system": "ICD-10", "display": "Diabetic renal disease", "onsetYear": 2014},
            ],
            "history": [
                {"code": "I48.91", "display": "Atrial fibrillation", "onsetYear": 2019},
                {"code": "K40.90", "display": "Inguinal hernia", "onsetYear": 2025},
            ],
        },
        "medications": {
            "active": [
                {"rxnorm": "197361", "display": "clopidogrel 75 MG Oral Tablet", "dose": "75 mg daily", "startDate": "2023-08-10"},
                {"rxnorm": "860975", "display": "metformin 500 MG Oral Tablet", "dose": "500 mg BID", "startDate": "2014-04-01"},
                {"rxnorm": "1364430", "display": "apixaban 5 MG Oral Tablet", "dose": "5 mg BID", "startDate": "2024-01-14"},
            ],
            "history": [
                {"rxnorm": "83367", "display": "warfarin sodium 5 MG Oral Tablet", "discontinuedDate": "2024-01-13", "reason": "unstable monitoring"},
            ],
        },
        "allergies": [
            {"substance": "ACE inhibitors", "reaction": "cough", "severity": "mild"},
        ],
        "biomarkers": [
            {"marker": "PSA", "status": "elevated", "method": "serum", "lastTested": "2026-04-20"},
        ],
        "labs": {
            "recent": [
                {"code": "33914-3", "system": "LOINC", "display": "Glomerular filtration rate/1.73 sq M.predicted", "value": 39, "unit": "mL/min/1.73m2", "date": "2026-04-20"},
                {"code": "4548-4", "system": "LOINC", "display": "Hemoglobin A1c/Hemoglobin.total in Blood", "value": 7.5, "unit": "%", "date": "2026-04-20"},
                {"code": "6301-6", "system": "LOINC", "display": "INR in Platelet poor plasma by Coagulation assay", "value": 1.1, "unit": "", "date": "2026-04-20"},
            ],
        },
        "encounters": {
            "recent": [
                {"id": "Enc/2026-04-20", "type": "oncology referral review", "provider": "Serrato62, C.", "date": "2026-04-20"},
                {"id": "Enc/2026-04-18", "type": "cardiology follow-up", "provider": "Brown30, R.", "date": "2026-04-18"},
            ],
        },
        "performance-status": {"scale": "ECOG", "value": 1, "date": "2026-04-20"},
    }


def _demo_med_access_record() -> dict:
    return {
        "patientId": "eec393be-2569-46db-a974-33d7c853d690",
        "name": "Demo Patient - Medication Access",
        "mrn": "demo-med-access",
        "dob": "1934-02-03",
        "demographics": {
            "age": 91,
            "sex": "F",
            "geography": {"zip": "02860", "city": "Pawtucket", "state": "RI"},
        },
        "diagnoses": {
            "active": [
                {"code": "E11.40", "system": "ICD-10", "display": "Type 2 diabetes mellitus with neuropathy", "onsetYear": 2010},
                {"code": "N18.32", "system": "ICD-10", "display": "Chronic kidney disease stage 3b", "onsetYear": 2018},
                {"code": "G89.29", "system": "ICD-10", "display": "Chronic pain", "onsetYear": 2017},
                {"code": "I69.30", "system": "ICD-10", "display": "Stroke history", "onsetYear": 2021},
            ],
            "history": [
                {"code": "H35.00", "display": "Diabetic retinopathy", "onsetYear": 2019},
                {"code": "C50.919", "display": "Breast cancer history", "onsetYear": 2022},
            ],
        },
        "medications": {
            "active": [
                {"rxnorm": "1364430", "display": "apixaban 5 MG Oral Tablet", "dose": "5 mg BID", "startDate": "2024-06-11"},
                {"rxnorm": "860975", "display": "metformin 500 MG Oral Tablet", "dose": "500 mg BID", "startDate": "2010-04-01"},
                {"rxnorm": "847230", "display": "insulin glargine 100 UNT/ML Injectable Solution", "dose": "22 units nightly", "startDate": "2018-02-01"},
            ],
            "history": [
                {"rxnorm": "617314", "display": "gabapentin 300 MG Oral Capsule", "discontinuedDate": "2025-11-04", "reason": "sedation"},
            ],
        },
        "allergies": [
            {"substance": "sulfa drugs", "reaction": "hives", "severity": "moderate"},
        ],
        "biomarkers": [],
        "labs": {
            "recent": [
                {"code": "33914-3", "system": "LOINC", "display": "Glomerular filtration rate/1.73 sq M.predicted", "value": 36, "unit": "mL/min/1.73m2", "date": "2026-04-18"},
                {"code": "4548-4", "system": "LOINC", "display": "Hemoglobin A1c/Hemoglobin.total in Blood", "value": 8.1, "unit": "%", "date": "2026-04-18"},
            ],
        },
        "encounters": {
            "recent": [
                {"id": "Enc/2026-04-18", "type": "medication access review", "provider": "Care coordination", "date": "2026-04-18"},
                {"id": "Enc/2026-04-10", "type": "endocrinology follow-up", "provider": "Nguyen, T.", "date": "2026-04-10"},
            ],
        },
        "performance-status": {"scale": "ECOG", "value": 2, "date": "2026-04-18"},
    }


PLUGIN_DEMO_RECORDS_BY_PATIENT_ID = {
    "81e1b4cb-6817-4bdc-97cd-c1f3ac960345": _demo_high_risk_record(),
    "8143897c-e650-4e55-b08d-8306e2f424bb": _demo_trial_match_record(),
    "eec393be-2569-46db-a974-33d7c853d690": _demo_med_access_record(),
}


def _use_fixtures_only() -> bool:
    """When true, prefer hardcoded demo fixtures over the live FHIR loader.

    Default false in all environments — fixtures are kept around as a pinned
    demo path for screenshots and marketing, not as the everyday data path.
    """
    return get_settings().plugin_anchor_use_fixtures


def load_raw_patient(patient_id: str) -> dict:
    """Load a raw anchor record for ``patient_id``.

    Resolution:
    1. Demo aliases ("demo-high-risk" etc.) resolve to their real Synthea UUID.
    2. If ``PLUGIN_ANCHOR_USE_FIXTURES=true``, the curated fixture for that
       UUID wins (preserves the demo experience for screenshots/marketing).
    3. Otherwise, the live FHIR bundle is loaded via
       ``lib.fhir_parser.bundle_parser.parse_bundle`` and projected into the
       anchor schema. This is the production path.
    4. Fallback to fixtures for legacy demo patient IDs that have no Synthea
       bundle (e.g., the canonical Hollister fixture ``8.4127.881``).
    """
    demo_patient = DEMO_PATIENT_BY_ALIAS.get(patient_id)
    if demo_patient is not None:
        patient_id = demo_patient.actual_patient_id

    if _use_fixtures_only():
        if DEFAULT_PATIENT_PATH.exists():
            record = json.loads(DEFAULT_PATIENT_PATH.read_text())
            if record.get("patientId") == patient_id:
                return record
        demo_record = PLUGIN_DEMO_RECORDS_BY_PATIENT_ID.get(patient_id)
        if demo_record is not None:
            return demo_record

    live = _load_from_fhir(patient_id)
    if live is not None:
        return live

    # No live bundle (e.g. Hollister 8.4127.881 has no Synthea file). Fixtures
    # remain available as a last-resort fallback so existing demos keep working.
    demo_record = PLUGIN_DEMO_RECORDS_BY_PATIENT_ID.get(patient_id)
    if demo_record is not None:
        return demo_record
    record = _hollister_record()
    if record["patientId"] != patient_id:
        raise AnchorError(f"unknown patient: {patient_id}")
    return record


# ============================================================
# FHIR → anchor-schema projection
# ============================================================


_LAB_LOINC_ECOG = {"89243-0", "42800-3"}  # ECOG performance status LOINC codes


def _load_from_fhir(patient_id: str) -> dict | None:
    """Load a patient bundle and project it into the anchor record shape.

    Returns ``None`` if no Synthea bundle exists for ``patient_id`` (the
    caller falls back to the fixture path). Any parse error raises
    ``AnchorError`` rather than returning None — a corrupt bundle for an
    indexed patient is a real failure, not a missing-data signal.
    """
    path = path_from_patient_id(patient_id)
    if path is None:
        return None
    try:
        # Lazy import: keep test setup cheap when the FHIR loader isn't needed.
        from lib.fhir_parser.bundle_parser import parse_bundle

        record = parse_bundle(path)
    except Exception as exc:
        raise AnchorError(
            f"failed to parse FHIR bundle for {patient_id}: {exc}"
        ) from exc

    summary = record.summary
    age = _years_since(summary.birth_date)

    diagnoses_active = []
    diagnoses_history = []
    for cond in record.conditions:
        entry = {
            "code": cond.code.code,
            "system": cond.code.system,
            "display": cond.code.label(),
            "onsetYear": cond.onset_dt.year if cond.onset_dt else None,
        }
        if cond.is_active:
            diagnoses_active.append(entry)
        else:
            diagnoses_history.append(entry)

    meds_active = []
    meds_history = []
    for med in record.medications:
        is_active = (med.status or "").lower() == "active"
        entry = {
            "rxnorm": med.rxnorm_code,
            "display": med.display,
            "dose": med.dosage_text,
            "startDate": med.authored_on.date().isoformat() if med.authored_on else None,
            "status": med.status,
        }
        if is_active:
            meds_active.append(entry)
        else:
            entry["reason"] = med.reason_display or None
            meds_history.append(entry)

    allergies = []
    for allergy in record.allergies:
        allergies.append(
            {
                "substance": allergy.code.label(),
                "reaction": allergy.allergy_type or "",
                "severity": allergy.criticality or "",
            }
        )

    labs_recent = []
    perf_status: dict[str, Any] | None = None
    for obs in record.observations:
        if obs.category == "laboratory" and obs.value_quantity is not None:
            labs_recent.append(
                {
                    "code": obs.loinc_code,
                    "system": "LOINC",
                    "display": obs.display,
                    "value": obs.value_quantity,
                    "unit": obs.value_unit,
                    "date": obs.effective_dt.date().isoformat() if obs.effective_dt else None,
                }
            )
        if obs.loinc_code in _LAB_LOINC_ECOG and obs.value_quantity is not None:
            perf_status = {
                "scale": "ECOG",
                "value": obs.value_quantity,
                "date": obs.effective_dt.date().isoformat() if obs.effective_dt else None,
            }
    labs_recent.sort(key=lambda r: r.get("date") or "", reverse=True)
    labs_recent = labs_recent[:25]

    encounters_recent = []
    for enc in sorted(
        record.encounters,
        key=lambda e: e.period.start or datetime.min,
        reverse=True,
    )[:10]:
        encounters_recent.append(
            {
                "id": enc.encounter_id,
                "type": enc.encounter_type or enc.class_code,
                "provider": enc.practitioner_name or enc.provider_org,
                "date": enc.period.start.date().isoformat() if enc.period.start else None,
            }
        )

    return {
        "patientId": summary.patient_id or patient_id,
        "name": summary.name,
        "mrn": summary.mrn or summary.patient_id,
        "dob": summary.birth_date.isoformat() if summary.birth_date else None,
        "demographics": {
            "age": age,
            "sex": (summary.gender or "").upper()[:1] or None,
            "geography": {
                "zip": summary.postal_code,
                "city": summary.city,
                "state": summary.state,
            },
        },
        "diagnoses": {"active": diagnoses_active, "history": diagnoses_history},
        "medications": {"active": meds_active, "history": meds_history},
        "allergies": allergies,
        "biomarkers": [],
        "labs": {"recent": labs_recent},
        "encounters": {"recent": encounters_recent},
        "performance-status": perf_status,
    }


def _years_since(birth: date | None) -> int | None:
    if birth is None:
        return None
    today = date.today()
    years = today.year - birth.year - (
        (today.month, today.day) < (birth.month, birth.day)
    )
    return max(years, 0)


# ============================================================
# Scope projection
# ============================================================


def _project_scope(record: dict, scope: list[str]) -> dict:
    """Pull only the fields named in ``scope`` out of the raw record.

    Scope tokens are dotted paths into a small fixed schema (see
    ``AnchorScopeField`` in models.py). Anything outside that schema
    is not addressable.
    """
    out: dict[str, Any] = {}
    for token in scope:
        if token == "demographics.age-band":
            demo = record.get("demographics", {})
            if "age-band" in demo:
                out["demographics.age-band"] = demo["age-band"]
            elif "age" in demo:
                out["demographics.age-band"] = _age_band(demo["age"])
            else:
                out["demographics.age-band"] = None
        elif token == "demographics.sex":
            out["demographics.sex"] = record.get("demographics", {}).get("sex")
        elif token == "demographics.geography":
            geo = record.get("demographics", {}).get("geography", {})
            out["demographics.geography"] = {k: geo.get(k) for k in geo}
        elif token == "diagnoses.active":
            out["diagnoses.active"] = list(record.get("diagnoses", {}).get("active", []))
        elif token == "diagnoses.history":
            out["diagnoses.history"] = list(record.get("diagnoses", {}).get("history", []))
        elif token == "medications.active":
            out["medications.active"] = list(record.get("medications", {}).get("active", []))
        elif token == "medications.history":
            out["medications.history"] = list(record.get("medications", {}).get("history", []))
        elif token == "allergies":
            out["allergies"] = list(record.get("allergies", []))
        elif token == "biomarkers":
            out["biomarkers"] = list(record.get("biomarkers", []))
        elif token == "labs.recent":
            out["labs.recent"] = list(record.get("labs", {}).get("recent", []))
        elif token == "encounters.recent":
            out["encounters.recent"] = list(record.get("encounters", {}).get("recent", []))
        elif token == "performance-status":
            out["performance-status"] = record.get("performance-status")
        else:
            raise OutOfScope(f"unknown anchor scope token: {token}")
    return out


def _age_band(age: int) -> str:
    lo = (age // 5) * 5
    return f"{lo}-{lo + 4}"


# ============================================================
# Compile + sign
# ============================================================


def compile_anchor_package(
    *,
    manifest: PluginManifest,
    patient_id: str,
    run_id: str,
    now: datetime | None = None,
) -> AnchorPackage:
    raw = load_raw_patient(patient_id)
    # Apply redactions on the raw nested record first so de-id presets
    # can see fields in their native shape (demographics.geography.zip,
    # demographics.age, etc.). Then project the redacted record into the
    # flat scope-token shape the plugin actually sees.
    redacted_raw = apply_preset(manifest.anchor.redactionPreset, raw)
    redacted = _project_scope(redacted_raw, list(manifest.anchor.scope))
    issued = (now or datetime.now(timezone.utc)).replace(microsecond=0)
    expires = issued + timedelta(seconds=manifest.anchor.ttlSeconds)

    payload = {
        "schemaVersion": SCHEMA_VERSION,
        "pluginId": manifest.id,
        "pluginVersion": manifest.version,
        "patientId": patient_id,
        "runId": run_id,
        "issuedAt": issued.isoformat().replace("+00:00", "Z"),
        "expiresAt": expires.isoformat().replace("+00:00", "Z"),
        "redactionPreset": manifest.anchor.redactionPreset,
        "scope": list(manifest.anchor.scope),
        "data": redacted,
    }
    sk, _ = atlas_keypair()
    payload["signature"] = sign_object(sk, payload, exclude_field=None)
    return AnchorPackage.model_validate(payload)


def verify_anchor_package(pkg: AnchorPackage, *, now: datetime | None = None) -> None:
    _, pk = atlas_keypair()
    raw = pkg.model_dump(mode="json")
    sig = raw.pop("signature")
    try:
        verify_object(pk, raw, sig, exclude_field=None)
    except SignatureError as e:
        raise AnchorError(f"anchor signature invalid: {e}") from e
    current = now or datetime.now(timezone.utc)
    if pkg.expiresAt < current:
        raise AnchorExpired(f"anchor expired at {pkg.expiresAt.isoformat()}")


def read_anchor_field(pkg: AnchorPackage, field: str) -> Any:
    """Look up a scope-keyed field on an anchor package, with bounds check."""
    if field not in pkg.scope:
        raise OutOfScope(
            f"field '{field}' is not in this anchor's scope: {pkg.scope}"
        )
    return pkg.data.get(field)


def new_run_id() -> str:
    return "r_" + uuid.uuid4().hex[:10]
