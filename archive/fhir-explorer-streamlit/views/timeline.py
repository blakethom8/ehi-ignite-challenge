"""
Page 2 — Patient Timeline
Chronological event stream with density chart and expandable encounter cards.
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
    st.title(f"Timeline — {stats.name}")

    if not record.encounters:
        st.info("No encounters found for this patient.")
        return

    # Sort encounters chronologically
    encounters_sorted = sorted(
        record.encounters,
        key=lambda e: e.period.start or datetime.min,
    )

    earliest = encounters_sorted[0].period.start
    latest = encounters_sorted[-1].period.start

    # --- Density chart ---
    st.subheader("Encounter Density by Year")
    year_counts: dict[int, int] = defaultdict(int)
    for enc in record.encounters:
        if enc.period.start:
            year_counts[enc.period.start.year] += 1

    if year_counts:
        years = sorted(year_counts.keys())
        df_density = pd.DataFrame({
            "Year": years,
            "Encounters": [year_counts[y] for y in years],
        })
        fig = px.bar(df_density, x="Year", y="Encounters", height=200)
        fig.update_layout(margin=dict(l=0, r=0, t=10, b=0))
        st.plotly_chart(fig, use_container_width=True)

    st.markdown("---")

    # --- Date range filter ---
    col_from, col_to, col_filter = st.columns([2, 2, 3])

    min_year = earliest.year if earliest else 2000
    max_year = latest.year if latest else 2025

    with col_from:
        year_from = st.number_input("From year", min_value=min_year, max_value=max_year, value=min_year)
    with col_to:
        year_to = st.number_input("To year", min_value=min_year, max_value=max_year, value=max_year)
    with col_filter:
        show_only = st.multiselect(
            "Show only encounters with",
            ["Conditions", "Procedures", "Medications", "Lab Results", "Immunizations"],
        )

    # --- Filter encounters ---
    filtered = []
    for enc in encounters_sorted:
        if enc.period.start:
            year = enc.period.start.year
            if year < year_from or year > year_to:
                continue
        if "Conditions" in show_only and not enc.linked_conditions:
            continue
        if "Procedures" in show_only and not enc.linked_procedures:
            continue
        if "Medications" in show_only and not enc.linked_medications:
            continue
        if "Lab Results" in show_only and not enc.linked_observations:
            continue
        if "Immunizations" in show_only and not enc.linked_immunizations:
            continue
        filtered.append(enc)

    st.subheader(f"Encounters ({len(filtered)} shown)")

    if not filtered:
        st.info("No encounters match the current filters.")
        return

    # --- Group by year ---
    by_year: dict[int, list] = defaultdict(list)
    for enc in filtered:
        year = enc.period.start.year if enc.period.start else 0
        by_year[year].append(enc)

    for year in sorted(by_year.keys(), reverse=True):
        year_encs = by_year[year]
        st.markdown(f"### {year}  `{len(year_encs)} visit{'s' if len(year_encs) != 1 else ''}`")

        for enc in year_encs:
            date_str = enc.period.start.strftime("%b %d") if enc.period.start else "Unknown date"
            enc_type = enc.encounter_type or "Encounter"
            class_badge = f"`{enc.class_code}`" if enc.class_code else ""

            # Resource summary for this encounter
            n_obs = len(enc.linked_observations)
            n_cond = len(enc.linked_conditions)
            n_proc = len(enc.linked_procedures)
            n_med = len(enc.linked_medications)
            n_imm = len(enc.linked_immunizations)
            n_dr = len(enc.linked_diagnostic_reports)

            parts = []
            if n_obs:
                parts.append(f"{n_obs} obs")
            if n_cond:
                parts.append(f"{n_cond} cond")
            if n_proc:
                parts.append(f"{n_proc} proc")
            if n_med:
                parts.append(f"{n_med} med")
            if n_imm:
                parts.append(f"{n_imm} imm")
            if n_dr:
                parts.append(f"{n_dr} report")

            resource_summary = " · ".join(parts) if parts else "no linked resources"
            provider = f" · {enc.practitioner_name}" if enc.practitioner_name else ""
            org = f" · {enc.provider_org}" if enc.provider_org else ""

            label = f"**{date_str}** — {enc_type} {class_badge}  |  {resource_summary}{provider}{org}"

            with st.expander(label):
                col_left, col_right = st.columns(2)

                with col_left:
                    st.markdown(f"**Encounter ID:** `{enc.encounter_id[:8]}...`")
                    st.markdown(f"**Status:** {enc.status}")
                    st.markdown(f"**Type:** {enc.encounter_type or '—'}")
                    st.markdown(f"**Class:** {enc.class_code or '—'}")
                    if enc.reason_display:
                        st.markdown(f"**Reason:** {enc.reason_display}")
                    if enc.period.start:
                        st.markdown(f"**Start:** {enc.period.start.strftime('%Y-%m-%d %H:%M')}")
                    if enc.period.end:
                        duration = enc.period.duration_days()
                        if duration is not None:
                            dur_str = f"{duration * 24 * 60:.0f} min" if duration < 1 else f"{duration:.1f} days"
                            st.markdown(f"**Duration:** {dur_str}")
                    if enc.practitioner_name:
                        st.markdown(f"**Provider:** {enc.practitioner_name}")
                    if enc.provider_org:
                        st.markdown(f"**Facility:** {enc.provider_org}")

                with col_right:
                    # Conditions diagnosed
                    if enc.linked_conditions:
                        st.markdown("**Conditions:**")
                        for cid in enc.linked_conditions:
                            cond = next((c for c in record.conditions if c.condition_id == cid), None)
                            if cond:
                                status_icon = "🔴" if cond.is_active else "✔"
                                st.markdown(f"  {status_icon} {cond.code.label()}")

                    # Procedures
                    if enc.linked_procedures:
                        st.markdown("**Procedures:**")
                        for pid in enc.linked_procedures:
                            proc = next((p for p in record.procedures if p.procedure_id == pid), None)
                            if proc:
                                st.markdown(f"  • {proc.code.label()}")

                    # Medications ordered
                    if enc.linked_medications:
                        st.markdown("**Medications Ordered:**")
                        for mid in enc.linked_medications:
                            med = next((m for m in record.medications if m.med_id == mid), None)
                            if med:
                                st.markdown(f"  💊 {med.display} `{med.status}`")

                    # Immunizations
                    if enc.linked_immunizations:
                        st.markdown("**Immunizations:**")
                        for iid in enc.linked_immunizations:
                            imm = next((i for i in record.immunizations if i.imm_id == iid), None)
                            if imm:
                                st.markdown(f"  💉 {imm.display}")

                # Observations table
                if enc.linked_observations:
                    obs_rows = []
                    for oid in enc.linked_observations:
                        obs = record.obs_index.get(oid)
                        if obs:
                            if obs.value_type == "quantity":
                                val = f"{obs.value_quantity} {obs.value_unit}".strip()
                            elif obs.value_type == "codeable_concept":
                                val = obs.value_concept_display or "—"
                            elif obs.value_type == "component":
                                val = " / ".join(
                                    f"{c.display}: {c.value} {c.unit}".strip()
                                    for c in obs.components
                                )
                            else:
                                val = "—"
                            obs_rows.append({
                                "Observation": obs.display,
                                "Category": obs.category,
                                "Value": val,
                            })
                    if obs_rows:
                        st.markdown("**Observations:**")
                        st.dataframe(
                            pd.DataFrame(obs_rows),
                            hide_index=True,
                            use_container_width=True,
                        )
