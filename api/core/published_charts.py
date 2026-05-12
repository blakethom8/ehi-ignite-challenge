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


def _fact_counts(summary: dict[str, Any]) -> dict[str, int]:
    counts = summary.get("candidate_counts")
    if not isinstance(counts, dict):
        return {}
    return {str(key): int(value or 0) for key, value in counts.items()}


def _count_delta(current: dict[str, int], previous: dict[str, int]) -> dict[str, int]:
    keys = set(current) | set(previous)
    return {key: current.get(key, 0) - previous.get(key, 0) for key in keys}


def _change_headline(change: dict[str, Any]) -> str:
    if not change.get("previous_snapshot_id"):
        return "Initial published chart snapshot."

    parts: list[str] = []
    fact_delta = int(change.get("fact_delta") or 0)
    source_delta = int(change.get("source_delta") or 0)
    if fact_delta:
        parts.append(f"{fact_delta:+d} candidate facts")
    if source_delta:
        parts.append(f"{source_delta:+d} sources")
    if not parts:
        return "No top-level fact or source count change from the prior active snapshot."
    return "Changed " + " and ".join(parts) + " from the prior active snapshot."


def _change_summary(run: dict[str, Any], previous_snapshot: dict[str, Any] | None) -> dict[str, Any]:
    summary = run.get("summary", {})
    previous_summary = previous_snapshot.get("summary", {}) if isinstance(previous_snapshot, dict) else {}
    current_counts = _fact_counts(summary)
    previous_counts = _fact_counts(previous_summary)
    change = {
        "previous_snapshot_id": previous_snapshot.get("snapshot_id") if previous_snapshot else None,
        "previous_run_id": previous_snapshot.get("run_id") if previous_snapshot else None,
        "fact_delta": int(summary.get("total_candidate_facts") or 0)
        - int(previous_summary.get("total_candidate_facts") or 0),
        "source_delta": int(summary.get("source_count") or 0)
        - int(previous_summary.get("source_count") or 0),
        "review_item_delta": int(summary.get("review_item_count") or 0)
        - int(previous_summary.get("review_item_count") or 0),
        "candidate_count_delta": _count_delta(current_counts, previous_counts),
    }
    change["headline"] = _change_headline(change)
    return change


def _review_decision_summary(run: dict[str, Any]) -> dict[str, Any]:
    summary = run.get("review_decision_summary")
    if isinstance(summary, dict):
        return summary
    events = run.get("review_events") or []
    review_items = run.get("review_items") or []
    decisions: dict[str, int] = {}
    latest_event_at: str | None = None
    for event in events:
        decision = str(event.get("decision") or "unknown")
        decisions[decision] = decisions.get(decision, 0) + 1
        created_at = event.get("created_at")
        if isinstance(created_at, str) and (latest_event_at is None or created_at > latest_event_at):
            latest_event_at = created_at
    return {
        "event_count": len(events),
        "resolved_item_count": sum(1 for item in review_items if bool(item.get("resolved"))),
        "open_item_count": sum(1 for item in review_items if not bool(item.get("resolved"))),
        "latest_event_at": latest_event_at,
        "decisions": decisions,
    }


def _snapshot_from_run(run: dict[str, Any], previous_snapshot: dict[str, Any] | None = None) -> dict[str, Any]:
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
        "review_decision_summary": _review_decision_summary(run),
        "activated_at": published_at,
        "activated_from_snapshot_id": previous_snapshot.get("snapshot_id") if previous_snapshot else None,
        "change_summary": _change_summary(run, previous_snapshot),
    }


def get_snapshot(collection_id: str, snapshot_id: str) -> dict[str, Any] | None:
    """Return the snapshot record with the given id, or None."""
    current = _load_state(collection_id)
    for snapshot in current["snapshots"]:
        if snapshot.get("snapshot_id") == snapshot_id:
            return snapshot
    return None


_DIFF_CATEGORIES = (
    "observations",
    "conditions",
    "medications",
    "allergies",
    "immunizations",
)


def _fact_label(category: str, fact: dict[str, Any]) -> str:
    if category == "observations":
        return str(fact.get("canonical_name") or fact.get("name") or fact.get("merged_ref") or "")
    if category in ("medications", "allergies", "immunizations", "conditions"):
        return str(fact.get("canonical_name") or fact.get("display") or fact.get("name") or fact.get("merged_ref") or "")
    return str(fact.get("merged_ref") or "")


def _fact_summary_value(category: str, fact: dict[str, Any]) -> str:
    if category == "observations":
        latest = fact.get("latest") or {}
        value = latest.get("value")
        unit = latest.get("unit") or ""
        if value is None:
            return ""
        return f"{value} {unit}".strip()
    if category == "medications":
        latest = fact.get("latest") or {}
        return str(latest.get("status") or fact.get("status") or "")
    if category == "conditions":
        return str(fact.get("clinical_status") or fact.get("status") or "")
    return ""


def _index_facts(candidate_record: dict[str, Any]) -> dict[str, dict[str, dict[str, Any]]]:
    """Build {category -> {merged_ref -> fact}} from a run's candidate_record."""
    by_category: dict[str, dict[str, dict[str, Any]]] = {}
    for category in _DIFF_CATEGORIES:
        rows = candidate_record.get(category) or []
        index: dict[str, dict[str, Any]] = {}
        for row in rows:
            if not isinstance(row, dict):
                continue
            ref = row.get("merged_ref") or row.get("name") or row.get("canonical_name")
            if not ref:
                continue
            index[str(ref)] = row
        by_category[category] = index
    return by_category


