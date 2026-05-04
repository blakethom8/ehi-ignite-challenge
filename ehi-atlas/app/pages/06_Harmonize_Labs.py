"""EHI Atlas Console — Harmonize Labs page.

The first vertical slice of the harmonization layer: takes per-source FHIR
Observation lists (Cedars-Sinai pull + Function Health PDF extractions),
identity-resolves them via LOINC code or the name→LOINC bridge, and
surfaces the merged longitudinal view alongside Provenance lineage.

Run from repo root:
    uv run streamlit run ehi-atlas/app/streamlit_app.py --server.port 8503
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

_APP_DIR = Path(__file__).parent.parent.resolve()
if str(_APP_DIR) not in sys.path:
    sys.path.insert(0, str(_APP_DIR))

# Make lib/ importable from the Streamlit page (repo root is two parents up
# from ehi-atlas/, three up from ehi-atlas/app/pages/).
_REPO_ROOT = _APP_DIR.parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import pandas as pd
import streamlit as st

from components.header import render_header
from lib.harmonize import (
    SourceBundle,
    merge_observations,
    mint_provenance,
)


st.set_page_config(
    page_title="EHI Atlas — Harmonize Labs",
    page_icon="🔗",
    layout="wide",
    initial_sidebar_state="expanded",
)

render_header("Harmonize Labs — Cross-Source Merge")

st.markdown(
    """
