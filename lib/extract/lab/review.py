"""Interactive ground-truth review for a lab run.

Walks resource-by-resource through the bundle, prompts the user for a
decision per resource, and persists the result via save_ground_truth.
Supports resume — partial sessions write a sidecar decisions file
that the next invocation picks up.

Used by `python -m lib.extract.lab review --run <run-id>`.
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Literal


_DECISION_HELP = """\
Commands per fact:
  a / accept         — keep the fact in ground truth as-is
  r / reject         — drop the fact (the gold pipeline got it wrong)
  e / edit           — open $EDITOR (or default editor) to edit the JSON
  s / skip           — defer, leave undecided (treated as accept on save)
  ? / help           — show this help
  q / quit-and-save  — save progress so far and exit
  Q / quit-no-save   — exit without saving
"""


@dataclass
class ReviewSession:
    run_id: str
    run_dir: Path
    bundle: dict
    pdf_sha256: str
    pdf_path: str
    decisions: list[dict]   # parallel to bundle["entry"]
    next_index: int          # cursor; resume picks up here


def load_session_for_run(
    run_id: str,
    *,
    lab_root: Path | None = None,
) -> ReviewSession:
    """Load a run + (optional) in-progress review-decisions sidecar."""
    from lib.extract.lab.recorder import DEFAULT_LAB_ROOT
    base = lab_root or DEFAULT_LAB_ROOT
    run_dir = base / "runs" / run_id
    if not run_dir.exists():
        raise FileNotFoundError(f"run not found: {run_id} ({run_dir})")
    manifest = json.loads((run_dir / "manifest.json").read_text())
    bundle = json.loads((run_dir / "bundle.json").read_text())
    sidecar = run_dir / "review_in_progress.json"
    if sidecar.exists():
        progress = json.loads(sidecar.read_text())
        decisions = progress["decisions"]
        next_index = progress["next_index"]
    else:
        decisions = []
        next_index = 0
    return ReviewSession(
        run_id=run_id,
        run_dir=run_dir,
        bundle=bundle,
        pdf_sha256=manifest["pdf_sha256"],
        pdf_path=manifest["pdf_path"],
        decisions=decisions,
        next_index=next_index,
    )


def render_resource_summary(resource: dict) -> str:
    """Compact one-line summary of a FHIR resource for the prompt."""
    rt = resource.get("resourceType", "?")
    if rt == "Observation":
        text = (resource.get("code", {}) or {}).get("text", "?")
        vq = resource.get("valueQuantity")
        if vq:
            value = f"{vq.get('value')} {vq.get('unit', '')}".strip()
        elif resource.get("valueString"):
            value = str(resource.get("valueString"))[:40]
        else:
            value = "?"
        return f"Observation: {text} = {value}"
    if rt == "Condition":
        return f"Condition: {resource.get('code', {}).get('text', '?')}"
    if rt == "MedicationRequest":
        med = resource.get("medicationCodeableConcept", {})
        return f"MedicationRequest: {med.get('text', '?')}"
    if rt == "AllergyIntolerance":
        return f"AllergyIntolerance: {resource.get('code', {}).get('text', '?')}"
    if rt == "Immunization":
        return f"Immunization: {resource.get('vaccineCode', {}).get('text', '?')}"
    if rt == "Patient":
        names = resource.get("name") or []
        if names:
            n = names[0]
            return f"Patient: {' '.join(n.get('given', []))} {n.get('family', '')}".strip()
        return f"Patient: {resource.get('id', '?')}"
    if rt == "Encounter":
        type_list = resource.get("type") or []
        return f"Encounter: {type_list[0].get('text', '?') if type_list else resource.get('id', '?')}"
    if rt == "Practitioner":
        names = resource.get("name") or []
        if names:
            n = names[0]
            return f"Practitioner: {n.get('text') or ' '.join(n.get('given', [])) + ' ' + n.get('family', '')}".strip()
        return f"Practitioner: {resource.get('id', '?')}"
    if rt == "Organization":
        return f"Organization: {resource.get('name', '?')}"
    if rt == "Coverage":
        return f"Coverage: {resource.get('payor', [{}])[0].get('display', '?')}"
    if rt == "DocumentReference":
        return f"DocumentReference: {resource.get('type', {}).get('text', '?')}"
    if rt == "Composition":
        return f"Composition: {resource.get('title', '?')}"
    return f"{rt}: {resource.get('id', '?')}"


def save_progress(session: ReviewSession) -> None:
    """Write the in-progress sidecar so the user can resume."""
    sidecar = session.run_dir / "review_in_progress.json"
    sidecar.write_text(json.dumps({
        "run_id": session.run_id,
        "decisions": session.decisions,
        "next_index": session.next_index,
    }, indent=2))


def discard_progress(session: ReviewSession) -> None:
    sidecar = session.run_dir / "review_in_progress.json"
    if sidecar.exists():
        sidecar.unlink()


def edit_resource(resource: dict, editor: str | None = None) -> dict | None:
    """Open the resource as JSON in $EDITOR. Returns the edited dict or
    None if the user didn't change it / aborted."""
    import os
    import subprocess
    import tempfile
    editor = editor or os.environ.get("EDITOR") or "vi"
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(resource, f, indent=2, default=str)
        tmp_path = f.name
    try:
        subprocess.run([editor, tmp_path], check=False)
        with open(tmp_path) as f:
            new_content = f.read()
        try:
            new_resource = json.loads(new_content)
            if new_resource == resource:
                return None  # no change
            return new_resource
        except json.JSONDecodeError as exc:
            print(f"  Warning: JSON parse error after edit: {exc}. Keeping original.", file=sys.stderr)
            return None
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


