"""
Condition & Episode Tracker — active vs. resolved conditions,
timeline of diagnoses, and linked medications per condition.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd
import plotly.express as px
import streamlit as st


def _naive(dt: datetime | None) -> datetime | None:
    """Strip timezone info for Plotly compatibility."""
    if dt is None:
        return None
    return dt.replace(tzinfo=None)

from lib.fhir_parser.models import PatientRecord
from lib.patient_catalog.single_patient import PatientStats

from core.episode_detector import ConditionEpisode, detect_condition_episodes


def _format_date(dt: datetime | None) -> str:
    if dt is None:
        return "—"
    return dt.strftime("%b %d, %Y")


def render(record: PatientRecord, stats: PatientStats) -> None:
    """Render the Condition & Episode Tracker."""
    st.title(f"Conditions — {stats.name}")

    if not record.conditions:
        st.info("No conditions found in this patient's record.")
        return

    episodes = detect_condition_episodes(record)

    # --- Summary metrics ---
    n_active = sum(1 for e in episodes if e.condition.is_active)
    n_resolved = sum(
        1 for e in episodes
        if e.condition.clinical_status == "resolved"
    )
    n_total = len(episodes)

    col1, col2, col3 = st.columns(3)
    col1.metric("Total Conditions", n_total)
    col2.metric("Active", n_active)
    col3.metric("Resolved", n_resolved)

    st.markdown("---")

    # --- Condition timeline chart ---
    st.subheader("Diagnosis Timeline")

    timeline_data = []
    for ep in episodes:
        cond = ep.condition
        if cond.onset_dt:
            timeline_data.append({
                "Condition": cond.code.label(),
                "Onset": _naive(cond.onset_dt),
                "End": _naive(cond.abatement_dt) or datetime.now().replace(tzinfo=None),
                "Status": "Active" if cond.is_active else cond.clinical_status.capitalize(),
            })

    if timeline_data:
        df = pd.DataFrame(timeline_data)
        fig = px.timeline(
            df,
            x_start="Onset",
            x_end="End",
            y="Condition",
            color="Status",
            color_discrete_map={
                "Active": "#e74c3c",
                "Resolved": "#95a5a6",
                "Inactive": "#bdc3c7",
                "Remission": "#2ecc71",
            },
            height=max(300, len(timeline_data) * 30 + 100),
        )
        fig.update_layout(
            yaxis=dict(autorange="reversed"),
            margin=dict(l=10, r=10, t=10, b=30),
            showlegend=True,
            legend=dict(orientation="h", yanchor="bottom", y=1.02),
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No conditions with onset dates available for timeline.")

    st.markdown("---")

    # --- Filters ---
    status_filter = st.selectbox(
        "Filter by status",
        ["All", "Active", "Resolved", "Inactive"],
    )

    # --- Condition cards ---
    st.subheader("Condition Details")

    for ep in episodes:
        cond = ep.condition

        # Apply filter
        if status_filter == "Active" and not cond.is_active:
            continue
        if status_filter == "Resolved" and cond.clinical_status != "resolved":
            continue
        if status_filter == "Inactive" and cond.clinical_status != "inactive":
            continue

        status_icon = "🔴" if cond.is_active else "✔️"
        status_text = "Active" if cond.is_active else cond.clinical_status.capitalize()

        header = (
            f"{status_icon} **{cond.code.label()}** — "
            f"{status_text} · onset {_format_date(cond.onset_dt)}"
        )

        with st.expander(header, expanded=cond.is_active):
            col_detail, col_meta = st.columns([3, 2])

            with col_detail:
                st.markdown(f"**Clinical Status:** {cond.clinical_status or '—'}")
                st.markdown(f"**Verification:** {cond.verification_status or '—'}")
                st.markdown(f"**Onset:** {_format_date(cond.onset_dt)}")
                if cond.abatement_dt:
                    st.markdown(f"**Resolved:** {_format_date(cond.abatement_dt)}")
                if cond.code.system:
                    st.markdown(f"**Code System:** `{cond.code.system}`")
                if cond.code.code:
                    st.markdown(f"**Code:** `{cond.code.code}`")

            with col_meta:
                # Duration
                if cond.onset_dt:
                    end = cond.abatement_dt or datetime.now(timezone.utc)
                    days = (end - cond.onset_dt).days
                    if days < 30:
                        dur_str = f"{days} days"
                    elif days < 365:
                        dur_str = f"{days / 30:.1f} months"
                    else:
                        dur_str = f"{days / 365:.1f} years"
                    label = "Active For" if cond.is_active else "Duration"
                    st.metric(label, dur_str)

            # Related encounters
            if ep.related_encounters:
                st.markdown("**Related Encounters:**")
                for enc in ep.related_encounters:
                    enc_date = _format_date(enc.period.start)
                    st.markdown(
                        f"&nbsp;&nbsp; 🏥 {enc.encounter_type or 'Visit'} "
                        f"(`{enc.class_code}`) — {enc_date} "
                        f"at {enc.provider_org or '—'}"
                    )

            # Related medications
            if ep.related_medications:
                st.markdown("**Related Medications:**")
                for med in ep.related_medications:
                    med_date = _format_date(med.authored_on)
                    active_badge = "🔴" if med.status == "active" else "⚪"
                    st.markdown(
                        f"&nbsp;&nbsp; {active_badge} 💊 {med.display} "
                        f"— {med.status} · {med_date}"
                    )
