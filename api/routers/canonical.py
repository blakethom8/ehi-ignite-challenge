"""/api/canonical — patient workspace read endpoints."""

from __future__ import annotations

from fastapi import APIRouter

from api.core.canonical_service import canonical_patient_summary
from api.models import CanonicalPatientSummary


router = APIRouter(prefix="/canonical", tags=["canonical"])


@router.get("/{patient_id}/summary", response_model=CanonicalPatientSummary)
def get_canonical_patient_summary(patient_id: str) -> CanonicalPatientSummary:
    return canonical_patient_summary(patient_id)
