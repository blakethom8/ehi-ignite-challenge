"""
Page 7 — Signal vs. Noise
LLM inclusion model, token budget estimator, and context preview generator.
This page directly informs what we send to the LLM in the patient-facing app.
"""

from __future__ import annotations

from datetime import datetime, timezone, timedelta

import pandas as pd
import streamlit as st

from ..parser.models import PatientRecord
from ..catalog.single_patient import PatientStats

# ---------------------------------------------------------------------------
# Signal tier definitions
# ---------------------------------------------------------------------------

TIERS = {
    1: {
        "label": "Always Include",
        "color": "#4CAF50",
        "icon": "✅",
        "resource_types": ["Patient", "AllergyIntolerance"],
        "description": "Core identity and safety-critical data. Always in context.",
    },
    2: {
        "label": "Include (Active Clinical)",
        "color": "#2196F3",
        "icon": "🔵",
        "resource_types": ["Condition (active)", "MedicationRequest (active)", "CarePlan", "Goal"],
        "description": "Active clinical state. Include in full.",
    },
    3: {
        "label": "Include Summarized",
        "color": "#FFC107",
        "icon": "🟡",
        "resource_types": ["Encounter (recent)", "Observation (recent)", "Immunization", "DiagnosticReport (recent)"],
        "description": "Recent activity. Summarize by time window rather than including all records.",
    },
    4: {
        "label": "Include on Request",
        "color": "#FF9800",
        "icon": "🟠",
        "resource_types": ["Condition (resolved)", "MedicationRequest (historical)", "Observation (all)", "Procedure", "ImagingStudy"],
        "description": "Historical data. Include only when the patient or query requires it.",
    },
    5: {
        "label": "Exclude Default",
        "color": "#F44336",
        "icon": "❌",
        "resource_types": ["Claim", "ExplanationOfBenefit", "Organization", "Practitioner", "PractitionerRole", "Location", "Device"],
        "description": "Billing and administrative noise. Excluded from LLM context by default.",
    },
}

# Rough token estimates per resource (based on typical JSON size / 4 chars per token)
TOKENS_PER_RESOURCE = {
    "Patient": 150,
    "AllergyIntolerance": 80,
    "Condition": 60,
    "MedicationRequest": 80,
    "Encounter": 100,
    "Observation": 50,
    "Procedure": 60,
    "DiagnosticReport": 80,
    "Immunization": 50,
    "CarePlan": 120,
    "CareTeam": 80,
    "Goal": 60,
    "ImagingStudy": 70,
    "Claim": 120,
    "ExplanationOfBenefit": 150,
}


def render(record: PatientRecord, stats: PatientStats) -> None:
    st.title(f"Signal vs. Noise — {stats.name}")
    st.markdown(
        "Design the LLM context strategy. Decide what to include, what to summarize, "
        "and what to exclude — then preview the actual context that would be sent."
    )

    # --- Tier table ---
    st.subheader("LLM Inclusion Tiers")
    for tier_num, tier in TIERS.items():
        with st.expander(f"{tier['icon']} Tier {tier_num}: {tier['label']}", expanded=(tier_num <= 3)):
            st.markdown(f"_{tier['description']}_")
            st.markdown("**Resource types:** " + ", ".join(f"`{r}`" for r in tier["resource_types"]))

    st.markdown("---")

    # --- Token budget controls ---
    st.subheader("Token Budget Estimator")

    col_budget, col_window = st.columns(2)
    with col_budget:
        token_budget = st.slider(
            "Target token budget",
            min_value=1000,
            max_value=100000,
            value=16000,
            step=1000,
            help="Typical: 8K for fast models, 16K for balanced, 32K+ for comprehensive",
        )
    with col_window:
        recent_years = st.slider(
            "Recency window for Tier 3 (years)",
            min_value=1,
            max_value=20,
            value=2,
            help="How many years back to include for Encounters, Observations, DiagnosticReports",
        )

    # Calculate what fits
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=recent_years * 365)

    # Count resources per tier
    tier_resource_counts = _count_tier_resources(record, cutoff)

    # Token estimates
    token_data = []
    cumulative_tokens = 0
    for tier_num, tier in TIERS.items():
        counts = tier_resource_counts.get(tier_num, {})
        tier_tokens = sum(
            cnt * TOKENS_PER_RESOURCE.get(rtype, 60)
            for rtype, cnt in counts.items()
        )
        total_count = sum(counts.values())
        cumulative_tokens += tier_tokens

        token_data.append({
            "Tier": f"{tier['icon']} {tier['label']}",
            "Resources": total_count,
            "Est. Tokens": tier_tokens,
            "Cumulative Tokens": cumulative_tokens,
            "Fits in Budget": "✅" if cumulative_tokens <= token_budget else "⚠️ Over",
        })

    st.dataframe(pd.DataFrame(token_data), hide_index=True, use_container_width=True)

    total_estimated = sum(r["Est. Tokens"] for r in token_data if r["Tier"].startswith(("✅", "🔵", "🟡")))
    st.metric(
        "Estimated tokens for Tiers 1–3",
        f"{total_estimated:,}",
        f"{'Within' if total_estimated <= token_budget else 'Exceeds'} {token_budget:,} token budget",
    )

    st.markdown("---")

    # --- LLM Context Preview ---
    st.subheader("Generate LLM Context Preview")
    st.markdown(
        "Shows the plain-text context block as it would be sent to the LLM. "
        "Tiers 1–3 are included by default. Tier 4 is optional."
    )

    include_tier4 = st.checkbox("Include Tier 4 (historical data)", value=False)

    if st.button("Generate Context Preview", type="primary"):
        context = _generate_context(record, stats, cutoff, include_tier4)
        char_count = len(context)
        token_estimate = char_count // 4

        col_a, col_b = st.columns(2)
        col_a.metric("Characters", f"{char_count:,}")
        col_b.metric("Est. Tokens", f"{token_estimate:,}")

        st.text_area("LLM Context Block", value=context, height=600)

        st.download_button(
            label="⬇️ Download context as .txt",
            data=context,
            file_name=f"llm_context_{stats.name.replace(' ', '_')}.txt",
            mime="text/plain",
        )


