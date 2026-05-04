"""Cached data loaders for the EHI Atlas corpus (bronze tier only).

The 5-layer pipeline (silver / gold / provenance) was archived in May 2026 —
see `archive/ehi-atlas-5layer/`. The live console drives the PDF→FHIR
extraction flow and reads bronze sources only.

Corpus paths are resolved relative to this file's location so the app works
regardless of cwd.
"""

from __future__ import annotations

import json
import os
from collections import Counter
from pathlib import Path
from typing import Any

import streamlit as st

_THIS_FILE = Path(__file__).resolve()
ATLAS_ROOT = _THIS_FILE.parent.parent.parent  # ehi-atlas/
CORPUS_ROOT = ATLAS_ROOT / "corpus"
BRONZE_ROOT = CORPUS_ROOT / "bronze"
SOURCES_ROOT = CORPUS_ROOT / "_sources"

DEFAULT_PATIENT = "rhett759"


def _mtime(path: Path) -> float:
    try:
        return os.path.getmtime(path)
    except OSError:
        return 0.0


@st.cache_data
def list_bronze_sources() -> list[str]:
    if not BRONZE_ROOT.exists():
        return []
    return sorted(d.name for d in BRONZE_ROOT.iterdir() if d.is_dir())


@st.cache_data
def load_bronze_metadata(source: str, patient_id: str = DEFAULT_PATIENT) -> dict[str, Any] | None:
    path = BRONZE_ROOT / source / patient_id / "metadata.json"
    if not path.exists():
        return None
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


@st.cache_data(hash_funcs={Path: lambda p: (_mtime(p), str(p))})
def load_bronze_bundle(source: str, patient_id: str = DEFAULT_PATIENT) -> dict[str, Any] | None:
    path = BRONZE_ROOT / source / patient_id / "data.json"
    if not path.exists():
        return None
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


@st.cache_data
def count_bronze_records(source: str, patient_id: str = DEFAULT_PATIENT) -> dict[str, int]:
    bundle = load_bronze_bundle(source, patient_id)
    if bundle is None:
        path = BRONZE_ROOT / source / patient_id
        if path.exists():
            files = [f for f in path.iterdir() if f.is_file()]
            return {"files": len(files)}
        return {}
    counts: Counter = Counter()
    for entry in bundle.get("entry", []):
        resource = entry.get("resource", {})
        rtype = resource.get("resourceType", "Unknown")
        counts[rtype] += 1
    return dict(counts)
