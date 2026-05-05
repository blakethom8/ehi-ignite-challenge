"""Persisted harmonization runs.

The existing harmonize service computes merged records on read. This module
wraps those matchers in a durable run artifact so the UI can express an
explicit "run harmonization" step before review and publish.
"""

from __future__ import annotations

import hashlib
import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from api.core import harmonize_service


REPO_ROOT = Path(__file__).resolve().parents[2]
RUNS_ROOT = Path(
    os.getenv("HARMONIZATION_RUN_STORE_PATH", REPO_ROOT / "data" / "harmonization-runs")
)
RUN_VERSION = "scripted-harmonize-v1"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _safe_segment(value: str) -> str:
    return "".join(c if c.isalnum() or c in {"-", "_", "."} else "-" for c in value).strip(".-")[:160] or "collection"


def _collection_dir(collection_id: str) -> Path:
    return RUNS_ROOT / _safe_segment(collection_id)


def _run_path(collection_id: str, run_id: str) -> Path:
    return _collection_dir(collection_id) / f"{run_id}.json"


def _latest_path(collection_id: str) -> Path:
    return _collection_dir(collection_id) / "latest.json"


def _run_review_decision_defaults(item: dict[str, Any]) -> dict[str, Any]:
    item.setdefault("resolved", False)
    item.setdefault("decision", None)
    item.setdefault("decision_notes", "")
    item.setdefault("resolved_at", None)
    return item


def _is_open_review_item(item: dict[str, Any]) -> bool:
    return not bool(item.get("resolved"))


