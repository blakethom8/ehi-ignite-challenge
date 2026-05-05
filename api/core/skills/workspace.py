"""Workspace runtime — Layer 1 of the skill harness.

A workspace is a per-run filesystem directory the agent reads and writes,
mediated by three primitives: `write`, `cite`, and `escalate`. The runtime
treats those primitives as the only legal write path so the audit trail and
citation graph cannot be bypassed.

This module also implements the three save destinations described in
`docs/architecture/SELF-MODIFYING-WORKSPACE.md`: per-run edits, pinning to
the patient memory layer, and saving as a reusable patient context package.
"""

from __future__ import annotations

import json
import os
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator, Literal

from api.core.skills.loader import Skill
from api.core.skills.patient_memory import PatientMemory


REPO_ROOT = Path(__file__).resolve().parents[3]
CASES_ROOT = Path(os.getenv("SKILLS_CASES_PATH", REPO_ROOT / "data" / "cases"))

_CITATION_ID_PATTERN = re.compile(r"^c_\d{4}$")
_APPROVAL_ID_PATTERN = re.compile(r"^a_\d{4}$")
_SECTION_ANCHOR_RE = re.compile(
    r"<!-- ([A-Z_]+)_START -->.*?<!-- \1_END -->", re.DOTALL
)

SaveDestination = Literal["run", "patient", "package"]
RunStatus = Literal[
    "created",
    "running",
    "escalated",
    "validated",
    "finished",
    "failed",
]


class WorkspaceContractError(RuntimeError):
    """Raised when an agent tool call violates the workspace contract.

    The runtime catches this, registers it as an `is_error` tool result, and
    lets the agent retry. It never bubbles to the user as a 500.
    """


@dataclass
class Citation:
    citation_id: str
    claim: str
    source_kind: str  # fhir_resource | external_url | clinician_input | agent_inference
    source_ref: str | None
    evidence_tier: str  # T1 | T2 | T3 | T4
    access_timestamp: str  # ISO datetime


@dataclass
class Escalation:
    approval_id: str
    condition: str
    prompt: str
    context: dict[str, Any]
    resolved: bool = False
    resolution_choice: str | None = None
    resolution_notes: str | None = None
    resolved_at: str | None = None
    raised_at: str = ""


@dataclass
class TranscriptEvent:
    """Generic event written to `transcript.jsonl`."""

    kind: str  # turn | tool_call | tool_result | escalation | edit | save
    payload: dict[str, Any]
    at: str = field(default_factory=lambda: _now_iso())


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _safe_segment(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]", "_", value.strip())
    return cleaned[:64] or "x"


def allocate_run_dir(patient_id: str, skill_name: str, run_id: str | None = None) -> Path:
    """Create a fresh `/cases/{pid}/{skill}/{run_id}/` directory."""
    rid = run_id or uuid.uuid4().hex[:12]
    case_dir = CASES_ROOT / _safe_segment(patient_id) / _safe_segment(skill_name) / rid
    case_dir.mkdir(parents=True, exist_ok=True)
    (case_dir / "artifacts").mkdir(exist_ok=True)
    return case_dir


def list_runs(patient_id: str, skill_name: str | None = None) -> list[dict[str, Any]]:
    """Enumerate runs for a patient, optionally filtered by skill name.

    Returns lightweight metadata only — full state is in each run's brief.json.
    """
    base = CASES_ROOT / _safe_segment(patient_id)
    if not base.is_dir():
        return []
    out: list[dict[str, Any]] = []
    skill_dirs = (
        [base / _safe_segment(skill_name)]
        if skill_name
        else [d for d in base.iterdir() if d.is_dir() and d.name != "_memory"]
    )
    for skill_dir in skill_dirs:
        if not skill_dir.is_dir():
            continue
        for run_dir in sorted(skill_dir.iterdir(), reverse=True):
            if not run_dir.is_dir():
                continue
            brief_path = run_dir / "brief.json"
            status_path = run_dir / "status.json"
            try:
                brief = json.loads(brief_path.read_text("utf-8")) if brief_path.is_file() else {}
                status_payload = (
                    json.loads(status_path.read_text("utf-8")) if status_path.is_file() else {}
                )
            except json.JSONDecodeError:
                continue
            out.append(
                {
                    "run_id": run_dir.name,
                    "skill_name": skill_dir.name,
                    "patient_id": patient_id,
                    "status": status_payload.get("status", "unknown"),
                    "started_at": brief.get("started_at"),
                    "finished_at": status_payload.get("finished_at"),
                }
            )
    return out


