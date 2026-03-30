"""
Patient Journey Timeline — Plotly Gantt-style medication timeline
with clinical events overlaid as markers.

Each medication is displayed as a horizontal bar showing its active
date range. Encounters, procedures, and diagnoses appear as markers
on the timeline.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st


def _naive(dt: datetime | None) -> datetime | None:
    """Strip timezone info for Plotly compatibility."""
    if dt is None:
        return None
    return dt.replace(tzinfo=None)

from fhir_explorer.parser.models import PatientRecord
from fhir_explorer.catalog.single_patient import PatientStats

from core.drug_classifier import DrugClassifier
from core.episode_detector import MedicationEpisode, detect_medication_episodes


# Drug class → color mapping for Gantt bars
_CLASS_COLORS: dict[str, str] = {
    "anticoagulants": "#e74c3c",
    "antiplatelets": "#c0392b",
    "ace_inhibitors": "#e67e22",
    "arbs": "#d35400",
    "jak_inhibitors": "#8e44ad",
    "immunosuppressants": "#9b59b6",
    "nsaids": "#f39c12",
    "opioids": "#e74c3c",
    "anticonvulsants": "#3498db",
    "psych_medications": "#2ecc71",
    "stimulants": "#1abc9c",
    "diabetes_medications": "#34495e",
}

_DEFAULT_COLOR = "#95a5a6"

# Encounter class → marker styling
_ENCOUNTER_MARKERS: dict[str, dict] = {
    "EMER": {"symbol": "diamond", "color": "#e74c3c", "label": "Emergency"},
    "IMP": {"symbol": "square", "color": "#e67e22", "label": "Inpatient"},
    "AMB": {"symbol": "circle", "color": "#3498db", "label": "Ambulatory"},
}


def _get_bar_color(episode: MedicationEpisode, classifier: DrugClassifier) -> str:
    """Pick a color based on the medication's drug class."""
    from fhir_explorer.parser.models import MedicationRecord
    dummy = MedicationRecord(
        display=episode.display,
        rxnorm_code=episode.rxnorm_code,
    )
    classes = classifier.classify_medication(dummy)
    if classes:
        return _CLASS_COLORS.get(classes[0], _DEFAULT_COLOR)
    return _DEFAULT_COLOR