def _file_hash(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _source_fingerprints(collection_id: str) -> list[dict[str, Any]]:
    collection = harmonize_service.get_collection(collection_id)
    manifest = harmonize_service.collection_source_manifest(collection_id) or []
    manifest_by_id = {source["id"]: source for source in manifest}
    if collection is None:
        return []

    out: list[dict[str, Any]] = []
    for source in collection.sources:
        stat = source.path.stat() if source.path.exists() else None
        manifest_item = manifest_by_id.get(source.id, {})
        out.append(
            {
                "id": source.id,
                "label": source.label,
                "kind": source.kind,
                "document_reference": source.document_reference,
                "path": str(source.path),
                "exists": source.path.exists(),
                "size_bytes": stat.st_size if stat else None,
                "modified_at": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat() if stat else None,
                "sha256": _file_hash(source.path),
                "status": manifest_item.get("status", "missing"),
                "status_label": manifest_item.get("status_label", "Source file missing"),
                "total_resources": manifest_item.get("total_resources", 0),
                "resource_counts": manifest_item.get("resource_counts", {}),
            }
        )
    return out


def _review_items(
    sources: list[dict[str, Any]],
    observations: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    if not sources:
        items.append(
            _run_review_decision_defaults({
                "id": "no-sources",
                "category": "source",
                "severity": "high",
                "title": "No sources available",
                "body": "Upload and prepare at least one source before publishing a canonical record.",
                "source_id": None,
                "resource_type": None,
                "merged_ref": None,
            })
        )
        return items

    ready_statuses = {"structured", "extracted"}
    for source in sources:
        if source["status"] in ready_statuses:
            continue
        items.append(
            _run_review_decision_defaults({
                "id": f"source-{source['id']}",
                "category": "source",
                "severity": "high" if source["status"] in {"missing", "pending_extraction"} else "medium",
                "title": source["status_label"],
                "body": f"{source['label']} is not ready to contribute structured facts.",
                "source_id": source["id"],
                "resource_type": None,
                "merged_ref": None,
            })
        )

    for obs in observations:
        if not obs.get("has_conflict"):
            continue
        items.append(
            _run_review_decision_defaults({
                "id": f"observation-conflict-{obs.get('merged_ref') or obs.get('canonical_name')}",
                "category": "fact",
                "severity": "medium",
                "title": "Lab value conflict",
                "body": f"{obs.get('canonical_name', 'Observation')} has same-day or same-fact values that need review.",
                "source_id": None,
                "resource_type": "Observation",
                "merged_ref": obs.get("merged_ref"),
            })
        )
    return items


def _summary(
    sources: list[dict[str, Any]],
    observations: list[dict[str, Any]],
    conditions: list[dict[str, Any]],
    medications: list[dict[str, Any]],
    allergies: list[dict[str, Any]],
    immunizations: list[dict[str, Any]],
    review_items: list[dict[str, Any]],
) -> dict[str, Any]:
    cross_source = {
        "observations": sum(1 for item in observations if item.get("source_count", 0) > 1),
        "conditions": sum(1 for item in conditions if item.get("source_count", 0) > 1),
        "medications": sum(1 for item in medications if item.get("source_count", 0) > 1),
        "allergies": sum(1 for item in allergies if item.get("source_count", 0) > 1),
        "immunizations": sum(1 for item in immunizations if item.get("source_count", 0) > 1),
    }
    candidate_counts = {
        "observations": len(observations),
        "conditions": len(conditions),
        "medications": len(medications),
        "allergies": len(allergies),
        "immunizations": len(immunizations),
    }
    total_candidate_facts = sum(candidate_counts.values())
    open_review_item_count = sum(1 for item in review_items if _is_open_review_item(item))
    return {
        "source_count": len(sources),
        "prepared_source_count": sum(1 for source in sources if source["status"] in {"structured", "extracted"}),
        "needs_preparation_count": sum(1 for source in sources if source["status"] not in {"structured", "extracted"}),
        "candidate_counts": candidate_counts,
        "cross_source_counts": cross_source,
        "total_candidate_facts": total_candidate_facts,
        "cross_source_facts": sum(cross_source.values()),
        "conflict_count": sum(1 for item in observations if item.get("has_conflict")),
        "review_item_count": open_review_item_count,
        "publishable": len(sources) > 0 and open_review_item_count == 0 and total_candidate_facts > 0,
    }


def _recompute_summary(payload: dict[str, Any]) -> None:
    candidate_record = payload.get("candidate_record") or {}
    payload["summary"] = _summary(
        payload.get("sources") or [],
        candidate_record.get("observations") or [],
        candidate_record.get("conditions") or [],
        candidate_record.get("medications") or [],
        candidate_record.get("allergies") or [],
        candidate_record.get("immunizations") or [],
        payload.get("review_items") or [],
    )


def _write_run(collection_id: str, payload: dict[str, Any]) -> None:
    out_dir = _collection_dir(collection_id)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = _run_path(collection_id, payload["run_id"])
    payload["artifact_path"] = str(path)
    text = json.dumps(payload, indent=2)
    path.write_text(text, encoding="utf-8")
    latest = latest_run(collection_id)
    if latest and latest.get("run_id") == payload["run_id"]:
        _latest_path(collection_id).write_text(text, encoding="utf-8")


def _build_run(collection_id: str, run_id: str, started_at: datetime) -> dict[str, Any]:
    collection = harmonize_service.get_collection(collection_id)
    if collection is None:
        raise FileNotFoundError(collection_id)

    sources = _source_fingerprints(collection_id)
    observations = [
        harmonize_service.serialize_observation(item)
        for item in harmonize_service.merged_observations(collection_id)
    ]
    conditions = [
        harmonize_service.serialize_condition(item)
        for item in harmonize_service.merged_conditions(collection_id)
    ]
    medications = [
        harmonize_service.serialize_medication(item)
        for item in harmonize_service.merged_medications(collection_id)
    ]
    allergies = [
        harmonize_service.serialize_allergy(item)
        for item in harmonize_service.merged_allergies(collection_id)
    ]
    immunizations = [
        harmonize_service.serialize_immunization(item)
        for item in harmonize_service.merged_immunizations(collection_id)
    ]
    review_items = _review_items(sources, observations)
    summary = _summary(
        sources,
        observations,
        conditions,
        medications,
        allergies,
        immunizations,
        review_items,
    )
    completed_at = _now()
    return {
        "run_id": run_id,
        "collection_id": collection_id,
        "collection_name": collection.name,
        "status": "complete",
        "rule_version": RUN_VERSION,
        "started_at": started_at.isoformat(),
        "completed_at": completed_at.isoformat(),
        "duration_seconds": round((completed_at - started_at).total_seconds(), 3),
        "sources": sources,
        "summary": summary,
        "review_items": review_items,
        "candidate_record": {
            "observations": observations,
            "conditions": conditions,
            "medications": medications,
            "allergies": allergies,
            "immunizations": immunizations,
        },
    }


def run_harmonization(collection_id: str) -> dict[str, Any]:
    """Create and persist a new scripted harmonization run."""
    run_id = uuid.uuid4().hex
    started_at = _now()
    try:
        payload = _build_run(collection_id, run_id, started_at)
    except Exception as exc:
        collection = harmonize_service.get_collection(collection_id)
        if collection is None:
            raise FileNotFoundError(collection_id) from exc
        completed_at = _now()
        payload = {
            "run_id": run_id,
            "collection_id": collection_id,
            "collection_name": collection.name,
            "status": "failed",
            "rule_version": RUN_VERSION,
            "started_at": started_at.isoformat(),
            "completed_at": completed_at.isoformat(),
            "duration_seconds": round((completed_at - started_at).total_seconds(), 3),
            "sources": _source_fingerprints(collection_id),
            "summary": {
                "source_count": 0,
                "prepared_source_count": 0,
                "needs_preparation_count": 0,
                "candidate_counts": {
                    "observations": 0,
                    "conditions": 0,
                    "medications": 0,
                    "allergies": 0,
                    "immunizations": 0,
                },
                "cross_source_counts": {
                    "observations": 0,
                    "conditions": 0,
                    "medications": 0,
                    "allergies": 0,
                    "immunizations": 0,
                },
                "total_candidate_facts": 0,
                "cross_source_facts": 0,
                "conflict_count": 0,
                "review_item_count": 1,
                "publishable": False,
            },
            "review_items": [
                {
                    "id": "run-failed",
                    "category": "system",
                    "severity": "high",
                    "title": "Harmonization run failed",
                    "body": f"{type(exc).__name__}: {exc}",
                    "source_id": None,
                    "resource_type": None,
                    "merged_ref": None,
                    "resolved": False,
                    "decision": None,
                    "decision_notes": "",
                    "resolved_at": None,
                }
            ],
            "candidate_record": {
                "observations": [],
                "conditions": [],
                "medications": [],
                "allergies": [],
                "immunizations": [],
            },
        }

    path = _run_path(collection_id, run_id)
    payload["artifact_path"] = str(path)
    text = json.dumps(payload, indent=2)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    _latest_path(collection_id).write_text(text, encoding="utf-8")
    return payload


def latest_run(collection_id: str) -> dict[str, Any] | None:
    path = _latest_path(collection_id)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def get_run(collection_id: str, run_id: str) -> dict[str, Any] | None:
    path = _run_path(collection_id, run_id)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def resolve_review_item(
    collection_id: str,
    run_id: str,
    item_id: str,
    decision: str,
    notes: str = "",
) -> dict[str, Any]:
    """Record a reviewer decision on a persisted run review item."""
    payload = get_run(collection_id, run_id)
    if payload is None:
        raise FileNotFoundError(run_id)

    review_items = payload.get("review_items") or []
    target = next((item for item in review_items if item.get("id") == item_id), None)
    if target is None:
        raise KeyError(item_id)

    target["resolved"] = True
    target["decision"] = decision
    target["decision_notes"] = notes.strip()
    target["resolved_at"] = _now().isoformat()
    for item in review_items:
        _run_review_decision_defaults(item)
    _recompute_summary(payload)
    _write_run(collection_id, payload)
    return payload
