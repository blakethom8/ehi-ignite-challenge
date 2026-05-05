"""Published canonical chart snapshots.

Publishing pins a completed harmonization run as the active chart snapshot for
downstream modules. The snapshot is intentionally small: it references the run
artifact rather than duplicating the full candidate record.
"""

from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from api.core import harmonization_runs


REPO_ROOT = Path(__file__).resolve().parents[2]
PUBLISHED_ROOT = Path(
    os.getenv("PUBLISHED_CHART_STORE_PATH", REPO_ROOT / "data" / "published-charts")
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _safe_segment(value: str) -> str:
    return "".join(c if c.isalnum() or c in {"-", "_", "."} else "-" for c in value).strip(".-")[:160] or "collection"


def _state_path(collection_id: str) -> Path:
    return PUBLISHED_ROOT / _safe_segment(collection_id) / "published.json"


def _load_state(collection_id: str) -> dict[str, Any]:
    path = _state_path(collection_id)
    if not path.exists():
        return {"collection_id": collection_id, "active_snapshot_id": None, "snapshots": []}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"collection_id": collection_id, "active_snapshot_id": None, "snapshots": []}
    if not isinstance(raw, dict):
        return {"collection_id": collection_id, "active_snapshot_id": None, "snapshots": []}
    raw.setdefault("collection_id", collection_id)
    raw.setdefault("active_snapshot_id", None)
    raw.setdefault("snapshots", [])
    if not isinstance(raw["snapshots"], list):
        raw["snapshots"] = []
    return raw


def _write_state(collection_id: str, state: dict[str, Any]) -> dict[str, Any]:
    path = _state_path(collection_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2), encoding="utf-8")
    return state


def _snapshot_from_run(run: dict[str, Any]) -> dict[str, Any]:
    published_at = _now().isoformat()
    return {
        "snapshot_id": uuid.uuid4().hex,
        "collection_id": run["collection_id"],
        "run_id": run["run_id"],
        "collection_name": run["collection_name"],
        "published_at": published_at,
        "run_completed_at": run["completed_at"],
        "rule_version": run["rule_version"],
        "artifact_path": run["artifact_path"],
        "summary": run["summary"],
        "source_count": run["summary"]["source_count"],
        "candidate_fact_count": run["summary"]["total_candidate_facts"],
        "review_item_count": run["summary"]["review_item_count"],
    }


def state(collection_id: str) -> dict[str, Any]:
    current = _load_state(collection_id)
    active_snapshot_id = current.get("active_snapshot_id")
    active = None
    for snapshot in current["snapshots"]:
        snapshot["is_active"] = snapshot.get("snapshot_id") == active_snapshot_id
        if snapshot["is_active"]:
            active = snapshot
    return {
        "collection_id": collection_id,
        "active_snapshot": active,
        "snapshots": sorted(current["snapshots"], key=lambda item: item.get("published_at", ""), reverse=True),
    }


def publish_run(collection_id: str, run_id: str) -> dict[str, Any]:
    run = harmonization_runs.get_run(collection_id, run_id)
    if run is None:
        raise FileNotFoundError(run_id)
    if run.get("status") != "complete":
        raise ValueError("Only completed harmonization runs can be published.")
    summary = run.get("summary", {})
    if summary.get("review_item_count", 0) > 0:
        raise ValueError("Resolve review items before publishing this run.")
    if summary.get("total_candidate_facts", 0) <= 0:
        raise ValueError("Cannot publish a run with no candidate facts.")

    current = _load_state(collection_id)
    snapshot = _snapshot_from_run(run)
    current["snapshots"].append(snapshot)
    current["active_snapshot_id"] = snapshot["snapshot_id"]
    _write_state(collection_id, current)
    return state(collection_id)


def activate_snapshot(collection_id: str, snapshot_id: str) -> dict[str, Any]:
    current = _load_state(collection_id)
    if not any(snapshot.get("snapshot_id") == snapshot_id for snapshot in current["snapshots"]):
        raise FileNotFoundError(snapshot_id)
    current["active_snapshot_id"] = snapshot_id
    _write_state(collection_id, current)
    return state(collection_id)


def unpublish(collection_id: str) -> dict[str, Any]:
    current = _load_state(collection_id)
    current["active_snapshot_id"] = None
    _write_state(collection_id, current)
    return state(collection_id)
