"""Multi-backend extraction comparison harness.

Runs the same PDF through multiple ``VisionBackend`` configurations and
returns a structured table of outcomes — latency, success, fact counts,
confidence, and the validated ``ExtractionResult`` for each run. Used by:

  - ``app/pages/02c_PDF_Compare.py`` — the Streamlit comparison page
  - the notebook (``notebooks/03_layer2b_vision_extraction.ipynb``) for
    inline A/B during development
  - ad-hoc CLI sessions when you want a markdown table to paste into a
    decision doc

The comparison is **structural** — same prompt, same schema, same
calibration pass — so differences in the output tables reflect actual
model behaviour, not test harness drift.

Caching: each ``(pdf, backend, model)`` pair has its own cache key, so a
second run is free for every (pdf × backend × model) triple that already
ran. Pass ``skip_cache=True`` to force a live re-run for every cell.
"""

from __future__ import annotations

import time
import traceback
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from ehi_atlas.extract.pdf import (
    DEFAULT_BACKEND,
    DEFAULT_GOOGLE_MODEL,
    DEFAULT_MODEL,
    extract_lab_pdf,
    get_backend,
)
from ehi_atlas.extract.schemas import ExtractionResult

# ---------------------------------------------------------------------------
# Default backend matrix
# ---------------------------------------------------------------------------

# (backend_name, model) tuples. Keep this list short — every entry triples
# the cost of a "compare all" sweep. Edit at the call site for one-off
# experiments; this is the demo-day default.
DEFAULT_MATRIX: list[tuple[str, str]] = [
    ("anthropic", DEFAULT_MODEL),
    ("gemma-google-ai-studio", DEFAULT_GOOGLE_MODEL),
    ("gemma-google-ai-studio", "gemma-4-26b-a4b-it"),
    ("gemma-google-ai-studio", "gemma-3-27b-it"),
]


# ---------------------------------------------------------------------------
# Result shape
# ---------------------------------------------------------------------------


@dataclass
class ComparisonRun:
    """One row of the comparison table — a single (pdf × backend × model) cell."""

    pdf_label: str
    pdf_path: Path
    backend_name: str
    model: str
    success: bool
    latency_s: float
    document_type: str | None = None
    fact_count: int = 0
    extraction_confidence: float | None = None
    error_type: str | None = None
    error_message: str | None = None
    result: ExtractionResult | None = field(default=None, repr=False)

    @property
    def cache_model_id(self) -> str:
        """The ``"<backend>/<model>"`` cache identifier for this run."""
        return f"{self.backend_name}/{self.model}"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


ProgressCallback = Callable[[int, int, ComparisonRun], None]


def compare_backends(
    pdfs: list[tuple[str, Path]],
    backends: list[tuple[str, str]] | None = None,
    *,
    skip_cache: bool = False,
    on_progress: ProgressCallback | None = None,
) -> list[ComparisonRun]:
    """Run each PDF through each backend and return one ComparisonRun per cell.

    Args:
        pdfs: List of ``(label, pdf_path)`` tuples.
        backends: List of ``(backend_name, model)`` tuples. Defaults to
            :data:`DEFAULT_MATRIX`.
        skip_cache: When ``True``, every cell makes a fresh API call even
            if the cache contains a prior result. Useful for re-baselining
            after prompt changes.
        on_progress: Optional callback ``(index, total, run)`` invoked
            after each cell completes. Streamlit pages use this to update
            a progress bar and stream rows into the UI.

    Returns:
        One :class:`ComparisonRun` per (pdf × backend) cell, in dispatch
        order. Failed runs are captured as rows with ``success=False`` —
        the harness never raises; it records the error and moves on.
    """
    backends = backends or list(DEFAULT_MATRIX)
    cells = [(label, path, name, model) for label, path in pdfs for name, model in backends]
    total = len(cells)
    runs: list[ComparisonRun] = []

    for idx, (label, path, backend_name, model) in enumerate(cells, start=1):
        run = _run_one_cell(label, path, backend_name, model, skip_cache=skip_cache)
        runs.append(run)
        if on_progress is not None:
            on_progress(idx, total, run)

    return runs


