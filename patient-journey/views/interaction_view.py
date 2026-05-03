"""
Drug Interactions View — displays detected drug-drug interactions
among the patient's medications with severity and clinical context.
"""

from __future__ import annotations

import streamlit as st

from lib.fhir_parser.models import PatientRecord
from lib.patient_catalog.single_patient import PatientStats

from lib.clinical.drug_classifier import DrugClassifier
from lib.clinical.interaction_checker import check_interactions, InteractionReport


_SEVERITY_ICONS = {
    "critical": "\U0001f534",  # red circle
    "warning": "\U0001f7e1",   # yellow circle
    "info": "\U0001f535",      # blue circle
}

_SEVERITY_LABELS = {
    "critical": "Critical",
    "warning": "Warning",
    "info": "Info",
}


def _render_interaction_card(interaction, idx: int) -> None:
    """Render a single interaction card."""
    icon = _SEVERITY_ICONS.get(interaction.severity, "")
    sev_label = _SEVERITY_LABELS.get(interaction.severity, interaction.severity)

    header = (
        f"{icon} **{interaction.label_a}** \u2194 **{interaction.label_b}** "
        f"\u2014 {sev_label}"
    )

    with st.expander(header, expanded=interaction.severity == "critical"):
        st.markdown(interaction.description)

        col_a, col_b = st.columns(2)

        with col_a:
            st.markdown(f"**{interaction.label_a} medications:**")
            for med in interaction.medications_a:
                status_icon = "\U0001f534" if med.status == "active" else "\u26aa"
                date_str = med.authored_on.strftime("%b %Y") if med.authored_on else "date unknown"
                st.markdown(f"- {status_icon} {med.display} ({med.status}, {date_str})")

        with col_b:
            st.markdown(f"**{interaction.label_b} medications:**")
            for med in interaction.medications_b:
                status_icon = "\U0001f534" if med.status == "active" else "\u26aa"
                date_str = med.authored_on.strftime("%b %Y") if med.authored_on else "date unknown"
                st.markdown(f"- {status_icon} {med.display} ({med.status}, {date_str})")


def render(record: PatientRecord, stats: PatientStats) -> None:
    """Render the Drug Interactions view."""
    st.title(f"Drug Interactions \u2014 {stats.name}")

    if not record.medications:
        st.info("No medications found in this patient's record.")
        return

    classifier = DrugClassifier()

    # Scope toggle
    active_only = st.toggle("Active medications only", value=True)

    report = check_interactions(
        record.medications,
        classifier=classifier,
        active_only=active_only,
    )

    # Summary metrics
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Interactions", report.total_count)
    col2.metric(
        "\U0001f534 Critical",
        report.critical_count,
    )
    col3.metric(
        "\U0001f7e1 Warnings",
        report.warning_count,
    )
    col4.metric(
        "\U0001f535 Info",
        report.info_count,
    )

    st.markdown("---")

    if report.total_count == 0:
        scope = "active" if active_only else "all"
        st.success(
            f"No drug interactions detected among {scope} medications. "
            f"({'Toggle to include historical medications for broader check.' if active_only else ''})"
        )
        return

    if report.has_critical:
        st.error(
            f"\u26a0\ufe0f {report.critical_count} critical interaction(s) detected. "
            "Review before proceeding with any procedure."
        )

    # Render interaction cards
    for i, interaction in enumerate(report.interactions):
        _render_interaction_card(interaction, i)

    # Disclaimer
    st.markdown("---")
    st.caption(
        "Drug interaction data is based on a curated rule set for surgical/pre-op "
        "settings. Always verify with current pharmacological references and "
        "clinical pharmacist consultation."
    )