def run_review(
    session: ReviewSession,
    *,
    reviewer: str,
    notes: str = "",
    input_fn: Callable[[str], str] = input,
    output_fn: Callable[[str], None] = print,
    edit_fn: Callable[[dict], dict | None] = edit_resource,
    auto_save_every: int = 5,
    lab_root: Path | None = None,
) -> tuple[Literal["completed", "saved-partial", "discarded"], int | None]:
    """Run the interactive review loop.

    Returns (status, version):
      - "completed", N   — full review done; saved as ground-truth version N
      - "saved-partial", None — user quit-and-saved progress; no GT version yet
      - "discarded", None — user quit-no-save

    input_fn / output_fn / edit_fn are injected for testability.
    """
    from lib.extract.lab.ground_truth import save_ground_truth

    entries = session.bundle.get("entry", []) or []
    total = len(entries)
    output_fn(f"Reviewing run {session.run_id} — {total} resources")
    output_fn(f"PDF: {session.pdf_path}")
    if session.next_index > 0:
        output_fn(f"Resuming at fact #{session.next_index + 1} of {total}")
    output_fn(_DECISION_HELP)

    # Mutable working copy of decisions + bundle (edits replace entries)
    decisions = list(session.decisions)
    working_bundle = json.loads(json.dumps(session.bundle))  # deep copy
    working_entries = working_bundle["entry"]

    i = session.next_index
    while i < total:
        resource = working_entries[i]["resource"]
        output_fn(f"\n[{i + 1}/{total}] {render_resource_summary(resource)}")
        output_fn(f"   resourceType={resource.get('resourceType')} id={resource.get('id', '<no-id>')}")
        cmd_raw = input_fn("   accept/reject/edit/skip/help/quit [a/r/e/s/?/q]: ").strip().lower()

        if cmd_raw in ("a", "accept", ""):
            decision = "accept"
        elif cmd_raw in ("r", "reject"):
            decision = "reject"
        elif cmd_raw in ("e", "edit"):
            new_resource = edit_fn(resource)
            if new_resource is not None:
                working_entries[i] = {"resource": new_resource}
                resource = new_resource
                decision = "edit"
            else:
                output_fn("  (no change applied)")
                continue  # re-prompt for the same fact
        elif cmd_raw in ("s", "skip"):
            decision = "skip"
        elif cmd_raw in ("?", "help"):
            output_fn(_DECISION_HELP)
            continue
        elif cmd_raw in ("q", "quit-and-save"):
            session.decisions = decisions
            session.next_index = i
            save_progress(session)
            output_fn(f"Saved progress at fact #{i + 1}. Resume with the same command later.")
            return "saved-partial", None
        elif cmd_raw in ("Q",):
            output_fn("Discarded progress.")
            return "discarded", None
        else:
            output_fn(f"Unknown command {cmd_raw!r}. Type ? for help.")
            continue

        decisions.append({
            "resource_id": resource.get("id"),
            "resource_type": resource.get("resourceType"),
            "decision": decision,
            "reviewed_at": _now_iso(),
        })
        i += 1

        # Auto-save every N facts
        if auto_save_every > 0 and i % auto_save_every == 0 and i < total:
            session.decisions = decisions
            session.next_index = i
            save_progress(session)
            output_fn(f"  (auto-saved progress at fact #{i})")

    # Filter out rejected entries; keep accepted + edited (skip → accept-by-default)
    accepted_indices = {
        idx
        for idx, d in enumerate(decisions)
        if d["decision"] in ("accept", "edit", "skip")
    }
    final_entries = [
        working_entries[idx]
        for idx in sorted(accepted_indices)
    ]
    final_bundle = {**working_bundle, "entry": final_entries}

    gtv = save_ground_truth(
        pdf_sha256=session.pdf_sha256,
        pdf_path=session.pdf_path,
        bundle=final_bundle,
        decisions=decisions,
        reviewer=reviewer,
        source_run_id=session.run_id,
        notes=notes,
        lab_root=lab_root,
    )
    discard_progress(session)
    output_fn(f"\nReview complete. Saved as ground-truth v{gtv.version} ({len(final_entries)}/{total} resources kept).")
    return "completed", gtv.version


def _now_iso() -> str:
    import datetime
    return datetime.datetime.utcnow().isoformat() + "Z"