def _run_one_cell(
    label: str,
    path: Path,
    backend_name: str,
    model: str,
    *,
    skip_cache: bool,
) -> ComparisonRun:
    """Execute a single (pdf × backend × model) cell with full error capture."""
    t0 = time.time()
    try:
        backend = get_backend(name=backend_name, model=model)
        result = extract_lab_pdf(path, backend=backend, skip_cache=skip_cache)
        elapsed = time.time() - t0

        doc = result.document
        if doc.document_type == "lab-report":
            fact_count = len(doc.results)
        elif doc.document_type == "clinical-note":
            fact_count = len(doc.extracted_conditions) + len(doc.extracted_symptoms)
        else:
            fact_count = 0

        return ComparisonRun(
            pdf_label=label,
            pdf_path=path,
            backend_name=backend_name,
            model=model,
            success=True,
            latency_s=elapsed,
            document_type=doc.document_type,
            fact_count=fact_count,
            extraction_confidence=result.extraction_confidence,
            result=result,
        )
    except Exception as e:
        elapsed = time.time() - t0
        return ComparisonRun(
            pdf_label=label,
            pdf_path=path,
            backend_name=backend_name,
            model=model,
            success=False,
            latency_s=elapsed,
            error_type=type(e).__name__,
            error_message=str(e)[:500],
        )


# ---------------------------------------------------------------------------
# Output formatters
# ---------------------------------------------------------------------------


def to_dataframe(runs: list[ComparisonRun]) -> "Any":
    """Return runs as a pandas DataFrame. Lazy import to keep this module
    importable without pandas (the Streamlit page already has it)."""
    import pandas as pd

    return pd.DataFrame(
        [
            {
                "pdf": r.pdf_label,
                "backend": r.backend_name,
                "model": r.model,
                "ok": "✓" if r.success else "✗",
                "latency_s": round(r.latency_s, 2),
                "doc_type": r.document_type or "—",
                "facts": r.fact_count if r.success else "—",
                "confidence": (
                    round(r.extraction_confidence, 2)
                    if r.extraction_confidence is not None
                    else "—"
                ),
                "error": r.error_type or "",
            }
            for r in runs
        ]
    )


def to_markdown_table(runs: list[ComparisonRun]) -> str:
    """Render runs as a GitHub-flavoured markdown table.

    Useful for pasting into PR descriptions or decision docs. Wider
    than the DataFrame view (includes truncated error messages).
    """
    if not runs:
        return "_(no runs)_\n"

    headers = [
        "pdf",
        "backend / model",
        "ok",
        "latency",
        "doc_type",
        "facts",
        "conf",
        "error",
    ]
    lines = ["| " + " | ".join(headers) + " |"]
    lines.append("|" + "|".join(["---"] * len(headers)) + "|")
    for r in runs:
        lines.append(
            "| "
            + " | ".join(
                [
                    r.pdf_label[:40],
                    f"{r.backend_name} / {r.model}",
                    "✓" if r.success else "✗",
                    f"{r.latency_s:.1f}s",
                    r.document_type or "—",
                    str(r.fact_count) if r.success else "—",
                    (
                        f"{r.extraction_confidence:.2f}"
                        if r.extraction_confidence is not None
                        else "—"
                    ),
                    (r.error_type or "") + (" — " + r.error_message[:60] if r.error_message else ""),
                ]
            )
            + " |"
        )
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Cross-run analysis helpers
# ---------------------------------------------------------------------------


def fact_count_by_backend(runs: list[ComparisonRun]) -> "Any":
    """Pivot table: rows = PDFs, cols = backend/model, cells = fact count."""
    import pandas as pd

    data: dict[str, dict[str, Any]] = {}
    for r in runs:
        col = f"{r.backend_name}/{r.model}"
        data.setdefault(r.pdf_label, {})[col] = (
            r.fact_count if r.success else f"✗ {r.error_type}"
        )
    df = pd.DataFrame.from_dict(data, orient="index").fillna("—")
    df.index.name = "pdf"
    return df


def latency_by_backend(runs: list[ComparisonRun]) -> "Any":
    """Pivot: rows = PDFs, cols = backend/model, cells = latency seconds."""
    import pandas as pd

    data: dict[str, dict[str, Any]] = {}
    for r in runs:
        col = f"{r.backend_name}/{r.model}"
        data.setdefault(r.pdf_label, {})[col] = round(r.latency_s, 2)
    df = pd.DataFrame.from_dict(data, orient="index").fillna(0.0)
    df.index.name = "pdf"
    return df
