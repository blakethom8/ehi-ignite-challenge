"""
Medication History Deep Dive — full medication list with drug class
grouping, episode detection, and per-drug detail cards.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd
import streamlit as st

from lib.fhir_parser.models import PatientRecord
from lib.patient_catalog.single_patient import PatientStats

from core.drug_classifier import DrugClassifier
from core.episode_detector import MedicationEpisode, detect_medication_episodes


def _format_date(dt: datetime | None) -> str:
    if dt is None:
        return "—"
    return dt.strftime("%b %d, %Y")


def render(record: PatientRecord, stats: PatientStats) -> None:
    """Render the Medication History Deep Dive."""
    st.title(f"Medication History — {stats.name}")

    if not record.medications:
        st.info("No medications found in this patient's record.")
        return

    classifier = DrugClassifier()
    episodes = detect_medication_episodes(record.medications)

    # --- Summary metrics ---
    n_active = sum(1 for e in episodes if e.is_active)
    n_historical = len(episodes) - n_active
    n_total_requests = len(record.medications)

    col1, col2, col3 = st.columns(3)
    col1.metric("Unique Medications", len(episodes))
    col2.metric("Currently Active", n_active)
    col3.metric("Total Prescriptions", n_total_requests)

    st.markdown("---")

    # --- Filters ---
    col_status, col_class = st.columns(2)

    with col_status:
        status_filter = st.selectbox(
            "Status filter",
            ["All", "Active only", "Historical only"],
        )

    with col_class:
        all_classes = ["All"] + [
            info.label for info in
            [classifier.get_class_info(k) for k in classifier.class_keys]
            if info
        ]
        class_filter = st.selectbox("Drug class filter", all_classes)

    # --- Group by drug class ---
    # Classify each episode
    classified_episodes: list[tuple[MedicationEpisode, list[str]]] = []
    for ep in episodes:
        # Apply status filter
        if status_filter == "Active only" and not ep.is_active:
            continue
        if status_filter == "Historical only" and ep.is_active:
            continue

        from lib.fhir_parser.models import MedicationRecord
        dummy = MedicationRecord(display=ep.display, rxnorm_code=ep.rxnorm_code)
        classes = classifier.classify_medication(dummy)

        # Apply class filter
        if class_filter != "All":
            matching_labels = [
                classifier.get_class_info(c).label
                for c in classes
                if classifier.get_class_info(c)
            ]
            if class_filter not in matching_labels:
                continue

        classified_episodes.append((ep, classes))

    if not classified_episodes:
        st.info("No medications match the current filters.")
        return

    # --- Render medication cards ---
    for ep, classes in classified_episodes:
        active_icon = "🔴" if ep.is_active else "⚪"
        class_tags = ""
        if classes:
            labels = [
                classifier.get_class_info(c).label
                for c in classes
                if classifier.get_class_info(c)
            ]
            class_tags = " · ".join(f"`{l}`" for l in labels)

        header = (
            f"{active_icon} **{ep.display}** — "
            f"{_format_date(ep.start_date)} → "
            f"{_format_date(ep.end_date) if ep.end_date else 'ongoing'}"
        )

        with st.expander(header, expanded=ep.is_active):
            col_detail, col_meta = st.columns([3, 2])

            with col_detail:
                st.markdown(f"**Status:** {ep.status}")
                st.markdown(f"**Dosage:** {ep.dosage_text or '—'}")
                st.markdown(f"**Reason:** {ep.reason or '—'}")
                if ep.rxnorm_code:
                    st.markdown(f"**RxNorm:** `{ep.rxnorm_code}`")
                if class_tags:
                    st.markdown(f"**Drug Classes:** {class_tags}")

            with col_meta:
                duration = ep.duration_days
                if duration is not None:
                    if duration < 30:
                        dur_str = f"{duration:.0f} days"
                    elif duration < 365:
                        dur_str = f"{duration / 30:.1f} months"
                    else:
                        dur_str = f"{duration / 365:.1f} years"
                    st.metric("Duration", dur_str)
                elif ep.is_active and ep.start_date:
                    days = (datetime.now(timezone.utc) - ep.start_date).days
                    if days < 30:
                        dur_str = f"{days} days"
                    elif days < 365:
                        dur_str = f"{days / 30:.1f} months"
                    else:
                        dur_str = f"{days / 365:.1f} years"
                    st.metric("Active For", dur_str)

                st.metric("Prescription Count", len(ep.requests))

            # Individual prescription records
            if len(ep.requests) > 1:
                st.markdown("**Prescription History:**")
                req_rows = []
                for req in sorted(
                    ep.requests,
                    key=lambda r: r.authored_on or datetime.min.replace(tzinfo=timezone.utc),
                    reverse=True,
                ):
                    req_rows.append({
                        "Date": _format_date(req.authored_on),
                        "Status": req.status,
                        "Dosage": req.dosage_text or "—",
                        "Prescriber": req.requester or "—",
                    })
                st.dataframe(
                    pd.DataFrame(req_rows),
                    hide_index=True,
                    use_container_width=True,
                )
