"""
Page 6 — Corpus Explorer
Browse and filter all 1,180 patients. Identify good test cases.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

from ..parser.models import PatientRecord
from ..catalog.single_patient import PatientStats
from ..catalog.corpus import load_corpus, CorpusCatalog

DATA_DIR = Path(__file__).parent.parent.parent / "data" / "synthea-samples" / "synthea-r4-individual" / "fhir"

TIER_COLORS = {
    "simple": "#4CAF50",
    "moderate": "#FFC107",
    "complex": "#FF9800",
    "highly_complex": "#F44336",
}
TIER_ICONS = {
    "simple": "🟢",
    "moderate": "🟡",
    "complex": "🟠",
    "highly_complex": "🔴",
}


@st.cache_data(show_spinner=False)
def get_corpus() -> CorpusCatalog | None:
    if not DATA_DIR.exists():
        return None
    return load_corpus(DATA_DIR)


def render(record: PatientRecord, stats: PatientStats) -> None:
    st.title("Corpus Explorer")
    st.markdown("Browse all patients in the dataset. Filter, search, and find representative test cases.")

    # Load corpus (cached)
    with st.spinner("Loading corpus index (first run takes ~30–60s for 1,180 patients)..."):
        corpus = get_corpus()

    if corpus is None:
        st.error(f"Could not find patient data directory:\n{DATA_DIR}")
        return

    # --- Corpus-level metrics ---
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Patients", corpus.patient_count)
    c2.metric("Total Resources", f"{corpus.total_resources:,}")
    tier_counts = {}
    for p in corpus.patients:
        tier_counts[p.complexity_tier] = tier_counts.get(p.complexity_tier, 0) + 1
    c3.metric("Highly Complex", tier_counts.get("highly_complex", 0))
    c4.metric("Simple", tier_counts.get("simple", 0))

    # Resource type distribution pie
    with st.expander("Global resource type distribution"):
        rtype_data = [
            {"Resource Type": k, "Count": v}
            for k, v in sorted(corpus.global_resource_type_counts.items(), key=lambda x: -x[1])
        ]
        fig = px.pie(
            pd.DataFrame(rtype_data),
            names="Resource Type",
            values="Count",
            height=350,
        )
        st.plotly_chart(fig, use_container_width=True)

    st.markdown("---")

    # --- Scenario Finder ---
    st.subheader("Scenario Finder")
    scen_cols = st.columns(5)
    scenario = None
    if scen_cols[0].button("🟢 Simplest patient"):
        scenario = "simplest"
    if scen_cols[1].button("🔴 Most complex patient"):
        scenario = "most_complex"
    if scen_cols[2].button("🤧 Has allergies"):
        scenario = "has_allergies"
    if scen_cols[3].button("💊 Active chronic conditions"):
        scenario = "chronic"
    if scen_cols[4].button("📅 50+ years of history"):
        scenario = "long_history"

    # --- Filters ---
    st.markdown("---")
    st.subheader("Filter Patients")

    col_f1, col_f2, col_f3 = st.columns(3)
    with col_f1:
        tier_options = ["all", "simple", "moderate", "complex", "highly_complex"]
        tier_filter = st.selectbox("Complexity tier", tier_options)
        allergy_filter = st.selectbox("Has allergies", ["any", "yes", "no"])
    with col_f2:
        min_conditions = st.number_input("Min conditions", min_value=0, value=0)
        max_conditions = st.number_input("Max conditions", min_value=0, value=999)
    with col_f3:
        min_years = st.number_input("Min years of history", min_value=0, value=0)
        condition_search = st.text_input("Search by condition name")

    # --- Apply filters ---
    patients = corpus.patients

    # Apply scenario shortcuts
    if scenario == "simplest":
        patients = sorted(patients, key=lambda p: p.complexity_score)[:1]
    elif scenario == "most_complex":
        patients = sorted(patients, key=lambda p: -p.complexity_score)[:1]
    elif scenario == "has_allergies":
        patients = [p for p in patients if p.has_allergies]
    elif scenario == "chronic":
        patients = [p for p in patients if p.active_condition_count >= 3]
    elif scenario == "long_history":
        patients = [p for p in patients if p.years_of_history >= 50]
    else:
        # Manual filters
        if tier_filter != "all":
            patients = [p for p in patients if p.complexity_tier == tier_filter]
        if allergy_filter == "yes":
            patients = [p for p in patients if p.has_allergies]
        elif allergy_filter == "no":
            patients = [p for p in patients if not p.has_allergies]
        patients = [p for p in patients if min_conditions <= p.condition_count <= max_conditions]
        patients = [p for p in patients if p.years_of_history >= min_years]
        if condition_search:
            search_lower = condition_search.lower()
            patients = [
                p for p in patients
                if any(search_lower in c.lower() for c in p.top_conditions)
            ]

    st.markdown(f"**{len(patients)} patient(s) match**")

    if not patients:
        st.info("No patients match the current filters.")
        return

    # --- Results table ---
    rows = []
    for p in patients:
        icon = TIER_ICONS.get(p.complexity_tier, "⚪")
        rows.append({
            "Name": p.patient_name,
            "Tier": f"{icon} {p.complexity_tier.replace('_', ' ').title()}",
            "Score": f"{p.complexity_score:.0f}",
            "Age": f"{p.age_years:.0f}",
            "Gender": p.gender.title(),
            "Conditions": p.condition_count,
            "Active Cond.": p.active_condition_count,
            "Meds": p.med_count,
            "Encounters": p.encounter_count,
            "Years": f"{p.years_of_history:.1f}",
            "Allergies": "✅" if p.has_allergies else "—",
            "Top Conditions": ", ".join(p.top_conditions) or "—",
            "Resources": p.total_resources,
            "_file_path": p.file_path,
        })

    df = pd.DataFrame(rows)
    display_df = df.drop(columns=["_file_path"])

    # Highlight selected patient
    selected_rows = st.dataframe(
        display_df,
        hide_index=True,
        use_container_width=True,
        height=400,
    )

    st.caption("To load a patient, select them from the sidebar file picker.")
