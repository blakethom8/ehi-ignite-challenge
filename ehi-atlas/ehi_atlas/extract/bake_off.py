"""Pipeline bake-off harness — empirical comparison across architectures.

Runs every (pipeline × PDF) cell, scoring outputs against ground truth
where available. The result is a comparison matrix that drives
architecture decisions per ``docs/architecture/PDF-PROCESSOR.md``
Decision 6.

How a bake-off run works
------------------------
1. Caller provides a list of pipelines (instances) and a list of test
   pairs ``(label, pdf_path, ground_truth_path | None)``.
2. For each (pipeline × pair) cell:
   - Pipeline runs ``extract(pdf_path)`` → returns a FHIR Bundle dict
   - If ``ground_truth_path`` is given, eval scores the Bundle against
     it and the EvalReport is captured per-cell.
   - Latency, success/failure, and any error are recorded.
3. Caller renders the result via :func:`format_markdown` (for a docs-
   pasteable table) or feeds the raw cells into the Streamlit
   Pipeline Bakeoff page for interactive inspection.

The bake-off does NOT decide anything itself. It produces structured
data; humans (or other agents) read the data and update the decision
record. That separation matters — the bake-off has to be trustworthy
even when the result is uncomfortable.
"""

from __future__ import annotations

import time
import traceback
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from ehi_atlas.extract.eval import (
    EvalReport,
    evaluate_bundle,
)
from ehi_atlas.extract.pipelines.base import ExtractionPipeline


# ---------------------------------------------------------------------------
# Result shape
# ---------------------------------------------------------------------------


@dataclass
class BakeoffCell:
    """One (pipeline × pdf) cell of the bake-off matrix.

    Failed cells (``success=False``) carry the error class + message
    instead of a Bundle/EvalReport.
    """

    pipeline_name: str
    pdf_label: str
    pdf_path: Path
    ground_truth_path: Path | None
    success: bool
    latency_s: float
    bundle: dict | None = None
    eval_report: EvalReport | None = None
    error_type: str | None = None
    error_message: str | None = None

    @property
    def has_ground_truth(self) -> bool:
        return self.ground_truth_path is not None

    @property
    def fact_count(self) -> int:
        if not self.bundle:
            return 0
        return len(self.bundle.get("entry", []))

    @property
    def overall_f1(self) -> float | None:
        """Weighted F1 across all fact types in the eval report.

        Weights each type by the ground-truth count, so types with more
        facts contribute more. Returns ``None`` if no eval was run.
        """
        if self.eval_report is None:
            return None
        total_gt = 0
        weighted_f1 = 0.0
        for type_report in self.eval_report.by_type.values():
            if type_report.gt_count == 0:
                continue
            total_gt += type_report.gt_count
            weighted_f1 += type_report.f1 * type_report.gt_count
        return weighted_f1 / total_gt if total_gt else 0.0


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


ProgressCallback = Callable[[int, int, BakeoffCell], None]


def bake_off(
    pipelines: list[ExtractionPipeline],
    pairs: list[tuple[str, Path, Path | None]],
    *,
    skip_cache: bool = False,
    findable_only: bool = False,
    on_progress: ProgressCallback | None = None,
) -> list[BakeoffCell]:
    """Run every (pipeline × pair) cell. Returns one BakeoffCell per cell.

    Args:
        pipelines: List of instantiated pipelines. Each must implement
            the :class:`ExtractionPipeline` Protocol.
        pairs: List of ``(label, pdf_path, ground_truth_path | None)``.
            ``ground_truth_path`` points at a ClientFullEHR JSON file,
            or is ``None`` if no ground truth is available for that PDF.
        skip_cache: Forwarded to each pipeline if it accepts the kwarg.
            Pipelines that don't accept it raise TypeError, which we
            catch and treat as cell failure.
        findable_only: When True, ground-truth facts are filtered to
            those whose text/codes actually appear in the PDF before
            scoring. Resolves the "GT covers full chart history but
            PDF only shows a snapshot" ambiguity. See
            :func:`filter_gt_to_findable_in_pdf`.
        on_progress: Optional callback invoked after each cell completes.
            Streamlit pages use this to stream live updates.

    Returns:
        One :class:`BakeoffCell` per (pipeline × pair). Failed cells have
        ``success=False`` and carry error info; successful cells have
        ``bundle`` populated and (if ground truth available) ``eval_report``.

    The harness never raises. Per-cell errors are captured in the
    BakeoffCell. This guarantees a partial bake-off is still useful even
    if some pipelines fail.
    """
    cells_input = [
        (pipeline, label, pdf, gt)
        for pipeline in pipelines
        for label, pdf, gt in pairs
    ]
    total = len(cells_input)
    out: list[BakeoffCell] = []

    for idx, (pipeline, label, pdf_path, gt_path) in enumerate(cells_input, start=1):
        cell = _run_one_cell(
            pipeline,
            label,
            pdf_path,
            gt_path,
            skip_cache=skip_cache,
            findable_only=findable_only,
        )
        out.append(cell)
        if on_progress is not None:
            on_progress(idx, total, cell)

    return out


