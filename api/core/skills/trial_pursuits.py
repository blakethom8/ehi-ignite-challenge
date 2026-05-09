"""Durable clinical-trial pursuit store.

Trial matching runs are transient workspaces. A pursuit is the durable
patient-level object created when a clinician decides a trial is worth
tracking across outreach, packet preparation, submission, and follow-up.
"""

from __future__ import annotations

import json
import os
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal


REPO_ROOT = Path(__file__).resolve().parents[3]
CASES_ROOT = Path(os.getenv("SKILLS_CASES_PATH", REPO_ROOT / "data" / "cases"))

PursuitStatus = Literal[
    "interested",
    "reviewing",
    "packet",
    "contacted",
    "submitted",
    "follow_up",
    "closed",
]
TaskStatus = Literal["pending", "done"]

VALID_STATUSES: set[str] = {
    "interested",
    "reviewing",
    "packet",
    "contacted",
    "submitted",
    "follow_up",
    "closed",
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _safe_segment(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]", "_", value.strip())
    return cleaned[:64] or "x"


def _coerce_status(value: str | None) -> PursuitStatus:
    if value in VALID_STATUSES:
        return value  # type: ignore[return-value]
    return "interested"


@dataclass
class TrialPursuitTask:
    task_id: str
    title: str
    status: TaskStatus = "pending"
    due_at: str | None = None
    created_at: str = field(default_factory=_now_iso)
    completed_at: str | None = None


@dataclass
class TrialPursuitEvent:
    event_id: str
    kind: str
    note: str
    actor: str = "agent"
    data: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=_now_iso)


@dataclass
class TrialPursuit:
    pursuit_id: str
    patient_id: str
    nct_id: str
    title: str
    status: PursuitStatus = "interested"
    sponsor: str | None = None
    trial_status: str | None = None
    source_url: str | None = None
    source_kind: str = "clinicaltrials.gov"
    source_updated_at: str | None = None
    fit_score: float | None = None
    next_step: str = "Review eligibility and decide whether to prepare an outreach packet."
    notes: str = ""
    tags: list[str] = field(default_factory=list)
    created_from_run_id: str | None = None
    created_from_canvas_node_id: str | None = None
    evidence_snapshot: dict[str, Any] = field(default_factory=dict)
    tasks: list[TrialPursuitTask] = field(default_factory=list)
    events: list[TrialPursuitEvent] = field(default_factory=list)
    created_at: str = field(default_factory=_now_iso)
    updated_at: str = field(default_factory=_now_iso)