class Workspace:
    """Mediated workspace for one run.

    A `Workspace` instance owns the run directory and exposes the three
    primitives (`write`, `cite`, `escalate`) plus lifecycle hooks
    (`start`, `append_transcript`, `finalize`) plus the three save
    destinations (`save_run_edits`, `pin_to_patient`,
    `save_as_context_package`).
    """

    def __init__(
        self,
        skill: Skill,
        patient_id: str,
        patient_memory: PatientMemory,
        run_dir: Path | None = None,
        brief: dict[str, Any] | None = None,
    ) -> None:
        self.skill = skill
        self.patient_id = patient_id
        self.patient_memory = patient_memory
        self.run_dir = run_dir or allocate_run_dir(patient_id, skill.name)
        self.run_id = self.run_dir.name
        self._brief = dict(brief or {})
        self._citations: list[Citation] = []
        self._escalations: list[Escalation] = []
        self._next_citation_seq = 1
        self._next_approval_seq = 1
        self._sections: dict[str, str] = {}
        self._status: RunStatus = "created"
        self._failure_reason: str | None = None

    # ── Lifecycle ───────────────────────────────────────────────────────

    @property
    def status(self) -> RunStatus:
        return self._status

    @property
    def brief(self) -> dict[str, Any]:
        return dict(self._brief)

    @property
    def workspace_md_path(self) -> Path:
        return self.run_dir / "workspace.md"

    def start(self) -> None:
        """Initialize the run dir from the skill's workspace template."""
        if self.skill.workspace_template is None:
            template = "# Workspace\n\n_(no template)_\n"
        else:
            template = self.skill.workspace_template

        self.workspace_md_path.write_text(template, encoding="utf-8")
        self._brief.setdefault("started_at", _now_iso())
        # Underscore-prefixed keys are internal (test injectables, transports);
        # they never get persisted alongside the run.
        public_brief = {k: v for k, v in self._brief.items() if not k.startswith("_")}
        (self.run_dir / "brief.json").write_text(
            json.dumps(public_brief, indent=2, sort_keys=True, default=str),
            encoding="utf-8",
        )
        self._set_status("running")
        self.append_transcript(
            TranscriptEvent(kind="run_started", payload={"run_id": self.run_id})
        )

    def _set_status(self, status: RunStatus, **extra: Any) -> None:
        self._status = status
        payload = {"status": status, "updated_at": _now_iso(), **extra}
        if status in {"finished", "failed"}:
            payload["finished_at"] = _now_iso()
        if self._failure_reason is not None and status == "failed":
            payload["failure_reason"] = self._failure_reason
        (self.run_dir / "status.json").write_text(
            json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8"
        )

    def append_transcript(self, event: TranscriptEvent) -> None:
        with (self.run_dir / "transcript.jsonl").open("a", encoding="utf-8") as fp:
            fp.write(json.dumps({"at": event.at, "kind": event.kind, **event.payload}, default=str) + "\n")

    # ── Mediated write primitive ────────────────────────────────────────

    def write(
        self,
        section: str,
        content: str,
        citation_ids: list[str] | None = None,
        *,
        anchor: str | None = None,
    ) -> None:
        """Append-or-replace a section of `workspace.md`.

        `anchor` (e.g., "TRIAL_SECTIONS") names a `<!-- ANCHOR_START --> ... <!-- ANCHOR_END -->`
        block in the template. If provided, the section is rendered between the
        anchor markers; otherwise it appends a `## {section}` block at the end.

        Every `[cite:c_NNNN]` reference embedded in `content` must resolve to a
        registered citation, otherwise `WorkspaceContractError` is raised.
        """
        if not section.strip():
            raise WorkspaceContractError("section name is required")
        if not content.strip():
            raise WorkspaceContractError(f"section '{section}' has no content")

        ids = list(citation_ids or [])
        for cid in self._extract_citation_refs(content):
            if cid not in ids:
                ids.append(cid)
        for cid in ids:
            if not _CITATION_ID_PATTERN.match(cid):
                raise WorkspaceContractError(
                    f"invalid citation id '{cid}' (must match c_NNNN)"
                )
            if not any(c.citation_id == cid for c in self._citations):
                raise WorkspaceContractError(
                    f"section '{section}' references unregistered citation '{cid}'"
                )

        rendered_section = f"### {section}\n\n{content.strip()}\n"
        self._sections[section] = rendered_section
        self._render_workspace_md(anchor=anchor, current_section=section)

        self.append_transcript(
            TranscriptEvent(
                kind="workspace_write",
                payload={
                    "section": section,
                    "anchor": anchor,
                    "citation_ids": ids,
                    "char_count": len(content),
                },
            )
        )

    def _extract_citation_refs(self, content: str) -> list[str]:
        return re.findall(r"\[cite:(c_\d{4})\]", content)

    def _render_workspace_md(self, *, anchor: str | None, current_section: str) -> None:
        existing = self.workspace_md_path.read_text(encoding="utf-8")
        if anchor:
            marker_start = f"<!-- {anchor}_START -->"
            marker_end = f"<!-- {anchor}_END -->"
            if marker_start not in existing or marker_end not in existing:
                # Anchor not in the template — append at end.
                existing += "\n" + self._sections[current_section]
                self.workspace_md_path.write_text(existing, encoding="utf-8")
                return
            block = "\n".join(
                self._sections[name]
                for name in self._sections
                if self._belongs_to_anchor(name, anchor)
            )
            new_text = re.sub(
                rf"{re.escape(marker_start)}.*?{re.escape(marker_end)}",
                f"{marker_start}\n{block}\n{marker_end}",
                existing,
                flags=re.DOTALL,
            )
            self.workspace_md_path.write_text(new_text, encoding="utf-8")
            return

        # No anchor — append the new section at the bottom (idempotent).
        sections_block = "\n".join(self._sections.values())
        if "<!-- WORKSPACE_BODY_START -->" in existing:
            new_text = re.sub(
                r"<!-- WORKSPACE_BODY_START -->.*?<!-- WORKSPACE_BODY_END -->",
                f"<!-- WORKSPACE_BODY_START -->\n{sections_block}\n<!-- WORKSPACE_BODY_END -->",
                existing,
                flags=re.DOTALL,
            )
        else:
            new_text = existing.rstrip() + "\n\n" + sections_block + "\n"
        self.workspace_md_path.write_text(new_text, encoding="utf-8")

    def _belongs_to_anchor(self, section_name: str, anchor: str) -> bool:
        # Sections are tagged into anchors by name prefix convention; the
        # default tag is the anchor name itself. Skills that need fine-grained
        # tagging can pass `anchor` explicitly per write call.
        return True  # all sections written under one anchor live in that anchor

    # ── Citation primitive ──────────────────────────────────────────────

    def cite(
        self,
        claim: str,
        source_kind: str,
        source_ref: str | None,
        evidence_tier: str,
    ) -> str:
        """Register a citation and return its id.

        - `source_kind` ∈ {fhir_resource, external_url, clinician_input,
          agent_inference}.
        - `source_ref` is required for `fhir_resource` and `external_url`.
        - `evidence_tier` ∈ {T1, T2, T3, T4}.
        """
        if not claim.strip():
            raise WorkspaceContractError("citation claim is required")
        if source_kind not in {
            "fhir_resource",
            "external_url",
            "clinician_input",
            "agent_inference",
        }:
            raise WorkspaceContractError(f"invalid source_kind '{source_kind}'")
        if source_kind in {"fhir_resource", "external_url"} and not (source_ref or "").strip():
            raise WorkspaceContractError(
                f"source_ref is required for source_kind={source_kind}"
            )
        if evidence_tier not in {"T1", "T2", "T3", "T4"}:
            raise WorkspaceContractError(
                f"evidence_tier must be T1..T4 (got '{evidence_tier}')"
            )

        cid = f"c_{self._next_citation_seq:04d}"
        self._next_citation_seq += 1
        citation = Citation(
            citation_id=cid,
            claim=claim.strip(),
            source_kind=source_kind,
            source_ref=(source_ref or "").strip() or None,
            evidence_tier=evidence_tier,
            access_timestamp=_now_iso(),
        )
        self._citations.append(citation)

        with (self.run_dir / "citations.jsonl").open("a", encoding="utf-8") as fp:
            fp.write(json.dumps(citation.__dict__, default=str) + "\n")

        self.append_transcript(
            TranscriptEvent(kind="cite", payload={"citation_id": cid, "source_kind": source_kind})
        )
        return cid

    def citations(self) -> list[Citation]:
        return list(self._citations)

    # ── Escalation primitive ────────────────────────────────────────────

    def escalate(
        self,
        condition: str,
        prompt: str,
        context: dict[str, Any] | None = None,
    ) -> Escalation:
        """Register an escalation and switch run status to 'escalated'.

        The runner is responsible for actually pausing the agent loop on this
        signal — the workspace just records the gate.
        """
        if not condition.strip():
            raise WorkspaceContractError("escalation condition is required")
        if not prompt.strip():
            raise WorkspaceContractError("escalation prompt is required")

        declared = {trig.condition for trig in self.skill.manifest.escalation}
        if declared and condition not in declared and not condition.startswith("ad_hoc:"):
            raise WorkspaceContractError(
                f"escalation condition '{condition}' is not in skill manifest. "
                f"Declared triggers: {sorted(declared)}. "
                f"Ad-hoc escalations must be prefixed 'ad_hoc:'."
            )

        aid = f"a_{self._next_approval_seq:04d}"
        self._next_approval_seq += 1
        esc = Escalation(
            approval_id=aid,
            condition=condition,
            prompt=prompt.strip(),
            context=dict(context or {}),
            raised_at=_now_iso(),
        )
        self._escalations.append(esc)

        with (self.run_dir / "approvals.jsonl").open("a", encoding="utf-8") as fp:
            fp.write(json.dumps(esc.__dict__, default=str) + "\n")

        self._set_status("escalated")
        self.append_transcript(
            TranscriptEvent(
                kind="escalation",
                payload={"approval_id": aid, "condition": condition, "prompt": prompt},
            )
        )
        return esc

    def resolve_escalation(
        self,
        approval_id: str,
        choice: str,
        notes: str = "",
        actor: str = "clinician",
    ) -> Escalation:
        if not _APPROVAL_ID_PATTERN.match(approval_id):
            raise WorkspaceContractError(f"invalid approval_id '{approval_id}'")
        for esc in self._escalations:
            if esc.approval_id != approval_id:
                continue
            if esc.resolved:
                raise WorkspaceContractError(
                    f"approval {approval_id} already resolved"
                )
            esc.resolved = True
            esc.resolution_choice = choice.strip() or "acknowledged"
            esc.resolution_notes = notes.strip() or None
            esc.resolved_at = _now_iso()
            self._rewrite_approvals()
            self.append_transcript(
                TranscriptEvent(
                    kind="escalation_resolved",
                    payload={
                        "approval_id": approval_id,
                        "choice": esc.resolution_choice,
                        "actor": actor,
                    },
                )
            )
            if all(e.resolved for e in self._escalations):
                self._set_status("running")
            return esc
        raise WorkspaceContractError(f"approval {approval_id} not found")

    def _rewrite_approvals(self) -> None:
        path = self.run_dir / "approvals.jsonl"
        with path.open("w", encoding="utf-8") as fp:
            for esc in self._escalations:
                fp.write(json.dumps(esc.__dict__, default=str) + "\n")

    def pending_escalations(self) -> list[Escalation]:
        return [e for e in self._escalations if not e.resolved]

    # ── Finalize ────────────────────────────────────────────────────────

    def finalize(self, output: dict[str, Any]) -> dict[str, Any]:
        """Validate the artifact against `output_schema`, lock `output.json`.

        Raises `WorkspaceContractError` on schema validation failure. The
        runner converts that into a final escalation; it never silently
        accepts an invalid artifact.
        """
        try:
            import jsonschema  # local import — keeps loader importable without it
        except ImportError as exc:
            raise WorkspaceContractError(
                "jsonschema is required to finalize a workspace"
            ) from exc

        validator = jsonschema.Draft202012Validator(self.skill.output_schema)
        errors = sorted(validator.iter_errors(output), key=lambda e: list(e.absolute_path))
        if errors:
            messages = [
                f"{'/'.join(str(p) for p in e.absolute_path) or '<root>'}: {e.message}"
                for e in errors[:10]
            ]
            raise WorkspaceContractError(
                "output failed schema validation: " + "; ".join(messages)
            )

        (self.run_dir / "output.json").write_text(
            json.dumps(output, indent=2, sort_keys=True), encoding="utf-8"
        )
        self._set_status("finished")
        self.append_transcript(
            TranscriptEvent(kind="finalize", payload={"trial_count": len(output.get("trials", []))})
        )
        return output

    def fail(self, reason: str) -> None:
        self._failure_reason = reason
        self._set_status("failed")
        self.append_transcript(
            TranscriptEvent(kind="run_failed", payload={"reason": reason})
        )

    # ── Save destinations (post-finalize) ───────────────────────────────

    def save_run_edits(self, edits_markdown: str, actor: str = "clinician") -> Path:
        """Destination (A): write `clinician_edits.md` in the run dir."""
        edits_path = self.run_dir / "clinician_edits.md"
        existing = edits_path.read_text("utf-8") if edits_path.is_file() else ""
        header = f"\n\n## Edit at {_now_iso()} by {actor}\n\n"
        edits_path.write_text(existing + header + edits_markdown.strip() + "\n", encoding="utf-8")
        self.append_transcript(
            TranscriptEvent(
                kind="save",
                payload={"destination": "run", "actor": actor, "char_count": len(edits_markdown)},
            )
        )
        return edits_path

    def pin_to_patient(
        self,
        facts: list[dict[str, Any]],
        actor: str = "clinician",
    ) -> Path:
        """Destination (B): promote selected facts to `_memory/pinned.md`.

        Each fact is `{"text": str, "citation_id": str | None, "evidence_tier": str | None}`.
        Citations are resolved through the run's citation registry so the
        pinned fact carries the original chip when read by future runs.
        """
        if not facts:
            raise WorkspaceContractError("at least one fact is required to pin")

        resolved_facts: list[dict[str, Any]] = []
        for fact in facts:
            text = (fact.get("text") or "").strip()
            if not text:
                raise WorkspaceContractError("each pinned fact must have text")
            cid = fact.get("citation_id")
            citation: dict[str, Any] | None = None
            if cid:
                match = next((c for c in self._citations if c.citation_id == cid), None)
                if match is None:
                    raise WorkspaceContractError(
                        f"pinned fact references unknown citation '{cid}'"
                    )
                citation = match.__dict__
            resolved_facts.append(
                {
                    "text": text,
                    "evidence_tier": fact.get("evidence_tier") or (citation or {}).get("evidence_tier"),
                    "citation": citation,
                    "source_run_id": self.run_id,
                    "source_skill": self.skill.name,
                    "promoted_at": _now_iso(),
                    "promoted_by": actor,
                }
            )

        path = self.patient_memory.append_pinned_facts(resolved_facts, source_run=self.run_id, actor=actor)
        self.append_transcript(
            TranscriptEvent(
                kind="save",
                payload={
                    "destination": "patient",
                    "actor": actor,
                    "fact_count": len(resolved_facts),
                },
            )
        )
        return path

    def save_as_context_package(
        self,
        package_name: str,
        content: str,
        actor: str = "clinician",
    ) -> Path:
        """Destination (C): materialize a reusable patient context package."""
        if not package_name.strip():
            raise WorkspaceContractError("package_name is required")
        if not content.strip():
            raise WorkspaceContractError("package content is required")
        path = self.patient_memory.write_context_package(
            package_name, content, source_run=self.run_id, source_skill=self.skill.name, actor=actor
        )
        self.append_transcript(
            TranscriptEvent(
                kind="save",
                payload={
                    "destination": "package",
                    "actor": actor,
                    "package_name": package_name,
                },
            )
        )
        return path

    # ── Replay helpers ──────────────────────────────────────────────────

    def transcript_events(self) -> Iterator[dict[str, Any]]:
        path = self.run_dir / "transcript.jsonl"
        if not path.is_file():
            return iter(())
        return (json.loads(line) for line in path.read_text("utf-8").splitlines() if line.strip())


