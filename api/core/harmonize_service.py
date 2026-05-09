"""Harmonization service — wraps `lib.harmonize` for the API layer.

The service knows how to load source bundles for a *collection* (a named
group of source documents the user is harmonizing together) and run the
matchers, returning shaped response objects the router can hand to the
React app.

Collections started as deliberately decoupled from "patient" — a collection is
"these documents the user uploaded / pulled," and harmonization runs over
that bag. The registry now has three halves:

1. **Static registry** — one well-known demo collection (``blake-real``)
   backed by the corpus drop in
   ``ehi-atlas/corpus/bronze/clinical-portfolios/blake_records/``.
2. **Upload-derived collections** — one per subdirectory under
   ``data/aggregation-uploads/<upload_session>/``. Each ``.json`` upload
   becomes a fhir-pull source; each ``.pdf`` upload becomes an
   extracted-pdf source whose extraction lives at
   ``<file>.extracted.json`` next to it (produced by the manual
   extract endpoint or pre-staged out-of-band). Each C-CDA ``.xml`` upload
   becomes a ccda-xml source that is converted to FHIR-shaped resources before
   merge, subject to patient identity checks.

This makes the application document-agnostic: any user can upload any
documents and the harmonizer surfaces a per-upload-session merged record
   without code changes.
3. **Patient workspaces** — dynamic ``workspace-<patient_id>`` collections
   that treat the selected Synthea bundle as the baseline source and attach
   any uploads for that same patient workspace.
"""

from __future__ import annotations

import base64
import binascii
import json
import os
import re
from dataclasses import dataclass, field
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Any

