"""Cached data loaders for the EHI Atlas corpus.

All loaders are decorated with @st.cache_data and invalidate on file mtime
change — so re-running `make pipeline` is reflected on the next page reload
without restarting the Streamlit server.

Corpus paths are resolved relative to this file's location so the app works
regardless of cwd.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import streamlit as st

# ---------------------------------------------------------------------------
# Path roots — everything resolved relative to ehi-atlas/
# ---------------------------------------------------------------------------

_THIS_FILE = Path(__file__).resolve()
# app/components/corpus_loader.py → up 3 levels → ehi-atlas/
ATLAS_ROOT = _THIS_FILE.parent.parent.parent  # ehi-atlas/
CORPUS_ROOT = ATLAS_ROOT / "corpus"
BRONZE_ROOT = CORPUS_ROOT / "bronze"
SILVER_ROOT = CORPUS_ROOT / "silver"
GOLD_ROOT = CORPUS_ROOT / "gold"

# Default showcase patient
DEFAULT_PATIENT = "rhett759"
GOLD_PATIENT_DIR = GOLD_ROOT / "patients" / DEFAULT_PATIENT


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mtime(path: Path) -> float:
    """Return mtime of a path, or 0 if it doesn't exist."""
    try:
        return os.path.getmtime(path)
    except OSError:
        return 0.0


# ---------------------------------------------------------------------------
# Gold-tier loaders
# ---------------------------------------------------------------------------


@st.cache_data(hash_funcs={Path: lambda p: (_mtime(p), str(p))})
def load_manifest(patient_id: str = DEFAULT_PATIENT) -> dict[str, Any] | None:
    """Load and return the manifest.json for a patient. Cached on mtime."""
    path = GOLD_ROOT / "patients" / patient_id / "manifest.json"
    if not path.exists():
        return None
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


@st.cache_data(hash_funcs={Path: lambda p: (_mtime(p), str(p))})
def load_gold_bundle(patient_id: str = DEFAULT_PATIENT) -> dict[str, Any] | None:
    """Load and return the gold bundle.json for a patient. Cached on mtime."""
    path = GOLD_ROOT / "patients" / patient_id / "bundle.json"
    if not path.exists():
        return None
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


@st.cache_data(hash_funcs={Path: lambda p: (_mtime(p), str(p))})
def load_provenance(patient_id: str = DEFAULT_PATIENT) -> list[dict[str, Any]]:
    """Load all Provenance records from provenance.ndjson. Cached on mtime."""
    path = GOLD_ROOT / "patients" / patient_id / "provenance.ndjson"
    if not path.exists():
        return []
    records = []
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    return records


# ---------------------------------------------------------------------------
# Bronze-tier loaders
# ---------------------------------------------------------------------------


@st.cache_data
def list_bronze_sources() -> list[str]:
    """Return the list of source names that have bronze-tier data."""
    if not BRONZE_ROOT.exists():
        return []
    return sorted(d.name for d in BRONZE_ROOT.iterdir() if d.is_dir())


@st.cache_data
def load_bronze_metadata(source: str, patient_id: str = DEFAULT_PATIENT) -> dict[str, Any] | None:
    """Load the metadata.json for a bronze source/patient combination."""
    path = BRONZE_ROOT / source / patient_id / "metadata.json"
    if not path.exists():
        return None
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


@st.cache_data(hash_funcs={Path: lambda p: (_mtime(p), str(p))})
def load_bronze_bundle(source: str, patient_id: str = DEFAULT_PATIENT) -> dict[str, Any] | None:
    """Load data.json from bronze for FHIR-bundle sources. Returns None if missing."""
    path = BRONZE_ROOT / source / patient_id / "data.json"
    if not path.exists():
        return None
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


@st.cache_data
def count_bronze_records(source: str, patient_id: str = DEFAULT_PATIENT) -> dict[str, int]:
    """Count resources by type in a bronze FHIR bundle. Returns {} if not a FHIR source."""
    bundle = load_bronze_bundle(source, patient_id)
    if bundle is None:
        # Non-FHIR source — return file-level count
        path = BRONZE_ROOT / source / patient_id
        if path.exists():
            files = [f for f in path.iterdir() if f.is_file()]
            return {"files": len(files)}
        return {}
    from collections import Counter
    counts: Counter = Counter()
    for entry in bundle.get("entry", []):
        resource = entry.get("resource", {})
        rtype = resource.get("resourceType", "Unknown")
        counts[rtype] += 1
    return dict(counts)


@st.cache_data(hash_funcs={Path: lambda p: (_mtime(p), str(p))})
def load_silver_bundle(source: str, patient_id: str = DEFAULT_PATIENT) -> dict[str, Any] | None:
    """Load silver bundle.json for a source/patient. Returns None if missing."""
    path = SILVER_ROOT / source / patient_id / "bundle.json"
    if not path.exists():
        return None
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


@st.cache_data
def count_silver_resources(source: str, patient_id: str = DEFAULT_PATIENT) -> dict[str, int]:
    """Count resources by type in a silver bundle."""
    bundle = load_silver_bundle(source, patient_id)
    if bundle is None:
        return {}
    from collections import Counter
    counts: Counter = Counter()
    for entry in bundle.get("entry", []):
        resource = entry.get("resource", {})
        rtype = resource.get("resourceType", "Unknown")
        counts[rtype] += 1
    return dict(counts)
