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

from lib.fhir_parser.bundle_parser import parse_bundle
from lib.patient_catalog.single_patient import compute_patient_stats, PatientStats
from lib.fhir_parser.models import PatientRecord

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


# Module-level cache: bare UUID → canonical filename stem.
# Populated lazily on first UUID-lookup miss; never cleared during process lifetime.
_uuid_to_stem: dict[str, str] | None = None
_UUID_RE = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)


def _build_uuid_index() -> dict[str, str]:
    """Build a map from FHIR Patient-resource id → canonical filename stem.

    Strategies, in preference order:
    1. Use the corpus catalog mapping from FHIR Patient id → filename.
    2. Read the legacy corpus cache if present.
    3. Use the UUID suffix embedded in the Synthea filename stem as a fallback.
    4. Scan each JSON file and extract the Patient resource id by reading
       bundle entries until the first Patient resource is found (slower but
       works without a corpus cache).
    """
    import json as _json

    index: dict[str, str] = {}

    # Strategy 1: use the same compact corpus catalog that backs /api/patients.
    # It stores the real FHIR Patient resource id, which can differ from the
    # UUID suffix embedded in the Synthea filename.
    try:
        from lib.patient_catalog.corpus import load_corpus

        catalog = load_corpus(_DATA_DIR)
        for patient in catalog.patients:
            patient_id = (patient.patient_id or "").lower()
            file_name = patient.file_name or ""
            if patient_id and file_name:
                index[patient_id] = Path(file_name).stem
        if index:
            return index
    except Exception:
        pass

    # Strategy 2: use legacy corpus cache if present
    _CORPUS_CACHE = _REPO_ROOT / "fhir_explorer" / "catalog" / ".corpus_cache.json"
    if _CORPUS_CACHE.exists():
        try:
            with open(_CORPUS_CACHE) as _f:
                cached = _json.load(_f)
            for p in cached.get("patients", []):
                pid = p.get("patient_id", "").lower()
                file_name = p.get("file_name", "")
                if pid and file_name:
                    stem = Path(file_name).stem
                    index[pid] = stem
            if index:
                return index
        except Exception:
            pass

    # Strategy 3: many Synthea filenames also end with a UUID. This does not
    # always match the FHIR Patient id, but it is cheap and useful as fallback.
    for path in _DATA_DIR.glob("*.json"):
        stem = path.stem
        maybe_uuid = stem.rsplit("_", 1)[-1].lower()
        if _UUID_RE.match(maybe_uuid):
            index[maybe_uuid] = stem
    if index:
        return index

    # Strategy 4: scan bundles for Patient resource id
    for path in _DATA_DIR.glob("*.json"):
        stem = path.stem
        try:
            with open(path) as _f:
                bundle = _json.load(_f)
            for entry in bundle.get("entry", []):
                resource = entry.get("resource", {})
                if resource.get("resourceType") == "Patient":
                    pid = resource.get("id", "").lower()
                    if pid:
                        index[pid] = stem
                    break  # Only need the first Patient entry
        except Exception:
            continue

    return index


def path_from_patient_id(patient_id: str) -> Path | None:
    """Resolve a patient ID back to its file path.

    Accepts two ID shapes:
    1. Canonical filename stem (e.g. ``Shelly431_Corwin846_eec393be-…``) — fast
       direct lookup.
    2. Bare UUID (e.g. ``eec393be-2569-46db-a974-33d7c853d690``) — resolved
       through the module-level UUID index, built once on first miss.
    """
    global _uuid_to_stem

    # Shape 1: exact filename match
    candidate = _DATA_DIR / f"{patient_id}.json"
    if candidate.exists():
        return candidate

    # Shape 2: bare UUID — build index on first use then look up
    if _uuid_to_stem is None:
        _uuid_to_stem = _build_uuid_index()
    stem = _uuid_to_stem.get(patient_id.lower())
    if stem is None:
        return None
    resolved = _DATA_DIR / f"{stem}.json"
    return resolved if resolved.exists() else None


def warm_patient_indexes() -> None:
    """Build lightweight lookup indexes that should be ready before traffic."""
    global _uuid_to_stem
    if _uuid_to_stem is None:
        _uuid_to_stem = _build_uuid_index()


@lru_cache(maxsize=30)
def _cached_load(canonical_stem: str) -> tuple[PatientRecord, PatientStats]:
    """Parse bundle and compute stats. Cached by canonical filename stem."""
    path = _DATA_DIR / f"{canonical_stem}.json"
    record = parse_bundle(str(path))
    stats = compute_patient_stats(record)
    return record, stats


def load_patient(patient_id: str) -> tuple[PatientRecord, PatientStats] | None:
    """Load and parse a patient bundle by ID. Returns None if not found. Cached.

    Accepts both the canonical filename stem and a bare resource UUID — both
    resolve to the same ``_cached_load`` entry via the canonical stem so the
    LRU cache is never double-populated for the same physical patient.
    """
    path = path_from_patient_id(patient_id)
    if path is None:
        return None
    # Always use the canonical stem as the cache key so bare-UUID and
    # filename-stem callers share the same cached entry.
    return _cached_load(path.stem)
