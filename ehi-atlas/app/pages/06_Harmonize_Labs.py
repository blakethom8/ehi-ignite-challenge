"""EHI Atlas Console — Harmonize page.

Cross-source merge surface for the harmonization layer. Takes per-source
FHIR resources from heterogeneous ingestion paths (FHIR pulls + vision-
extracted PDFs) and surfaces the merged longitudinal view + Provenance
lineage.

Currently demos against the Cedars + Function Health fixture in
``corpus/bronze/clinical-portfolios/blake_records/``, but the matcher is
dataset-agnostic — swap in any pair of source bundles and the same view
renders.

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

_REPO_ROOT = _APP_DIR.parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import pandas as pd
import streamlit as st

from components.header import render_header
from lib.harmonize import (
    SourceBundle,
    merge_conditions,
    merge_observations,
    mint_provenance,
)


st.set_page_config(
    page_title="EHI Atlas — Harmonize",
    page_icon="🔗",
    layout="wide",
    initial_sidebar_state="expanded",
)

render_header("Harmonize — Cross-Source Merge")

st.markdown(
    """
The harmonization layer takes per-source FHIR resources from heterogeneous
ingestion paths (native FHIR pulls + vision-extracted PDFs) and produces a
merged longitudinal view, with FHIR Provenance edges recording where each
fact came from. This page demos against the Cedars + Function Health
fixture; the matcher itself is dataset-agnostic.
"""
)

# ---------------------------------------------------------------------------
# Source loading
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
def load_cedars_fhir() -> dict[str, list[dict]]:
    """Cedars Health-Skillz pull, all resource types as flat lists."""
    path = _BLAKE_DIR / "cedars-healthskillz-download" / "health-records.json"
    if not path.exists():
        return {}
    doc = json.loads(path.read_text())
    return doc[0]["fhir"]


@st.cache_data
def load_cedars_pdf() -> dict[str, list[dict]]:
    """Cedars HealthSummary PDF, vision-extracted via multipass-fhir."""
    path = _BLAKE_DIR / "HealthSummary_May_03_2026" / "extracted-cedars-healthsummary.json"
    if not path.exists():
        return {}
    bundle = json.loads(path.read_text())
    out: dict[str, list[dict]] = {}
    for entry in bundle.get("entry", []):
        r = entry["resource"]
        out.setdefault(r["resourceType"], []).append(r)
    return out


@st.cache_data
def load_function_health() -> list[tuple[str, dict[str, list[dict]]]]:
    """Function Health PDFs, one (label, resources-by-type) per PDF."""
    fh_dir = _BLAKE_DIR / "blake_function_pdfs"
    out: list[tuple[str, dict[str, list[dict]]]] = []
    for f in sorted(fh_dir.glob("extracted-*.json")):
        b = json.loads(f.read_text())
        by_type: dict[str, list[dict]] = {}
        for entry in b.get("entry", []):
            r = entry["resource"]
            by_type.setdefault(r["resourceType"], []).append(r)
        out.append((f.stem.replace("extracted-", ""), by_type))
    return out


cedars_fhir = load_cedars_fhir()
cedars_pdf = load_cedars_pdf()
fh_pdfs = load_function_health()

if not cedars_fhir and not cedars_pdf and not fh_pdfs:
    st.warning(
        "No sources found at `corpus/bronze/clinical-portfolios/blake_records/`. "
        "Add the Cedars Health-Skillz pull and run the PDF → FHIR pipeline first."
    )
    st.stop()

# ---------------------------------------------------------------------------
# Source overview
# ---------------------------------------------------------------------------

st.subheader("1 · Sources")

source_rows = [
    {
        "source": "Cedars-Sinai (FHIR)",
        "kind": "Native FHIR pull",
        "Observations": len(cedars_fhir.get("Observation", [])),
        "Conditions": len(cedars_fhir.get("Condition", [])),
    },
    {
        "source": "Cedars-Sinai (PDF)",
        "kind": "Vision-extracted PDF",
        "Observations": len(cedars_pdf.get("Observation", [])),
        "Conditions": len(cedars_pdf.get("Condition", [])),
    },
]
for stem, by_type in fh_pdfs:
    source_rows.append(
        {
            "source": f"Function Health · {stem}",
            "kind": "Vision-extracted PDF",
            "Observations": len(by_type.get("Observation", [])),
            "Conditions": len(by_type.get("Condition", [])),
        }
    )
st.dataframe(pd.DataFrame(source_rows), use_container_width=True, hide_index=True)


# ---------------------------------------------------------------------------
# Helper: render a merged-record view for either resource type
# ---------------------------------------------------------------------------


def _render_merged_view(
    *,
    merged_records: list,
    resource_label: str,
    table_columns_fn,
    detail_panel_fn,
    default_picker_filter: callable | None = None,
) -> None:
    """Shared render shape: stats → table → fact picker → detail/provenance."""
    cross_source = [
        m for m in merged_records if len({s.source_label for s in m.sources}) > 1
    ]
    cc1, cc2, cc3 = st.columns(3)
    cc1.metric(f"Total canonical {resource_label}", len(merged_records))
    cc2.metric("Cross-source merges", len(cross_source))
    has_conflict_attr = hasattr(merged_records[0], "has_conflict") if merged_records else False
    cc3.metric(
        "Conflicts flagged",
        sum(1 for m in cross_source if getattr(m, "has_conflict", False)) if has_conflict_attr else "—",
    )

    show_only_cross = st.toggle(
        f"Show only cross-source merges",
        value=True,
        key=f"toggle_{resource_label}",
    )
    display = cross_source if show_only_cross else merged_records

    if not display:
        st.info(f"No {resource_label.lower()} to display.")
        return

    table_rows = [table_columns_fn(m) for m in display]
    st.dataframe(pd.DataFrame(table_rows), use_container_width=True, hide_index=True)

    st.markdown("---")
    st.markdown(f"**Inspect a {resource_label[:-1].lower()} + Provenance graph**")

    default_idx = 0
    if default_picker_filter:
        for i, m in enumerate(display):
            if default_picker_filter(m):
                default_idx = i
                break

    names = [_picker_label(m) for m in display]
    choice = st.selectbox(
        "Pick", names, index=default_idx, key=f"picker_{resource_label}"
    )
    selected = display[names.index(choice)]
    detail_panel_fn(selected)


def _picker_label(m) -> str:
    """Best display label for either MergedObservation or MergedCondition."""
    name = m.canonical_name[:60]
    if hasattr(m, "loinc_code"):
        return f"{name} (LOINC {m.loinc_code or '—'})"
    codes = []
    if m.snomed:
        codes.append(f"SCT {m.snomed}")
    if m.icd10:
        codes.append(f"ICD-10 {m.icd10}")
    return f"{name} ({' / '.join(codes) or 'text-only'})"


# ---------------------------------------------------------------------------
# Build SourceBundles + run merges (one per resource type)
# ---------------------------------------------------------------------------


obs_bundles: list[SourceBundle] = []
if cedars_fhir.get("Observation"):
    obs_bundles.append(
        SourceBundle(
            "Cedars-Sinai (FHIR)",
            cedars_fhir["Observation"],
            "DocumentReference/cedars-healthskillz-2025-11-07",
        )
    )
if cedars_pdf.get("Observation"):
    obs_bundles.append(
        SourceBundle(
            "Cedars-Sinai (PDF)",
            cedars_pdf["Observation"],
            "DocumentReference/cedars-health-summary-pdf",
        )
    )
for stem, by_type in fh_pdfs:
    if by_type.get("Observation"):
        obs_bundles.append(
            SourceBundle(
                "Function Health",
                by_type["Observation"],
                f"DocumentReference/function-health-{stem}",
            )
        )
merged_obs = merge_observations(obs_bundles)


cond_bundles: list[SourceBundle] = []
if cedars_fhir.get("Condition"):
    cond_bundles.append(
        SourceBundle(
            "Cedars-Sinai (FHIR)",
            cedars_fhir["Condition"],
            "DocumentReference/cedars-healthskillz-2025-11-07",
        )
    )
if cedars_pdf.get("Condition"):
    cond_bundles.append(
        SourceBundle(
            "Cedars-Sinai (PDF)",
            cedars_pdf["Condition"],
            "DocumentReference/cedars-health-summary-pdf",
        )
    )
for stem, by_type in fh_pdfs:
    if by_type.get("Condition"):
        cond_bundles.append(
            SourceBundle(
                "Function Health",
                by_type["Condition"],
                f"DocumentReference/function-health-{stem}",
            )
        )
merged_cond = merge_conditions(cond_bundles)


# ---------------------------------------------------------------------------
# Tabs: Labs / Conditions
# ---------------------------------------------------------------------------

st.divider()
st.subheader("2 · Merged longitudinal view")

tab_labs, tab_conds = st.tabs(["🧪 Labs", "🩺 Conditions"])


def _obs_row(m) -> dict:
    return {
        "Lab": m.canonical_name[:50],
        "LOINC": m.loinc_code or "—",
        "Sources": len({s.source_label for s in m.sources}),
        "Measurements": len(m.sources),
        "Latest": m.latest.value if m.latest else None,
        "Unit": m.canonical_unit or (m.latest.unit if m.latest else None),
        "Conflict": "⚠" if m.has_conflict else "",
    }


def _obs_detail(selected) -> None:
    left, right = st.columns([2, 1])
    with left:
        st.markdown(f"**{selected.canonical_name}**")
        if selected.loinc_code:
            st.caption(
                f"LOINC `{selected.loinc_code}` · canonical unit `{selected.canonical_unit or '—'}`"
            )
        long_rows = []
        for s in selected.sources:
            long_rows.append(
                {
                    "Date": s.effective_date.date().isoformat() if s.effective_date else "—",
                    "Source": s.source_label,
                    "Value": s.value,
                    "Unit": s.unit,
                }
            )
        long_df = pd.DataFrame(long_rows).sort_values("Date")
        st.dataframe(long_df, use_container_width=True, hide_index=True)
        numeric = [
            (s.effective_date.date(), s.value, s.source_label)
            for s in selected.sources
            if s.value is not None and s.effective_date is not None
        ]
        if len(numeric) >= 2:
            chart_df = pd.DataFrame(numeric, columns=["date", "value", "source"]).sort_values("date")
            st.line_chart(chart_df, x="date", y="value", color="source", height=240)
    with right:
        _render_provenance(selected)


def _cond_row(m) -> dict:
    return {
        "Condition": m.canonical_name[:60],
        "SNOMED": m.snomed or "—",
        "ICD-10": m.icd10 or "—",
        "Sources": len({s.source_label for s in m.sources}),
        "Occurrences": len(m.sources),
        "Active": "●" if m.is_active else "○",
    }


def _cond_detail(selected) -> None:
    left, right = st.columns([2, 1])
    with left:
        st.markdown(f"**{selected.canonical_name}**")
        codes = []
        if selected.snomed:
            codes.append(f"SNOMED `{selected.snomed}`")
        if selected.icd10:
            codes.append(f"ICD-10 `{selected.icd10}`")
        if selected.icd9:
            codes.append(f"ICD-9 `{selected.icd9}`")
        st.caption(" · ".join(codes) if codes else "text-only")
        rows = []
        for s in selected.sources:
            rows.append(
                {
                    "Onset": s.onset_date.date().isoformat() if s.onset_date else "—",
                    "Source": s.source_label,
                    "Display": s.display,
                    "Status": s.clinical_status or "—",
                }
            )
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    with right:
        _render_provenance(selected)


def _render_provenance(selected) -> None:
    st.markdown("**Provenance**")
    prov = mint_provenance(selected)
    activity = prov["activity"]["coding"][0]["code"]
    st.caption(f"Activity: `{activity}` · {len(prov['entity'])} source edge(s)")
    for entity in prov["entity"]:
        ext = {
            e["url"].rsplit("/", 1)[-1]: e["valueString"]
            for e in entity.get("extension", [])
        }
        ref = entity["what"]["reference"]
        st.markdown(
            f"**{ext.get('source-label', '?')}** · `{ext.get('harmonize-activity', '?')}`  \n"
            f"<small><code>{ref}</code></small>",
            unsafe_allow_html=True,
        )
    with st.expander("Raw FHIR Provenance JSON"):
        st.code(json.dumps(prov, indent=2, default=str), language="json")


with tab_labs:
    _render_merged_view(
        merged_records=merged_obs,
        resource_label="Labs",
        table_columns_fn=_obs_row,
        detail_panel_fn=_obs_detail,
        default_picker_filter=lambda m: "hdl" in m.canonical_name.lower()
        and "non" not in m.canonical_name.lower(),
    )

with tab_conds:
    _render_merged_view(
        merged_records=merged_cond,
        resource_label="Conditions",
        table_columns_fn=_cond_row,
        detail_panel_fn=_cond_detail,
        default_picker_filter=lambda m: m.snomed is not None
        and len({s.source_label for s in m.sources}) > 1,
    )

st.caption(
    "The Provenance graph is the Atlas wedge: every merged fact retains pointers "
    "back to its sources via FHIR Provenance entities. Atlas extension URLs "
    "(`source-label`, `harmonize-activity`) carry the lineage that downstream "
    "consumers (clinician UI, agent assistant) read to render explainability."
)
