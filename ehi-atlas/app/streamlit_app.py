"""EHI Atlas Console — Overview page (main entry point).

Run from the repo root:
    uv run streamlit run ehi-atlas/app/streamlit_app.py --server.port 8503

Or from inside ehi-atlas/:
    uv run streamlit run app/streamlit_app.py --server.port 8503
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure the app/components package is importable regardless of cwd.
_APP_DIR = Path(__file__).parent.resolve()
if str(_APP_DIR) not in sys.path:
    sys.path.insert(0, str(_APP_DIR))

import streamlit as st

from components.header import render_header
from components.pipeline_diagram import render_pipeline_diagram
from components.corpus_loader import (
    load_manifest,
    load_gold_bundle,
    load_provenance,
    list_bronze_sources,
    count_bronze_records,
    BRONZE_ROOT,
    GOLD_PATIENT_DIR,
)

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="EHI Atlas Console",
    page_icon="🗂️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------

render_header("Overview")

# ---------------------------------------------------------------------------
# Sidebar: showcase patient
# ---------------------------------------------------------------------------

with st.sidebar:
    st.markdown("### Showcase Patient")
    st.info("**rhett759** (Rhett Rohan)\nFully synthetic · Synthea + Epic EHI + lab PDF")
    st.caption(
        "v1 locks to rhett759. Patient selector coming in Phase 2."
    )
    st.divider()
    st.markdown("### Quick Links")
    st.page_link("pages/01_Sources_and_Bronze.py", label="Sources & Bronze", icon="📦")
    st.page_link("pages/02_Standardize.py", label="Standardize", icon="🔄")
    st.page_link("pages/03_PDF_Lab.py", label="PDF Lab (single PDF)", icon="🧪")
    st.page_link("pages/04_PDF_Compare.py", label="PDF Compare (backends)", icon="🆚")
    st.page_link("pages/05_Pipeline_Bakeoff.py", label="Pipeline Bakeoff (architectures)", icon="🥧")
    st.page_link("pages/06_Harmonize.py", label="Harmonize", icon="🔗")
    st.page_link("pages/07_Gold_and_Provenance.py", label="Gold & Provenance", icon="🏆")

# ---------------------------------------------------------------------------
# Explainer
# ---------------------------------------------------------------------------

st.markdown("""
**EHI Atlas** is a patient-side EHI harmonization pipeline — a workflow tool, not a clinical app.
It ingests patient health data from heterogeneous sources (Synthea FHIR R4, Epic EHI Export SQLite,
payer claims, lab PDFs, synthesized clinical notes), standardizes every source to FHIR R4, and
merges them into a single canonical gold-tier record with full Provenance lineage. This console
visualizes each stage of that workflow for the showcase patient, **rhett759**, so engineers and
judges can walk the pipeline from raw input through to the final unified record.
""")

# ---------------------------------------------------------------------------
# Pipeline diagram
# ---------------------------------------------------------------------------

st.subheader("Five-Layer Pipeline")
render_pipeline_diagram(use_graphviz=True)

# ---------------------------------------------------------------------------
# Pipeline status + metrics
# ---------------------------------------------------------------------------

st.subheader("Pipeline Status")

manifest = load_manifest()
if manifest is None:
    st.warning(
        f"No manifest found at `{GOLD_PATIENT_DIR / 'manifest.json'}`. "
        "Run `make pipeline` from `ehi-atlas/` to build the gold tier."
    )
else:
    built_at = manifest.get("built_at", "unknown")
    harmonizer_version = manifest.get("harmonizer_version", "unknown")

    status_cols = st.columns([2, 2, 1])
    with status_cols[0]:
        st.metric("Last built", built_at)
    with status_cols[1]:
        st.metric("Harmonizer version", harmonizer_version)
    with status_cols[2]:
        st.success("Gold tier ready", icon="✅")

    st.divider()

    # ---------- Top-level metrics ----------
    st.subheader("Corpus Counts")

    resource_counts = manifest.get("resource_counts", {})
    merge_summary = manifest.get("merge_summary", {})

    # Compute bronze counts
    bronze_sources = list_bronze_sources()
    total_bronze = sum(
        sum(count_bronze_records(s).values()) for s in bronze_sources
    )

    # Gold resource total (excl. Provenance)
    gold_resources = sum(v for k, v in resource_counts.items() if k != "Provenance")
    provenance_edges = resource_counts.get("Provenance", 0)

    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("Sources", len(bronze_sources))
    col2.metric("Bronze records", total_bronze)

    # Silver: only synthea has real silver
    silver_bundle_path = Path(__file__).parent.parent / "corpus" / "silver" / "synthea" / "rhett759" / "bundle.json"
    if silver_bundle_path.exists():
        import json
        with silver_bundle_path.open() as fh:
            sb = json.load(fh)
        silver_count = len(sb.get("entry", []))
    else:
        silver_count = 0
    col3.metric("Silver resources (synthea)", silver_count)
    col4.metric("Gold resources", gold_resources)
    col5.metric("Provenance edges", provenance_edges)

    # Merge summary
    st.divider()
    st.subheader("Harmonization Summary")
    ms_cols = st.columns(4)
    ms_cols[0].metric("Conditions merged", merge_summary.get("conditions_merged", 0))
    ms_cols[1].metric("Medications reconciled", merge_summary.get("medications_reconciled", 0))
    ms_cols[2].metric("Observations deduped", merge_summary.get("observations_deduped", 0))
    ms_cols[3].metric("Conflicts detected", merge_summary.get("conflicts_detected", 0))

    # Sources table
    st.divider()
    st.subheader("Sources in This Pipeline Run")
    sources = manifest.get("sources", [])
    if sources:
        rows = []
        for s in sources:
            bundle_path = s.get("bundle_path", "")
            is_stub = "stub-silver" in bundle_path or bundle_path.startswith("(stub")
            rows.append({
                "Source": s.get("name", ""),
                "Silver type": "stub-silver (Phase 1)" if is_stub else "real silver (L2)",
                "Bundle path": bundle_path[:80] + "…" if len(bundle_path) > 80 else bundle_path,
                "Fetched at": s.get("fetched_at", ""),
            })
        import pandas as pd
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

# ---------------------------------------------------------------------------
# Page cards
# ---------------------------------------------------------------------------

st.divider()
st.subheader("Explore the Pipeline")

card_cols = st.columns(3)
_CARDS = [
    ("📦", "Sources & Bronze", "What we received: one record per source, immutable.", "pages/01_Sources_and_Bronze.py"),
    ("🔄", "Standardize", "Silver tier: all sources projected to FHIR R4.", "pages/02_Standardize.py"),
    ("🔗", "Harmonize", "Merge visualization: cross-source dedup, conflict detection.", "pages/06_Harmonize.py"),
]
for col, (icon, title, desc, page) in zip(card_cols, _CARDS):
    with col:
        st.markdown(f"**{icon} {title}**")
        st.caption(desc)
        st.page_link(page, label=f"Open {title} →")

# Vision-extraction tools — PDF Lab and PDF Compare are the developer-facing
# surfaces for iterating on the Layer 2-B vision pipeline.
st.markdown("")
tool_cols = st.columns(3)
_TOOLS = [
    ("🧪", "PDF Lab", "Drop a PDF, watch it parse end-to-end. Live extraction, four-panel inspection.", "pages/03_PDF_Lab.py"),
    ("🆚", "PDF Compare", "Compare vision-LLM backends (Claude vs Gemma) on the same PDF.", "pages/04_PDF_Compare.py"),
    ("🥧", "Pipeline Bakeoff", "Compare entire extraction architectures (single-pass vs multi-pass vs OCR-first) with F1 scoring.", "pages/05_Pipeline_Bakeoff.py"),
]
for col, (icon, title, desc, page) in zip(tool_cols, _TOOLS):
    with col:
        st.markdown(f"**{icon} {title}**")
        st.caption(desc)
        st.page_link(page, label=f"Open {title} →")
