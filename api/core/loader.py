"""
Patient loader — wraps fhir_explorer parser for use by the API layer.

Parsed bundles are cached in-memory (LRU, 30 patients) so repeated requests
to the same patient don't re-parse from disk.
"""

from __future__ import annotations

import re
import sys
from functools import lru_cache
from pathlib import Path

# Ensure repo root is on path so fhir_explorer imports work
_REPO_ROOT = Path(__file__).parent.parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from fhir_explorer.parser.bundle_parser import parse_bundle
from fhir_explorer.catalog.single_patient import compute_patient_stats, PatientStats
from fhir_explorer.parser.models import PatientRecord

_DATA_DIR = _REPO_ROOT / "data" / "synthea-samples" / "synthea-r4-individual" / "fhir"


def data_dir() -> Path:
    return _DATA_DIR


def list_patient_files() -> list[Path]:
    """Return sorted list of all FHIR bundle JSON files."""
    return sorted(_DATA_DIR.glob("*.json"))


def patient_display_name(path: Path) -> str:
    """Extract a readable name from the filename stem."""
    parts = path.stem.split("_")
    if len(parts) >= 2:
        first = re.sub(r"\d+", "", parts[0]).strip()
        last = re.sub(r"\d+", "", parts[1]).strip()
        return f"{first} {last}"
    return path.stem


def patient_id_from_path(path: Path) -> str:
    """Use the filename stem (without .json) as the stable patient ID."""
    return path.stem


def path_from_patient_id(patient_id: str) -> Path | None:
    """Resolve a patient ID back to its file path."""
    candidate = _DATA_DIR / f"{patient_id}.json"
    return candidate if candidate.exists() else None


@lru_cache(maxsize=30)
def _cached_load(patient_id: str) -> tuple[PatientRecord, PatientStats]:
    """Parse bundle and compute stats. Result is cached per patient_id."""
    path = _DATA_DIR / f"{patient_id}.json"
    record = parse_bundle(str(path))
    stats = compute_patient_stats(record)
    return record, stats


def load_patient(patient_id: str) -> tuple[PatientRecord, PatientStats] | None:
    """Load and parse a patient bundle by ID. Returns None if not found. Cached."""
    path = path_from_patient_id(patient_id)
    if path is None:
        return None
    return _cached_load(patient_id)
