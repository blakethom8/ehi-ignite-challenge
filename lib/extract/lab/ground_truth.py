"""Ground-truth bundle storage — versioned, append-on-revise.

A ground-truth bundle is a verified FHIR Bundle for a specific PDF.
Lives at data/pdf-lab/ground-truth/<pdf-sha-prefix>/vN.json. Each
version is immutable; revisions create a new vN+1 file. The
<pdf-sha-prefix>.meta.json file tracks cross-version metadata.

Used as the F1 reference by the lab eval (EVAL-T01).
"""

from __future__ import annotations

import datetime
import json
import shutil
from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import Any, Literal


@dataclass
class GroundTruthVersion:
    """One immutable version of a ground-truth bundle.

    Represents the verified Bundle plus per-fact decisions made by
    the reviewer. The `decisions` list is parallel to bundle.entry —
    one decision entry per resource — so reviewers can selectively
    accept / reject / edit each emitted fact from the gold pipeline
    without losing the audit trail.
    """
    version: int                       # 1, 2, 3, ...
    pdf_sha256: str                     # full sha256 of the PDF
    pdf_path: str                       # original PDF path (informational)
    bundle: dict                        # the verified FHIR Bundle
    decisions: list[dict] = field(default_factory=list)
    # Each decision: {
    #   "resource_id": "<id>",
    #   "resource_type": "Observation",
    #   "decision": "accept" | "reject" | "edit",
    #   "edited_fields": {...} (only when decision=="edit"),
    #   "note": "free-text reviewer note",
    # }
    reviewer: str = "unknown"           # name / email / handle
    created_at: str = ""                # ISO 8601 UTC
    source_run_id: str | None = None    # which lab run was the starting point
    notes: str = ""                     # free-text version notes


@dataclass
class GroundTruthMeta:
    """Cross-version metadata. One file per PDF (regardless of version count)."""
    pdf_sha256: str
    pdf_sha_prefix: str
    pdf_path: str
    latest_version: int
    versions_created: list[str] = field(default_factory=list)  # ISO timestamps


# Directory layout helpers
DEFAULT_GT_ROOT_NAME = "ground-truth"


def _sha_prefix(pdf_sha256: str, *, prefix_len: int = 8) -> str:
    if len(pdf_sha256) < prefix_len:
        raise ValueError(f"pdf_sha256 too short: {pdf_sha256!r}")
    return pdf_sha256[:prefix_len]


def gt_dir_for_pdf(pdf_sha256: str, *, lab_root: Path | None = None) -> Path:
    """Resolve the ground-truth directory for a given PDF SHA."""
    from lib.extract.lab.recorder import DEFAULT_LAB_ROOT
    base = lab_root or DEFAULT_LAB_ROOT
    return base / DEFAULT_GT_ROOT_NAME / _sha_prefix(pdf_sha256)


def save_ground_truth(
    *,
    pdf_sha256: str,
    pdf_path: str,
    bundle: dict,
    decisions: list[dict] | None = None,
    reviewer: str = "unknown",
    source_run_id: str | None = None,
    notes: str = "",
    lab_root: Path | None = None,
) -> GroundTruthVersion:
    """Persist a new ground-truth version. Auto-increments version number
    based on existing files. Creates the directory if needed. Refuses to
    overwrite an existing version (versions are immutable)."""
    gt_dir = gt_dir_for_pdf(pdf_sha256, lab_root=lab_root)
    gt_dir.mkdir(parents=True, exist_ok=True)

    # Find next version number
    existing = sorted(int(p.stem[1:]) for p in gt_dir.glob("v*.json")
                      if p.stem.startswith("v") and p.stem[1:].isdigit())
    next_version = (existing[-1] + 1) if existing else 1

    gtv = GroundTruthVersion(
        version=next_version,
        pdf_sha256=pdf_sha256,
        pdf_path=pdf_path,
        bundle=bundle,
        decisions=decisions or [],
        reviewer=reviewer,
        created_at=datetime.datetime.utcnow().isoformat() + "Z",
        source_run_id=source_run_id,
        notes=notes,
    )
    out_path = gt_dir / f"v{next_version}.json"
    out_path.write_text(json.dumps(asdict(gtv), indent=2, default=str))

    # Update meta
    meta_path = gt_dir / f"{_sha_prefix(pdf_sha256)}.meta.json"
    if meta_path.exists():
        meta_data = json.loads(meta_path.read_text())
    else:
        meta_data = {
            "pdf_sha256": pdf_sha256,
            "pdf_sha_prefix": _sha_prefix(pdf_sha256),
            "pdf_path": pdf_path,
            "latest_version": 0,
            "versions_created": [],
        }
    meta_data["latest_version"] = next_version
    meta_data["versions_created"].append(gtv.created_at)
    meta_path.write_text(json.dumps(meta_data, indent=2))

    return gtv


def load_latest_ground_truth(
    pdf_sha256: str,
    *,
    lab_root: Path | None = None,
) -> GroundTruthVersion | None:
    """Load the latest ground-truth version for a PDF, or None if not found."""
    gt_dir = gt_dir_for_pdf(pdf_sha256, lab_root=lab_root)
    if not gt_dir.exists():
        return None
    versions = sorted(int(p.stem[1:]) for p in gt_dir.glob("v*.json")
                      if p.stem.startswith("v") and p.stem[1:].isdigit())
    if not versions:
        return None
    latest = versions[-1]
    data = json.loads((gt_dir / f"v{latest}.json").read_text())
    return GroundTruthVersion(**data)


def load_ground_truth_version(
    pdf_sha256: str,
    version: int,
    *,
    lab_root: Path | None = None,
) -> GroundTruthVersion | None:
    """Load a specific version. Returns None when the file is missing."""
    gt_dir = gt_dir_for_pdf(pdf_sha256, lab_root=lab_root)
    path = gt_dir / f"v{version}.json"
    if not path.exists():
        return None
    return GroundTruthVersion(**json.loads(path.read_text()))


def list_ground_truth_versions(
    pdf_sha256: str,
    *,
    lab_root: Path | None = None,
) -> list[int]:
    """List all version numbers available for a PDF, in ascending order."""
    gt_dir = gt_dir_for_pdf(pdf_sha256, lab_root=lab_root)
    if not gt_dir.exists():
        return []
    return sorted(
        int(p.stem[1:])
        for p in gt_dir.glob("v*.json")
        if p.stem.startswith("v") and p.stem[1:].isdigit()
    )


def has_ground_truth(
    pdf_sha256: str,
    *,
    lab_root: Path | None = None,
) -> bool:
    """Quick check used by the eval integration (EVAL-T01)."""
    return bool(list_ground_truth_versions(pdf_sha256, lab_root=lab_root))
