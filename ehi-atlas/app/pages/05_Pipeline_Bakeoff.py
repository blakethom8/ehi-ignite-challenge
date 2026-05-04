"""EHI Atlas Console — Pipeline Bakeoff page.

Empirical comparison across PDF→FHIR extraction architectures. Pick
pipelines, pick PDFs (with optional ground-truth pairs), run the matrix,
see F1 / latency / fact-counts side-by-side. Per
``docs/architecture/PDF-PROCESSOR.md`` Decision 6, this is where
architecture decisions are *measured*, not argued.

Run from repo root:
    uv run streamlit run ehi-atlas/app/streamlit_app.py --server.port 8503
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

_APP_DIR = Path(__file__).parent.parent.resolve()
if str(_APP_DIR) not in sys.path:
    sys.path.insert(0, str(_APP_DIR))

import pandas as pd
import streamlit as st

from components.badges import engine_badge_row
from components.header import render_header
from ehi_atlas.extract.bake_off import (
    BakeoffCell,
    bake_off,
    format_markdown,
)
from ehi_atlas.extract.pipelines import get, list_pipelines
from ehi_atlas.extract.uploads import list_uploads

# ---------------------------------------------------------------------------
# Page config + header
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="EHI Atlas — Pipeline Bakeoff",
    page_icon="🥧",
    layout="wide",
    initial_sidebar_state="expanded",
)

render_header("Pipeline Bakeoff — Architecture A/B Harness")

st.markdown(
    """
