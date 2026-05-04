"""EHI Atlas Console — Overview page (main entry point).

Run from the repo root:
    uv run streamlit run ehi-atlas/app/streamlit_app.py --server.port 8503

Or from inside ehi-atlas/:
    uv run streamlit run app/streamlit_app.py --server.port 8503
"""

from __future__ import annotations

import sys
from pathlib import Path

_APP_DIR = Path(__file__).parent.resolve()
if str(_APP_DIR) not in sys.path:
    sys.path.insert(0, str(_APP_DIR))

import streamlit as st

from components.header import render_header
from components.corpus_loader import (
    list_bronze_sources,
    count_bronze_records,
    BRONZE_ROOT,
)

st.set_page_config(
    page_title="EHI Atlas Console",
    page_icon="🗂️",
    layout="wide",
    initial_sidebar_state="expanded",
)

render_header("Overview")

with st.sidebar:
    st.markdown("### Console")
    st.caption(
        "The dev surface for the Atlas data platform. Active focus: PDF → FHIR "
        "extraction. The 5-layer harmonization pipeline (silver / gold / "
        "Provenance) was archived; see `archive/ehi-atlas-5layer/`."
    )
    st.divider()
    st.markdown("### Pages")
    st.page_link("pages/01_Sources_and_Bronze.py", label="Sources & Bronze", icon="📦")
    st.page_link("pages/03_PDF_Lab.py", label="PDF Lab (single PDF)", icon="🧪")
    st.page_link("pages/04_PDF_Compare.py", label="PDF Compare (backends)", icon="🆚")
    st.page_link("pages/05_Pipeline_Bakeoff.py", label="Pipeline Bakeoff", icon="🥧")
    st.page_link("pages/06_Harmonize_Labs.py", label="Harmonize Labs", icon="🔗")

st.markdown(
    """
**EHI Atlas** is the dev surface for patient-side EHI ingestion. The current
focus is the **PDF → FHIR** extraction pipeline: turning unstructured clinical
PDFs (lab reports, H&Ps, discharge summaries, portal exports) into FHIR R4
resources with measurable F1 against ground truth.

The architectural cuts and decision history live in
[`docs/architecture/PDF-PROCESSOR.md`](../../docs/architecture/PDF-PROCESSOR.md);
the running experiment journal lives in
[`docs/architecture/PIPELINE-LOG.md`](../../docs/architecture/PIPELINE-LOG.md).
"""
)

st.divider()
st.subheader("Corpus")

bronze_sources = list_bronze_sources()
total_bronze = sum(sum(count_bronze_records(s).values()) for s in bronze_sources)

c1, c2 = st.columns(2)
c1.metric("Bronze sources", len(bronze_sources))
c2.metric("Bronze records (across sources)", total_bronze)

st.caption(f"Bronze root: `{BRONZE_ROOT}`")

st.divider()
st.subheader("Where to start")

cols = st.columns(4)
_CARDS = [
    (
        "🧪",
        "PDF Lab",
        "Drop a PDF, watch one pipeline parse it end-to-end. Live extraction, four-panel inspection.",
        "pages/03_PDF_Lab.py",
    ),
    (
        "🆚",
        "PDF Compare",
        "Compare vision-LLM backends (Claude vs Gemma) on the same PDF, same prompt.",
        "pages/04_PDF_Compare.py",
    ),
    (
        "🥧",
        "Pipeline Bakeoff",
        "Compare extraction architectures (single-pass vs multi-pass) with F1 scoring against ground truth.",
        "pages/05_Pipeline_Bakeoff.py",
    ),
    (
        "🔗",
        "Harmonize Labs",
        "Cross-source merge: Cedars FHIR + Function Health PDFs identity-resolved, longitudinal view, Provenance lineage.",
        "pages/06_Harmonize_Labs.py",
    ),
]
for col, (icon, title, desc, page) in zip(cols, _CARDS):
    with col:
        st.markdown(f"**{icon} {title}**")
        st.caption(desc)
        st.page_link(page, label=f"Open {title} →")
