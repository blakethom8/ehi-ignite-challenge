"""
Page 1 — Patient Overview
Demographics, resource counts, signal/noise split, active conditions + meds.
"""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from ..parser.models import PatientRecord
from ..catalog.single_patient import PatientStats

CLINICAL_TYPES = {
    "Observation", "Condition", "MedicationRequest", "Procedure",
    "DiagnosticReport", "Immunization", "AllergyIntolerance", "Encounter",
    "CarePlan", "CareTeam", "Goal", "ImagingStudy", "Device",
}
BILLING_TYPES = {"Claim", "ExplanationOfBenefit"}


def render(record: PatientRecord, stats: PatientStats) -> None:
    s = record.summary
    st.title(f"Patient Overview — {stats.name}")

    # --- Top metrics row ---
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Total Resources", f"{stats.total_resources:,}")
    c2.metric("Clinical Resources", f"{stats.clinical_resource_count:,}")
    c3.metric("Billing Resources", f"{stats.billing_resource_count:,}", f"{stats.billing_pct:.1f}%")
    c4.metric("Complexity Score", f"{stats.complexity_score:.0f}/100")
    c5.metric("Complexity Tier", stats.complexity_tier.replace("_", " ").title())

    st.markdown("---")

    # --- Demographics + data span ---
    col_demo, col_span = st.columns([2, 1])

    with col_demo:
        st.subheader("Demographics")
        demo_data = {
            "Name": s.name,
            "Gender": s.gender.title(),
            "Date of Birth": str(s.birth_date) if s.birth_date else "—",
            "Age": f"{stats.age_years:.1f} years",
            "Status": "Deceased" if stats.is_deceased else "Living",
            "Race": s.race or "—",
            "Ethnicity": s.ethnicity or "—",
            "Location": f"{stats.city}, {stats.state}" if stats.city else "—",
            "Language": s.language or "—",
            "Marital Status": s.marital_status or "—",
        }
        if s.daly is not None:
            demo_data["DALY"] = f"{s.daly:.3f}"
        if s.qaly is not None:
            demo_data["QALY"] = f"{s.qaly:.3f}"

        df_demo = pd.DataFrame(list(demo_data.items()), columns=["Field", "Value"])
        st.dataframe(df_demo, hide_index=True, use_container_width=True)

    with col_span:
        st.subheader("Data Span")
        if stats.earliest_encounter_dt:
            st.metric("First Encounter", stats.earliest_encounter_dt.strftime("%Y-%m-%d"))
        if stats.latest_encounter_dt:
            st.metric("Last Encounter", stats.latest_encounter_dt.strftime("%Y-%m-%d"))
        if stats.years_of_history > 0:
            st.metric("Years of History", f"{stats.years_of_history:.1f}")
        st.metric("Encounters", stats.encounter_count)

    st.markdown("---")

    # --- Resource distribution chart ---
    st.subheader("Resource Distribution")

    chart_data = []
    for rtype, count in sorted(record.resource_type_counts.items(), key=lambda x: -x[1]):
        if rtype in BILLING_TYPES:
            category = "Billing"
        elif rtype in {"Organization", "Practitioner", "PractitionerRole", "Location"}:
            category = "Administrative"
        else:
            category = "Clinical"
        chart_data.append({"Resource Type": rtype, "Count": count, "Category": category})

    df_chart = pd.DataFrame(chart_data)
    color_map = {"Clinical": "#2196F3", "Billing": "#FF9800", "Administrative": "#9E9E9E"}
    fig = px.bar(
        df_chart,
        x="Count",
        y="Resource Type",
        color="Category",
        color_discrete_map=color_map,
        orientation="h",
        height=max(300, len(chart_data) * 28),
    )
    fig.update_layout(margin=dict(l=0, r=0, t=20, b=0), yaxis=dict(autorange="reversed"))
    st.plotly_chart(fig, use_container_width=True)

    st.markdown("---")

    # --- Conditions + Medications side by side ---
    col_cond, col_med = st.columns(2)

    with col_cond:
        st.subheader(f"Conditions ({stats.active_condition_count} active, {stats.resolved_condition_count} resolved)")
        if stats.condition_catalog:
            rows = []
            for c in stats.condition_catalog:
                rows.append({
                    "Status": "✅ Active" if c.is_active else "✔ Resolved",
                    "Condition": c.display,
                    "Onset": c.onset_dt.strftime("%Y-%m-%d") if c.onset_dt else "—",
                    "Resolved": c.abatement_dt.strftime("%Y-%m-%d") if c.abatement_dt else "—",
                })
            st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)
        else:
            st.info("No conditions recorded.")

    with col_med:
        st.subheader(f"Medications ({stats.active_med_count} active, {stats.total_med_count} total)")
        if stats.med_catalog:
            rows = []
            for m in stats.med_catalog:
                rows.append({
                    "Status": m.status.title(),
                    "Medication": m.display,
                    "Ordered": m.authored_on.strftime("%Y-%m-%d") if m.authored_on else "—",
                })
            st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)
        else:
            st.info("No medications recorded.")

    # --- Allergies + Immunizations ---
    col_allergy, col_imm = st.columns(2)

    with col_allergy:
        st.subheader(f"Allergies ({stats.allergy_count})")
        if stats.allergy_labels:
            for label in stats.allergy_labels:
                st.markdown(f"- {label}")
        else:
            st.info("No allergies recorded.")

    with col_imm:
        st.subheader(f"Immunizations ({stats.immunization_count})")
        if stats.unique_vaccines:
            for vaccine in stats.unique_vaccines:
                st.markdown(f"- {vaccine}")
        else:
            st.info("No immunizations recorded.")

    # --- Parse warnings ---
    if record.parse_warnings:
        with st.expander(f"⚠️ Parse Warnings ({len(record.parse_warnings)})"):
            for w in record.parse_warnings:
                st.text(w)
