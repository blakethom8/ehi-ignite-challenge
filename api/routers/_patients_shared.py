"""
Shared constants and helpers for the /api/patients sub-routers.

The patients router was split into ``patients_core``, ``patients_timeline``,
and ``patients_risk`` modules. This module hosts the few helpers and constants
they all need so the sub-routers don't import from each other.
"""

from __future__ import annotations

import logging
import re
from collections import defaultdict
from datetime import datetime
from pathlib import Path

from fastapi import Request

from api.core.auth import authorize_patient_access, require_access_session
from api.settings import get_settings
from lib.clinical.drug_classifier import DrugClassifier

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Drug classifier (shared across core risk-summary, timeline care-journey,
# and the risk safety / interactions / surgical-risk handlers).
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).parent.parent.parent
_DRUG_MAPPING = _REPO_ROOT / "lib" / "clinical" / "drug_classes.json"
_classifier = DrugClassifier(mapping_path=_DRUG_MAPPING)

# ---------------------------------------------------------------------------
# Module-level constants shared by overview/risk
# ---------------------------------------------------------------------------

BILLING_TYPES = {"Claim", "ExplanationOfBenefit"}
ADMIN_TYPES = {"Organization", "Practitioner", "PractitionerRole", "Location"}
DEMO_PATIENT_LIMIT = get_settings().ehi_demo_patient_limit
DEMO_PATIENT_IDS = (
    # Current working demo patient and early aggregation fixture.
    "763b6101-133a-44bb-ac60-3c097d6c0ba1",
    "5cbc121b-cd71-4428-b8b7-31e53eba8184",
    # Curated high-signal Synthea records for development and demos.
    "eec393be-2569-46db-a974-33d7c853d690",
    "8143897c-e650-4e55-b08d-8306e2f424bb",
    "0718123b-5034-4965-a145-3d8d71b11389",
    "8055d1ca-46b7-44a3-a033-b918e4c3ecfb",
    "86017b61-3171-45b6-9bd7-b6ca6a946604",
    "4b5e42a8-b3e6-411b-b32d-585f71bca118",
    "8e674838-e3da-4bc9-b9e3-7d726b07291d",
    "fc863fc4-dbe2-430b-b213-ce400f6e47a8",
    "81e1b4cb-6817-4bdc-97cd-c1f3ac960345",
    "86337f98-0d8d-40ee-ad5d-68811024c886",
    "2d75e3a4-f0f6-45dd-8b57-75fb2f303c9e",
    "f636829a-4277-4392-a9a2-1050ef6eceed",
    "afafca2f-b97d-4fc9-b3b6-984e46d4c0b8",
    "b0f49c80-b59b-4df6-8292-40ce8b8f8612",
    "8937b6dc-4484-49c1-9bef-5700688d5f90",
    "df121e33-f3dc-4d02-a523-3bbd89c8fa5b",
    "6e965c83-1c3f-42bb-9604-f809c18bad6b",
    "fa7e100a-ff60-4edb-9fc6-9574a42784aa",
)


def _authorized_patient_id(request: Request, patient_id: str) -> str:
    return authorize_patient_access(require_access_session(request), patient_id)


# ---------------------------------------------------------------------------
# Encounter / care-network labelling helpers (used by overview's care-team
# summary in patients_core AND by timeline's encounter semantics in
# patients_timeline).
# ---------------------------------------------------------------------------

def _encounter_date_sort(value: datetime | None) -> int:
    return value.toordinal() if value else 0


def _clean_network_label(value: str | None) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
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
    if raw != cleaned:
        return re.sub(r"[-_]+", " ", stem).strip().title() or raw
    return raw


def _network_specialty(name: str, related: list[str], class_breakdown: dict[str, int]) -> str:
    haystack = " ".join([name, *related, *class_breakdown.keys()]).lower()
    if any(term in haystack for term in ("nephro", "renal", "kidney")):
        return "Nephrology"
    if any(term in haystack for term in ("cardio", "heart", "ekg", "ecg")):
        return "Cardiology"
    if any(term in haystack for term in ("dermat", "skin")):
        return "Dermatology"
    if any(term in haystack for term in ("lab", "diagnostic", "quest", "function health", "blood draw")):
        return "Laboratory / diagnostics"
    if any(term in haystack for term in ("medication", "pharmacy")):
        return "Medication records"
    if any(term in haystack for term in ("problem list", "condition")):
        return "Problem list"
    if "immunization" in haystack:
        return "Immunization records"
    if "cedars-sinai" in haystack or "kaiser permanente" in haystack:
        return "Health system records"
    return "Clinical source records"


def _fallback_provider_label(site_name: str, encounter_type: str) -> str:
    if not site_name or site_name == "Unknown organization":
        return "Unknown provider"
    event_type = encounter_type.lower()
    if "lab" in event_type or "diagnostic" in event_type:
        return f"{site_name} lab / diagnostic records"
    if "medication" in event_type:
        return f"{site_name} medication records"
    if "problem list" in event_type or "condition" in event_type:
        return f"{site_name} problem list"
    if "immunization" in event_type:
        return f"{site_name} immunization records"
    return f"{site_name} records"


def _encounter_source_category(encounter_type: str, class_code: str, reason: str, provider_org: str, practitioner: str) -> str:
    haystack = " ".join([encounter_type, class_code, reason, provider_org, practitioner]).lower()
    if any(term in haystack for term in ("lab", "diagnostic", "blood draw", "observation", "function health", "quest")):
        return "Lab / diagnostic event"
    if any(term in haystack for term in ("document", "source", "report", "summary", "note", "pdf")):
        return "Source document event"
    if any(term in haystack for term in ("office", "ambulatory", "outpatient", "wellness", "consult")):
        return "Office / outpatient visit"
    if any(term in haystack for term in ("emergency", "urgent", "emer")):
        return "Emergency / urgent care"
    if any(term in haystack for term in ("inpatient", "hospital", "admission")):
        return "Inpatient encounter"
    if any(term in haystack for term in ("procedure", "surgery", "imaging")):
        return "Procedure / imaging event"
    if any(term in haystack for term in ("immunization", "vaccine")):
        return "Immunization event"
    if any(term in haystack for term in ("medication", "pharmacy")):
        return "Medication record event"
    if any(term in haystack for term in ("condition", "problem list")):
        return "Problem-list event"
    return "Clinical encounter"


def _encounter_semantics(enc) -> tuple[str, str, str]:
    provider_org = _clean_network_label(enc.provider_org) or enc.provider_org or ""
    practitioner = _clean_network_label(enc.practitioner_name) or enc.practitioner_name or ""
    source_category = _encounter_source_category(
        enc.encounter_type or "",
        enc.class_code or "",
        enc.reason_display or "",
        provider_org,
        practitioner,
    )
    specialty = _network_specialty(
        practitioner or provider_org or source_category,
        [provider_org, enc.encounter_type or "", enc.reason_display or "", source_category],
        {enc.class_code or "Unknown": 1},
    )
    provenance_label = provider_org or practitioner or "Published chart snapshot"
    return specialty, source_category, provenance_label


__all__ = [
    "logger",
    "_classifier",
    "_REPO_ROOT",
    "_DRUG_MAPPING",
    "BILLING_TYPES",
    "ADMIN_TYPES",
    "DEMO_PATIENT_LIMIT",
    "DEMO_PATIENT_IDS",
    "_authorized_patient_id",
    "_encounter_date_sort",
    "_clean_network_label",
    "_network_specialty",
    "_fallback_provider_label",
    "_encounter_source_category",
    "_encounter_semantics",
    "defaultdict",  # re-exported for convenience inside helpers
]
