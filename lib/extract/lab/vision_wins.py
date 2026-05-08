"""Vision-wins triage for the gold-standard build.

When a production pipeline extracts a fact that's not in the latest
ground truth, that fact lands in eval.json's `extracted_only` list.
The vision-wins triage walks each such fact and asks the reviewer:
  - 'valid_extra'      — real finding; incorporate into a new GT version
  - 'hallucination'    — model error; record as such, eval penalty stands
  - 'out_of_scope'     — real but doesn't belong in our schema
                          (e.g., free-text from a section we don't model);
                          eval ignores rather than penalizes

Produces a verdicts file at:
  data/pdf-lab/runs/<run-id>/vision_wins_verdicts.json

When a fact is marked valid_extra, the corresponding resource is added
to a new ground-truth version (vN+1) so subsequent runs see it as
matched.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import Callable, Literal


VerdictType = Literal["valid_extra", "hallucination", "out_of_scope", "skip"]


@dataclass
class VisionWinVerdict:
    resource_type: str
    fact_display: str
    fact_code: str | None
    verdict: VerdictType
    reviewer: str
    reviewed_at: str
    note: str = ""


@dataclass
class TriageSession:
    run_id: str
    run_dir: Path
    extracted_only: dict[str, list[dict]]   # from eval.json
    extracted_resources: list[dict]          # from bundle.json (for resource lookup)
    pdf_sha256: str
    pdf_path: str
    verdicts: list[dict]                     # parallel to flattened extracted_only items
    next_index: int


_TRIAGE_HELP = """\
Per fact:
  v / valid_extra    — incorporate into ground truth (new GT version)
  h / hallucination  — model error, eval penalty stands
  o / out_of_scope   — real but not in our schema; eval ignores
  s / skip           — defer
  ? / help           — show this help
  q / quit-and-save  — save progress so far and exit
"""


def load_triage_session(
    run_id: str,
    *,
    lab_root: Path | None = None,
) -> TriageSession:
    """Load a run's eval.json + bundle.json + (optional) sidecar."""
    from lib.extract.lab.recorder import DEFAULT_LAB_ROOT
    base = lab_root or DEFAULT_LAB_ROOT
    run_dir = base / "runs" / run_id
    if not run_dir.exists():
        raise FileNotFoundError(f"run not found: {run_id}")

    eval_path = run_dir / "eval.json"
    if not eval_path.exists():
        raise FileNotFoundError(
            f"no eval.json in run {run_id}. Run 'lab run' first; eval is "
            "auto-computed when ground truth exists."
        )
    eval_data = json.loads(eval_path.read_text())
    extracted_only = eval_data.get("extracted_only") or {}

    bundle = json.loads((run_dir / "bundle.json").read_text())
    extracted_resources = [e.get("resource", {}) for e in bundle.get("entry", [])]

    manifest = json.loads((run_dir / "manifest.json").read_text())

    sidecar = run_dir / "vision_wins_in_progress.json"
    if sidecar.exists():
        progress = json.loads(sidecar.read_text())
        verdicts = progress["verdicts"]
        next_index = progress["next_index"]
    else:
        verdicts = []
        next_index = 0

    return TriageSession(
        run_id=run_id,
        run_dir=run_dir,
        extracted_only=extracted_only,
        extracted_resources=extracted_resources,
        pdf_sha256=manifest["pdf_sha256"],
        pdf_path=manifest["pdf_path"],
        verdicts=verdicts,
        next_index=next_index,
    )


def _flatten_extracted_only(extracted_only: dict[str, list[dict]]) -> list[tuple[str, dict]]:
    """[(resource_type, fact_dict), ...] flattened in insertion order."""
    flat: list[tuple[str, dict]] = []
    for rt, facts in extracted_only.items():
        for f in facts:
            flat.append((rt, f))
    return flat


def _find_resource_for_fact(
    resources: list[dict],
    rt: str,
    display: str,
    code: str | None,
) -> dict | None:
    """Find the FHIR resource matching this fact's (display, code) tuple."""
    norm_display = (display or "").lower().strip()
    norm_code = (code or "").lower()
    for r in resources:
        if r.get("resourceType") != rt:
            continue
        # Match-key per resource type — same logic as compare.py / eval
        if rt == "Observation":
            text = (r.get("code", {}) or {}).get("text", "") or ""
            codings = (r.get("code", {}) or {}).get("coding") or []
            r_code = next(
                (c.get("code", "") for c in codings if "loinc" in (c.get("system", "") or "").lower()),
                "",
            )
            if (text.lower().strip() == norm_display
                    and (r_code or "").lower() == norm_code):
                return r
        elif rt == "Condition":
            text = (r.get("code", {}) or {}).get("text", "") or ""
            if text.lower().strip() == norm_display:
                return r
        # Fallback: display-only match
        else:
            display_field = (
                r.get("name") or r.get("title")
                or (r.get("code", {}) or {}).get("text", "")
            )
            if isinstance(display_field, list):
                display_field = display_field[0] if display_field else ""
            if isinstance(display_field, dict):
                display_field = display_field.get("family", "")
            if (display_field or "").lower().strip() == norm_display:
                return r
    return None


def save_progress(session: TriageSession) -> None:
    sidecar = session.run_dir / "vision_wins_in_progress.json"
    sidecar.write_text(json.dumps({
        "run_id": session.run_id,
        "verdicts": session.verdicts,
        "next_index": session.next_index,
    }, indent=2))


def discard_progress(session: TriageSession) -> None:
    sidecar = session.run_dir / "vision_wins_in_progress.json"
    if sidecar.exists():
        sidecar.unlink()


