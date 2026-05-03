"""EHI Atlas Console — PDF Compare page.

A/B harness for vision-extraction backends. Pick a set of PDFs and a set of
``(backend, model)`` configurations; the page runs every (pdf × backend)
cell, shows a live progress stream, and renders three views: a flat run
table, a fact-count pivot, and a latency pivot. Each row carries a
"detail" expander with the raw ``ExtractionResult`` for further inspection.

Run from repo root:
    uv run streamlit run ehi-atlas/app/streamlit_app.py --server.port 8503
Or from inside ehi-atlas/:
    uv run streamlit run app/streamlit_app.py --server.port 8503

Then click into "PDF Compare" in the sidebar.
"""

from __future__ import annotations

import sys
from pathlib import Path

_APP_DIR = Path(__file__).parent.parent.resolve()
if str(_APP_DIR) not in sys.path:
    sys.path.insert(0, str(_APP_DIR))

import pandas as pd
import streamlit as st

from components.badges import engine_badge_row
from components.header import render_header
from ehi_atlas.extract.compare import (
    DEFAULT_MATRIX,
    ComparisonRun,
    compare_backends,
    fact_count_by_backend,
    latency_by_backend,
    to_markdown_table,
)
from ehi_atlas.extract.uploads import list_uploads

# ---------------------------------------------------------------------------
# Page config + header
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="EHI Atlas — PDF Compare",
    page_icon="🆚",
    layout="wide",
    initial_sidebar_state="expanded",
)

render_header("PDF Compare — Backend A/B Harness")

st.markdown(
    """
**Run the same PDFs through multiple vision-extraction backends and compare
the outputs.** Identical prompts, identical schemas, identical bbox
calibration — differences in this table reflect actual model behaviour, not
test-harness drift. Cached cells return instantly; uncached cells make a
live API call (visible per-cell in the progress stream).
"""
)

# ---------------------------------------------------------------------------
# Sidebar — engine key
# ---------------------------------------------------------------------------

with st.sidebar:
    st.markdown("### Engine")
    engine_badge_row(
        [
            ("script", "rasterize + bbox calibration"),
            ("llm", "swappable backend per cell"),
        ]
    )
    st.divider()
    st.page_link("streamlit_app.py", label="← Overview", icon="🏠")
    st.page_link("pages/02b_PDF_Lab.py", label="← PDF Lab (single-PDF view)", icon="🧪")

# ---------------------------------------------------------------------------
# 1 · Pick PDFs
# ---------------------------------------------------------------------------

_FIXTURE_PDF = (
    Path(__file__).resolve().parents[2]
    / "corpus"
    / "_sources"
    / "synthesized-lab-pdf"
    / "raw"
    / "lab-report-2025-09-12-quest.pdf"
)


def _available_pdfs() -> list[tuple[str, Path]]:
    out: list[tuple[str, Path]] = []
    if _FIXTURE_PDF.exists():
        out.append(("rhett759 (Quest CMP fixture)", _FIXTURE_PDF))
    for record in reversed(list_uploads()):
        out.append((record.label, record.pdf_path))
    return out


st.subheader("1 · Pick PDFs")

available = _available_pdfs()
if not available:
    st.warning(
        "No PDFs available. Upload some via the **PDF Lab** page first, or "
        "place a file at the documented fixture path."
    )
    st.stop()

selected_pdf_labels = st.multiselect(
    "PDFs to run",
    options=[label for label, _ in available],
    default=[label for label, _ in available],  # all selected by default
    help="Each selected PDF is run through every selected backend cell.",
)
selected_pdfs = [(label, path) for label, path in available if label in selected_pdf_labels]

# ---------------------------------------------------------------------------
# 2 · Pick backends
# ---------------------------------------------------------------------------

st.subheader("2 · Pick backends")

# Available backend-model pairs. Edit at the call site to add new ones.
_AVAILABLE_BACKENDS: list[tuple[str, str]] = [
    ("anthropic", "claude-opus-4-7"),
    ("gemma-google-ai-studio", "gemma-4-31b-it"),
    ("gemma-google-ai-studio", "gemma-4-26b-a4b-it"),
    ("gemma-google-ai-studio", "gemma-3-27b-it"),
    ("gemma-google-ai-studio", "gemma-3-12b-it"),
]


def _backend_label(name: str, model: str) -> str:
    return f"{name} / {model}"


backend_labels = [_backend_label(n, m) for n, m in _AVAILABLE_BACKENDS]
default_backend_labels = [_backend_label(n, m) for n, m in DEFAULT_MATRIX]
selected_backend_labels = st.multiselect(
    "Backends to compare",
    options=backend_labels,
    default=default_backend_labels,
    help=(
        "Each PDF is run through every selected backend. "
        "Watch your API quota — each cell can be a fresh call."
    ),
)
selected_backends = [
    (n, m)
    for n, m in _AVAILABLE_BACKENDS
    if _backend_label(n, m) in selected_backend_labels
]

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
            "When OFF, cells with a prior cached result return instantly. "
            "When ON, every cell makes a fresh API call — useful after a "
            "prompt or schema change."
        ),
    )
total_cells = len(selected_pdfs) * len(selected_backends)
opts_col.caption(
    f"Will run **{total_cells} cells** "
    f"({len(selected_pdfs)} PDFs × {len(selected_backends)} backends)."
)
with run_col:
    run_clicked = st.button(
        "▶ Run comparison",
        type="primary",
        use_container_width=True,
        disabled=total_cells == 0,
    )

