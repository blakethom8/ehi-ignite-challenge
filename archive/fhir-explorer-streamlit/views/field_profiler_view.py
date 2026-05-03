"""
Page 5 — Field Profiler
Field presence heatmap across a resource type for the active patient.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

from ..parser.models import PatientRecord
from ..catalog.single_patient import PatientStats
from ..catalog.field_profiler import profile_resources

TIER_COLORS = {
    "always": "#4CAF50",
    "usually": "#FFC107",
    "sometimes": "#FF9800",
    "rarely": "#F44336",
}


def render(record: PatientRecord, stats: PatientStats) -> None:
    st.title(f"Field Profiler — {stats.name}")
    st.markdown(
        "Recursively analyzes field presence across a resource type. "
        "Answers: **what fields can we rely on vs. what's optional?**"
    )

    # Resource type selector
    available_types = sorted(record.resource_type_counts.keys())
    selected_type = st.selectbox("Select resource type to profile", available_types)

    # Collect raw resources of that type from the bundle file
    raw_resources = _get_raw_resources(record, selected_type)
    n = len(raw_resources)

    if n == 0:
        st.info(f"No {selected_type} resources found.")
        return

    st.markdown(f"Profiling **{n}** `{selected_type}` resources")

    max_depth = st.slider("Max nesting depth", min_value=1, max_value=6, value=4)
    show_nested = st.checkbox("Show nested paths (e.g. code.coding[*].system)", value=True)

    profile = profile_resources(raw_resources, selected_type, max_depth=max_depth)

    fields = profile.fields
    if not show_nested:
        fields = [f for f in fields if "." not in f.field_path and "[*]" not in f.field_path]

    if not fields:
        st.info("No fields found at this depth.")
        return

    # --- Tier summary badges ---
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("🟢 Always (100%)", len(profile.always_present))
    col2.metric("🟡 Usually (80–99%)", len(profile.usually_present))
    col3.metric("🟠 Sometimes (20–79%)", len(profile.sometimes_present))
    col4.metric("🔴 Rarely (<20%)", len(profile.rarely_present))

    st.markdown("---")

    # --- Table ---
    rows = []
    for f in fields:
        rows.append({
            "Field Path": f.field_path,
            "Present": f.present_count,
            "Total": f.total_count,
            "Presence %": f.presence_pct,
            "Tier": f.tier,
            "Sample Values": ", ".join(f.sample_values[:3]),
        })

    df = pd.DataFrame(rows)

    # Color code by tier
    def color_row(row):
        colors = {
            "always": "background-color: #E8F5E9",
            "usually": "background-color: #FFF9C4",
            "sometimes": "background-color: #FFF3E0",
            "rarely": "background-color: #FFEBEE",
        }
        return [colors.get(row["Tier"], "")] * len(row)

    st.dataframe(
        df.style.apply(color_row, axis=1),
        hide_index=True,
        use_container_width=True,
        height=500,
    )

    # --- Export ---
    csv = df.to_csv(index=False)
    st.download_button(
        label=f"⬇️ Download {selected_type} field profile as CSV",
        data=csv,
        file_name=f"field_profile_{selected_type}.csv",
        mime="text/csv",
    )

    # --- Always-present summary ---
    if profile.always_present:
        with st.expander("✅ Always-present fields (100%)"):
            for f in profile.always_present:
                st.code(f.field_path)


def _get_raw_resources(record: PatientRecord, resource_type: str) -> list[dict]:
    """
    Re-read the raw resources from the bundle file for profiling.
    We need the raw dicts (not our parsed models) for field profiling.
    """
    import json

    file_path = Path(record.summary.file_path)
    if not file_path.exists():
        return []

    try:
        with open(file_path) as f:
            bundle = json.load(f)
        return [
            entry["resource"]
            for entry in bundle.get("entry", [])
            if entry.get("resource", {}).get("resourceType") == resource_type
        ]
    except Exception:
        return []