def run_triage(
    session: TriageSession,
    *,
    reviewer: str,
    notes: str = "",
    input_fn: Callable[[str], str] = input,
    output_fn: Callable[[str], None] = print,
    auto_save_every: int = 5,
    lab_root: Path | None = None,
) -> tuple[Literal["completed", "saved-partial", "discarded"], int | None]:
    """Run the interactive triage loop.

    Returns (status, gt_version_or_None):
      - "completed", N      — full triage done; valid_extras incorporated
                              into ground-truth version N (or None if
                              no valid_extras were marked)
      - "saved-partial", None
      - "discarded", None
    """
    from lib.extract.lab.ground_truth import (
        save_ground_truth,
        load_latest_ground_truth,
    )

    flat = _flatten_extracted_only(session.extracted_only)
    total = len(flat)
    output_fn(f"Vision-wins triage for run {session.run_id} — {total} facts to review")
    output_fn(f"PDF: {session.pdf_path}")
    if session.next_index > 0:
        output_fn(f"Resuming at fact #{session.next_index + 1} of {total}")
    output_fn(_TRIAGE_HELP)

    verdicts = list(session.verdicts)
    i = session.next_index
    while i < total:
        rt, fact = flat[i]
        display = fact.get("display", "?")
        code = fact.get("code")
        output_fn(f"\n[{i + 1}/{total}] {rt}: {display}{f' ({code})' if code else ''}")
        cmd_raw = input_fn("   valid_extra/hallucination/out_of_scope/skip [v/h/o/s/?/q]: ").strip().lower()

        if cmd_raw in ("v", "valid_extra", "valid", ""):
            verdict: VerdictType = "valid_extra"
        elif cmd_raw in ("h", "hallucination"):
            verdict = "hallucination"
        elif cmd_raw in ("o", "out_of_scope", "oos"):
            verdict = "out_of_scope"
        elif cmd_raw in ("s", "skip"):
            verdict = "skip"
        elif cmd_raw in ("?", "help"):
            output_fn(_TRIAGE_HELP)
            continue
        elif cmd_raw in ("q", "quit-and-save"):
            session.verdicts = verdicts
            session.next_index = i
            save_progress(session)
            output_fn(f"Saved progress at fact #{i + 1}.")
            return "saved-partial", None
        else:
            output_fn(f"Unknown command {cmd_raw!r}. Type ? for help.")
            continue

        verdicts.append(asdict(VisionWinVerdict(
            resource_type=rt,
            fact_display=display,
            fact_code=code,
            verdict=verdict,
            reviewer=reviewer,
            reviewed_at=_now_iso(),
        )))
        i += 1

        if auto_save_every > 0 and i % auto_save_every == 0 and i < total:
            session.verdicts = verdicts
            session.next_index = i
            save_progress(session)
            output_fn(f"  (auto-saved progress at fact #{i})")

    # Persist verdicts
    verdicts_path = session.run_dir / "vision_wins_verdicts.json"
    verdicts_path.write_text(json.dumps({
        "run_id": session.run_id,
        "reviewer": reviewer,
        "verdicts": verdicts,
        "completed_at": _now_iso(),
    }, indent=2))

    # Incorporate valid_extras into a new GT version
    valid_extras = [v for v in verdicts if v["verdict"] == "valid_extra"]
    new_gt_version: int | None = None
    if valid_extras:
        latest_gt = load_latest_ground_truth(session.pdf_sha256, lab_root=lab_root)
        if latest_gt is None:
            output_fn(
                "  Warning: valid_extras marked but no existing ground truth "
                "for this PDF. Skipping GT update; verdicts saved only."
            )
        else:
            # Find the FHIR resources for each valid_extra and append
            new_resources = []
            for v in valid_extras:
                resource = _find_resource_for_fact(
                    session.extracted_resources,
                    v["resource_type"],
                    v["fact_display"],
                    v["fact_code"],
                )
                if resource is not None:
                    new_resources.append(resource)
            if new_resources:
                new_bundle = json.loads(json.dumps(latest_gt.bundle))  # deep copy
                new_bundle["entry"] = list(new_bundle.get("entry", [])) + [
                    {"resource": r} for r in new_resources
                ]
                gtv = save_ground_truth(
                    pdf_sha256=session.pdf_sha256,
                    pdf_path=session.pdf_path,
                    bundle=new_bundle,
                    decisions=latest_gt.decisions,
                    reviewer=reviewer,
                    source_run_id=session.run_id,
                    notes=(
                        f"Vision-wins incorporation from run {session.run_id}: "
                        f"{len(new_resources)} valid_extra fact(s) added. "
                        + (notes or "")
                    ).strip(),
                    lab_root=lab_root,
                )
                new_gt_version = gtv.version
                output_fn(
                    f"  Incorporated {len(new_resources)} valid_extra(s) into "
                    f"ground-truth v{gtv.version}."
                )

    discard_progress(session)
    output_fn(
        f"\nTriage complete. {sum(1 for v in verdicts if v['verdict'] == 'valid_extra')} valid_extra, "
        f"{sum(1 for v in verdicts if v['verdict'] == 'hallucination')} hallucination, "
        f"{sum(1 for v in verdicts if v['verdict'] == 'out_of_scope')} out_of_scope, "
        f"{sum(1 for v in verdicts if v['verdict'] == 'skip')} skip."
    )
    return "completed", new_gt_version


def _now_iso() -> str:
    import datetime
    return datetime.datetime.utcnow().isoformat() + "Z"