def _run_one_cell(
    pipeline: ExtractionPipeline,
    pdf_label: str,
    pdf_path: Path,
    ground_truth_path: Path | None,
    *,
    skip_cache: bool,
    findable_only: bool = False,
) -> BakeoffCell:
    """Execute a single (pipeline × pair) cell with full error capture."""
    pipeline_name = pipeline.metadata.name
    t0 = time.time()

    # Run the pipeline
    try:
        # Pass skip_cache through if the pipeline's extract accepts it
        try:
            bundle = pipeline.extract(pdf_path, skip_cache=skip_cache)
        except TypeError:
            # Pipeline doesn't accept skip_cache — call without it
            bundle = pipeline.extract(pdf_path)
        elapsed = time.time() - t0
    except Exception as e:
        elapsed = time.time() - t0
        return BakeoffCell(
            pipeline_name=pipeline_name,
            pdf_label=pdf_label,
            pdf_path=pdf_path,
            ground_truth_path=ground_truth_path,
            success=False,
            latency_s=elapsed,
            error_type=type(e).__name__,
            error_message=str(e)[:500],
        )

    # If ground truth available, run the eval
    eval_report = None
    if ground_truth_path is not None:
        try:
            import json

            gt = json.loads(ground_truth_path.read_text())
            eval_report = evaluate_bundle(
                ground_truth=gt,
                bundle=bundle,
                extraction_label=pipeline_name,
                ground_truth_label=ground_truth_path.name,
                pdf_path=pdf_path,
                findable_only=findable_only,
            )
        except Exception as e:
            # Eval failure is logged but doesn't fail the whole cell — we
            # still got a Bundle, just couldn't score it.
            return BakeoffCell(
                pipeline_name=pipeline_name,
                pdf_label=pdf_label,
                pdf_path=pdf_path,
                ground_truth_path=ground_truth_path,
                success=True,
                latency_s=elapsed,
                bundle=bundle,
                eval_report=None,
                error_type=f"EvalError({type(e).__name__})",
                error_message=str(e)[:500],
            )

    return BakeoffCell(
        pipeline_name=pipeline_name,
        pdf_label=pdf_label,
        pdf_path=pdf_path,
        ground_truth_path=ground_truth_path,
        success=True,
        latency_s=elapsed,
        bundle=bundle,
        eval_report=eval_report,
    )


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------


def format_markdown(cells: list[BakeoffCell]) -> str:
    """Render bake-off cells as a markdown comparison table.

    Two views: a compact summary matrix (pipeline × pdf with F1 cells)
    and a per-cell detail section.
    """
    if not cells:
        return "_(no cells)_\n"

    pipelines = sorted({c.pipeline_name for c in cells})
    pdfs = sorted({c.pdf_label for c in cells})

    lines: list[str] = []
    lines.append("# Bake-off comparison")
    lines.append("")
    lines.append(f"_{len(cells)} cells: {len(pipelines)} pipelines × {len(pdfs)} PDFs_")
    lines.append("")

    # --- Summary matrix: F1 per cell ---
    lines.append("## F1 matrix (weighted across fact types)")
    lines.append("")
    header = ["pipeline"] + pdfs
    lines.append("| " + " | ".join(header) + " |")
    lines.append("|" + "|".join(["---"] * len(header)) + "|")
    for pipeline in pipelines:
        row = [pipeline]
        for pdf in pdfs:
            cell = next(
                (c for c in cells if c.pipeline_name == pipeline and c.pdf_label == pdf),
                None,
            )
            if cell is None:
                row.append("—")
            elif not cell.success:
                row.append(f"✗ {cell.error_type}")
            elif cell.eval_report is None:
                row.append(f"({cell.fact_count} facts, no GT)")
            else:
                f1 = cell.overall_f1
                row.append(f"**{f1:.2f}** ({cell.latency_s:.0f}s)" if f1 is not None else "—")
        lines.append("| " + " | ".join(row) + " |")
    lines.append("")

    # --- Per-cell detail (only for cells with eval reports) ---
    lines.append("## Per-cell detail (cells with ground truth)")
    lines.append("")
    for cell in cells:
        if cell.eval_report is None:
            continue
        lines.append(f"### {cell.pipeline_name} × {cell.pdf_label}")
        lines.append(f"_{cell.latency_s:.1f}s · {cell.fact_count} bundle entries · weighted F1 = {cell.overall_f1:.2f}_")
        lines.append("")
        lines.append("| type | gt | extracted | TP | FP | FN | precision | recall | F1 |")
        lines.append("|---|---|---|---|---|---|---|---|---|")
        for ft, r in cell.eval_report.by_type.items():
            lines.append(
                f"| {ft} | {r.gt_count} | {r.extracted_count} | {r.tp} | {r.fp} | {r.fn} | "
                f"{r.precision:.2f} | {r.recall:.2f} | {r.f1:.2f} |"
            )
        lines.append("")

    # --- Cells with no ground truth ---
    no_gt_cells = [c for c in cells if c.success and c.eval_report is None]
    if no_gt_cells:
        lines.append("## Cells without ground truth (eyeball review)")
        lines.append("")
        for cell in no_gt_cells:
            lines.append(
                f"- `{cell.pipeline_name} × {cell.pdf_label}`: "
                f"{cell.fact_count} bundle entries in {cell.latency_s:.1f}s"
            )
        lines.append("")

    # --- Failures ---
    failed = [c for c in cells if not c.success]
    if failed:
        lines.append("## Failures")
        lines.append("")
        for cell in failed:
            lines.append(
                f"- `{cell.pipeline_name} × {cell.pdf_label}`: "
                f"**{cell.error_type}** — {cell.error_message}"
            )
        lines.append("")

    return "\n".join(lines) + "\n"
