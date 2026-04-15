"""
/api/classifications — patient classification categories and raw FHIR data.
"""

from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

from api.core.loader import path_from_patient_id

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
    if path is None:
        raise HTTPException(status_code=404, detail="Patient not found")
    bundle = json.loads(path.read_text())
    return JSONResponse(content=bundle)