def render(record: PatientRecord, stats: PatientStats) -> None:
    """Render the Patient Journey Timeline."""
    st.title(f"Patient Journey — {stats.name}")
    st.caption(
        "Medication durations shown as horizontal bars (Gantt-style). "
        "Clinical encounters overlaid as markers."
    )

    if not record.medications:
        st.info("No medications found in this patient's record.")
        return

    # --- Detect medication episodes ---
    episodes = detect_medication_episodes(record.medications)
    dated_episodes = [e for e in episodes if e.start_date]

    if not dated_episodes:
        st.warning("No medications with dates found — cannot build timeline.")
        return

    classifier = DrugClassifier()

    # --- Filter controls ---
    col_range, col_filter = st.columns([3, 3])

    all_starts = [e.start_date for e in dated_episodes if e.start_date]
    all_ends = [e.end_date for e in dated_episodes if e.end_date]
    global_min = min(all_starts).year if all_starts else 2000
    global_max = max(
        max(e.year for e in all_ends) if all_ends else datetime.now(timezone.utc).year,
        datetime.now(timezone.utc).year,
    )

    with col_range:
        year_range = st.slider(
            "Year range",
            min_value=global_min,
            max_value=global_max,
            value=(global_min, global_max),
        )

    with col_filter:
        show_options = st.multiselect(
            "Overlay",
            ["Encounters", "Procedures", "Diagnoses"],
            default=["Encounters"],
        )

    show_active_only = st.checkbox("Show only active medications", value=False)

    # --- Build Gantt figure ---
    range_start = datetime(year_range[0], 1, 1, tzinfo=timezone.utc)
    range_end = datetime(year_range[1], 12, 31, tzinfo=timezone.utc)
    now = datetime.now(timezone.utc)

    filtered_episodes = []
    for ep in dated_episodes:
        if show_active_only and not ep.is_active:
            continue
        ep_end = ep.end_date or now
        if ep.start_date and ep.start_date <= range_end and ep_end >= range_start:
            filtered_episodes.append(ep)

    if not filtered_episodes:
        st.info("No medications match the current filters.")
        return

    # Sort by start date for a clean layout
    filtered_episodes.sort(key=lambda e: e.start_date or datetime.min.replace(tzinfo=timezone.utc))

    # Build medication bars as a DataFrame for px.timeline
    med_rows = []
    for ep in filtered_episodes:
        start = ep.start_date or range_start
        end = ep.end_date or now
        # Ensure minimum visible width (7 days)
        if (end - start).days < 7:
            end = start + timedelta(days=7)

        color = _get_bar_color(ep, classifier)
        active_label = " (active)" if ep.is_active else ""

        med_rows.append({
            "Medication": ep.display,
            "Start": _naive(start),
            "End": _naive(end),
            "Status": "Active" if ep.is_active else ep.status,
            "Color": color,
            "Hover": (
                f"<b>{ep.display}</b>{active_label}<br>"
                f"Start: {start.strftime('%b %d, %Y')}<br>"
                f"End: {end.strftime('%b %d, %Y') if ep.end_date else 'ongoing'}<br>"
                f"Status: {ep.status}<br>"
                f"Dosage: {ep.dosage_text or '—'}<br>"
                f"Reason: {ep.reason or '—'}"
            ),
        })

    med_df = pd.DataFrame(med_rows)
    fig = px.timeline(
        med_df,
        x_start="Start",
        x_end="End",
        y="Medication",
        color="Status",
        custom_data=["Hover"],
    )
    fig.update_traces(hovertemplate="%{customdata[0]}<extra></extra>")

    # --- Overlay encounter markers ---
    if "Encounters" in show_options and record.encounters:
        for class_code, style in _ENCOUNTER_MARKERS.items():
            encs = [
                e for e in record.encounters
                if e.class_code == class_code
                and e.period.start
                and range_start <= e.period.start <= range_end
            ]
            if encs:
                fig.add_trace(go.Scatter(
                    x=[_naive(e.period.start) for e in encs],
                    y=[filtered_episodes[0].display] * len(encs),  # pin to top row
                    mode="markers",
                    marker=dict(
                        symbol=style["symbol"],
                        size=8,
                        color=style["color"],
                        line=dict(width=1, color="white"),
                    ),
                    name=style["label"],
                    hovertext=[
                        f"<b>{style['label']}</b><br>"
                        f"{e.encounter_type or class_code}<br>"
                        f"{e.period.start.strftime('%b %d, %Y')}<br>"
                        f"{e.reason_display or ''}"
                        for e in encs
                    ],
                    hoverinfo="text",
                    showlegend=True,
                ))

    # --- Overlay procedures ---
    if "Procedures" in show_options and record.procedures:
        procs_dated = [
            p for p in record.procedures
            if p.performed_period and p.performed_period.start
            and range_start <= p.performed_period.start <= range_end
        ]
        if procs_dated:
            fig.add_trace(go.Scatter(
                x=[_naive(p.performed_period.start) for p in procs_dated],
                y=[filtered_episodes[0].display] * len(procs_dated),
                mode="markers",
                marker=dict(
                    symbol="cross",
                    size=10,
                    color="#2c3e50",
                    line=dict(width=1, color="white"),
                ),
                name="Procedures",
                hovertext=[
                    f"<b>Procedure</b><br>{p.code.label()}<br>"
                    f"{p.performed_period.start.strftime('%b %d, %Y')}"
                    for p in procs_dated
                ],
                hoverinfo="text",
                showlegend=True,
            ))

    # --- Overlay diagnoses ---
    if "Diagnoses" in show_options and record.conditions:
        conds_dated = [
            c for c in record.conditions
            if c.onset_dt and range_start <= c.onset_dt <= range_end
        ]
        if conds_dated:
            fig.add_trace(go.Scatter(
                x=[_naive(c.onset_dt) for c in conds_dated],
                y=[filtered_episodes[0].display] * len(conds_dated),
                mode="markers",
                marker=dict(
                    symbol="star",
                    size=9,
                    color="#8e44ad",
                    line=dict(width=1, color="white"),
                ),
                name="Diagnoses",
                hovertext=[
                    f"<b>Diagnosis</b><br>{c.code.label()}<br>"
                    f"{c.onset_dt.strftime('%b %d, %Y')}<br>"
                    f"Status: {c.clinical_status}"
                    for c in conds_dated
                ],
                hoverinfo="text",
                showlegend=True,
            ))

    # Layout
    height = max(400, len(filtered_episodes) * 28 + 120)
    fig.update_layout(
        barmode="overlay",
        height=height,
        xaxis=dict(
            title="",
            type="date",
            range=[_naive(range_start), _naive(range_end)],
        ),
        yaxis=dict(
            title="",
            autorange="reversed",
            dtick=1,
        ),
        margin=dict(l=10, r=10, t=30, b=30),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1,
        ),
        hoverlabel=dict(align="left"),
    )

    st.plotly_chart(fig, use_container_width=True)

    # --- Summary table below ---
    st.subheader("Medication Episodes")

    rows = []
    for ep in filtered_episodes:
        classes = classifier.classify_medication(
            type("M", (), {"display": ep.display, "rxnorm_code": ep.rxnorm_code})()  # type: ignore[arg-type]
        )
        rows.append({
            "Medication": ep.display,
            "Status": "🔴 Active" if ep.is_active else f"⚪ {ep.status}",
            "Start": ep.start_date.strftime("%Y-%m-%d") if ep.start_date else "—",
            "End": ep.end_date.strftime("%Y-%m-%d") if ep.end_date else "ongoing",
            "Drug Classes": ", ".join(classes) if classes else "—",
            "Dosage": ep.dosage_text or "—",
            "Reason": ep.reason or "—",
        })

    if rows:
        st.dataframe(
            pd.DataFrame(rows),
            hide_index=True,
            use_container_width=True,
        )