def _count_tier_resources(record: PatientRecord, cutoff: datetime) -> dict[int, dict[str, int]]:
    """Count resources per tier given the recency cutoff."""

    def make_aware(dt):
        if dt and dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt

    cutoff_aware = make_aware(cutoff)

    return {
        1: {
            "Patient": 1,
            "AllergyIntolerance": len(record.allergies),
        },
        2: {
            "Condition (active)": sum(1 for c in record.conditions if c.is_active),
            "MedicationRequest (active)": sum(1 for m in record.medications if m.status in ("active", "on-hold")),
            "CarePlan": len(record.care_plans_raw),
            "Goal": len(record.goals_raw),
        },
        3: {
            "Encounter (recent)": sum(
                1 for e in record.encounters
                if e.period.start and make_aware(e.period.start) >= cutoff_aware
            ),
            "Observation (recent)": sum(
                1 for o in record.observations
                if o.effective_dt and make_aware(o.effective_dt) >= cutoff_aware
            ),
            "Immunization": len(record.immunizations),
        },
        4: {
            "Condition (resolved)": sum(1 for c in record.conditions if not c.is_active),
            "MedicationRequest (hist.)": sum(1 for m in record.medications if m.status not in ("active", "on-hold")),
            "Procedure": len(record.procedures),
        },
        5: {
            "Claim": len(record.claims),
            "ExplanationOfBenefit": record.resource_type_counts.get("ExplanationOfBenefit", 0),
        },
    }


