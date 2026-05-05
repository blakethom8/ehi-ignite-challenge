"""Patient memory layer — cross-run, cross-skill persistence.

Per `docs/architecture/SELF-MODIFYING-WORKSPACE.md` §4: each patient has a
`/cases/{patient_id}/_memory/` directory that future skill runs read at
session start. The agent never writes here directly; only the runtime
mediates writes via clinician-initiated save destinations.
"""

from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[3]
CASES_ROOT = Path(os.getenv("SKILLS_CASES_PATH", REPO_ROOT / "data" / "cases"))


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _safe_segment(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]", "_", value.strip())
    return cleaned[:64] or "x"


def _safe_package_name(value: str) -> str:
    cleaned = re.sub(r"[^a-z0-9-]", "-", value.strip().lower())
    cleaned = re.sub(r"-+", "-", cleaned).strip("-")
    return cleaned[:64] or "package"


class PatientMemory:
    """Read/write surface for `/cases/{pid}/_memory/`."""

    def __init__(self, patient_id: str) -> None:
        self.patient_id = patient_id
        self.memory_dir = CASES_ROOT / _safe_segment(patient_id) / "_memory"
        self.packages_dir = self.memory_dir / "context_packages"

    # ── Reads ───────────────────────────────────────────────────────────

    @property
    def pinned_path(self) -> Path:
        return self.memory_dir / "pinned.md"

    @property
    def notes_path(self) -> Path:
        return self.memory_dir / "notes.jsonl"

    def pinned(self) -> str:
        if not self.pinned_path.is_file():
            return ""
        return self.pinned_path.read_text("utf-8")

    def context_packages(self) -> dict[str, str]:
        if not self.packages_dir.is_dir():
            return {}
        out: dict[str, str] = {}
        for child in sorted(self.packages_dir.iterdir()):
            if child.is_file() and child.suffix == ".md":
                out[child.stem] = child.read_text("utf-8")
        return out

    def session_context(self, requested_packages: list[str] | None = None) -> str:
        """Render the patient memory layer as a context block for the agent.

        Always includes `pinned.md` if present. Includes the requested context
        packages by name; silently skips ones that don't exist (the runner can
        choose to surface those as a warning).
        """
        chunks: list[str] = []
        pinned = self.pinned()
        if pinned.strip():
            chunks.append("# Patient memory — pinned facts\n\n" + pinned.rstrip())
        for name in requested_packages or []:
            path = self.packages_dir / f"{_safe_package_name(name)}.md"
            if path.is_file():
                chunks.append(f"# Context: {name}\n\n" + path.read_text("utf-8").rstrip())
        return "\n\n".join(chunks)

    def notes(self) -> list[dict[str, Any]]:
        if not self.notes_path.is_file():
            return []
        return [
            json.loads(line)
            for line in self.notes_path.read_text("utf-8").splitlines()
            if line.strip()
        ]

    # ── Writes ──────────────────────────────────────────────────────────

    def append_pinned_facts(
        self,
        facts: list[dict[str, Any]],
        *,
        source_run: str,
        actor: str,
    ) -> Path:
        """Append a block of pinned facts to `pinned.md` and log the event."""
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        existing = self.pinned() or ""
        block_lines = [f"\n\n## Promoted from run `{source_run}` at {_now_iso()} by {actor}\n"]
        for fact in facts:
            text = fact["text"].strip()
            tier = fact.get("evidence_tier") or "T?"
            citation = fact.get("citation") or {}
            ref = citation.get("source_ref") or "(no source)"
            kind = citation.get("source_kind") or "unknown"
            block_lines.append(f"- **{text}** ({tier}, {kind}: `{ref}`)")
        block = "\n".join(block_lines) + "\n"
        self.pinned_path.write_text(existing + block, encoding="utf-8")

        self._append_event(
            {
                "kind": "pin_to_patient",
                "source_run": source_run,
                "actor": actor,
                "fact_count": len(facts),
                "fact_summaries": [f["text"][:120] for f in facts],
            }
        )
        return self.pinned_path

    def write_context_package(
        self,
        name: str,
        content: str,
        *,
        source_run: str,
        source_skill: str,
        actor: str,
    ) -> Path:
        """Materialize a context package; later skills can name it in their frontmatter."""
        self.packages_dir.mkdir(parents=True, exist_ok=True)
        safe_name = _safe_package_name(name)
        path = self.packages_dir / f"{safe_name}.md"
        provenance = (
            f"<!-- promoted from run {source_run} (skill={source_skill}) "
            f"by {actor} at {_now_iso()} -->\n\n"
        )
        existing = path.read_text("utf-8") if path.is_file() else ""
        # Newer content goes on top; the file is append-only over time.
        path.write_text(provenance + content.strip() + "\n\n" + existing, encoding="utf-8")

        self._append_event(
            {
                "kind": "save_context_package",
                "package_name": safe_name,
                "source_run": source_run,
                "source_skill": source_skill,
                "actor": actor,
                "char_count": len(content),
            }
        )
        return path

    def _append_event(self, event: dict[str, Any]) -> None:
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        with self.notes_path.open("a", encoding="utf-8") as fp:
            fp.write(json.dumps({"at": _now_iso(), **event}, default=str) + "\n")