**Empirically compare PDF→FHIR pipeline architectures.** Each pipeline takes
a PDF and emits a FHIR Bundle. The bake-off scores every Bundle against
ClientFullEHR ground truth (where available) and surfaces F1, latency, and
fact-count side-by-side. Per [`docs/architecture/PDF-PROCESSOR.md`](../../../docs/architecture/PDF-PROCESSOR.md)
this is where architecture decisions are *measured*, not argued.
"""
)

# ---------------------------------------------------------------------------
# Sidebar — engine summary + nav
# ---------------------------------------------------------------------------

with st.sidebar:
    st.markdown("### Registered pipelines")
    for meta in list_pipelines():
        st.markdown(f"**{meta.name}**")
        st.caption(meta.description)
        st.write("")
    st.divider()
    st.page_link("streamlit_app.py", label="← Overview", icon="🏠")
    st.page_link("pages/03_PDF_Lab.py", label="🧪 PDF Lab (single PDF)", icon="🧪")
    st.page_link("pages/04_PDF_Compare.py", label="🆚 PDF Compare (backends)", icon="🆚")

# ---------------------------------------------------------------------------
# 1 · Pick pipelines
# ---------------------------------------------------------------------------

st.subheader("1 · Pick pipelines")

available_pipelines = list_pipelines()
if not available_pipelines:
    st.warning("No pipelines registered. Implement one in `ehi_atlas/extract/pipelines/`.")
    st.stop()

selected_pipeline_names = st.multiselect(
    "Pipelines to run",
    options=[m.name for m in available_pipelines],
    default=[m.name for m in available_pipelines],
    help="Each selected pipeline runs against every selected PDF.",
)

# ---------------------------------------------------------------------------
# 2 · Pick PDFs + optional ground-truth pairs
# ---------------------------------------------------------------------------

st.subheader("2 · Pick PDFs")

_FIXTURE_PDF = (
    Path(__file__).resolve().parents[2]
    / "corpus"
    / "_sources"
    / "synthesized-lab-pdf"
    / "raw"
    / "lab-report-2025-09-12-quest.pdf"
)

# Hard-coded "known pairs" — PDFs with ClientFullEHR ground truth files.
# Add more as we accumulate ground truth.
_ATLAS_ROOT = Path(__file__).resolve().parents[2]
_KNOWN_PAIRS: list[tuple[str, Path, Path | None]] = [
    (
        "rhett759 (Quest CMP fixture)",
        _FIXTURE_PDF,
        None,  # no ground truth — synthesized fixture
    ),
]

# Look for the Cedars pair in the user's corpus
_CEDARS_PDF = (
    _ATLAS_ROOT
    / "corpus"
    / "bronze"
    / "clinical-portfolios"
    / "blake_records"
    / "HealthSummary_May_03_2026"
    / "1 of 1 - My Health Summary.PDF"
)
_CEDARS_GT = (
    _ATLAS_ROOT
    / "corpus"
    / "bronze"
    / "clinical-portfolios"
    / "blake_records"
    / "cedars-healthskillz-download"
    / "health-records.json"
)
if _CEDARS_PDF.exists() and _CEDARS_GT.exists():
    _KNOWN_PAIRS.append(
        ("blake-cedars-health-summary (with FHIR GT)", _CEDARS_PDF, _CEDARS_GT)
    )

# Plus uploads (no ground truth by default)
for record in reversed(list_uploads()):
    _KNOWN_PAIRS.append((record.label, record.pdf_path, None))

selected_pdf_labels = st.multiselect(
    "PDFs to run",
    options=[p[0] for p in _KNOWN_PAIRS],
    default=[
        p[0]
        for p in _KNOWN_PAIRS
        if "with FHIR GT" in p[0] or "rhett759" in p[0]
    ][:1],  # default to one ground-truth-bearing PDF if available
    help=(
        "PDFs marked **(with FHIR GT)** have ClientFullEHR ground truth — "
        "they get F1 scores. Others run as eyeball-review only."
    ),
)

selected_pairs = [p for p in _KNOWN_PAIRS if p[0] in selected_pdf_labels]

# ---------------------------------------------------------------------------
# 3 · Run controls
# ---------------------------------------------------------------------------

st.subheader("3 · Run")

run_col, opts_col = st.columns([1, 3])
with opts_col:
    skip_cache = st.toggle(
        "Force live runs (skip cache)",
        value=False,
        help=(
            "OFF: cells with prior cached output return instantly. "
            "ON: every cell makes fresh API calls — useful after a "
            "prompt or schema change."
        ),
    )
total_cells = len(selected_pipeline_names) * len(selected_pairs)
opts_col.caption(
    f"Will run **{total_cells} cells** "
    f"({len(selected_pipeline_names)} pipelines × {len(selected_pairs)} PDFs)."
)
with run_col:
    run_clicked = st.button(
        "▶ Run bakeoff",
        type="primary",
        use_container_width=True,
        disabled=total_cells == 0,
    )

# Stable session-state key so cells survive interactions (sort, expand, etc.)
_CELLS_KEY = "bakeoff_cells"

if run_clicked:
    progress = st.progress(0.0, text="Starting…")
    status_lines: list[str] = []
    status = st.empty()

    # Instantiate pipelines — patient_id is a placeholder; real harmonizer
    # rewrites this after identity resolution.
    pipelines = []
    for name in selected_pipeline_names:
        cls = get(name)
        # Each pipeline's __init__ varies — try patient_id, fall back to no-arg
        try:
            inst = cls(patient_id="blake-thomson")
        except TypeError:
            inst = cls()
        pipelines.append(inst)

    def _on_progress(idx: int, total: int, cell: BakeoffCell) -> None:
        progress.progress(
            idx / total,
            text=(
                f"[{idx}/{total}] {cell.pipeline_name} × {cell.pdf_label}"
            ),
        )
        ok = "✓" if cell.success else "✗"
        f1 = (
            f" F1={cell.overall_f1:.2f}"
            if cell.overall_f1 is not None
            else ""
        )
        line = (
            f"{ok} `{cell.pipeline_name:25}` × `{cell.pdf_label[:35]:35}` · "
            f"{cell.latency_s:5.1f}s · "
            f"{cell.fact_count if cell.success else cell.error_type or '—'}"
            f"{f1}"
        )
        status_lines.append(line)
        status.markdown("\n".join(status_lines[-15:]))

    cells = bake_off(
        pipelines,
        selected_pairs,
        skip_cache=skip_cache,
        on_progress=_on_progress,
    )
    progress.progress(1.0, text=f"Done · {len(cells)} cells.")
    st.session_state[_CELLS_KEY] = cells

# ---------------------------------------------------------------------------
# 4 · Results
# ---------------------------------------------------------------------------

cells: list[BakeoffCell] = st.session_state.get(_CELLS_KEY) or []

st.divider()
st.subheader("4 · Results")

if not cells:
    st.info(
        "Pick pipelines + PDFs above and click **Run bakeoff**. "
        "Cells stream live during the run; the F1 matrix and per-cell "
        "detail populate when the run completes."
    )
else:
    matrix_tab, detail_tab, md_tab = st.tabs(
        ["📊 F1 matrix", "🔬 Per-cell detail", "📝 Markdown export"]
    )

    with matrix_tab:
        st.markdown(
            "Weighted F1 across fact types (weight = ground-truth count per type). "
            "Cells without ground truth show fact-count instead."
        )
        pipelines_seen = sorted({c.pipeline_name for c in cells})
        pdfs_seen = sorted({c.pdf_label for c in cells})
        rows: list[dict] = []
        for pipe in pipelines_seen:
            row = {"Pipeline": pipe}
            for pdf in pdfs_seen:
                cell = next(
                    (c for c in cells if c.pipeline_name == pipe and c.pdf_label == pdf),
                    None,
                )
                if cell is None:
                    row[pdf] = "—"
                elif not cell.success:
                    row[pdf] = f"✗ {cell.error_type}"
                elif cell.eval_report is None:
                    row[pdf] = f"({cell.fact_count} facts, no GT)"
                else:
                    f1 = cell.overall_f1
                    row[pdf] = f"{f1:.2f}" if f1 is not None else "—"
            rows.append(row)
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

        # Latency matrix as a sub-table
        st.markdown("**Latency (seconds)**")
        lat_rows = []
        for pipe in pipelines_seen:
            row = {"Pipeline": pipe}
            for pdf in pdfs_seen:
                cell = next(
                    (c for c in cells if c.pipeline_name == pipe and c.pdf_label == pdf),
                    None,
                )
                row[pdf] = round(cell.latency_s, 1) if cell else None
            lat_rows.append(row)
        st.dataframe(pd.DataFrame(lat_rows), use_container_width=True, hide_index=True)

    with detail_tab:
        st.markdown("Click a cell below to see its EvalReport and Bundle preview.")
        for cell in cells:
            ok_icon = "✓" if cell.success else "✗"
            title = (
                f"{ok_icon} **{cell.pipeline_name}** × **{cell.pdf_label}** · "
                f"{cell.latency_s:.1f}s"
            )
            if cell.success:
                title += f" · {cell.fact_count} entries"
                if cell.overall_f1 is not None:
                    title += f" · F1={cell.overall_f1:.2f}"
            else:
                title += f" · {cell.error_type}"
            with st.expander(title, expanded=False):
                if not cell.success:
                    st.error(f"**{cell.error_type}** — {cell.error_message}")
                    continue
                if cell.eval_report:
                    rep = cell.eval_report
                    st.markdown("**Eval (per fact type):**")
                    eval_rows = [
                        {
                            "type": ft,
                            "gt": r.gt_count,
                            "extracted": r.extracted_count,
                            "TP": r.tp,
                            "FP": r.fp,
                            "FN": r.fn,
                            "precision": round(r.precision, 2),
                            "recall": round(r.recall, 2),
                            "F1": round(r.f1, 2),
                            "schema_gap": "✓" if r.is_schema_gap else "",
                        }
                        for ft, r in rep.by_type.items()
                    ]
                    st.dataframe(
                        pd.DataFrame(eval_rows),
                        use_container_width=True,
                        hide_index=True,
                    )
                if cell.bundle:
                    with st.expander("Bundle JSON (resource-type breakdown)", expanded=False):
                        from collections import Counter

                        rt_counts = Counter(
                            e["resource"].get("resourceType", "?")
                            for e in cell.bundle.get("entry", [])
                        )
                        st.json(dict(rt_counts))
                        st.caption(f"Total entries: {sum(rt_counts.values())}")

    with md_tab:
        st.markdown(
            "Copy-pasteable comparison — useful for PR descriptions, decision-log "
            "updates, or pasting back to me for analysis."
        )
        st.code(format_markdown(cells), language="markdown")

# ---------------------------------------------------------------------------
# Footer
# ---------------------------------------------------------------------------

st.divider()
st.caption(
    "Architecture decision record: "
    "[`docs/architecture/PDF-PROCESSOR.md`](../../../docs/architecture/PDF-PROCESSOR.md) · "
    "Pipeline contributor guide: "
    "`ehi_atlas/extract/pipelines/README.md` · "
    "Bake-off module: `ehi_atlas/extract/bake_off.py`"
)
