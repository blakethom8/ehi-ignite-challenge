"""
FHIR bundle loader — wraps the existing fhir_explorer parser.

Provides a clean interface for loading patient records from FHIR R4
JSON bundle files, with caching support for Streamlit.
"""

from __future__ import annotations

from pathlib import Path

from fhir_explorer.parser.bundle_parser import parse_bundle
from fhir_explorer.parser.models import PatientRecord
from fhir_explorer.catalog.single_patient import PatientStats, compute_patient_stats


# Default data directory — Synthea individual patient bundles
DATA_DIR = Path(__file__).parent.parent.parent / "data" / "synthea-samples" / "synthea-r4-individual" / "fhir"


def load_patient(file_path: str | Path) -> PatientRecord:
    """Load and parse a single FHIR R4 bundle JSON into a PatientRecord."""
    return parse_bundle(str(file_path))


def load_patient_with_stats(file_path: str | Path) -> tuple[PatientRecord, PatientStats]:
    """Load a patient and compute summary statistics."""
    record = load_patient(file_path)
    stats = compute_patient_stats(record)
    return record, stats


def list_patient_files(data_dir: Path | None = None) -> list[Path]:
    """Return sorted list of FHIR bundle JSON files in the data directory."""
    directory = data_dir or DATA_DIR
    if not directory.exists():
        return []
    return sorted(directory.glob("*.json"))


def patient_display_name(file_path: Path) -> str:
    """Extract a human-readable patient name from the filename.

    Synthea filenames look like: FirstName_LastName_UUID.json
    """
    stem = file_path.stem
    parts = stem.rsplit("_", 1)  # split off the UUID
    name_part = parts[0] if len(parts) > 1 else stem
    # Replace remaining underscores (between first/last) with spaces
    # Handle numbered names like "Robert854"
    return name_part.replace("_", " ")