def _generate_context(
    record: PatientRecord,
    stats: PatientStats,
    cutoff: datetime,
    include_tier4: bool,
) -> str:
    """Generate a plain-text LLM context block for this patient."""
    s = record.summary
    lines = []

    def make_aware(dt):
        if dt and dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt

    cutoff_aware = make_aware(cutoff)

    # --- TIER 1: Patient identity ---
    lines.append("=== PATIENT PROFILE ===")
    lines.append(f"Name: {stats.name}")
    lines.append(f"Date of Birth: {s.birth_date}")
    lines.append(f"Age: {stats.age_years:.0f} years")
    lines.append(f"Gender: {stats.gender.title()}")
    lines.append(f"Race/Ethnicity: {s.race} / {s.ethnicity}")
    lines.append(f"Location: {stats.city}, {stats.state}")
    lines.append(f"Status: {'Deceased' if stats.is_deceased else 'Living'}")
    if stats.years_of_history > 0:
        lines.append(f"Medical history spans: {stats.years_of_history:.1f} years")
        if stats.earliest_encounter_dt:
            lines.append(f"Earliest record: {stats.earliest_encounter_dt.strftime('%Y-%m-%d')}")
        if stats.latest_encounter_dt:
            lines.append(f"Most recent record: {stats.latest_encounter_dt.strftime('%Y-%m-%d')}")

    if record.allergies:
        lines.append(f"\nALLERGIES ({len(record.allergies)}):")
        for a in record.allergies:
            crit = f" [criticality: {a.criticality}]" if a.criticality else ""
            lines.append(f"  - {a.code.label()}{crit}")
    else:
        lines.append("\nALLERGIES: None recorded")

    # --- TIER 2: Active clinical state ---
    active_conditions = [c for c in record.conditions if c.is_active]
    if active_conditions:
        lines.append(f"\nACTIVE CONDITIONS ({len(active_conditions)}):")
        for c in sorted(active_conditions, key=lambda x: x.onset_dt or datetime.min):
            onset = f" (since {c.onset_dt.strftime('%Y-%m-%d')})" if c.onset_dt else ""
            lines.append(f"  - {c.code.label()}{onset}")
    else:
        lines.append("\nACTIVE CONDITIONS: None")

    active_meds = [m for m in record.medications if m.status in ("active", "on-hold")]
    if active_meds:
        lines.append(f"\nCURRENT MEDICATIONS ({len(active_meds)}):")
        for m in active_meds:
            dosage = f" — {m.dosage_text}" if m.dosage_text else ""
            lines.append(f"  - {m.display}{dosage}")
    else:
        lines.append("\nCURRENT MEDICATIONS: None")

    if record.care_plans_raw:
        lines.append(f"\nCARE PLANS: {len(record.care_plans_raw)} active care plan(s)")

    # --- TIER 3: Recent activity ---
    recent_encounters = [
        e for e in record.encounters
        if e.period.start and make_aware(e.period.start) >= cutoff_aware
    ]
    recent_encounters_sorted = sorted(recent_encounters, key=lambda e: e.period.start, reverse=True)

    if recent_encounters_sorted:
        lines.append(f"\nRECENT ENCOUNTERS (last {int((datetime.now(timezone.utc) - cutoff_aware).days / 365)} years, {len(recent_encounters_sorted)} visits):")
        for enc in recent_encounters_sorted[:10]:
            date_str = enc.period.start.strftime("%Y-%m-%d")
            n_obs = len(enc.linked_observations)
            lines.append(f"  - {date_str}: {enc.encounter_type or 'Encounter'} [{enc.class_code}]"
                         + (f" — {n_obs} observations" if n_obs else "")
                         + (f" at {enc.provider_org}" if enc.provider_org else ""))
        if len(recent_encounters_sorted) > 10:
            lines.append(f"  ... and {len(recent_encounters_sorted) - 10} more recent encounters")

    # Recent labs — show last value per LOINC code
    recent_obs = [
        o for o in record.observations
        if o.effective_dt and make_aware(o.effective_dt) >= cutoff_aware
        and o.value_type == "quantity"
        and o.category in ("laboratory", "vital-signs")
    ]
    if recent_obs:
        # Group by LOINC, keep most recent
        loinc_latest: dict[str, tuple] = {}
        for o in recent_obs:
            if o.loinc_code not in loinc_latest or o.effective_dt > loinc_latest[o.loinc_code][0]:
                loinc_latest[o.loinc_code] = (o.effective_dt, o)

        lines.append(f"\nRECENT LAB/VITAL VALUES ({len(loinc_latest)} unique tests):")
        vitals = {k: v for k, v in loinc_latest.items() if v[1].category == "vital-signs"}
        labs = {k: v for k, v in loinc_latest.items() if v[1].category == "laboratory"}

        if vitals:
            lines.append("  Vitals:")
            for _, (dt, o) in sorted(vitals.items(), key=lambda x: x[1][0], reverse=True)[:10]:
                lines.append(f"    {o.display}: {o.value_quantity} {o.value_unit} ({dt.strftime('%Y-%m-%d')})")

        if labs:
            lines.append("  Labs:")
            for _, (dt, o) in sorted(labs.items(), key=lambda x: x[1][0], reverse=True)[:15]:
                lines.append(f"    {o.display}: {o.value_quantity} {o.value_unit} ({dt.strftime('%Y-%m-%d')})")

    if record.immunizations:
        lines.append(f"\nIMMUNIZATIONS ({len(record.immunizations)} total):")
        for imm in sorted(record.immunizations, key=lambda x: x.occurrence_dt or datetime.min, reverse=True)[:5]:
            dt_str = imm.occurrence_dt.strftime("%Y-%m-%d") if imm.occurrence_dt else "—"
            lines.append(f"  - {imm.display} ({dt_str})")
        if len(record.immunizations) > 5:
            lines.append(f"  ... and {len(record.immunizations) - 5} more")

    # --- TIER 4 (optional): Historical data ---
    if include_tier4:
        resolved_conditions = [c for c in record.conditions if not c.is_active]
        if resolved_conditions:
            lines.append(f"\nPAST CONDITIONS ({len(resolved_conditions)} resolved):")
            for c in sorted(resolved_conditions, key=lambda x: x.onset_dt or datetime.min):
                onset = c.onset_dt.strftime("%Y-%m-%d") if c.onset_dt else "?"
                resolved = c.abatement_dt.strftime("%Y-%m-%d") if c.abatement_dt else "?"
                lines.append(f"  - {c.code.label()} ({onset} → {resolved})")

        if record.procedures:
            lines.append(f"\nPROCEDURES ({len(record.procedures)} total):")
            from collections import Counter
            proc_counts = Counter(p.code.label() for p in record.procedures)
            for proc, cnt in proc_counts.most_common(10):
                lines.append(f"  - {proc}" + (f" (×{cnt})" if cnt > 1 else ""))
            if len(proc_counts) > 10:
                lines.append(f"  ... and {len(proc_counts) - 10} more procedure types")

    lines.append("\n=== END OF PATIENT CONTEXT ===")
    return "\n".join(lines)