class TrialPursuitStore:
    """JSON-backed patient-level pursuit board."""

    def __init__(self, patient_id: str, root: Path | None = None) -> None:
        self.patient_id = patient_id
        self.root = root or CASES_ROOT
        self.patient_dir = self.root / _safe_segment(patient_id)
        self.path = self.patient_dir / "_trial_pursuits.json"

    def list(self) -> list[TrialPursuit]:
        return [
            self._pursuit_from_dict(item)
            for item in self._read_payload().get("pursuits", [])
            if isinstance(item, dict)
        ]

    def upsert(self, payload: dict[str, Any], *, actor: str = "agent") -> TrialPursuit:
        nct_id = str(payload.get("nct_id") or "").strip().upper()
        if not re.match(r"^NCT\d{8}$", nct_id):
            raise ValueError("nct_id must match NCT########")
        title = str(payload.get("title") or nct_id).strip()
        now = _now_iso()
        data = self._read_payload()
        pursuits = [p for p in data.get("pursuits", []) if isinstance(p, dict)]
        existing = next((p for p in pursuits if str(p.get("nct_id", "")).upper() == nct_id), None)

        if existing is None:
            existing = {
                "pursuit_id": f"tp_{uuid.uuid4().hex[:12]}",
                "patient_id": self.patient_id,
                "nct_id": nct_id,
                "title": title,
                "status": _coerce_status(str(payload.get("status") or "interested")),
                "tasks": [],
                "events": [],
                "created_at": now,
                "updated_at": now,
            }
            pursuits.append(existing)
            self._append_event(
                existing,
                kind="created",
                note=f"Added {nct_id} to the trial pursuit board.",
                actor=actor,
                data={"source": payload.get("source_kind") or "clinicaltrials.gov"},
            )
        else:
            existing["updated_at"] = now
            self._append_event(
                existing,
                kind="updated",
                note=f"Updated pursuit metadata for {nct_id}.",
                actor=actor,
            )

        merge_fields = {
            "title",
            "sponsor",
            "trial_status",
            "source_url",
            "source_kind",
            "source_updated_at",
            "fit_score",
            "next_step",
            "notes",
            "created_from_run_id",
            "created_from_canvas_node_id",
            "evidence_snapshot",
        }
        for key in merge_fields:
            if key in payload and payload[key] is not None:
                existing[key] = payload[key]
        if "status" in payload:
            existing["status"] = _coerce_status(str(payload.get("status")))
        if "tags" in payload and isinstance(payload["tags"], list):
            existing["tags"] = [str(tag) for tag in payload["tags"] if str(tag).strip()]
        existing.setdefault("source_kind", "clinicaltrials.gov")
        existing.setdefault("next_step", "Review eligibility and decide whether to prepare an outreach packet.")
        existing.setdefault("notes", "")
        existing.setdefault("tags", [])
        existing.setdefault("evidence_snapshot", {})
        existing.setdefault("tasks", [])
        existing.setdefault("events", [])
        existing["updated_at"] = now

        data["pursuits"] = pursuits
        self._write_payload(data)
        return self._pursuit_from_dict(existing)

    def update(self, pursuit_id: str, updates: dict[str, Any], *, actor: str = "clinician") -> TrialPursuit:
        data = self._read_payload()
        pursuits = [p for p in data.get("pursuits", []) if isinstance(p, dict)]
        pursuit = next((p for p in pursuits if p.get("pursuit_id") == pursuit_id), None)
        if pursuit is None:
            raise KeyError(pursuit_id)

        allowed = {"status", "next_step", "notes", "tags"}
        for key in allowed:
            if key not in updates:
                continue
            if key == "status":
                pursuit[key] = _coerce_status(str(updates[key]))
            elif key == "tags" and isinstance(updates[key], list):
                pursuit[key] = [str(tag) for tag in updates[key] if str(tag).strip()]
            elif updates[key] is not None:
                pursuit[key] = str(updates[key])
        pursuit["updated_at"] = _now_iso()
        self._append_event(
            pursuit,
            kind="status_changed" if "status" in updates else "updated",
            note=str(updates.get("event_note") or "Clinician updated the trial pursuit."),
            actor=actor,
            data={k: updates[k] for k in allowed if k in updates},
        )
        data["pursuits"] = pursuits
        self._write_payload(data)
        return self._pursuit_from_dict(pursuit)

    def add_event(
        self,
        pursuit_id: str,
        *,
        kind: str,
        note: str,
        actor: str = "agent",
        data_payload: dict[str, Any] | None = None,
    ) -> TrialPursuit:
        data = self._read_payload()
        pursuits = [p for p in data.get("pursuits", []) if isinstance(p, dict)]
        pursuit = next((p for p in pursuits if p.get("pursuit_id") == pursuit_id), None)
        if pursuit is None:
            raise KeyError(pursuit_id)
        self._append_event(
            pursuit,
            kind=kind,
            note=note,
            actor=actor,
            data=data_payload or {},
        )
        pursuit["updated_at"] = _now_iso()
        data["pursuits"] = pursuits
        self._write_payload(data)
        return self._pursuit_from_dict(pursuit)

    def add_task(
        self,
        pursuit_id: str,
        *,
        title: str,
        due_at: str | None = None,
        actor: str = "agent",
    ) -> TrialPursuit:
        if not title.strip():
            raise ValueError("task title is required")
        data = self._read_payload()
        pursuits = [p for p in data.get("pursuits", []) if isinstance(p, dict)]
        pursuit = next((p for p in pursuits if p.get("pursuit_id") == pursuit_id), None)
        if pursuit is None:
            raise KeyError(pursuit_id)
        pursuit.setdefault("tasks", []).append(
            {
                "task_id": f"tt_{uuid.uuid4().hex[:12]}",
                "title": title.strip(),
                "status": "pending",
                "due_at": due_at,
                "created_at": _now_iso(),
                "completed_at": None,
            }
        )
        self._append_event(
            pursuit,
            kind="task_added",
            note=f"Added task: {title.strip()}",
            actor=actor,
        )
        pursuit["updated_at"] = _now_iso()
        data["pursuits"] = pursuits
        self._write_payload(data)
        return self._pursuit_from_dict(pursuit)

    def _append_event(
        self,
        pursuit: dict[str, Any],
        *,
        kind: str,
        note: str,
        actor: str,
        data: dict[str, Any] | None = None,
    ) -> None:
        pursuit.setdefault("events", []).append(
            {
                "event_id": f"te_{uuid.uuid4().hex[:12]}",
                "kind": kind,
                "note": note,
                "actor": actor,
                "data": data or {},
                "created_at": _now_iso(),
            }
        )

    def _read_payload(self) -> dict[str, Any]:
        if not self.path.is_file():
            return {"patient_id": self.patient_id, "pursuits": []}
        try:
            payload = json.loads(self.path.read_text("utf-8"))
        except json.JSONDecodeError:
            return {"patient_id": self.patient_id, "pursuits": []}
        if not isinstance(payload, dict):
            return {"patient_id": self.patient_id, "pursuits": []}
        payload.setdefault("patient_id", self.patient_id)
        payload.setdefault("pursuits", [])
        return payload

    def _write_payload(self, payload: dict[str, Any]) -> None:
        self.patient_dir.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(payload, indent=2, sort_keys=True, default=str),
            encoding="utf-8",
        )

    def _pursuit_from_dict(self, raw: dict[str, Any]) -> TrialPursuit:
        tasks = [
            TrialPursuitTask(
                task_id=str(task.get("task_id") or f"tt_{uuid.uuid4().hex[:12]}"),
                title=str(task.get("title") or "Untitled task"),
                status="done" if task.get("status") == "done" else "pending",
                due_at=task.get("due_at"),
                created_at=str(task.get("created_at") or _now_iso()),
                completed_at=task.get("completed_at"),
            )
            for task in raw.get("tasks", [])
            if isinstance(task, dict)
        ]
        events = [
            TrialPursuitEvent(
                event_id=str(event.get("event_id") or f"te_{uuid.uuid4().hex[:12]}"),
                kind=str(event.get("kind") or "event"),
                note=str(event.get("note") or ""),
                actor=str(event.get("actor") or "agent"),
                data=dict(event.get("data") or {}),
                created_at=str(event.get("created_at") or _now_iso()),
            )
            for event in raw.get("events", [])
            if isinstance(event, dict)
        ]
        return TrialPursuit(
            pursuit_id=str(raw.get("pursuit_id") or f"tp_{uuid.uuid4().hex[:12]}"),
            patient_id=self.patient_id,
            nct_id=str(raw.get("nct_id") or ""),
            title=str(raw.get("title") or raw.get("nct_id") or "Untitled trial"),
            status=_coerce_status(str(raw.get("status") or "interested")),
            sponsor=raw.get("sponsor"),
            trial_status=raw.get("trial_status"),
            source_url=raw.get("source_url"),
            source_kind=str(raw.get("source_kind") or "clinicaltrials.gov"),
            source_updated_at=raw.get("source_updated_at"),
            fit_score=float(raw["fit_score"]) if raw.get("fit_score") is not None else None,
            next_step=str(raw.get("next_step") or "Review eligibility and decide whether to prepare an outreach packet."),
            notes=str(raw.get("notes") or ""),
            tags=[str(tag) for tag in raw.get("tags", []) if str(tag).strip()],
            created_from_run_id=raw.get("created_from_run_id"),
            created_from_canvas_node_id=raw.get("created_from_canvas_node_id"),
            evidence_snapshot=dict(raw.get("evidence_snapshot") or {}),
            tasks=tasks,
            events=events,
            created_at=str(raw.get("created_at") or _now_iso()),
            updated_at=str(raw.get("updated_at") or _now_iso()),
        )

