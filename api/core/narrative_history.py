"""Thin helpers over ``lib.narratives.storage`` for the history surface.

`write_current_narrative()` archives the prior Composition to
``data/narratives/<patient>/<slug>/history/<timestamp>.json`` whenever
it writes a new ``current.json``. This module exposes that archive to
the UI + bundle pipeline.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from lib.narratives.storage import history_dir_for


def _timestamp_from_filename(path: Path) -> str:
    """Filename without extension is the archive timestamp slug."""
    return path.stem


def list_history(patient_id: str, episode_slug: str) -> list[dict[str, Any]]:
    """Return archived narrative versions, newest-first.

    Each entry::

        {
            "timestamp": str,           # archive slug (filename stem)
            "composition_id": str | None,
            "replaces_id": str | None,  # from relatesTo[0]
            "archived_path": str,
        }

    Returns ``[]`` when no history exists for this (patient, slug).
    """
    history = history_dir_for(patient_id, episode_slug)
    if not history.exists():
        return []
    rows: list[dict[str, Any]] = []
    for path in sorted(history.glob("*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(payload, dict):
            continue
        replaces_id: str | None = None
        for related in payload.get("relatesTo") or []:
            if not isinstance(related, dict):
                continue
            if related.get("code") == "replaces":
                target = related.get("targetReference") or {}
                ref = target.get("reference") if isinstance(target, dict) else None
                if isinstance(ref, str) and "/" in ref:
                    replaces_id = ref.split("/", 1)[1]
                break
        rows.append(
            {
                "timestamp": _timestamp_from_filename(path),
                "composition_id": payload.get("id"),
                "replaces_id": replaces_id,
                "archived_path": str(path),
            }
        )
    rows.sort(key=lambda row: row["timestamp"], reverse=True)
    return rows


def load_archived(
    patient_id: str, episode_slug: str, timestamp: str
) -> dict[str, Any] | None:
    """Return the archived FHIR Composition for one (patient, slug, timestamp)."""
    history = history_dir_for(patient_id, episode_slug)
    path = history / f"{timestamp}.json"
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def load_history_compositions(
    patient_id: str, episode_slug: str
) -> list[dict[str, Any]]:
    """Return every archived Composition dict, oldest-first.

    Used by the bundle packager to embed history under
    ``fhir/narratives/<slug>/history/<timestamp>.json``.
    """
    rows = list_history(patient_id, episode_slug)
    out: list[dict[str, Any]] = []
    for row in reversed(rows):  # oldest-first for bundle layout
        archived = load_archived(patient_id, episode_slug, row["timestamp"])
        if archived is not None:
            out.append({"timestamp": row["timestamp"], "composition": archived})
    return out
