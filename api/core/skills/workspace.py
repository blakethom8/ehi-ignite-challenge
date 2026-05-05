"""Workspace runtime — Layer 1 of the skill harness.

A workspace is a per-run filesystem directory the agent reads and writes,
mediated by three primitives: `write`, `cite`, and `escalate`. The runtime
treats those primitives as the only legal write path so the audit trail and
citation graph cannot be bypassed.

This module also implements the three save destinations described in
`docs/architecture/skill-runtime/SELF-MODIFYING-WORKSPACE.md`: per-run edits, pinning to
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

from api.core.skills.event_hub import EventHub
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
        event_hub: EventHub | None = None,
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
        # Per-section anchor membership. None means "append at the end of the
        # body" (or to the WORKSPACE_BODY anchor if present). The same section
        # name in different anchors are kept distinct via the
        # `(anchor, section)` composite key the renderer uses.
        self._section_anchors: dict[str, str | None] = {}
        self._status: RunStatus = "created"
        self._failure_reason: str | None = None
        # Optional live broadcast — when attached, every transcript event
        # also reaches connected SSE subscribers. Disk remains the source
        # of truth; the hub is the fast path.
        self.event_hub = event_hub

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
        """Initialize (or re-attach to) the run dir.

        Idempotent: on a fresh run it renders the skill's workspace template
        with brief/run/skill substitutions; on a resume (workspace.md
        already exists) it preserves whatever the agent has written so far.
        Either way, brief.json and status.json are kept in sync, and the
        status moves to `running` if no escalations are pending.
        """
        is_fresh = not self.workspace_md_path.is_file()
        if is_fresh:
            template = self.skill.workspace_template or "# Workspace\n\n_(no template)_\n"
            rendered = self._substitute_template_vars(template)
            self.workspace_md_path.write_text(rendered, encoding="utf-8")

        self._brief.setdefault("started_at", _now_iso())
        # Underscore-prefixed keys are internal (test injectables, transports);
        # they never get persisted alongside the run.
        public_brief = {k: v for k, v in self._brief.items() if not k.startswith("_")}
        (self.run_dir / "brief.json").write_text(
            json.dumps(public_brief, indent=2, sort_keys=True, default=str),
            encoding="utf-8",
        )
        if not self.pending_escalations():
            self._set_status("running")
        if is_fresh:
            self.append_transcript(
                TranscriptEvent(kind="run_started", payload={"run_id": self.run_id})
            )
        else:
            self.append_transcript(
                TranscriptEvent(kind="run_resumed", payload={"run_id": self.run_id})
            )

    def _substitute_template_vars(self, template: str) -> str:
        """Resolve `{{var.path}}` placeholders in the workspace template.

        Supported keys:
        - run.id, run.started_at
        - skill.name, skill.version
        - patient.id, patient.display_name
        - brief.<key> (top-level brief keys, joined to a string)
        Unknown keys are left as-is so the renderer can flag them visibly.
        """
        started_at = self._brief.get("started_at") or _now_iso()
        display_name = (
            self._brief.get("patient_display_name")
            or self._brief.get("patient_name")
            or self.patient_id
        )
        ctx: dict[str, str] = {
            "run.id": self.run_id,
            "run.started_at": started_at,
            "skill.name": self.skill.name,
            "skill.version": self.skill.manifest.version,
            "patient.id": self.patient_id,
            "patient.display_name": str(display_name),
        }
        for key, value in self._brief.items():
            if key.startswith("_") or not isinstance(key, str):
                continue
            if isinstance(value, (str, int, float, bool)):
                ctx[f"brief.{key}"] = str(value)
            elif isinstance(value, list) and all(
                isinstance(item, (str, int, float, bool)) for item in value
            ):
                ctx[f"brief.{key}"] = ", ".join(str(v) for v in value)

        # Friendly fallbacks for fields the trial-matching template references
        # but which aren't directly populated.
        anchors = self._brief.get("anchors")
        if isinstance(anchors, list) and anchors:
            displays = [
                str(a.get("display") or a.get("text") or a.get("resource_id") or "")
                for a in anchors
                if isinstance(a, dict)
            ]
            displays = [d for d in displays if d]
            if displays:
                ctx.setdefault("brief.anchors_summary", "; ".join(displays))
        ctx.setdefault("brief.anchors_summary", "_(none yet)_")
        ctx.setdefault("brief.search_constraints_summary", "")
        ctx.setdefault("brief.patient_context_summary", "")

        def _resolve(match: "re.Match[str]") -> str:
            key = match.group(1).strip()
            return ctx.get(key, match.group(0))

        return re.sub(r"\{\{\s*([\w.]+)\s*\}\}", _resolve, template)

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
        """Persist an event to disk and broadcast to live subscribers.

        Disk write happens *first* — durability before broadcast. If a
        subscriber's queue is full, the live event is dropped for them;
        they recover via transcript replay on reconnect.
        """
        record = {"at": event.at, "kind": event.kind, **event.payload}
        with (self.run_dir / "transcript.jsonl").open("a", encoding="utf-8") as fp:
            fp.write(json.dumps(record, default=str) + "\n")
        if self.event_hub is not None:
            self.event_hub.publish_nowait(record)

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
        # Track the anchor this section belongs to so the renderer can keep
        # WORKSPACE_BODY content out of the TRIAL_SECTIONS block (and vice
        # versa). A section re-written under a different anchor migrates to
        # the new one rather than being duplicated.
        self._section_anchors[section] = anchor
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
        """Update the anchors that have in-memory sections.

        Only touches anchors with sections currently in `_sections` so that
        post-resume writes (where in-memory state is partial) don't wipe
        anchors written before the escalation. Each section is rendered into
        the anchor it was last written under — that's the "fix to
        `_belongs_to_anchor` always returning true" behavior change.
        """
        rendered_text = self.workspace_md_path.read_text(encoding="utf-8")
        by_anchor: dict[str | None, list[str]] = {}
        for name, rendered in self._sections.items():
            target = self._section_anchors.get(name)
            by_anchor.setdefault(target, []).append(rendered)

        for declared, blocks in by_anchor.items():
            if declared is None:
                continue
            marker_start = f"<!-- {declared}_START -->"
            marker_end = f"<!-- {declared}_END -->"
            block = "\n".join(blocks)
            if marker_start in rendered_text and marker_end in rendered_text:
                rendered_text = re.sub(
                    rf"{re.escape(marker_start)}.*?{re.escape(marker_end)}",
                    f"{marker_start}\n{block}\n{marker_end}",
                    rendered_text,
                    flags=re.DOTALL,
                )
            else:
                # Declared anchor not in the template — append a fresh
                # marker block so subsequent writes can find it.
                rendered_text = (
                    rendered_text.rstrip()
                    + f"\n\n{marker_start}\n{block}\n{marker_end}\n"
                )

        untagged = by_anchor.get(None, [])
        if untagged and anchor is None:
            untagged_block = "\n".join(untagged)
            if "<!-- WORKSPACE_BODY_START -->" in rendered_text:
                rendered_text = re.sub(
                    r"<!-- WORKSPACE_BODY_START -->.*?<!-- WORKSPACE_BODY_END -->",
                    f"<!-- WORKSPACE_BODY_START -->\n{untagged_block}\n<!-- WORKSPACE_BODY_END -->",
                    rendered_text,
                    flags=re.DOTALL,
                )
            else:
                rendered_text = self._strip_appended_untagged_block(rendered_text)
                rendered_text = (
                    rendered_text.rstrip()
                    + "\n\n<!-- WORKSPACE_BODY_START -->\n"
                    + untagged_block
                    + "\n<!-- WORKSPACE_BODY_END -->\n"
                )

        self.workspace_md_path.write_text(rendered_text, encoding="utf-8")

    @staticmethod
    def _strip_appended_untagged_block(text: str) -> str:
        """Remove a previously-appended WORKSPACE_BODY block to keep the doc tidy."""
        return re.sub(
            r"\n*<!-- WORKSPACE_BODY_START -->.*?<!-- WORKSPACE_BODY_END -->\n*",
            "",
            text,
            flags=re.DOTALL,
        )

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
