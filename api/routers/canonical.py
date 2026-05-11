"""/api/canonical — patient workspace read endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Request

from api.core.auth import authorize_patient_access, require_access_session
from api.core.canonical_service import canonical_patient_summary
from api.models import CanonicalPatientSummary


router = APIRouter(prefix="/canonical", tags=["canonical"])


@router.get("/{patient_id}/summary", response_model=CanonicalPatientSummary)
def get_canonical_patient_summary(patient_id: str, request: Request) -> CanonicalPatientSummary:
    session = require_access_session(request)
    resolved_patient_id = authorize_patient_access(session, patient_id, event_type="canonical.summary")
    summary = canonical_patient_summary(resolved_patient_id)
    if patient_id != resolved_patient_id:
        return summary.model_copy(update={"patient_id": patient_id})
    return summary