The harmonization layer takes per-source FHIR Observations from heterogeneous
ingestion paths and produces a merged longitudinal view, with FHIR Provenance
edges recording where each fact came from. This page runs the v1 matcher on
Blake's two real sources: **Cedars-Sinai** (FHIR pull via Health Skillz) and
**Function Health** (Quest lab PDFs ingested via the PDF → FHIR pipeline).
"""
)

# ---------------------------------------------------------------------------
# Load sources
# ---------------------------------------------------------------------------

_BLAKE_DIR = (
    _REPO_ROOT
    / "ehi-atlas"
    / "corpus"
    / "bronze"
    / "clinical-portfolios"
    / "blake_records"
)


@st.cache_data
def load_cedars() -> list[dict]:
    path = _BLAKE_DIR / "cedars-healthskillz-download" / "health-records.json"
    if not path.exists():
        return []
    doc = json.loads(path.read_text())
    return doc[0]["fhir"].get("Observation", [])


@st.cache_data
def load_function_health() -> list[tuple[str, list[dict]]]:
    """Return [(pdf_stem, observations), ...] for each extracted PDF."""
    fh_dir = _BLAKE_DIR / "blake_function_pdfs"
    out: list[tuple[str, list[dict]]] = []
    for f in sorted(fh_dir.glob("extracted-*.json")):
        b = json.loads(f.read_text())
        obs = [e["resource"] for e in b.get("entry", [])]
        out.append((f.stem.replace("extracted-", ""), obs))
    return out


cedars_obs = load_cedars()
fh_pdfs = load_function_health()

if not cedars_obs and not fh_pdfs:
    st.warning(
        "No sources found at `corpus/bronze/clinical-portfolios/blake_records/`. "
        "Add the Cedars Health-Skillz pull and run the PDF → FHIR pipeline on "
        "Function Health PDFs first."
    )
    st.stop()

st.subheader("1 · Sources")

c1, c2 = st.columns(2)
c1.metric("Cedars-Sinai (FHIR)", f"{len(cedars_obs)} Observations")
c2.metric("Function Health (PDF)", f"{sum(len(o) for _, o in fh_pdfs)} Observations across {len(fh_pdfs)} PDFs")

with st.expander("Per-source detail"):
    rows = [{"source": "Cedars-Sinai", "kind": "FHIR pull", "obs_count": len(cedars_obs)}]
    for stem, obs in fh_pdfs:
        rows.append({"source": f"Function Health · {stem}", "kind": "PDF extraction", "obs_count": len(obs)})
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

# ---------------------------------------------------------------------------
# Merge
# ---------------------------------------------------------------------------

bundles: list[SourceBundle] = []
if cedars_obs:
    bundles.append(
        SourceBundle(
            label="Cedars-Sinai",
            observations=cedars_obs,
            document_reference="DocumentReference/cedars-healthskillz-2025-11-07",
        )
    )
for stem, obs in fh_pdfs:
    bundles.append(
        SourceBundle(
            label="Function Health",
            observations=obs,
            document_reference=f"DocumentReference/function-health-{stem}",
        )
    )

merged = merge_observations(bundles)
cross_source = [m for m in merged if len({s.source_label for s in m.sources}) > 1]

st.divider()
st.subheader("2 · Merged longitudinal view")

cc1, cc2, cc3 = st.columns(3)
cc1.metric("Total canonical facts", len(merged))
cc2.metric("Cross-source merges", len(cross_source))
cc3.metric("Conflicts flagged", sum(1 for m in cross_source if m.has_conflict))

show_only_cross = st.toggle(
    "Show only cross-source merges",
    value=True,
    help=(
        "Cross-source merges are facts that appear in ≥2 distinct sources — "
        "they're the value-add of the harmonization layer."
    ),
)
display = cross_source if show_only_cross else merged

# Longitudinal table
table_rows = []
for m in display:
    row = {
        "Lab": m.canonical_name[:50],
        "LOINC": m.loinc_code or "—",
        "Sources": len({s.source_label for s in m.sources}),
        "Measurements": len(m.sources),
        "Latest": m.latest.value if m.latest else None,
        "Unit": m.canonical_unit or (m.latest.unit if m.latest else None),
        "Conflict": "⚠" if m.has_conflict else "",
    }
    table_rows.append(row)

st.dataframe(
    pd.DataFrame(table_rows),
    use_container_width=True,
    hide_index=True,
    column_config={
        "Latest": st.column_config.NumberColumn(format="%.2f"),
    },
)

# ---------------------------------------------------------------------------
# Inspect a single fact
# ---------------------------------------------------------------------------

st.divider()
st.subheader("3 · Inspect a fact + Provenance graph")

if not display:
    st.info("No facts to inspect.")
    st.stop()

# Default to one with both sources + clinical interest (HDL Cholesterol)
default_idx = 0
for i, m in enumerate(display):
    n = m.canonical_name.lower()
    if "hdl" in n and "non" not in n:
        default_idx = i
        break

names = [f"{m.canonical_name[:60]} (LOINC {m.loinc_code or '—'})" for m in display]
choice = st.selectbox("Pick a fact", names, index=default_idx)
selected = display[names.index(choice)]

left, right = st.columns([2, 1])

with left:
    st.markdown(f"**{selected.canonical_name}**")
    if selected.loinc_code:
        st.caption(f"LOINC `{selected.loinc_code}` · canonical unit `{selected.canonical_unit or '—'}`")
    long_rows = []
    for s in selected.sources:
        long_rows.append(
            {
                "Date": s.effective_date.date().isoformat() if s.effective_date else "—",
                "Source": s.source_label,
                "Value": s.value,
                "Unit": s.unit,
                "Raw value": s.raw_value if s.raw_value != s.value else "",
                "Raw unit": s.raw_unit if s.raw_unit and s.raw_unit != s.unit else "",
            }
        )
    long_df = pd.DataFrame(long_rows).sort_values("Date")
    st.dataframe(long_df, use_container_width=True, hide_index=True)

    # Trajectory chart when there are 2+ numeric measurements. Normalize
    # all datetimes to plain dates (no tz) so the chart sort doesn't trip
    # on mixed naive/aware values across sources.
    numeric = [
        (s.effective_date.date(), s.value, s.source_label)
        for s in selected.sources
        if s.value is not None and s.effective_date is not None
    ]
    if len(numeric) >= 2:
        chart_df = pd.DataFrame(numeric, columns=["date", "value", "source"])
        chart_df = chart_df.sort_values("date")
        st.line_chart(chart_df, x="date", y="value", color="source", height=240)

with right:
    st.markdown("**Provenance**")
    prov = mint_provenance(selected)
    activity = prov["activity"]["coding"][0]["code"]
    st.caption(f"Activity: `{activity}` · {len(prov['entity'])} source edge(s)")
    for entity in prov["entity"]:
        ext = {e["url"].rsplit("/", 1)[-1]: e["valueString"] for e in entity.get("extension", [])}
        ref = entity["what"]["reference"]
        st.markdown(
            f"**{ext.get('source-label', '?')}** · `{ext.get('harmonize-activity', '?')}`  \n"
            f"<small><code>{ref}</code></small>",
            unsafe_allow_html=True,
        )
    with st.expander("Raw FHIR Provenance JSON"):
        st.code(json.dumps(prov, indent=2, default=str), language="json")

st.caption(
    "The Provenance graph is the Atlas wedge: every merged fact retains pointers "
    "back to its sources via FHIR Provenance entities. Atlas extension URLs "
    "(`source-label`, `harmonize-activity`) carry the lineage that downstream "
    "consumers (clinician UI, agent assistant) read to render explainability."
)