# Stable session-state key so cells survive interactions (sort, expand, etc.)
_RUNS_KEY = "compare_runs"
_LAST_CONFIG_KEY = "compare_last_config"

if run_clicked:
    progress = st.progress(0.0, text="Starting…")
    status_lines: list[str] = []
    status = st.empty()
    runs: list[ComparisonRun] = []

    def _on_progress(idx: int, total: int, run: ComparisonRun) -> None:
        progress.progress(
            idx / total,
            text=f"[{idx}/{total}] {run.pdf_label[:30]} via {run.backend_name}/{run.model}",
        )
        ok = "✓" if run.success else "✗"
        line = (
            f"{ok} `{run.pdf_label[:35]:35}` · "
            f"`{run.backend_name}/{run.model:25}` · "
            f"{run.latency_s:5.1f}s · "
            f"{run.fact_count if run.success else run.error_type or '—'}"
        )
        status_lines.append(line)
        status.markdown("\n".join(status_lines[-12:]))

    runs = compare_backends(
        selected_pdfs,
        selected_backends,
        skip_cache=skip_cache,
        on_progress=_on_progress,
    )
    progress.progress(1.0, text=f"Done · {len(runs)} cells.")

    st.session_state[_RUNS_KEY] = runs
    st.session_state[_LAST_CONFIG_KEY] = {
        "pdfs": [p[0] for p in selected_pdfs],
        "backends": [_backend_label(n, m) for n, m in selected_backends],
        "skip_cache": skip_cache,
    }

# ---------------------------------------------------------------------------
# 4 · Result views
# ---------------------------------------------------------------------------

runs: list[ComparisonRun] = st.session_state.get(_RUNS_KEY) or []

st.divider()
st.subheader("4 · Results")

if not runs:
    st.info(
        "Pick PDFs + backends above and click **Run comparison**. The "
        "progress stream will show each cell as it completes; the table "
        "and pivots populate when all cells finish."
    )
else:
    last_cfg = st.session_state.get(_LAST_CONFIG_KEY) or {}
    st.caption(
        f"Last run: **{len(runs)} cells** · "
        f"PDFs: {len(last_cfg.get('pdfs', []))} · "
        f"backends: {len(last_cfg.get('backends', []))} · "
        f"skip_cache={last_cfg.get('skip_cache', False)}"
    )

    flat_tab, fact_tab, latency_tab, md_tab = st.tabs(
        ["📋 Flat table", "🔢 Fact-count pivot", "⏱️ Latency pivot", "📝 Markdown"]
    )

    with flat_tab:
        rows = [
            {
                "PDF": r.pdf_label,
                "Backend": r.backend_name,
                "Model": r.model,
                "OK": "✓" if r.success else "✗",
                "Latency (s)": round(r.latency_s, 2),
                "Doc type": r.document_type or "—",
                "Facts": r.fact_count if r.success else 0,
                "Confidence": (
                    round(r.extraction_confidence, 2)
                    if r.extraction_confidence is not None
                    else None
                ),
                "Error": r.error_type or "",
            }
            for r in runs
        ]
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    with fact_tab:
        st.markdown(
            "Rows are PDFs, columns are backends/models, cells are fact counts "
            "(lab results, or conditions+symptoms). `✗ <ErrorType>` if the cell failed."
        )
        st.dataframe(fact_count_by_backend(runs), use_container_width=True)

    with latency_tab:
        st.markdown(
            "Wall-clock seconds per cell. **Cached cells run in ~0.0–0.5s**; "
            "uncached cells reflect the actual API latency."
        )
        st.dataframe(
            latency_by_backend(runs).style.format("{:.2f}"),
            use_container_width=True,
        )

    with md_tab:
        st.markdown(
            "Copy-pasteable comparison table — useful for PR descriptions or "
            "decision docs. Same data as the Flat table tab."
        )
        st.code(to_markdown_table(runs), language="markdown")

    # Per-row detail expanders
    st.divider()
    st.subheader("5 · Cell details")
    st.caption("Click any cell below to inspect the validated `ExtractionResult` it produced.")
    for r in runs:
        ok_icon = "✓" if r.success else "✗"
        title = (
            f"{ok_icon} **{r.pdf_label}** · "
            f"`{r.backend_name}/{r.model}` · "
            f"{r.latency_s:.1f}s"
        )
        if r.success:
            title += f" · {r.fact_count} facts · {r.document_type}"
        else:
            title += f" · {r.error_type}"
        with st.expander(title, expanded=False):
            if not r.success:
                st.error(f"**{r.error_type}** — {r.error_message}")
                continue
            st.markdown(
                f"- Document type: `{r.document_type}`  \n"
                f"- Confidence: `{r.extraction_confidence:.2f}`  \n"
                f"- Facts: `{r.fact_count}`  \n"
                f"- Cache key model id: `{r.cache_model_id}`"
            )
            if r.result is not None:
                st.json(r.result.model_dump(), expanded=False)

# ---------------------------------------------------------------------------
# Footer
# ---------------------------------------------------------------------------

st.divider()
st.caption(
    "Single-PDF inspection: [PDF Lab](./PDF_Lab) · "
    "Notebook: `notebooks/03_layer2b_vision_extraction.ipynb` · "
    "Compare module: `ehi_atlas/extract/compare.py`"
)
