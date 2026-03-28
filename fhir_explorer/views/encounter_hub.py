"""
Page 3 — Encounter Hub
Select an encounter and see all linked resources in detail.
"""

from __future__ import annotations

from datetime import datetime

import pandas as pd
import streamlit as st

from ..parser.models import PatientRecord
from ..catalog.single_patient import PatientStats


def render(record: PatientRecord, stats: PatientStats) -> None:
    st.title(f"Encounter Hub — {stats.name}")

    if not record.encounters:
        st.info("No encounters found for this patient.")
        return

    # Sort encounters newest first for the selector
    encounters_sorted = sorted(
        record.encounters,
        key=lambda e: e.period.start or datetime.min,
        reverse=True,
    )

    # Build display labels
    def enc_label(enc) -> str:
        date_str = enc.period.start.strftime("%Y-%m-%d") if enc.period.start else "Unknown"
        n_linked = (
            len(enc.linked_observations) + len(enc.linked_conditions) +
            len(enc.linked_procedures) + len(enc.linked_medications) +
            len(enc.linked_immunizations)
        )
        return f"{date_str} — {enc.encounter_type or 'Encounter'} [{enc.class_code}] ({n_linked} resources)"

    col_sel, col_billing = st.columns([3, 1])
    with col_sel:
        selected_idx = st.selectbox(
            "Select encounter",
            range(len(encounters_sorted)),
            format_func=lambda i: enc_label(encounters_sorted[i]),
        )
    with col_billing:
        show_billing = st.checkbox("Show billing info", value=False)

    enc = encounters_sorted[selected_idx]
    st.markdown("---")

    # --- Encounter header ---
    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown(f"**Type:** {enc.encounter_type or '—'}")
        st.markdown(f"**Class:** {enc.class_code or '—'}")
        st.markdown(f"**Status:** {enc.status}")
        if enc.reason_display:
            st.markdown(f"**Reason:** {enc.reason_display}")
    with col2:
        if enc.period.start:
            st.markdown(f"**Date:** {enc.period.start.strftime('%Y-%m-%d')}")
            st.markdown(f"**Time:** {enc.period.start.strftime('%H:%M')}")
        if enc.period.end:
            dur = enc.period.duration_days()
            if dur is not None:
                dur_str = f"{dur * 24 * 60:.0f} min" if dur < 1 else f"{dur:.1f} days"
                st.markdown(f"**Duration:** {dur_str}")
    with col3:
        if enc.practitioner_name:
            st.markdown(f"**Provider:** {enc.practitioner_name}")
        if enc.provider_org:
            st.markdown(f"**Facility:** {enc.provider_org}")
        st.markdown(f"**ID:** `{enc.encounter_id[:12]}...`")

    st.markdown("---")

    # --- Clinical sections ---
    # Conditions
    if enc.linked_conditions:
        st.subheader(f"Conditions ({len(enc.linked_conditions)})")
        rows = []
        for cid in enc.linked_conditions:
            c = next((x for x in record.conditions if x.condition_id == cid), None)
            if c:
                rows.append({
                    "Status": "🔴 Active" if c.is_active else "✔ Resolved",
                    "Condition": c.code.label(),
                    "SNOMED": c.code.code,
                    "Onset": c.onset_dt.strftime("%Y-%m-%d") if c.onset_dt else "—",
                })
        st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)

    # Procedures
    if enc.linked_procedures:
        st.subheader(f"Procedures ({len(enc.linked_procedures)})")
        rows = []
        for pid in enc.linked_procedures:
            p = next((x for x in record.procedures if x.procedure_id == pid), None)
            if p:
                rows.append({
                    "Procedure": p.code.label(),
                    "Code": p.code.code,
                    "Status": p.status,
                    "Reason": p.reason_display or "—",
                })
        st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)

    # Medications
    if enc.linked_medications:
        st.subheader(f"Medications Ordered ({len(enc.linked_medications)})")
        rows = []
        for mid in enc.linked_medications:
            m = next((x for x in record.medications if x.med_id == mid), None)
            if m:
                rows.append({
                    "Medication": m.display,
                    "RxNorm": m.rxnorm_code,
                    "Status": m.status,
                    "As Needed": "Yes" if m.as_needed else "No",
                    "Dosage": m.dosage_text or "—",
                })
        st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)

    # Immunizations
    if enc.linked_immunizations:
        st.subheader(f"Immunizations ({len(enc.linked_immunizations)})")
        rows = []
        for iid in enc.linked_immunizations:
            i = next((x for x in record.immunizations if x.imm_id == iid), None)
            if i:
                rows.append({
                    "Vaccine": i.display,
                    "CVX": i.cvx_code,
                    "Status": i.status,
                    "Date": i.occurrence_dt.strftime("%Y-%m-%d") if i.occurrence_dt else "—",
                })
        st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)

    # Diagnostic Reports
    if enc.linked_diagnostic_reports:
        st.subheader(f"Diagnostic Reports ({len(enc.linked_diagnostic_reports)})")
        for rid in enc.linked_diagnostic_reports:
            dr = next((x for x in record.diagnostic_reports if x.report_id == rid), None)
            if dr:
                with st.expander(f"📋 {dr.code.label()} — {dr.category}"):
                    st.markdown(f"**Status:** {dr.status}")
                    if dr.effective_dt:
                        st.markdown(f"**Date:** {dr.effective_dt.strftime('%Y-%m-%d')}")
                    if dr.has_presented_form:
                        st.markdown("**Clinical Note:**")
                        st.text(dr.presented_form_text[:2000])
                    elif dr.result_refs:
                        st.markdown(f"**Results ({len(dr.result_refs)} observations):**")
                        rows = []
                        for oid in dr.result_refs:
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
                                rows.append({"Test": obs.display, "Value": val, "LOINC": obs.loinc_code})
                        if rows:
                            st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)

    # Observations (all, outside of reports)
    if enc.linked_observations:
        report_obs_ids = set()
        for rid in enc.linked_diagnostic_reports:
            dr = next((x for x in record.diagnostic_reports if x.report_id == rid), None)
            if dr:
                report_obs_ids.update(dr.result_refs)

        standalone_obs = [
            oid for oid in enc.linked_observations if oid not in report_obs_ids
        ]

        if standalone_obs:
            st.subheader(f"Observations ({len(standalone_obs)} standalone)")
            rows = []
            for oid in standalone_obs:
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
                    rows.append({
                        "Observation": obs.display,
                        "Category": obs.category,
                        "Value": val,
                        "LOINC": obs.loinc_code,
                    })
            st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)

    # --- Billing (toggle) ---
    if show_billing:
        st.markdown("---")
        st.subheader("Billing")
        claim = next((c for c in record.claims if c.encounter_id == enc.encounter_id), None)
        if claim:
            col_a, col_b, col_c = st.columns(3)
            col_a.metric("Total Billed", f"${claim.total_billed:,.2f}" if claim.total_billed else "—")
            col_b.metric("Total Paid", f"${claim.total_paid:,.2f}" if claim.total_paid else "—")
            col_c.metric("Insurer", claim.insurer or "—")
            st.markdown(f"**Claim Type:** {claim.claim_type or '—'}")
            if claim.billable_period.start:
                st.markdown(f"**Billable Period:** {claim.billable_period.start.strftime('%Y-%m-%d')}")
        else:
            st.info("No claim found for this encounter.")