def load_workspace(skill: Skill, patient_id: str, run_id: str) -> Workspace:
    """Reattach to an existing run dir (used by post-run save/edit endpoints)."""
    run_dir = CASES_ROOT / _safe_segment(patient_id) / _safe_segment(skill.name) / run_id
    if not run_dir.is_dir():
        raise FileNotFoundError(f"run not found: {run_dir}")

    workspace = Workspace(
        skill=skill,
        patient_id=patient_id,
        patient_memory=PatientMemory(patient_id),
        run_dir=run_dir,
    )
    # Reload state from disk.
    brief_path = run_dir / "brief.json"
    if brief_path.is_file():
        workspace._brief = json.loads(brief_path.read_text("utf-8"))
    citations_path = run_dir / "citations.jsonl"
    if citations_path.is_file():
        for line in citations_path.read_text("utf-8").splitlines():
            if not line.strip():
                continue
            data = json.loads(line)
            workspace._citations.append(Citation(**data))
        if workspace._citations:
            last = workspace._citations[-1].citation_id
            workspace._next_citation_seq = int(last.split("_")[1]) + 1
    approvals_path = run_dir / "approvals.jsonl"
    if approvals_path.is_file():
        latest_by_id: dict[str, dict[str, Any]] = {}
        for line in approvals_path.read_text("utf-8").splitlines():
            if not line.strip():
                continue
            data = json.loads(line)
            latest_by_id[data["approval_id"]] = data
        for data in latest_by_id.values():
            workspace._escalations.append(Escalation(**data))
        if workspace._escalations:
            last = max(int(e.approval_id.split("_")[1]) for e in workspace._escalations)
            workspace._next_approval_seq = last + 1
    status_path = run_dir / "status.json"
    if status_path.is_file():
        workspace._status = json.loads(status_path.read_text("utf-8")).get("status", "created")
    return workspace