def compute_snapshot_diff(
    collection_id: str, snapshot_a: str, snapshot_b: str
) -> dict[str, Any]:
    """Compute the per-category fact-level diff between two snapshots.

    Returns ``{snapshot_a, snapshot_b, categories: {category: {added, removed,
    changed}}, totals}``. Each fact entry includes ``merged_ref``, ``label``,
    and (when applicable) the value/status snapshot from each side.

    Raises ``FileNotFoundError`` if either snapshot or its underlying run is
    missing.
    """
    from api.core import harmonization_runs

    snap_a = get_snapshot(collection_id, snapshot_a)
    snap_b = get_snapshot(collection_id, snapshot_b)
    if snap_a is None or snap_b is None:
        raise FileNotFoundError(snapshot_a if snap_a is None else snapshot_b)

    run_a = harmonization_runs.get_run(collection_id, snap_a["run_id"])
    run_b = harmonization_runs.get_run(collection_id, snap_b["run_id"])
    if run_a is None or run_b is None:
        raise FileNotFoundError(snap_a["run_id"] if run_a is None else snap_b["run_id"])

    a_index = _index_facts(run_a.get("candidate_record") or {})
    b_index = _index_facts(run_b.get("candidate_record") or {})

    categories: dict[str, dict[str, list[dict[str, Any]]]] = {}
    totals = {"added": 0, "removed": 0, "changed": 0}

    for category in _DIFF_CATEGORIES:
        a_map = a_index.get(category, {})
        b_map = b_index.get(category, {})
        a_keys = set(a_map.keys())
        b_keys = set(b_map.keys())

        added = []
        removed = []
        changed = []

        # "Added in B" means present in B but not in A.
        for ref in sorted(b_keys - a_keys):
            fact = b_map[ref]
            added.append(
                {
                    "merged_ref": ref,
                    "label": _fact_label(category, fact),
                    "value": _fact_summary_value(category, fact),
                }
            )
        # "Removed in B" means present in A but absent in B.
        for ref in sorted(a_keys - b_keys):
            fact = a_map[ref]
            removed.append(
                {
                    "merged_ref": ref,
                    "label": _fact_label(category, fact),
                    "value": _fact_summary_value(category, fact),
                }
            )
        # "Changed" — present in both, but a summary field shifted.
        for ref in sorted(a_keys & b_keys):
            a_value = _fact_summary_value(category, a_map[ref])
            b_value = _fact_summary_value(category, b_map[ref])
            if a_value != b_value:
                changed.append(
                    {
                        "merged_ref": ref,
                        "label": _fact_label(category, a_map[ref]),
                        "before": a_value,
                        "after": b_value,
                    }
                )

        categories[category] = {"added": added, "removed": removed, "changed": changed}
        totals["added"] += len(added)
        totals["removed"] += len(removed)
        totals["changed"] += len(changed)

    return {
        "snapshot_a": {
            "snapshot_id": snap_a["snapshot_id"],
            "run_id": snap_a["run_id"],
            "published_at": snap_a.get("published_at"),
        },
        "snapshot_b": {
            "snapshot_id": snap_b["snapshot_id"],
            "run_id": snap_b["run_id"],
            "published_at": snap_b.get("published_at"),
        },
        "categories": categories,
        "totals": totals,
    }


def previous_snapshot_id(collection_id: str, snapshot_id: str) -> str | None:
    """Return the chronologically previous snapshot for diff defaults."""
    current = _load_state(collection_id)
    snapshots = sorted(
        current["snapshots"],
        key=lambda item: item.get("published_at", ""),
    )
    prior_id: str | None = None
    for snapshot in snapshots:
        if snapshot.get("snapshot_id") == snapshot_id:
            return prior_id
        prior_id = snapshot.get("snapshot_id")
    return None


def state(collection_id: str) -> dict[str, Any]:
    current = _load_state(collection_id)
    active_snapshot_id = current.get("active_snapshot_id")
    active = None
    for snapshot in current["snapshots"]:
        snapshot.setdefault("review_decision_summary", {
            "event_count": 0,
            "resolved_item_count": 0,
            "open_item_count": snapshot.get("review_item_count", 0),
            "latest_event_at": None,
            "decisions": {},
        })
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
    previous_snapshot = next(
        (
            snapshot
            for snapshot in current["snapshots"]
            if snapshot.get("snapshot_id") == current.get("active_snapshot_id")
        ),
        None,
    )
    snapshot = _snapshot_from_run(run, previous_snapshot)
    current["snapshots"].append(snapshot)
    current["active_snapshot_id"] = snapshot["snapshot_id"]
    _write_state(collection_id, current)
    return state(collection_id)


def activate_snapshot(collection_id: str, snapshot_id: str) -> dict[str, Any]:
    current = _load_state(collection_id)
    previous_snapshot_id = current.get("active_snapshot_id")
    target = next((snapshot for snapshot in current["snapshots"] if snapshot.get("snapshot_id") == snapshot_id), None)
    if target is None:
        raise FileNotFoundError(snapshot_id)
    target["activated_at"] = _now().isoformat()
    target["activated_from_snapshot_id"] = previous_snapshot_id if previous_snapshot_id != snapshot_id else None
    current["active_snapshot_id"] = snapshot_id
    _write_state(collection_id, current)
    return state(collection_id)


def unpublish(collection_id: str) -> dict[str, Any]:
    current = _load_state(collection_id)
    current["active_snapshot_id"] = None
    _write_state(collection_id, current)
    return state(collection_id)
