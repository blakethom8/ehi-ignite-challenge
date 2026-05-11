"""Anchor package compiler.

Given a verified manifest and a raw patient record, compile the
scope-limited, redacted, signed slice the plugin will see.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

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


def load_raw_patient(patient_id: str) -> dict:
    if DEFAULT_PATIENT_PATH.exists():
        record = json.loads(DEFAULT_PATIENT_PATH.read_text())
        if record.get("patientId") == patient_id:
            return record
    record = _hollister_record()
    if record["patientId"] != patient_id:
        raise AnchorError(f"unknown patient: {patient_id}")
    return record


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
