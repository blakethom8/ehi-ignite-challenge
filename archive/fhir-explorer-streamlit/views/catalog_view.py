"""
Page 4 — Code Catalogs
Tabbed view of all LOINC / SNOMED / RxNorm / CVX codes in this patient's record.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime

import pandas as pd
import plotly.express as px
import streamlit as st

from ..parser.models import PatientRecord
from ..catalog.single_patient import PatientStats


def render(record: PatientRecord, stats: PatientStats) -> None:
    st.title(f"Code Catalogs — {stats.name}")

    tab_loinc, tab_snomed, tab_rxnorm, tab_cvx = st.tabs([
        f"🔬 LOINC ({stats.unique_loinc_count})",
        f"🏥 SNOMED ({len(record.conditions) + len(record.procedures)})",
        f"💊 RxNorm ({len(record.medications)})",
        f"💉 CVX ({len(record.immunizations)})",
    ])

    # -------------------------------------------------------------------
    # LOINC tab
    # -------------------------------------------------------------------
    with tab_loinc:
        st.subheader("Observations by LOINC Code")

        if not stats.loinc_catalog:
            st.info("No LOINC-coded observations found.")
        else:
            # Category filter
            categories = sorted({e.category for e in stats.loinc_catalog if e.category})
            selected_cats = st.multiselect(
                "Filter by category",
                options=categories,
                default=categories,
                key="loinc_cat_filter",
            )

            filtered = [e for e in stats.loinc_catalog if e.category in selected_cats]

            rows = []
            for e in filtered:
                value_str = "—"
                if e.min_value is not None:
                    if e.min_value == e.max_value:
                        value_str = f"{e.last_value} {e.unit}".strip()
                    else:
                        value_str = f"{e.min_value:.1f}–{e.max_value:.1f} {e.unit}".strip()
                        if e.last_value is not None:
                            value_str += f"  (last: {e.last_value:.1f})"
                elif e.value_counts:
                    top = max(e.value_counts, key=e.value_counts.get)
                    value_str = f"{top} ({e.value_counts[top]}×)"

                rows.append({
                    "LOINC": e.code,
                    "Description": e.display,
                    "Category": e.category,
                    "Count": e.count,
                    "First": e.first_dt.strftime("%Y-%m-%d") if e.first_dt else "—",
                    "Last": e.last_dt.strftime("%Y-%m-%d") if e.last_dt else "—",
                    "Value Range": value_str,
                })

            df = pd.DataFrame(rows)
            st.dataframe(df, hide_index=True, use_container_width=True, height=400)

            # Trend sparkline for a selected LOINC code
            quantity_codes = [e for e in filtered if e.min_value is not None]
            if quantity_codes:
                st.markdown("---")
                st.subheader("Value Trend")
                selected_code = st.selectbox(
                    "Select observation to plot",
                    options=[e.code for e in quantity_codes],
                    format_func=lambda c: next(
                        (f"{e.display} ({e.unit})" for e in quantity_codes if e.code == c), c
                    ),
                    key="loinc_trend_select",
                )
                obs_ids = record.obs_by_loinc.get(selected_code, [])
                trend_rows = []
                for oid in obs_ids:
                    obs = record.obs_index.get(oid)
                    if obs and obs.value_type == "quantity" and obs.value_quantity is not None and obs.effective_dt:
                        trend_rows.append({"Date": obs.effective_dt, "Value": obs.value_quantity})

                if trend_rows:
                    df_trend = pd.DataFrame(trend_rows).sort_values("Date")
                    entry = next((e for e in quantity_codes if e.code == selected_code), None)
                    unit_label = entry.unit if entry else ""
                    fig = px.line(
                        df_trend,
                        x="Date",
                        y="Value",
                        markers=True,
                        labels={"Value": unit_label},
                        height=300,
                    )
                    fig.update_layout(margin=dict(l=0, r=0, t=10, b=0))
                    st.plotly_chart(fig, use_container_width=True)

    # -------------------------------------------------------------------
    # SNOMED tab
    # -------------------------------------------------------------------
    with tab_snomed:
        col_cond, col_proc = st.columns(2)

        with col_cond:
            st.subheader(f"Conditions ({len(record.conditions)})")
            if record.conditions:
                rows = []
                for c in sorted(record.conditions, key=lambda x: x.onset_dt or datetime.min):
                    rows.append({
                        "Status": "🔴 Active" if c.is_active else "✔ Resolved",
                        "Condition": c.code.label(),
                        "SNOMED": c.code.code,
                        "Onset": c.onset_dt.strftime("%Y-%m-%d") if c.onset_dt else "—",
                        "Resolved": c.abatement_dt.strftime("%Y-%m-%d") if c.abatement_dt else "—",
                    })
                st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True, height=400)
            else:
                st.info("No conditions recorded.")

        with col_proc:
            st.subheader(f"Procedures ({len(record.procedures)})")
            if record.procedures:
                proc_counts: dict[str, dict] = {}
                for p in record.procedures:
                    key = p.code.code or p.code.label()
                    if key not in proc_counts:
                        proc_counts[key] = {
                            "Procedure": p.code.label(),
                            "SNOMED": p.code.code,
                            "Count": 0,
                            "First": None,
                            "Last": None,
                        }
                    proc_counts[key]["Count"] += 1
                    dt = p.performed_period.start if p.performed_period else None
                    if dt:
                        if proc_counts[key]["First"] is None or dt < proc_counts[key]["First"]:
                            proc_counts[key]["First"] = dt
                        if proc_counts[key]["Last"] is None or dt > proc_counts[key]["Last"]:
                            proc_counts[key]["Last"] = dt

                rows = []
                for v in sorted(proc_counts.values(), key=lambda x: -x["Count"]):
                    rows.append({
                        "Procedure": v["Procedure"],
                        "SNOMED": v["SNOMED"],
                        "Count": v["Count"],
                        "First": v["First"].strftime("%Y-%m-%d") if v["First"] else "—",
                        "Last": v["Last"].strftime("%Y-%m-%d") if v["Last"] else "—",
                    })
                st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True, height=400)
            else:
                st.info("No procedures recorded.")

    # -------------------------------------------------------------------
    # RxNorm tab
    # -------------------------------------------------------------------
    with tab_rxnorm:
        st.subheader(f"Medications ({len(record.medications)})")
        if record.medications:
            rows = []
            for m in sorted(record.medications, key=lambda x: x.authored_on or datetime.min):
                rows.append({
                    "Status": m.status.title(),
                    "Medication": m.display,
                    "RxNorm": m.rxnorm_code,
                    "Ordered": m.authored_on.strftime("%Y-%m-%d") if m.authored_on else "—",
                    "As Needed": "Yes" if m.as_needed else "No",
                    "Dosage": m.dosage_text or "—",
                    "Reason": m.reason_display or "—",
                })
            df = pd.DataFrame(rows)

            # Status filter
            statuses = sorted(df["Status"].unique())
            selected_statuses = st.multiselect(
                "Filter by status",
                options=statuses,
                default=statuses,
                key="rxnorm_status_filter",
            )
            st.dataframe(
                df[df["Status"].isin(selected_statuses)],
                hide_index=True,
                use_container_width=True,
                height=400,
            )
        else:
            st.info("No medications recorded.")

    # -------------------------------------------------------------------
    # CVX tab
    # -------------------------------------------------------------------
    with tab_cvx:
        st.subheader(f"Immunizations ({len(record.immunizations)})")
        if record.immunizations:
            rows = []
            for i in sorted(record.immunizations, key=lambda x: x.occurrence_dt or datetime.min):
                rows.append({
                    "Vaccine": i.display,
                    "CVX": i.cvx_code,
                    "Date": i.occurrence_dt.strftime("%Y-%m-%d") if i.occurrence_dt else "—",
                    "Status": i.status,
                })
            st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)
        else:
            st.info("No immunizations recorded.")