from api.core.loader import path_from_patient_id, patient_display_name
from api.core.ccda import (
    compare_patient_identity,
    convert_ccda_to_fhir_bundle,
    is_ccda_xml,
    is_converter_required,
)
from lib.harmonize import (
    SourceBundle,
    merge_allergies,
    merge_conditions,
    merge_immunizations,
    merge_medications,
    merge_observations,
    mint_provenance,
)
from lib.harmonize.models import (
    MergedAllergy,
    MergedCondition,
    MergedImmunization,
    MergedMedication,
    MergedObservation,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
UPLOADS_ROOT = Path(
    os.getenv("AGGREGATION_UPLOAD_STORE_PATH", REPO_ROOT / "data" / "aggregation-uploads")
)
PROFILE_ROOT = Path(
    os.getenv("AGGREGATION_PROFILE_STORE_PATH", REPO_ROOT / "data" / "aggregation-profiles")
)
PROFILE_REGISTRY_PATH = PROFILE_ROOT / "profiles.json"

# ---------------------------------------------------------------------------
# Collection registry
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CollectionDefinition:
    """One harmonizable collection of source documents.

    A collection is the user-visible unit: "these documents I'm
    harmonizing together." The harmonize layer doesn't care whether a
    collection is one patient's record or a research cohort or an
    arbitrary upload session — it just merges whatever it's given.
    """

    id: str
    """Stable collection identifier used in URLs."""

    name: str
    """Human-readable name shown in the UI."""

    description: str
    """One-line description of what's in the collection."""

    sources: tuple["SourceDefinition", ...]
    """Concrete source documents that feed the harmonizer."""


@dataclass(frozen=True)
class SourceDefinition:
    """One source document inside a collection.

    The ``kind`` field drives loading: native FHIR pulls return the FHIR
    dict directly, while extracted PDFs return a Bundle that we flatten
    by resourceType.
    """

    id: str
    label: str
    kind: str  # "fhir-pull" | "extracted-pdf" | "ccda-xml"
    path: Path
    document_reference: str | None = None


_BLAKE_DIR = (
    REPO_ROOT
    / "ehi-atlas"
    / "corpus"
    / "bronze"
    / "clinical-portfolios"
    / "blake_records"
)


# ---------------------------------------------------------------------------
# Synthea demo collection — self-bootstrapping cross-source merge fixture
# ---------------------------------------------------------------------------
#
# Goal: a fresh-clone reviewer who has no Blake-private data should still
# see a working harmonize page. We synthesize a cross-source dataset by
# splitting one rich Synthea patient bundle into two temporal snapshots
# ("EHR snapshot 2018" / "EHR snapshot 2024") that share chronic
# conditions / persistent meds / immunizations across the cutoff.
#
# Generation runs at module import time; output is cached under
# ``data/harmonize-demo/synthea-demo/`` and is regenerated when the
# source patient bundle changes.

_SYNTHEA_DEMO_PATIENT = (
    REPO_ROOT
    / "data"
    / "synthea-samples"
    / "synthea-r4-individual"
    / "fhir"
    / "Adria871_Ankunding277_89d97565-2497-4d7b-91b0-90543c0e6a9c.json"
)
_SYNTHEA_DEMO_DIR = REPO_ROOT / "data" / "harmonize-demo" / "synthea-demo"
_SYNTHEA_SPLIT_DATE = "2018-01-01"


def _synthea_resource_date(resource: dict[str, Any]) -> str | None:
    """Pull a representative date from a Synthea FHIR resource for splitting."""
    for key in (
        "effectiveDateTime",
        "onsetDateTime",
        "authoredOn",
        "occurrenceDateTime",
        "recordedDate",
        "issued",
    ):
        v = resource.get(key)
        if isinstance(v, str) and v:
            return v[:10]
    period = resource.get("period")
    if isinstance(period, dict) and isinstance(period.get("start"), str):
        return period["start"][:10]
    return None


def _ensure_synthea_demo_artifacts() -> tuple[Path, Path] | None:
    """Generate the two temporal-snapshot bundles if they don't exist or are stale.

    Returns ``(snapshot_2018_path, snapshot_2024_path)`` or ``None`` if the
    source Synthea patient isn't checked out.
    """
    if not _SYNTHEA_DEMO_PATIENT.exists():
        return None

    early = _SYNTHEA_DEMO_DIR / "ehr-snapshot-2018.json"
    late = _SYNTHEA_DEMO_DIR / "ehr-snapshot-2024.json"

    src_mtime = _SYNTHEA_DEMO_PATIENT.stat().st_mtime
    if (
        early.exists()
        and late.exists()
        and early.stat().st_mtime >= src_mtime
        and late.stat().st_mtime >= src_mtime
    ):
        return early, late

    bundle = json.loads(_SYNTHEA_DEMO_PATIENT.read_text())
    early_entries: list[dict[str, Any]] = []
    late_entries: list[dict[str, Any]] = []

    # The Patient resource (and other identity-anchoring resources) goes into
    # both snapshots so each looks like a complete record.
    persistent_types = {"Patient", "Practitioner", "Organization", "CareTeam"}

    for entry in bundle.get("entry", []):
        resource = entry.get("resource", {})
        rt = resource.get("resourceType")
        if rt in persistent_types:
            early_entries.append(entry)
            late_entries.append(entry)
            continue
        # Conditions are chronic state — if they onset before the cutoff
        # they should appear in BOTH snapshots (the late snapshot has
        # carried them forward as ongoing problems).
        if rt == "Condition":
            onset = _synthea_resource_date(resource)
            if onset and onset < _SYNTHEA_SPLIT_DATE:
                early_entries.append(entry)
                late_entries.append(entry)
                continue
            # Conditions that onset after the cutoff only appear in late.
            late_entries.append(entry)
            continue
        # MedicationRequests: a request authored before the cutoff with
        # status active appears in both (carried prescription).
        if rt == "MedicationRequest":
            authored = _synthea_resource_date(resource)
            status = resource.get("status")
            if authored and authored < _SYNTHEA_SPLIT_DATE:
                early_entries.append(entry)
                if status == "active":
                    late_entries.append(entry)
                continue
            late_entries.append(entry)
            continue
        # Everything else: split on the first available date.
        dt = _synthea_resource_date(resource)
        if dt and dt < _SYNTHEA_SPLIT_DATE:
            early_entries.append(entry)
        else:
            late_entries.append(entry)

    _SYNTHEA_DEMO_DIR.mkdir(parents=True, exist_ok=True)
    early.write_text(
        json.dumps({"resourceType": "Bundle", "type": "collection", "entry": early_entries}, indent=2)
    )
    late.write_text(
        json.dumps({"resourceType": "Bundle", "type": "collection", "entry": late_entries}, indent=2)
    )
    return early, late


def _synthea_demo_collection() -> CollectionDefinition | None:
    paths = _ensure_synthea_demo_artifacts()
    if paths is None:
        return None
    early, late = paths
    return CollectionDefinition(
        id="synthea-demo",
        name="Synthea — demo patient (temporal split)",
        description=(
            "A synthetic single-patient record split into two temporal EHR "
            "snapshots (pre-2018 and full record) so the harmonize layer has "
            "two cross-referencing sources to merge. Use this when you don't "
            "have your own data uploaded yet — every USCDI core resource "
            "type contributes to both sources, and chronic conditions / "
            "active meds / immunizations cross-source merge realistically."
        ),
        sources=(
            SourceDefinition(
                id="synthea-snapshot-2018",
                label="EHR snapshot · 2018",
                kind="fhir-pull",
                path=early,
                document_reference="DocumentReference/synthea-snapshot-2018",
            ),
            SourceDefinition(
                id="synthea-snapshot-2024",
                label="EHR snapshot · 2024",
                kind="fhir-pull",
                path=late,
                document_reference="DocumentReference/synthea-snapshot-2024",
            ),
        ),
    )


_COLLECTIONS: dict[str, CollectionDefinition] = {
    "blake-real": CollectionDefinition(
        id="blake-real",
        name="Blake Thomson — real EHI exports",
        description=(
            "Cross-source aggregation of Blake's actual records: the Cedars-Sinai "
            "Health-Skillz FHIR pull, the Cedars-Sinai HealthSummary PDF, and three "
            "Function Health Quest lab PDFs."
        ),
        sources=(
            SourceDefinition(
                id="cedars-fhir",
                label="Cedars-Sinai (FHIR)",
                kind="fhir-pull",
                path=_BLAKE_DIR / "cedars-healthskillz-download" / "health-records.json",
                document_reference="DocumentReference/cedars-healthskillz-2025-11-07",
            ),
            SourceDefinition(
                id="cedars-pdf",
                label="Cedars-Sinai (PDF)",
                kind="extracted-pdf",
                path=_BLAKE_DIR
                / "HealthSummary_May_03_2026"
                / "extracted-cedars-healthsummary.json",
                document_reference="DocumentReference/cedars-health-summary-pdf",
            ),
            SourceDefinition(
                id="function-health-2024-07-26",
                label="Function Health · 2024-07-26",
                kind="extracted-pdf",
                path=_BLAKE_DIR
                / "blake_function_pdfs"
                / "extracted-2024-07-26.json",
                document_reference="DocumentReference/function-health-2024-07-26",
            ),
            SourceDefinition(
                id="function-health-2024-07-29",
                label="Function Health · 2024-07-29",
                kind="extracted-pdf",
                path=_BLAKE_DIR
                / "blake_function_pdfs"
                / "extracted-2024-07-29.json",
                document_reference="DocumentReference/function-health-2024-07-29",
            ),
            SourceDefinition(
                id="function-health-2025-11-29",
                label="Function Health · 2025-11-29",
                kind="extracted-pdf",
                path=_BLAKE_DIR
                / "blake_function_pdfs"
                / "extracted-2025-11-29.json",
                document_reference="DocumentReference/function-health-2025-11-29",
            ),
        ),
    ),
}


# ---------------------------------------------------------------------------
# Upload-derived collection discovery
# ---------------------------------------------------------------------------
#
# Each subdirectory under ``data/aggregation-uploads/<upload_session>/``
# becomes one collection. A subdirectory's source list is built from the
# files inside it:
#
#   foo.pdf                 → extracted-pdf source (extraction at
#                             foo.extracted.json if cached)
#   bar.json                → fhir-pull source (if FHIR-shaped)
#   baz.xml                 → ccda-xml source (if it is a CDA ClinicalDocument)
#
# The collection ID is ``upload-<session>``. The ``session`` segment is
# whatever the upload flow chose to key on (currently the patient_id, but
# the harmonizer doesn't care).


def _looks_like_fhir(path: Path) -> bool:
    """Cheap structural check: does this JSON look like FHIR?"""
    if path.suffix.lower() != ".json":
        return False
    try:
        with path.open() as fh:
            head = fh.read(4096)
        # Accept both the Health-Skillz envelope and plain Bundles.
        return (
            '"resourceType"' in head
            or '"fhir"' in head
            or '"providers"' in head
        )
    except OSError:
        return False


def _upload_session_to_collection(session_dir: Path) -> CollectionDefinition | None:
    """Synthesize a CollectionDefinition from one upload-session directory."""
    if not session_dir.is_dir():
        return None
    sources: list[SourceDefinition] = []
    for entry in sorted(session_dir.iterdir()):
        if not entry.is_file():
            continue
        # Skip metadata sidecars and extraction-cache files.
        if entry.name.endswith((".metadata.json", ".extracted.json")):
            continue
        suffix = entry.suffix.lower()
        if suffix == ".pdf":
            sources.append(
                SourceDefinition(
                    id=f"pdf-{entry.stem}",
                    label=entry.name,
                    kind="extracted-pdf",
                    # The extracted JSON is conventionally written next to
                    # the PDF as ``<basename>.extracted.json``. The loader
                    # will return an empty dict if the extraction hasn't
                    # been run yet — the manifest reflects that.
                    path=entry.with_suffix(entry.suffix + ".extracted.json"),
                    document_reference=f"DocumentReference/upload-{entry.stem}",
                )
            )
        elif suffix == ".json" and _looks_like_fhir(entry):
            sources.append(
                SourceDefinition(
                    id=f"fhir-{entry.stem}",
                    label=entry.name,
                    kind="fhir-pull",
                    path=entry,
                    document_reference=f"DocumentReference/upload-{entry.stem}",
                )
            )
        elif suffix == ".xml" and is_ccda_xml(entry):
            sources.append(
                SourceDefinition(
                    id=f"ccda-{entry.stem}",
                    label=entry.name,
                    kind="ccda-xml",
                    path=entry,
                    document_reference=f"DocumentReference/upload-{entry.stem}",
                )
            )
    if not sources:
        return None
    return CollectionDefinition(
        id=f"upload-{session_dir.name}",
        name=f"Uploaded session · {session_dir.name}",
        description=(
            f"Documents uploaded under session ``{session_dir.name}``: "
            f"{sum(1 for s in sources if s.kind == 'extracted-pdf')} PDF(s), "
            f"{sum(1 for s in sources if s.kind == 'fhir-pull')} FHIR file(s), "
            f"{sum(1 for s in sources if s.kind == 'ccda-xml')} C-CDA file(s)."
        ),
        sources=tuple(sources),
    )


def _discover_upload_collections() -> dict[str, CollectionDefinition]:
    if not UPLOADS_ROOT.exists():
        return {}
    out: dict[str, CollectionDefinition] = {}
    for sub in sorted(UPLOADS_ROOT.iterdir()):
        coll = _upload_session_to_collection(sub)
        if coll is not None:
            out[coll.id] = coll
    return out


# ---------------------------------------------------------------------------
# Patient workspace collections
# ---------------------------------------------------------------------------


def _safe_upload_segment(value: str) -> str:
    """Mirror the aggregation upload-store path sanitization."""
    import re

    return re.sub(r"[^A-Za-z0-9_.-]+", "-", value).strip(".-")[:120] or "patient"


def workspace_collection_id(patient_id: str) -> str:
    """Stable collection id for the selected patient's canonical workspace."""
    return f"workspace-{_safe_upload_segment(patient_id)}"


def _patient_id_from_workspace_collection(collection_id: str) -> str | None:
    if not collection_id.startswith("workspace-"):
        return None
    return collection_id.removeprefix("workspace-")


def _profile_display_name(patient_id: str) -> str | None:
    """Return the server-local workspace label without importing aggregation.

    Harmonization must be able to represent an empty workspace before any
    sources are uploaded. The profile registry is the durable signal that the
    workspace exists.
    """
    if not PROFILE_REGISTRY_PATH.exists():
        return None
    try:
        raw = json.loads(PROFILE_REGISTRY_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    items = raw.get("profiles") if isinstance(raw, dict) else raw
    if not isinstance(items, list):
        return None
    safe_id = _safe_upload_segment(patient_id)
    for item in items:
        if not isinstance(item, dict):
            continue
        if item.get("id") != safe_id:
            continue
        display_name = item.get("display_name")
        if isinstance(display_name, str) and display_name.strip():
            return display_name.strip()
    return None


def patient_workspace_collection(patient_id: str) -> CollectionDefinition | None:
    """Build the harmonize collection for one selected patient workspace.

    The Synthea patient bundle is the baseline source for development users.
    Any uploaded files under the same patient workspace are additional sources
    that can be extracted and merged on top.
    """
    safe_id = _safe_upload_segment(patient_id)
    sources: list[SourceDefinition] = []
    profile_label = _profile_display_name(patient_id)
    upload_root = UPLOADS_ROOT / safe_id

    patient_path = path_from_patient_id(patient_id)
    if patient_path is not None:
        sources.append(
            SourceDefinition(
                id="synthea-fhir",
                label="Synthea FHIR patient bundle",
                kind="fhir-pull",
                path=patient_path,
                document_reference=f"DocumentReference/synthea-baseline-{safe_id}",
            )
        )

    upload_collection = _upload_session_to_collection(upload_root)
    if upload_collection is not None:
        sources.extend(
            SourceDefinition(
                id=f"upload-{source.id}",
                label=source.label,
                kind=source.kind,
                path=source.path,
                document_reference=source.document_reference,
            )
            for source in upload_collection.sources
        )

    workspace_exists = profile_label is not None or upload_root.exists()
    if not sources and not workspace_exists:
        return None

    patient_label = (
        patient_display_name(patient_path)
        if patient_path is not None
        else profile_label or patient_id
    )
    upload_count = max(0, len(sources) - (1 if patient_path is not None else 0))
    return CollectionDefinition(
        id=workspace_collection_id(patient_id),
        name=f"{patient_label} — patient workspace",
        description=(
            "The selected patient's baseline FHIR bundle plus any uploaded "
            f"source files staged in Source Intake. {upload_count} uploaded "
            f"source{'s' if upload_count != 1 else ''} attached."
        ),
        sources=tuple(sources),
    )


def _all_static_collections() -> dict[str, CollectionDefinition]:
    """Public collections — Synthea demo if its source patient is checked out,
    plus blake-real if any of its sources are present locally.

    Conditional registration keeps fresh-clone reviewers from seeing an
    empty blake-real collection. The Synthea demo bootstraps from public
    Synthea data shipped with the repo, so it's available everywhere.
    """
    out: dict[str, CollectionDefinition] = {}
    demo = _synthea_demo_collection()
    if demo is not None:
        out[demo.id] = demo
    blake = _COLLECTIONS.get("blake-real")
    if blake is not None and any(s.path.exists() for s in blake.sources):
        out[blake.id] = blake
    return out


def list_collections() -> list[CollectionDefinition]:
    """Static + Synthea demo first, then any upload-derived collections."""
    out: list[CollectionDefinition] = list(_all_static_collections().values())
    out.extend(_discover_upload_collections().values())
    return out


def get_collection(collection_id: str) -> CollectionDefinition | None:
    workspace_patient_id = _patient_id_from_workspace_collection(collection_id)
    if workspace_patient_id:
        return patient_workspace_collection(workspace_patient_id)
    static = _all_static_collections()
    if collection_id in static:
        return static[collection_id]
    return _discover_upload_collections().get(collection_id)


# ---------------------------------------------------------------------------
# Source loading
# ---------------------------------------------------------------------------


def _load_resources_by_type(source: SourceDefinition) -> dict[str, list[dict]]:
    """Return ``{resourceType: [resource, ...]}`` for one source."""
    if not source.path.exists():
        return {}
    out: dict[str, list[dict]] = {}
    if source.kind == "ccda-xml":
        try:
            raw_bundle = convert_ccda_to_fhir_bundle(str(source.path), source.id)
        except Exception:
            if is_converter_required():
                raise
            return {}
        for entry in raw_bundle.get("entry", []):
            r = entry.get("resource", {}) if isinstance(entry, dict) else {}
            rt = r.get("resourceType") if isinstance(r, dict) else None
            if rt:
                out.setdefault(rt, []).append(r)
        return out

    raw = json.loads(source.path.read_text())
    if source.kind == "fhir-pull":
        # Health-Skillz envelope variants:
        #   dict with top-level fhir: {ResourceType: [...]}
        #   list[{provider, fhir: {ResourceType: [...]}}]
        if isinstance(raw, dict) and isinstance(raw.get("fhir"), dict):
            for rtype, resources in raw["fhir"].items():
                if isinstance(resources, list):
                    out[rtype] = list(resources)
            return out
        if isinstance(raw, list) and raw and isinstance(raw[0].get("fhir"), dict):
            for rtype, resources in raw[0]["fhir"].items():
                if isinstance(resources, list):
                    out[rtype] = list(resources)
            return out
        # Plain FHIR Bundle fallback
        entries = raw.get("entry", []) if isinstance(raw, dict) else []
        for entry in entries:
            r = entry.get("resource", {})
            rt = r.get("resourceType")
            if rt:
                out.setdefault(rt, []).append(r)
        return out
    # extracted-pdf — multipass-fhir always emits a Bundle
    for entry in raw.get("entry", []):
        r = entry.get("resource", {})
        rt = r.get("resourceType")
        if rt:
            out.setdefault(rt, []).append(r)
    return out


def _first_patient(resources_by_type: dict[str, list[dict]]) -> dict[str, Any] | None:
    for patient in resources_by_type.get("Patient", []):
        if isinstance(patient, dict):
            return patient
    return None


def _baseline_patient_for_identity_check(
    coll: CollectionDefinition,
    loaded: dict[str, dict[str, list[dict]]],
) -> dict[str, Any] | None:
    """Choose a non-C-CDA patient anchor for source identity checks."""

    for source in coll.sources:
        if source.kind == "ccda-xml":
            continue
        patient = _first_patient(loaded.get(source.id, {}))
        if patient is not None:
            return patient
    return None


def _ccda_identity_status(
    baseline_patient: dict[str, Any] | None,
    source_resources: dict[str, list[dict]],
) -> str:
    if baseline_patient is None:
        return "not_checked"
    candidate = _first_patient(source_resources)
    return compare_patient_identity(baseline_patient, candidate).status


# Cache by mtime tuple so re-extracting any source PDF naturally invalidates.
def _mtime_key(collection: CollectionDefinition) -> tuple:
    return tuple(
        (s.id, s.path.stat().st_mtime if s.path.exists() else 0.0) for s in collection.sources
    )


@lru_cache(maxsize=8)
def _cached_load(collection_id: str, mtime_signature: tuple) -> dict[str, dict[str, list[dict]]]:
    """Loads every source for a collection, returning ``{source_id: {rtype: [resource]}}``."""
    coll = get_collection(collection_id)
    if not coll:
        return {}
    loaded = {s.id: _load_resources_by_type(s) for s in coll.sources}
    baseline_patient = _baseline_patient_for_identity_check(coll, loaded)
    if baseline_patient is None:
        return loaded
    for source in coll.sources:
        if source.kind != "ccda-xml":
            continue
        if _ccda_identity_status(baseline_patient, loaded.get(source.id, {})) == "mismatch":
            loaded[source.id] = {}
    return loaded


def load_collection_resources(collection_id: str) -> dict[str, dict[str, list[dict]]]:
    coll = get_collection(collection_id)
    if not coll:
        return {}
    return _cached_load(collection_id, _mtime_key(coll))


# ---------------------------------------------------------------------------
# Source manifest
# ---------------------------------------------------------------------------


def collection_source_manifest(collection_id: str) -> list[dict[str, Any]] | None:
    coll = get_collection(collection_id)
    if not coll:
        return None
    resources = load_collection_resources(collection_id)
    baseline_patient = _baseline_patient_for_identity_check(coll, resources)
    out = []
    for s in coll.sources:
        rs = resources.get(s.id, {})
        total = sum(len(v) for v in rs.values())
        available = s.path.exists()
        if s.kind == "fhir-pull":
            if not available:
                status = "missing"
                status_label = "Source file missing"
            elif total > 0:
                status = "structured"
                status_label = "Structured source ready"
            else:
                status = "unparsed_structured"
                status_label = "Structured file not parsed"
        elif s.kind == "extracted-pdf":
            if not available:
                status = "pending_extraction"
                status_label = "PDF pending extraction"
            elif total > 0:
                status = "extracted"
                status_label = "Extracted candidate facts"
            else:
                status = "empty_extraction"
                status_label = "Extracted with no structured facts"
        elif s.kind == "ccda-xml":
            raw_rs = _load_resources_by_type(s) if available else {}
            identity_status = _ccda_identity_status(baseline_patient, raw_rs)
            if not available:
                status = "missing"
                status_label = "C-CDA source file missing"
            elif identity_status == "mismatch":
                status = "identity_mismatch"
                status_label = "C-CDA patient identity does not match workspace patient"
            elif total > 0:
                status = "structured"
                status_label = "Converted C-CDA facts ready"
            else:
                status = "unparsed_structured"
                status_label = "C-CDA parsed with no supported facts"
        else:
            status = "missing" if not available else "structured"
            status_label = "Source ready" if available else "Source file missing"
        out.append(
            {
                "id": s.id,
                "label": s.label,
                "kind": s.kind,
                "available": available,
                "document_reference": s.document_reference,
                "resource_counts": {rt: len(v) for rt, v in rs.items()},
                "total_resources": total,
                "status": status,
                "status_label": status_label,
            }
        )
    return out


# ---------------------------------------------------------------------------
# Supporting clinical artifacts
# ---------------------------------------------------------------------------


def _raw_source_payload(source: SourceDefinition) -> dict[str, Any] | list[Any] | None:
    if not source.path.exists():
        return None
    try:
        raw = json.loads(source.path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if isinstance(raw, (dict, list)):
        return raw
    return None


def _codeable_text(value: Any) -> str:
    if not isinstance(value, dict):
        return ""
    if isinstance(value.get("text"), str) and value["text"].strip():
        return value["text"].strip()
    for coding in value.get("coding") or []:
        if isinstance(coding, dict):
            display = coding.get("display")
            if isinstance(display, str) and display.strip():
                return display.strip()
            code = coding.get("code")
            if isinstance(code, str) and code.strip():
                return code.strip()
    return ""


def _codeable_code(value: Any) -> str:
    if not isinstance(value, dict):
        return ""
    for coding in value.get("coding") or []:
        if isinstance(coding, dict) and isinstance(coding.get("code"), str):
            return coding["code"].strip()
    return ""


def _codeable_system(value: Any) -> str:
    if not isinstance(value, dict):
        return ""
    for coding in value.get("coding") or []:
        if isinstance(coding, dict) and isinstance(coding.get("system"), str):
            return coding["system"].strip()
    return ""


def _reference_id(value: Any) -> str | None:
    if not isinstance(value, dict):
        return None
    ref = value.get("reference")
    if not isinstance(ref, str) or not ref.strip():
        return None
    return ref.rsplit("/", 1)[-1].removeprefix("urn:uuid:")


def _reference_type_and_id(value: Any) -> tuple[str, str]:
    if not isinstance(value, dict):
        return "", ""
    ref = value.get("reference")
    if not isinstance(ref, str) or not ref.strip():
        return "", ""
    cleaned = ref.strip()
    if cleaned.startswith("urn:uuid:"):
        return "", cleaned.removeprefix("urn:uuid:")
    if "/" not in cleaned:
        return "", cleaned
    resource_type, resource_id = cleaned.rsplit("/", 1)
    return resource_type.rsplit("/", 1)[-1], resource_id


def _human_name_text(value: Any) -> str:
    if isinstance(value, list):
        for item in value:
            text = _human_name_text(item)
            if text:
                return text
        return ""
    if not isinstance(value, dict):
        return ""
    if isinstance(value.get("text"), str) and value["text"].strip():
        return value["text"].strip()
    parts: list[str] = []
    for key in ("prefix", "given"):
        raw = value.get(key)
        if isinstance(raw, list):
            parts.extend(str(item).strip() for item in raw if str(item).strip())
        elif isinstance(raw, str) and raw.strip():
            parts.append(raw.strip())
    family = value.get("family")
    if isinstance(family, str) and family.strip():
        parts.append(family.strip())
    suffix = value.get("suffix")
    if isinstance(suffix, list):
        parts.extend(str(item).strip() for item in suffix if str(item).strip())
    elif isinstance(suffix, str) and suffix.strip():
        parts.append(suffix.strip())
    return " ".join(parts)


def _resource_display(resource: dict[str, Any]) -> str:
    resource_type = resource.get("resourceType")
    if resource_type == "Organization":
        name = resource.get("name")
        return name.strip() if isinstance(name, str) and name.strip() else ""
    if resource_type == "Practitioner":
        return _human_name_text(resource.get("name"))
    if resource_type == "Location":
        name = resource.get("name")
        return name.strip() if isinstance(name, str) and name.strip() else ""
    if resource_type == "PractitionerRole":
        practitioner = resource.get("practitioner")
        if isinstance(practitioner, dict) and isinstance(practitioner.get("display"), str) and practitioner["display"].strip():
            return practitioner["display"].strip()
        specialty = resource.get("specialty")
        if isinstance(specialty, list) and specialty:
            label = _codeable_text(specialty[0])
            if label:
                return label
        organization = resource.get("organization")
        if isinstance(organization, dict) and isinstance(organization.get("display"), str) and organization["display"].strip():
            return organization["display"].strip()
    return ""


def _specialty_labels(resource: dict[str, Any]) -> list[str]:
    labels: list[str] = []
    for item in resource.get("specialty") or []:
        label = _codeable_text(item) if isinstance(item, dict) else ""
        if label and label not in labels:
            labels.append(label)
    for qualification in resource.get("qualification") or []:
        if not isinstance(qualification, dict):
            continue
        label = _codeable_text(qualification.get("code"))
        if label and label not in labels:
            labels.append(label)
    return labels


def _reference_display(value: Any, display_index: dict[tuple[str, str], str], id_index: dict[str, str]) -> str:
    if not isinstance(value, dict):
        return ""
    display = value.get("display")
    if isinstance(display, str) and display.strip():
        return display.strip()
    resource_type, resource_id = _reference_type_and_id(value)
    if resource_type and resource_id:
        indexed = display_index.get((resource_type, resource_id))
        if indexed:
            return indexed
    if resource_id:
        return id_index.get(resource_id, "")
    return ""


def _reference_display_list(
    values: Any,
    display_index: dict[tuple[str, str], str],
    id_index: dict[str, str],
) -> list[str]:
    out: list[str] = []
    for value in values or []:
        label = _reference_display(value, display_index, id_index)
        if label and label not in out:
            out.append(label)
    return out


def _reference_display_pairs(
    values: Any,
    display_index: dict[tuple[str, str], str],
    id_index: dict[str, str],
) -> list[tuple[str, str]]:
    refs = values if isinstance(values, list) else [values]
    out: list[tuple[str, str]] = []
    for value in refs or []:
        resource_type, _resource_id = _reference_type_and_id(value)
        label = _reference_display(value, display_index, id_index)
        if label and (resource_type, label) not in out:
            out.append((resource_type, label))
    return out


def _labels_for_type(pairs: list[tuple[str, str]], *resource_types: str) -> list[str]:
    wanted = set(resource_types)
    labels: list[str] = []
    for resource_type, label in pairs:
        if resource_type in wanted and label not in labels:
            labels.append(label)
    return labels


def _specialty_labels_for_refs(values: Any, resource_index: dict[tuple[str, str], dict[str, Any]]) -> list[str]:
    refs = values if isinstance(values, list) else [values]
    labels: list[str] = []
    for value in refs or []:
        resource_type, resource_id = _reference_type_and_id(value)
        resource = resource_index.get((resource_type, resource_id)) if resource_type and resource_id else None
        if not isinstance(resource, dict):
            continue
        for label in _specialty_labels(resource):
            if label and label not in labels:
                labels.append(label)
    return labels


def _resource_display_indexes(
    resources_by_source: dict[str, dict[str, list[dict]]],
) -> tuple[dict[tuple[str, str], str], dict[str, str]]:
    display_index: dict[tuple[str, str], str] = {}
    id_index: dict[str, str] = {}
    for source_resources in resources_by_source.values():
        for resource_type in ("Organization", "Practitioner", "PractitionerRole", "Location"):
            for resource in source_resources.get(resource_type, []):
                if not isinstance(resource, dict):
                    continue
                resource_id = str(resource.get("id") or "").strip()
                label = _resource_display(resource)
                if resource_id and label:
                    display_index[(resource_type, resource_id)] = label
                    id_index.setdefault(resource_id, label)
    return display_index, id_index


def _resource_date(resource: dict[str, Any]) -> str | None:
    for key in (
        "effectiveDateTime",
        "performedDateTime",
        "occurrenceDateTime",
        "onsetDateTime",
        "authoredOn",
        "recordedDate",
        "issued",
        "date",
    ):
        value = resource.get(key)
        if isinstance(value, str) and value:
            return value
    for key in ("period", "performedPeriod", "effectivePeriod"):
        period = resource.get(key)
        if isinstance(period, dict) and isinstance(period.get("start"), str):
            return period["start"]
    return None


def _period(resource: dict[str, Any], key: str) -> dict[str, str | None]:
    value = resource.get(key)
    if isinstance(value, dict):
        return {
            "start": value.get("start") if isinstance(value.get("start"), str) else None,
            "end": value.get("end") if isinstance(value.get("end"), str) else None,
        }
    dt = _resource_date(resource)
    return {"start": dt, "end": dt}


def _date_span(resources_by_type: dict[str, list[dict]]) -> dict[str, str | None]:
    dates = []
    for resources in resources_by_type.values():
        for resource in resources:
            dt = _resource_date(resource)
            if dt:
                dates.append(dt)
    dates.sort()
    return {"start": dates[0] if dates else None, "end": dates[-1] if dates else None}


def _document_context(source: SourceDefinition) -> dict[str, Any] | None:
    raw = _raw_source_payload(source)
    if not isinstance(raw, dict):
        return None
    meta = raw.get("meta")
    if not isinstance(meta, dict):
        return None
    for ext in meta.get("extension") or []:
        if not isinstance(ext, dict):
            continue
        url = ext.get("url")
        if not isinstance(url, str) or not url.endswith("/document-context"):
            continue
        value = ext.get("valueString")
        if not isinstance(value, str) or not value.strip():
            return None
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return {"raw": value}
        return parsed if isinstance(parsed, dict) else None
    return None


def _strip_html(value: str) -> str:
    text = re.sub(r"<[^>]+>", " ", value)
    return re.sub(r"\s+", " ", text).strip()


def _attachment_text(attachment: Any) -> str:
    if not isinstance(attachment, dict):
        return ""
    if isinstance(attachment.get("data"), str):
        try:
            return base64.b64decode(attachment["data"], validate=True).decode("utf-8", errors="replace").strip()
        except (binascii.Error, ValueError):
            return ""
    if isinstance(attachment.get("url"), str):
        return attachment["url"].strip()
    return ""


def _annotation_author(note: dict[str, Any]) -> str:
    author = note.get("authorString")
    if isinstance(author, str) and author.strip():
        return author.strip()
    author_ref = note.get("authorReference")
    if isinstance(author_ref, dict):
        display = author_ref.get("display")
        if isinstance(display, str) and display.strip():
            return display.strip()
        reference = author_ref.get("reference")
        if isinstance(reference, str) and reference.strip():
            return reference.strip()
    return ""


def _resource_note_entries(resource: dict[str, Any]) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for note in resource.get("note") or []:
        if isinstance(note, dict) and isinstance(note.get("text"), str) and note["text"].strip():
            out.append(
                {
                    "text": note["text"].strip(),
                    "author": _annotation_author(note),
                    "time": note.get("time") if isinstance(note.get("time"), str) else "",
                }
            )
    if resource.get("resourceType") == "DiagnosticReport":
        for attachment in resource.get("presentedForm") or []:
            text = _attachment_text(attachment)
            if text:
                out.append(
                    {
                        "text": text,
                        "attachment_content_type": attachment.get("contentType")
                        if isinstance(attachment, dict) and isinstance(attachment.get("contentType"), str)
                        else "",
                    }
                )
    if resource.get("resourceType") == "Composition":
        for section in resource.get("section") or []:
            if not isinstance(section, dict):
                continue
            text = section.get("text")
            if isinstance(text, dict) and isinstance(text.get("div"), str):
                stripped = _strip_html(text["div"])
                if stripped:
                    out.append(
                        {
                            "text": stripped,
                            "section_title": section.get("title") if isinstance(section.get("title"), str) else "",
                        }
                    )
    if resource.get("resourceType") == "DocumentReference":
        description = resource.get("description")
        if isinstance(description, str) and description.strip():
            out.append({"text": description.strip()})
    return out


def _resource_notes(resource: dict[str, Any]) -> list[str]:
    return [entry["text"] for entry in _resource_note_entries(resource) if entry.get("text")]


def clinical_artifacts(collection_id: str) -> dict[str, list[dict[str, Any]]]:
    """Return document-heavy supporting artifacts from every collection source.

    The harmonizer's first-class matchers focus on canonical clinical facts.
    This companion payload keeps the document context, clinical notes, procedures,
    encounters, and diagnostic reports visible so downstream chart surfaces do not
    silently lose narrative or CDR resources.
    """
    coll = get_collection(collection_id)
    if not coll:
        return {
            "patients": [],
            "documents": [],
            "organizations": [],
            "practitioners": [],
            "practitioner_roles": [],
            "locations": [],
            "encounters": [],
            "observations": [],
            "procedures": [],
            "diagnostic_reports": [],
            "clinical_notes": [],
        }

    resources_by_source = load_collection_resources(collection_id)
    display_index, id_index = _resource_display_indexes(resources_by_source)
    resource_index: dict[tuple[str, str], dict[str, Any]] = {}
    for source_resources in resources_by_source.values():
        for resource_type, resources in source_resources.items():
            for resource in resources:
                if isinstance(resource, dict) and isinstance(resource.get("id"), str):
                    resource_index[(resource_type, resource["id"])] = resource
    documents: list[dict[str, Any]] = []
    patients: list[dict[str, Any]] = []
    organizations: list[dict[str, Any]] = []
    practitioners: list[dict[str, Any]] = []
    practitioner_roles: list[dict[str, Any]] = []
    locations: list[dict[str, Any]] = []
    encounters: list[dict[str, Any]] = []
    observations: list[dict[str, Any]] = []
    procedures: list[dict[str, Any]] = []
    diagnostic_reports: list[dict[str, Any]] = []
    clinical_notes: list[dict[str, Any]] = []

    for source in coll.sources:
        source_resources = resources_by_source.get(source.id, {})
        counts = {rtype: len(items) for rtype, items in source_resources.items()}
        span = _date_span(source_resources)
        context = _document_context(source)
        document_author_pairs: list[tuple[str, str]] = []
        for document_resource in source_resources.get("DocumentReference", []):
            if not isinstance(document_resource, dict):
                continue
            document_author_pairs.extend(
                _reference_display_pairs(document_resource.get("author"), display_index, id_index)
            )
        documents.append(
            {
                "source_id": source.id,
                "source_label": source.label,
                "source_kind": source.kind,
                "document_reference": source.document_reference,
                "path": str(source.path),
                "available": source.path.exists(),
                "document_context": context,
                "author_labels": _reference_display_list(
                    (context or {}).get("authors") if isinstance((context or {}).get("authors"), list) else [],
                    display_index,
                    id_index,
                ),
                "author_organization_labels": _labels_for_type(document_author_pairs, "Organization"),
                "author_practitioner_labels": _labels_for_type(document_author_pairs, "Practitioner"),
                "date_start": span["start"] or (context or {}).get("encounter_date"),
                "date_end": span["end"] or (context or {}).get("encounter_date"),
                "resource_counts": counts,
                "total_resources": sum(counts.values()),
            }
        )

        for resource_type, target in (
            ("Organization", organizations),
            ("Practitioner", practitioners),
            ("PractitionerRole", practitioner_roles),
            ("Location", locations),
        ):
            for resource in source_resources.get(resource_type, []):
                if not isinstance(resource, dict):
                    continue
                target.append(
                    {
                        "source_id": source.id,
                        "source_label": source.label,
                        "id": str(resource.get("id") or ""),
                        "display": _resource_display(resource),
                        "specialty_labels": _specialty_labels(resource),
                        "resource": resource,
                    }
                )

        for resource in source_resources.get("Patient", []):
            if not isinstance(resource, dict):
                continue
            patients.append(
                {
                    "source_id": source.id,
                    "source_label": source.label,
                    "id": str(resource.get("id") or ""),
                    "resource": resource,
                }
            )

        for resource in source_resources.get("Encounter", []):
            period = _period(resource, "period")
            service_provider = _reference_display(resource.get("serviceProvider"), display_index, id_index)
            participant_labels = []
            participant_refs = []
            for participant in resource.get("participant") or []:
                if not isinstance(participant, dict):
                    continue
                participant_refs.append(participant.get("individual"))
                label = _reference_display(participant.get("individual"), display_index, id_index)
                if label and label not in participant_labels:
                    participant_labels.append(label)
            location_labels = []
            for location in resource.get("location") or []:
                if not isinstance(location, dict):
                    continue
                label = _reference_display(location.get("location"), display_index, id_index)
                if label and label not in location_labels:
                    location_labels.append(label)
            provider = participant_labels[0] if participant_labels else ""
            encounters.append(
                {
                    "source_id": source.id,
                    "source_label": source.label,
                    "id": str(resource.get("id") or ""),
                    "status": str(resource.get("status") or ""),
                    "class_code": (resource.get("class") or {}).get("code") if isinstance(resource.get("class"), dict) else "",
                    "type": _codeable_text((resource.get("type") or [{}])[0]),
                    "reason": _codeable_text((resource.get("reasonCode") or [{}])[0]),
                    "period_start": period["start"],
                    "period_end": period["end"],
                    "provider": provider,
                    "service_provider": service_provider,
                    "participant_labels": participant_labels,
                    "practitioner_labels": participant_labels,
                    "specialty_labels": _specialty_labels_for_refs(participant_refs, resource_index),
                    "location_labels": location_labels,
                    "site": service_provider or (location_labels[0] if location_labels else ""),
                }
            )

        for resource in source_resources.get("Observation", []):
            if not isinstance(resource, dict):
                continue
            performer_labels = _reference_display_list(resource.get("performer"), display_index, id_index)
            performer_pairs = _reference_display_pairs(resource.get("performer"), display_index, id_index)
            observations.append(
                {
                    "source_id": source.id,
                    "source_label": source.label,
                    "id": str(resource.get("id") or ""),
                    "status": str(resource.get("status") or ""),
                    "category": _codeable_text((resource.get("category") or [{}])[0]),
                    "code": _codeable_code(resource.get("code")),
                    "system": _codeable_system(resource.get("code")),
                    "display": _codeable_text(resource.get("code")) or "Observation",
                    "effective_date": _resource_date(resource),
                    "encounter_id": _reference_id(resource.get("encounter")),
                    "performer_labels": performer_labels,
                    "performer_organization_labels": _labels_for_type(performer_pairs, "Organization"),
                    "performer_practitioner_labels": _labels_for_type(performer_pairs, "Practitioner", "PractitionerRole"),
                    "specialty_labels": _specialty_labels_for_refs(resource.get("performer"), resource_index),
                }
            )

        for resource in source_resources.get("Procedure", []):
            period = _period(resource, "performedPeriod")
            if not period["start"] and isinstance(resource.get("performedDateTime"), str):
                period = {"start": resource["performedDateTime"], "end": resource["performedDateTime"]}
            performer_labels = []
            performer_pairs: list[tuple[str, str]] = []
            for performer in resource.get("performer") or []:
                if not isinstance(performer, dict):
                    continue
                label = _reference_display(performer.get("actor"), display_index, id_index)
                if label and label not in performer_labels:
                    performer_labels.append(label)
                performer_pairs.extend(
                    _reference_display_pairs(performer.get("actor"), display_index, id_index)
                )
            procedures.append(
                {
                    "source_id": source.id,
                    "source_label": source.label,
                    "id": str(resource.get("id") or ""),
                    "status": str(resource.get("status") or ""),
                    "code": _codeable_code(resource.get("code")),
                    "system": _codeable_system(resource.get("code")),
                    "display": _codeable_text(resource.get("code")) or "Procedure",
                    "performed_start": period["start"],
                    "performed_end": period["end"],
                    "reason": _codeable_text((resource.get("reasonCode") or [{}])[0]),
                    "encounter_id": _reference_id(resource.get("encounter")),
                    "performer_labels": performer_labels,
                    "performer_organization_labels": _labels_for_type(performer_pairs, "Organization"),
                    "performer_practitioner_labels": _labels_for_type(performer_pairs, "Practitioner", "PractitionerRole"),
                    "specialty_labels": _specialty_labels_for_refs(
                        [performer.get("actor") for performer in resource.get("performer") or [] if isinstance(performer, dict)],
                        resource_index,
                    ),
                }
            )

        for resource in source_resources.get("DiagnosticReport", []):
            presented_text = "\n\n".join(_attachment_text(a) for a in resource.get("presentedForm") or [])
            presented_text = presented_text.strip()
            performer_labels = _reference_display_list(resource.get("performer"), display_index, id_index)
            performer_pairs = _reference_display_pairs(resource.get("performer"), display_index, id_index)
            results_interpreter_labels = _reference_display_list(
                resource.get("resultsInterpreter"),
                display_index,
                id_index,
            )
            results_interpreter_pairs = _reference_display_pairs(
                resource.get("resultsInterpreter"),
                display_index,
                id_index,
            )
            diagnostic_reports.append(
                {
                    "source_id": source.id,
                    "source_label": source.label,
                    "id": str(resource.get("id") or ""),
                    "status": str(resource.get("status") or ""),
                    "category": _codeable_text((resource.get("category") or [{}])[0]),
                    "code": _codeable_code(resource.get("code")),
                    "system": _codeable_system(resource.get("code")),
                    "display": _codeable_text(resource.get("code")) or "Diagnostic report",
                    "effective_date": _resource_date(resource),
                    "result_refs": [
                        ref
                        for ref in (_reference_id(item) for item in resource.get("result") or [])
                        if ref
                    ],
                    "encounter_id": _reference_id(resource.get("encounter")),
                    "performer_labels": performer_labels,
                    "performer_organization_labels": _labels_for_type(performer_pairs, "Organization"),
                    "performer_practitioner_labels": _labels_for_type(performer_pairs, "Practitioner", "PractitionerRole"),
                    "results_interpreter_labels": results_interpreter_labels,
                    "results_interpreter_organization_labels": _labels_for_type(
                        results_interpreter_pairs,
                        "Organization",
                    ),
                    "results_interpreter_practitioner_labels": _labels_for_type(
                        results_interpreter_pairs,
                        "Practitioner",
                        "PractitionerRole",
                    ),
                    "specialty_labels": _specialty_labels_for_refs(resource.get("performer"), resource_index)
                    + [
                        label
                        for label in _specialty_labels_for_refs(resource.get("resultsInterpreter"), resource_index)
                        if label not in _specialty_labels_for_refs(resource.get("performer"), resource_index)
                    ],
                    "has_presented_form": bool(resource.get("presentedForm")),
                    "presented_form_text": presented_text,
                }
            )

        for resource_type, resources in source_resources.items():
            for resource in resources:
                if not isinstance(resource, dict):
                    continue
                encounter_id = _reference_id(resource.get("encounter"))
                author_pairs = _reference_display_pairs(resource.get("author"), display_index, id_index)
                performer_pairs = _reference_display_pairs(resource.get("performer"), display_index, id_index)
                organization_labels = _labels_for_type(author_pairs + performer_pairs, "Organization")
                for idx, note_entry in enumerate(_resource_note_entries(resource)):
                    clinical_notes.append(
                        {
                            "source_id": source.id,
                            "source_label": source.label,
                            "resource_type": resource_type,
                            "resource_id": str(resource.get("id") or ""),
                            "note_index": idx,
                            "encounter_id": encounter_id,
                            "date": _resource_date(resource),
                            "author": note_entry.get("author") or "",
                            "organization": organization_labels[0] if organization_labels else "",
                            "document_type": _codeable_text(resource.get("type"))
                            or _codeable_text(resource.get("code"))
                            or note_entry.get("section_title")
                            or resource_type,
                            "category": _codeable_text((resource.get("category") or [{}])[0]),
                            "time": note_entry.get("time") or "",
                            "section_title": note_entry.get("section_title") or "",
                            "attachment_content_type": note_entry.get("attachment_content_type") or "",
                            "text": note_entry.get("text") or "",
                        }
                    )

    return {
        "patients": patients,
        "documents": documents,
        "organizations": organizations,
        "practitioners": practitioners,
        "practitioner_roles": practitioner_roles,
        "locations": locations,
        "encounters": encounters,
        "observations": observations,
        "procedures": procedures,
        "diagnostic_reports": diagnostic_reports,
        "clinical_notes": clinical_notes,
    }


# ---------------------------------------------------------------------------
# Merge orchestration
# ---------------------------------------------------------------------------


def _bundles_for(collection_id: str, resource_type: str) -> list[SourceBundle]:
    coll = get_collection(collection_id)
    if not coll:
        return []
    resources = load_collection_resources(collection_id)
    bundles = []
    for s in coll.sources:
        items = resources.get(s.id, {}).get(resource_type, [])
        if items:
            bundles.append(
                SourceBundle(
                    label=s.label,
                    observations=items,
                    document_reference=s.document_reference,
                )
            )
    return bundles


def merged_observations(collection_id: str) -> list[MergedObservation]:
    return merge_observations(_bundles_for(collection_id, "Observation"))


def merged_conditions(collection_id: str) -> list[MergedCondition]:
    return merge_conditions(_bundles_for(collection_id, "Condition"))


def merged_allergies(collection_id: str) -> list[MergedAllergy]:
    return merge_allergies(_bundles_for(collection_id, "AllergyIntolerance"))


def merged_immunizations(collection_id: str) -> list[MergedImmunization]:
    return merge_immunizations(_bundles_for(collection_id, "Immunization"))


def merged_medications(collection_id: str) -> list[MergedMedication]:
    """Merge MedicationRequests across sources.

    The matcher needs both ``MedicationRequest`` (the orders) and
    ``Medication`` (the contained resources holding RxNorm codes), so
    we hand both resource types into each ``SourceBundle``.
    """
    coll = get_collection(collection_id)
    if not coll:
        return []
    resources = load_collection_resources(collection_id)
    bundles: list[SourceBundle] = []
    for s in coll.sources:
        rs = resources.get(s.id, {})
        pool: list[dict] = list(rs.get("MedicationRequest", [])) + list(rs.get("Medication", []))
        if pool:
            bundles.append(
                SourceBundle(
                    label=s.label,
                    observations=pool,
                    document_reference=s.document_reference,
                )
            )
    return merge_medications(bundles)


# ---------------------------------------------------------------------------
# Serialization helpers (lib.harmonize.models → JSON-friendly dicts)
# ---------------------------------------------------------------------------


def _iso(dt: datetime | None) -> str | None:
    return dt.isoformat() if dt else None


def serialize_observation(m: MergedObservation) -> dict[str, Any]:
    return {
        "merged_ref": getattr(m, "_merged_ref", None),
        "canonical_name": m.canonical_name,
        "loinc_code": m.loinc_code,
        "canonical_unit": m.canonical_unit,
        "source_count": len({s.source_label for s in m.sources}),
        "measurement_count": len(m.sources),
        "has_conflict": m.has_conflict,
        "latest": (
            {
                "value": m.latest.value,
                "unit": m.latest.unit,
                "source_label": m.latest.source_label,
                "effective_date": _iso(m.latest.effective_date),
            }
            if m.latest
            else None
        ),
        "sources": [
            {
                "source_label": s.source_label,
                "source_observation_ref": s.source_observation_ref,
                "value": s.value,
                "unit": s.unit,
                "raw_value": s.raw_value,
                "raw_unit": s.raw_unit,
                "effective_date": _iso(s.effective_date),
                "document_reference": s.document_reference,
                "reference_low": s.reference_low,
                "reference_high": s.reference_high,
                "reference_unit": s.reference_unit,
            }
            for s in m.sources
        ],
    }


def serialize_allergy(m: MergedAllergy) -> dict[str, Any]:
    return {
        "merged_ref": getattr(m, "_merged_ref", None),
        "canonical_name": m.canonical_name,
        "snomed": m.snomed,
        "rxnorm": m.rxnorm,
        "is_active": m.is_active,
        "highest_criticality": m.highest_criticality,
        "source_count": len({s.source_label for s in m.sources}),
        "occurrence_count": len(m.sources),
        "sources": [
            {
                "source_label": s.source_label,
                "source_allergy_ref": s.source_allergy_ref,
                "display": s.display,
                "snomed": s.snomed,
                "rxnorm": s.rxnorm,
                "criticality": s.criticality,
                "clinical_status": s.clinical_status,
                "recorded_date": _iso(s.recorded_date),
                "document_reference": s.document_reference,
            }
            for s in m.sources
        ],
    }


def serialize_immunization(m: MergedImmunization) -> dict[str, Any]:
    return {
        "merged_ref": getattr(m, "_merged_ref", None),
        "canonical_name": m.canonical_name,
        "cvx": m.cvx,
        "ndc": m.ndc,
        "occurrence_date": _iso(m.occurrence_date),
        "source_count": len({s.source_label for s in m.sources}),
        "occurrence_count": len(m.sources),
        "sources": [
            {
                "source_label": s.source_label,
                "source_immunization_ref": s.source_immunization_ref,
                "display": s.display,
                "cvx": s.cvx,
                "ndc": s.ndc,
                "occurrence_date": _iso(s.occurrence_date),
                "status": s.status,
                "document_reference": s.document_reference,
            }
            for s in m.sources
        ],
    }


def serialize_medication(m: MergedMedication) -> dict[str, Any]:
    return {
        "merged_ref": getattr(m, "_merged_ref", None),
        "canonical_name": m.canonical_name,
        "rxnorm_codes": list(m.rxnorm_codes),
        "is_active": m.is_active,
        "source_count": len({s.source_label for s in m.sources}),
        "occurrence_count": len(m.sources),
        "sources": [
            {
                "source_label": s.source_label,
                "source_request_ref": s.source_request_ref,
                "display": s.display,
                "rxnorm_codes": list(s.rxnorm_codes),
                "status": s.status,
                "authored_on": _iso(s.authored_on),
                "document_reference": s.document_reference,
            }
            for s in m.sources
        ],
    }


def serialize_condition(m: MergedCondition) -> dict[str, Any]:
    return {
        "merged_ref": getattr(m, "_merged_ref", None),
        "canonical_name": m.canonical_name,
        "snomed": m.snomed,
        "icd10": m.icd10,
        "icd9": m.icd9,
        "is_active": m.is_active,
        "source_count": len({s.source_label for s in m.sources}),
        "occurrence_count": len(m.sources),
        "sources": [
            {
                "source_label": s.source_label,
                "source_condition_ref": s.source_condition_ref,
                "display": s.display,
                "snomed": s.snomed,
                "icd10": s.icd10,
                "icd9": s.icd9,
                "clinical_status": s.clinical_status,
                "onset_date": _iso(s.onset_date),
                "document_reference": s.document_reference,
            }
            for s in m.sources
        ],
    }


# ---------------------------------------------------------------------------
# Manual extraction trigger (PDFs in upload-derived collections)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ExtractResult:
    source_id: str
    label: str
    extracted_path: str
    cache_hit: bool
    entry_count: int
    elapsed_seconds: float


@dataclass(frozen=True)
class ExtractJobEvent:
    event_id: str
    event_type: str
    created_at: datetime
    stage: str
    message: str
    source_id: str | None = None
    source_label: str | None = None
    page_start: int | None = None
    page_end: int | None = None
    page_count: int | None = None
    processed_pages: int = 0
    total_pages: int | None = None
    processed_files: int = 0
    total_files: int = 0
    progress_basis: str = "lifecycle"
    is_estimate: bool = False


# ---------------------------------------------------------------------------
# Async extract job store
# ---------------------------------------------------------------------------
#
# Extraction takes 30-90s per PDF and blocks the request thread when run
# synchronously. We hand the React page a job_id immediately and let the
# extraction run in a background thread; the page polls the job for
# completion. The store is in-memory because:
#
#   * Jobs never need to survive process restart — a restart implies the
#     cache files might already be stale anyway.
#   * The job result is just a list of ExtractResult; the canonical state
#     lives on disk (the .extracted.json files next to each PDF).
#   * Single-process deployment for now; if/when we move to multi-worker,
#     this lifts cleanly to Redis with the same shape.

import threading
import uuid


@dataclass
class ExtractJob:
    """Background-executed extraction over the PDFs in one collection."""

    job_id: str
    collection_id: str
    status: str  # "pending" | "running" | "complete" | "failed"
    results: list[ExtractResult]
    error: str | None
    started_at: datetime
    completed_at: datetime | None
    total_files: int = 0
    processed_files: int = 0
    total_pages: int | None = None
    processed_pages: int = 0
    current_source_label: str | None = None
    stage: str = "queued"
    estimated_seconds: int | None = None
    events: list[ExtractJobEvent] = field(default_factory=list)


_EXTRACT_JOBS: dict[str, ExtractJob] = {}
_EXTRACT_COLLECTION_JOBS: dict[str, str] = {}
_EXTRACT_JOBS_LOCK = threading.Lock()


def _set_job_state(job: ExtractJob) -> None:
    with _EXTRACT_JOBS_LOCK:
        _EXTRACT_JOBS[job.job_id] = job
        _EXTRACT_COLLECTION_JOBS[job.collection_id] = job.job_id


def get_extract_job(job_id: str) -> ExtractJob | None:
    with _EXTRACT_JOBS_LOCK:
        return _EXTRACT_JOBS.get(job_id)


def get_latest_extract_job(collection_id: str) -> ExtractJob | None:
    with _EXTRACT_JOBS_LOCK:
        job_id = _EXTRACT_COLLECTION_JOBS.get(collection_id)
        return _EXTRACT_JOBS.get(job_id) if job_id else None


def _append_extract_event(
    job: ExtractJob,
    event_type: str,
    *,
    stage: str | None = None,
    message: str,
    source_id: str | None = None,
    source_label: str | None = None,
    page_start: int | None = None,
    page_end: int | None = None,
    page_count: int | None = None,
    progress_basis: str = "lifecycle",
    is_estimate: bool = False,
) -> None:
    job.events.append(
        ExtractJobEvent(
            event_id=uuid.uuid4().hex,
            event_type=event_type,
            created_at=datetime.now(),
            stage=stage or job.stage,
            message=message,
            source_id=source_id,
            source_label=source_label,
            page_start=page_start,
            page_end=page_end,
            page_count=page_count,
            processed_pages=job.processed_pages,
            total_pages=job.total_pages,
            processed_files=job.processed_files,
            total_files=job.total_files,
            progress_basis=progress_basis,
            is_estimate=is_estimate,
        )
    )
    # Keep the in-memory job bounded. The frontend only needs recent lifecycle
    # and checkpoint events, not an unbounded stream.
    if len(job.events) > 200:
        del job.events[:-200]


def _pdf_page_count(pdf_path: Path) -> int | None:
    """Best-effort page count for progress estimates.

    This intentionally never raises. Extraction itself owns hard PDF failures;
    progress metadata should not prevent a job from being enqueued.
    """
    try:
        import pypdfium2 as pdfium

        pdf = pdfium.PdfDocument(str(pdf_path))
        try:
            return len(pdf)
        finally:
            pdf.close()
    except Exception:
        return None


def _pending_pdf_work(collection: CollectionDefinition) -> list[tuple[SourceDefinition, Path, Path, int | None]]:
    work: list[tuple[SourceDefinition, Path, Path, int | None]] = []
    for src in collection.sources:
        if src.kind != "extracted-pdf":
            continue
        extracted_json = src.path
        pdf_name = extracted_json.name.removesuffix(".extracted.json")
        pdf_path = extracted_json.with_name(pdf_name)
        if not pdf_path.exists() or extracted_json.exists():
            continue
        work.append((src, pdf_path, extracted_json, _pdf_page_count(pdf_path)))
    return work


def _run_extract_job(job_id: str, collection_id: str) -> None:
    """Background entry point — invoked from a daemon thread."""
    job = get_extract_job(job_id)
    if job is None:
        return
    job.status = "running"
    job.stage = "Preparing PDF pipeline"
    _append_extract_event(
        job,
        "job_started",
        stage=job.stage,
        message="Extraction worker started.",
    )
    _set_job_state(job)
    try:
        results = extract_pending_pdfs(collection_id, job_id=job_id) or []
        job.results = list(results)
        job.status = "complete"
        job.stage = "Extraction complete"
        job.current_source_label = None
        job.processed_files = max(job.processed_files, job.total_files)
        if job.total_pages is not None:
            job.processed_pages = max(job.processed_pages, job.total_pages)
        _append_extract_event(
            job,
            "job_completed",
            stage=job.stage,
            message="Extraction job completed.",
        )
    except Exception as exc:
        job.status = "failed"
        job.error = f"{type(exc).__name__}: {exc}"
        job.stage = "Extraction failed"
        _append_extract_event(
            job,
            "job_failed",
            stage=job.stage,
            message=job.error,
        )
    finally:
        job.completed_at = datetime.now()
        _set_job_state(job)


def start_extract_job(collection_id: str) -> ExtractJob | None:
    """Enqueue an extraction job over a collection, return immediately.

    Returns ``None`` when the collection doesn't support extraction (static
    demo collections, unknown id) so the caller can 400/404 appropriately.
    """
    coll = get_collection(collection_id)
    if coll is None:
        return None
    if not (collection_id.startswith("upload-") or collection_id.startswith("workspace-")):
        return None
    latest = get_latest_extract_job(collection_id)
    if latest and latest.status in {"pending", "running"}:
        return latest
    pending_work = _pending_pdf_work(coll)
    total_pages = sum(item[3] for item in pending_work if item[3] is not None)
    job = ExtractJob(
        job_id=uuid.uuid4().hex,
        collection_id=collection_id,
        status="pending",
        results=[],
        error=None,
        started_at=datetime.now(),
        completed_at=None,
        total_files=len(pending_work),
        processed_files=0,
        total_pages=total_pages or None,
        processed_pages=0,
        stage="Queued",
        estimated_seconds=(max(30, total_pages * 45) if total_pages else (len(pending_work) * 60 or 30)),
    )
    _append_extract_event(
        job,
        "job_queued",
        stage=job.stage,
        message=(
            f"Queued {len(pending_work)} PDF file"
            f"{'' if len(pending_work) == 1 else 's'} for extraction."
        ),
    )
    page_cursor = 1
    for src, _pdf_path, _extracted_json, page_count in pending_work:
        page_start = page_cursor if page_count else None
        page_end = page_cursor + page_count - 1 if page_count else None
        _append_extract_event(
            job,
            "file_queued",
            stage=job.stage,
            message=(
                f"Queued {src.label}"
                + (f" with {page_count} page{'' if page_count == 1 else 's'}." if page_count else ".")
            ),
            source_id=src.id,
            source_label=src.label,
            page_start=page_start,
            page_end=page_end,
            page_count=page_count,
            progress_basis="metadata",
        )
        if page_count:
            page_cursor += page_count
    _set_job_state(job)
    thread = threading.Thread(
        target=_run_extract_job,
        args=(job.job_id, collection_id),
        daemon=True,
        name=f"harmonize-extract-{job.job_id[:8]}",
    )
    thread.start()
    return job


def extract_pending_pdfs(collection_id: str, job_id: str | None = None) -> list[ExtractResult] | None:
    """Run the multipass-fhir pipeline on every uploaded PDF in this collection
    that doesn't yet have a cached extraction next to it.

    Returns one ``ExtractResult`` per PDF processed (empty list if all PDFs
    already had cached extractions). Returns ``None`` when the collection
    doesn't exist or doesn't support extraction (the static demo collections
    are read-only).
    """
    coll = get_collection(collection_id)
    if coll is None:
        return None
    # Only upload-derived and patient workspace collections support extraction.
    # Static demo registry paths point at pre-staged extractions.
    if not (collection_id.startswith("upload-") or collection_id.startswith("workspace-")):
        return None

    # Lazy import — keeps the api/ surface free of the heavy
    # extraction stack at module-load time.
    import time

    from lib.extract.pipelines import get as get_pipeline

    PipelineCls = get_pipeline("multipass-fhir")
    pipeline = PipelineCls()

    results: list[ExtractResult] = []
    for src in coll.sources:
        if src.kind != "extracted-pdf":
            continue
        # ``src.path`` is the *extracted* JSON path (which may not exist yet).
        # The actual PDF is next to it; strip the ``.extracted.json`` suffix.
        extracted_json = src.path
        pdf_name = extracted_json.name.removesuffix(".extracted.json")
        pdf_path = extracted_json.with_name(pdf_name)
        if not pdf_path.exists():
            continue
        if extracted_json.exists():
            results.append(
                ExtractResult(
                    source_id=src.id,
                    label=src.label,
                    extracted_path=str(extracted_json),
                    cache_hit=True,
                    entry_count=len(json.loads(extracted_json.read_text()).get("entry", [])),
                    elapsed_seconds=0.0,
                )
            )
            continue
        job = get_extract_job(job_id) if job_id else None
        page_count = _pdf_page_count(pdf_path)
        if job is not None:
            job.current_source_label = src.label
            job.stage = "Reading pages and running FHIR passes"
            page_start = job.processed_pages + 1 if page_count else None
            page_end = job.processed_pages + page_count if page_count else None
            _append_extract_event(
                job,
                "file_started",
                stage=job.stage,
                message=(
                    f"Started extracting {src.label}"
                    + (f" ({page_count} page{'' if page_count == 1 else 's'})." if page_count else ".")
                ),
                source_id=src.id,
                source_label=src.label,
                page_start=page_start,
                page_end=page_end,
                page_count=page_count,
                progress_basis="reported",
            )
            _set_job_state(job)
        t0 = time.time()
        bundle = pipeline.extract(pdf_path)
        elapsed = time.time() - t0
        extracted_json.write_text(json.dumps(bundle, indent=2))
        if job is not None:
            job.processed_files += 1
            if page_count is not None:
                job.processed_pages += page_count
            job.stage = "Writing extracted FHIR bundle"
            _append_extract_event(
                job,
                "file_completed",
                stage=job.stage,
                message=(
                    f"Completed {src.label}"
                    + (f" and reported {page_count} page{'' if page_count == 1 else 's'} complete." if page_count else ".")
                ),
                source_id=src.id,
                source_label=src.label,
                page_start=(job.processed_pages - page_count + 1 if page_count else None),
                page_end=(job.processed_pages if page_count else None),
                page_count=page_count,
                progress_basis="reported",
            )
            _set_job_state(job)
        results.append(
            ExtractResult(
                source_id=src.id,
                label=src.label,
                extracted_path=str(extracted_json),
                cache_hit=False,
                entry_count=len(bundle.get("entry", [])),
                elapsed_seconds=elapsed,
            )
        )
    # Bust the resource-loading cache so the next manifest/observations call
    # picks up the freshly-extracted JSON.
    _cached_load.cache_clear()
    return results


# ---------------------------------------------------------------------------
# Bidirectional Provenance walk — "what did this source document contribute?"
# ---------------------------------------------------------------------------


def facts_for_document_reference(
    collection_id: str, document_reference: str
) -> dict[str, Any] | None:
    """Reverse-walk the Provenance graph: list every merged fact whose
    sources include the given DocumentReference.

    Returns a dict shaped:

        {
          "document_reference": "DocumentReference/...",
          "label": "Cedars-Sinai (FHIR)",
          "kind": "fhir-pull",
          "observations": [serialized MergedObservation, ...],
          "conditions":   [serialized MergedCondition,   ...],
          "medications":  [serialized MergedMedication,  ...],
          "allergies":    [serialized MergedAllergy,     ...],
          "immunizations":[serialized MergedImmunization,...],
          "totals": {"observations": N, ...},
        }

    Each merged record appears in the list of resources of the right
    type if at least one of its sources points at this DocumentReference.
    Returns ``None`` for unknown collections.
    """
    coll = get_collection(collection_id)
    if coll is None:
        return None

    # Find the matching SourceDefinition for the doc ref. Clinical note
    # artifacts are source-scoped rather than merged-fact-scoped, so they use
    # the source id instead of the DocumentReference edge.
    matching_source_id: str | None = None
    matching_label: str | None = None
    matching_kind: str | None = None
    for s in coll.sources:
        if s.document_reference == document_reference:
            matching_source_id = s.id
            matching_label = s.label
            matching_kind = s.kind
            break

    def _has_doc_ref(sources: list, attr: str = "document_reference") -> bool:
        return any(getattr(s, attr, None) == document_reference for s in sources)

    obs_hits = [m for m in merged_observations(collection_id) if _has_doc_ref(m.sources)]
    cond_hits = [m for m in merged_conditions(collection_id) if _has_doc_ref(m.sources)]
    med_hits = [m for m in merged_medications(collection_id) if _has_doc_ref(m.sources)]
    allergy_hits = [m for m in merged_allergies(collection_id) if _has_doc_ref(m.sources)]
    im_hits = [m for m in merged_immunizations(collection_id) if _has_doc_ref(m.sources)]
    artifacts = clinical_artifacts(collection_id)

    def _source_artifacts(name: str) -> list[dict[str, Any]]:
        if matching_source_id is None:
            return []
        return [
            a
            for a in artifacts.get(name, [])
            if isinstance(a, dict) and a.get("source_id") == matching_source_id
        ]

    def _report_payload(report: dict[str, Any]) -> dict[str, Any]:
        payload = {k: v for k, v in report.items() if k != "presented_form_text"}
        text = str(report.get("presented_form_text") or "").strip()
        payload["note_preview"] = text[:500]
        return payload

    encounter_hits = _source_artifacts("encounters")
    procedure_hits = _source_artifacts("procedures")
    report_hits = [_report_payload(r) for r in _source_artifacts("diagnostic_reports")]
    note_hits = [
        {**n, "text": str(n.get("text") or "")[:4000]}
        for n in artifacts.get("clinical_notes", [])
        if matching_source_id is not None and n.get("source_id") == matching_source_id
    ]

    return {
        "document_reference": document_reference,
        "label": matching_label,
        "kind": matching_kind,
        "observations": [serialize_observation(m) for m in obs_hits],
        "conditions": [serialize_condition(m) for m in cond_hits],
        "medications": [serialize_medication(m) for m in med_hits],
        "allergies": [serialize_allergy(m) for m in allergy_hits],
        "immunizations": [serialize_immunization(m) for m in im_hits],
        "encounters": encounter_hits,
        "procedures": procedure_hits,
        "diagnostic_reports": report_hits,
        "clinical_notes": note_hits,
        "totals": {
            "observations": len(obs_hits),
            "conditions": len(cond_hits),
            "medications": len(med_hits),
            "allergies": len(allergy_hits),
            "immunizations": len(im_hits),
            "encounters": len(encounter_hits),
            "procedures": len(procedure_hits),
            "diagnostic_reports": len(report_hits),
            "clinical_notes": len(note_hits),
            "all": (
                len(obs_hits)
                + len(cond_hits)
                + len(med_hits)
                + len(allergy_hits)
                + len(im_hits)
                + len(encounter_hits)
                + len(procedure_hits)
                + len(report_hits)
                + len(note_hits)
            ),
        },
    }


# ---------------------------------------------------------------------------
# Multi-source contribution diff — "what did each source uniquely add?"
# ---------------------------------------------------------------------------


def source_contribution_diff(collection_id: str) -> dict[str, Any] | None:
    """Per-source unique vs shared fact counts and unique-fact listings.

    For each source bundle in the collection, compute:

      * **unique**: merged records where this source is the only contributor
        (i.e. ``len({s.source_label for s in record.sources}) == 1`` and
        the record's source label matches this source).
      * **shared**: merged records where this source contributed alongside
        at least one other source.

    Unique facts are the high-signal "if I removed this source, here's
    what I'd lose" set — and on the demo data they correspond to:

      * **vision wins** (PDF-only): clinical findings present in the
        narrative-PDF that the structured FHIR pull never coded
        (e.g. "Bilateral inferior turbinate hypertrophy" — see
        Move H in PIPELINE-LOG.md).
      * **FHIR-only**: structured facts only the API surfaces, like
        the COVID-19 Pfizer 2021 doses in the immunization history.

    Returns ``None`` for unknown collections.
    """
    coll = get_collection(collection_id)
    if coll is None:
        return None

    obs = merged_observations(collection_id)
    cond = merged_conditions(collection_id)
    med = merged_medications(collection_id)
    allergy = merged_allergies(collection_id)
    im = merged_immunizations(collection_id)

    def _is_unique_to(record: Any, source_label: str) -> bool:
        labels = {s.source_label for s in record.sources}
        return len(labels) == 1 and source_label in labels

    def _is_shared_with(record: Any, source_label: str) -> bool:
        labels = {s.source_label for s in record.sources}
        return len(labels) > 1 and source_label in labels

    sources_out: list[dict[str, Any]] = []
    for s in coll.sources:
        unique_obs = [m for m in obs if _is_unique_to(m, s.label)]
        unique_cond = [m for m in cond if _is_unique_to(m, s.label)]
        unique_med = [m for m in med if _is_unique_to(m, s.label)]
        unique_allergy = [m for m in allergy if _is_unique_to(m, s.label)]
        unique_im = [m for m in im if _is_unique_to(m, s.label)]
        shared_obs = sum(1 for m in obs if _is_shared_with(m, s.label))
        shared_cond = sum(1 for m in cond if _is_shared_with(m, s.label))
        shared_med = sum(1 for m in med if _is_shared_with(m, s.label))
        shared_allergy = sum(1 for m in allergy if _is_shared_with(m, s.label))
        shared_im = sum(1 for m in im if _is_shared_with(m, s.label))

        unique_total = (
            len(unique_obs)
            + len(unique_cond)
            + len(unique_med)
            + len(unique_allergy)
            + len(unique_im)
        )
        shared_total = (
            shared_obs + shared_cond + shared_med + shared_allergy + shared_im
        )

        sources_out.append(
            {
                "id": s.id,
                "label": s.label,
                "kind": s.kind,
                "document_reference": s.document_reference,
                "totals": {
                    "unique": {
                        "observations": len(unique_obs),
                        "conditions": len(unique_cond),
                        "medications": len(unique_med),
                        "allergies": len(unique_allergy),
                        "immunizations": len(unique_im),
                        "all": unique_total,
                    },
                    "shared": {
                        "observations": shared_obs,
                        "conditions": shared_cond,
                        "medications": shared_med,
                        "allergies": shared_allergy,
                        "immunizations": shared_im,
                        "all": shared_total,
                    },
                },
                "unique_facts": {
                    "observations": [serialize_observation(m) for m in unique_obs],
                    "conditions": [serialize_condition(m) for m in unique_cond],
                    "medications": [serialize_medication(m) for m in unique_med],
                    "allergies": [serialize_allergy(m) for m in unique_allergy],
                    "immunizations": [serialize_immunization(m) for m in unique_im],
                },
            }
        )

    return {
        "collection_id": collection_id,
        "sources": sources_out,
    }


def find_merged_record(collection_id: str, merged_ref: str):
    """Look up a merged record by its synthetic ref ID across all resource types."""
    if merged_ref.startswith("Observation/"):
        for m in merged_observations(collection_id):
            if getattr(m, "_merged_ref", "") == merged_ref:
                return m
    if merged_ref.startswith("Condition/"):
        for m in merged_conditions(collection_id):
            if getattr(m, "_merged_ref", "") == merged_ref:
                return m
    if merged_ref.startswith("MedicationRequest/"):
        for m in merged_medications(collection_id):
            if getattr(m, "_merged_ref", "") == merged_ref:
                return m
    if merged_ref.startswith("AllergyIntolerance/"):
        for m in merged_allergies(collection_id):
            if getattr(m, "_merged_ref", "") == merged_ref:
                return m
    if merged_ref.startswith("Immunization/"):
        for m in merged_immunizations(collection_id):
            if getattr(m, "_merged_ref", "") == merged_ref:
                return m
    return None


def provenance_for_ref(collection_id: str, merged_ref: str) -> dict[str, Any] | None:
    record = find_merged_record(collection_id, merged_ref)
    if record is None:
        return None
    return mint_provenance(record)
