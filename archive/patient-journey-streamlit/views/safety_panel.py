"""
Pre-Op Surgical Safety Panel — auto-populated drug class flags.

Scans the patient's medication history and flags drug categories
relevant to surgical safety: anticoagulants, immunosuppressants,
opioid history, JAK inhibitors, etc.
"""

from __future__ import annotations

from datetime import datetime

import streamlit as st

from lib.fhir_parser.models import PatientRecord
from lib.patient_catalog.single_patient import PatientStats

from lib.clinical.drug_classifier import DrugClassifier, SafetyFlag


# Severity → visual styling
_STATUS_BADGES = {
    "ACTIVE": ("🔴", "red"),
    "HISTORICAL": ("🟡", "orange"),
    "NONE": ("✅", "green"),
}

_SEVERITY_ICONS = {
    "critical": "⚠️",
    "warning": "⚡",
    "info": "ℹ️",
}


def _format_date(dt: datetime | None) -> str:
    if dt is None:
        return "—"
    return dt.strftime("%b %Y")


def _render_flag(flag: SafetyFlag) -> None:
    """Render a single safety flag row."""
    status_icon, color = _STATUS_BADGES.get(flag.status, ("❓", "gray"))
    severity_icon = _SEVERITY_ICONS.get(flag.severity, "")

    # Header row
    col_icon, col_label, col_status = st.columns([0.5, 4, 2])
    with col_icon:
        st.markdown(f"### {severity_icon}")
    with col_label:
        st.markdown(f"**{flag.label}**")
        if flag.status != "NONE":
            st.caption(flag.surgical_note)
    with col_status:
        st.markdown(f"### {status_icon} {flag.status}")

    # Medication details (if any found)
    if flag.medications:
        for cm in flag.medications:
            med = cm.medication
            active_badge = "🔴 ACTIVE" if cm.is_active else "⚪ stopped"
            date_str = _format_date(med.authored_on)
            dosage = f" — {med.dosage_text}" if med.dosage_text else ""
            reason = f" (for {med.reason_display})" if med.reason_display else ""

            st.markdown(
                f"&nbsp;&nbsp;&nbsp;&nbsp; 💊 **{med.display}** "
                f"`{active_badge}` · prescribed {date_str}{dosage}{reason}"
            )

    st.markdown("---")


def render(record: PatientRecord, stats: PatientStats) -> None:
    """Render the Pre-Op Surgical Safety Panel."""
    st.title(f"Pre-Op Safety Panel — {stats.name}")
    st.caption(
        "Auto-scanned from medication history. "
        "Flags drug classes with surgical risk implications."
    )

    if not record.medications:
        st.info("No medications found in this patient's record.")
        return

    classifier = DrugClassifier()
    flags = classifier.generate_safety_flags(record.medications)

    # Summary counts at the top
    n_active = sum(1 for f in flags if f.status == "ACTIVE")
    n_historical = sum(1 for f in flags if f.status == "HISTORICAL")
    n_clear = sum(1 for f in flags if f.status == "NONE")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Medications", len(record.medications))
    col2.metric("Active Flags", n_active)
    col3.metric("Historical Flags", n_historical)
    col4.metric("Clear", n_clear)

    st.markdown("---")

    # Filter controls
    show_clear = st.checkbox("Show clear (no match) categories", value=False)

    # Render each flag
    for flag in flags:
        if flag.status == "NONE" and not show_clear:
            continue
        _render_flag(flag)
