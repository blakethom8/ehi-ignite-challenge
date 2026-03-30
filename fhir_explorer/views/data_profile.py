"""
Data Profile — Categorical value distributions across the dataset.

Scans patient files and profiles the actual values that appear in categorical
FHIR fields: statuses, codes, categories, class codes, etc. Helps you
understand what your data actually contains before building on top of it.
"""

from __future__ import annotations

import json
import hashlib
from collections import Counter
from pathlib import Path

import pandas as pd
import streamlit as st

# ---------------------------------------------------------------------------
# Data directory
# ---------------------------------------------------------------------------

_DATA_DIR = Path(__file__).parent.parent.parent / "data" / "synthea-samples" / "synthea-r4-individual" / "fhir"

# ---------------------------------------------------------------------------
# Categorical field definitions
#
# Each entry defines how to extract a categorical value from a raw resource.
# "path" is a dot-separated accessor chain; lists pick index 0 automatically.
# "label" is the human-readable column header.
# ---------------------------------------------------------------------------

CATEGORICAL_FIELDS: dict[str, list[dict]] = {
    "Encounter": [
        {"label": "Class Code", "path": "class.code"},
        {"label": "Status", "path": "status"},
        {"label": "Type (SNOMED)", "path": "type.0.coding.0.display"},
        {"label": "Type Code", "path": "type.0.coding.0.code"},
        {"label": "Reason", "path": "reasonCode.0.coding.0.display"},
    ],
    "Observation": [
        {"label": "Category", "path": "category.0.coding.0.code"},
        {"label": "Status", "path": "status"},
        {"label": "LOINC Code", "path": "code.coding.0.code"},
        {"label": "LOINC Display", "path": "code.coding.0.display"},
        {"label": "Value Type", "path": "_value_type"},  # special: derived
        {"label": "Unit", "path": "valueQuantity.unit"},
    ],
    "Condition": [
        {"label": "Clinical Status", "path": "clinicalStatus.coding.0.code"},
        {"label": "Verification Status", "path": "verificationStatus.coding.0.code"},
        {"label": "SNOMED Code", "path": "code.coding.0.code"},
        {"label": "SNOMED Display", "path": "code.coding.0.display"},
    ],
    "MedicationRequest": [
        {"label": "Status", "path": "status"},
        {"label": "Intent", "path": "intent"},
        {"label": "RxNorm Code", "path": "medicationCodeableConcept.coding.0.code"},
        {"label": "Medication", "path": "medicationCodeableConcept.coding.0.display"},
        {"label": "Category", "path": "category.0.coding.0.code"},
    ],
    "Procedure": [
        {"label": "Status", "path": "status"},
        {"label": "SNOMED Code", "path": "code.coding.0.code"},
        {"label": "SNOMED Display", "path": "code.coding.0.display"},
        {"label": "Reason", "path": "reasonCode.0.coding.0.display"},
    ],
    "Immunization": [
        {"label": "Status", "path": "status"},
        {"label": "CVX Code", "path": "vaccineCode.coding.0.code"},
        {"label": "Vaccine", "path": "vaccineCode.coding.0.display"},
    ],
    "AllergyIntolerance": [
        {"label": "Clinical Status", "path": "clinicalStatus.coding.0.code"},
        {"label": "Type", "path": "type"},
        {"label": "Category", "path": "category.0"},
        {"label": "Criticality", "path": "criticality"},
        {"label": "Substance", "path": "code.coding.0.display"},
    ],
    "DiagnosticReport": [
        {"label": "Status", "path": "status"},
        {"label": "Category Code", "path": "category.0.coding.0.code"},
        {"label": "Category Display", "path": "category.0.coding.0.display"},
        {"label": "Report Code", "path": "code.coding.0.code"},
        {"label": "Report Display", "path": "code.coding.0.display"},
    ],
    "Claim": [
        {"label": "Status", "path": "status"},
        {"label": "Type", "path": "type.coding.0.code"},
        {"label": "Use", "path": "use"},
    ],
    "CarePlan": [
        {"label": "Status", "path": "status"},
        {"label": "Intent", "path": "intent"},
        {"label": "Category", "path": "category.0.coding.0.display"},
    ],
}


def _resolve_path(resource: dict, path: str) -> str | None:
    """Walk a dot-separated path into a nested dict/list structure.

    Numeric path segments index into lists. Returns None if any step fails.
    """
    # Special derived fields
    if path == "_value_type":
        if "valueQuantity" in resource:
            return "quantity"
        if "valueCodeableConcept" in resource:
            return "codeable_concept"
        if "valueString" in resource:
            return "string"
        if "component" in resource:
            return "component"
        if "valueBoolean" in resource:
            return "boolean"
        return "none"

    obj = resource
    for segment in path.split("."):
        if obj is None:
            return None
        if isinstance(obj, list):
            try:
                obj = obj[int(segment)]
            except (IndexError, ValueError):
                return None
        elif isinstance(obj, dict):
            obj = obj.get(segment)
        else:
            return None

    if isinstance(obj, (str, int, float, bool)):
        return str(obj)
    return None


@st.cache_data(show_spinner="Profiling dataset...", ttl=3600)
def _profile_dataset(sample_size: int, _file_hash: str) -> dict:
    """Scan sample_size patient files and count categorical values.

    Returns dict: resource_type -> field_label -> Counter of values.
    Also returns total resource counts and patient count.
    """
    files = sorted(_DATA_DIR.glob("*.json"))
    if not files:
        return {"profiles": {}, "resource_counts": {}, "patient_count": 0, "files_scanned": 0}

    # Sample evenly across the file list
    if sample_size >= len(files):
        sample = files
    else:
        step = len(files) / sample_size
        sample = [files[int(i * step)] for i in range(sample_size)]

    profiles: dict[str, dict[str, Counter]] = {}
    resource_counts: Counter = Counter()

    for filepath in sample:
        with open(filepath, "r", encoding="utf-8") as f:
            bundle = json.load(f)

        for entry in bundle.get("entry", []):
            resource = entry.get("resource", {})
            rtype = resource.get("resourceType", "Unknown")
            resource_counts[rtype] += 1

            if rtype not in CATEGORICAL_FIELDS:
                continue

            if rtype not in profiles:
                profiles[rtype] = {fd["label"]: Counter() for fd in CATEGORICAL_FIELDS[rtype]}

            for field_def in CATEGORICAL_FIELDS[rtype]:
                value = _resolve_path(resource, field_def["path"])
                if value is not None:
                    profiles[rtype][field_def["label"]][value] += 1

    return {
        "profiles": {rtype: {label: dict(counter.most_common()) for label, counter in fields.items()}
                     for rtype, fields in profiles.items()},
        "resource_counts": dict(resource_counts.most_common()),
        "patient_count": len(sample),
        "files_scanned": len(sample),
    }


def render() -> None:
    st.title("Data Profile")
    st.markdown(
        "Categorical value distributions across the FHIR dataset. "
        "Shows what values actually appear in each field and how often."
    )

    # --- Sample size control ---
    total_files = len(sorted(_DATA_DIR.glob("*.json"))) if _DATA_DIR.exists() else 0
    if total_files == 0:
        st.error("No patient files found.")
        return

    col_sample, col_info = st.columns([1, 3])
    with col_sample:
        sample_size = st.selectbox(
            "Patients to scan",
            options=[50, 100, 250, 500, total_files],
            format_func=lambda n: f"All ({n})" if n == total_files else str(n),
            index=1,
        )
    with col_info:
        st.caption(
            f"{total_files} total patient files available. "
            "Larger samples give more representative distributions but take longer on first load."
        )

    # Build a hash of the file list for cache invalidation
    file_hash = hashlib.md5(str(total_files).encode()).hexdigest()
    data = _profile_dataset(sample_size, file_hash)

    st.markdown(f"**Scanned {data['files_scanned']} patients** — "
                f"{sum(data['resource_counts'].values()):,} total resources")

    st.markdown("---")

    # --- Resource type overview ---
    st.subheader("Resource Type Counts")
    rc = data["resource_counts"]
    df_rc = pd.DataFrame([
        {"Resource Type": rtype, "Count": count, "Avg / Patient": round(count / data["files_scanned"], 1)}
        for rtype, count in rc.items()
    ])
    st.dataframe(df_rc, hide_index=True, width="stretch", height=min(400, 35 * len(df_rc) + 38))

    st.markdown("---")

    # --- Per-resource-type categorical profiles ---
    st.subheader("Categorical Field Values")

    profiles = data["profiles"]
    resource_types = list(profiles.keys())

    if not resource_types:
        st.info("No categorical profiles generated.")
        return

    selected_type = st.selectbox(
        "Resource type",
        resource_types,
        format_func=lambda t: f"{t} ({rc.get(t, 0):,} resources)",
    )

    fields = profiles[selected_type]
    field_labels = list(fields.keys())

    if not field_labels:
        st.info(f"No categorical fields defined for {selected_type}.")
        return

    selected_field = st.selectbox("Field", field_labels)

    value_counts = fields[selected_field]

    if not value_counts:
        st.info(f"No values found for {selected_field}.")
        return

    # --- Filter ---
    filter_text = st.text_input(
        "Filter values",
        placeholder="Type to search...",
        key=f"filter_{selected_type}_{selected_field}",
    )

    # Build dataframe
    total_values = sum(value_counts.values())
    rows = []
    for value, count in value_counts.items():
        rows.append({
            "Value": value,
            "Count": count,
            "% of Total": round(count / total_values * 100, 1),
        })

    df = pd.DataFrame(rows)

    if filter_text:
        mask = df["Value"].str.contains(filter_text, case=False, na=False)
        df = df[mask]

    unique_count = len(value_counts)
    st.caption(
        f"**{unique_count}** unique values — "
        f"**{total_values:,}** total occurrences"
        + (f" — **{len(df)}** matching filter" if filter_text else "")
    )

    # Use a tall dataframe for scrollability
    display_height = min(800, max(200, 35 * len(df) + 38))
    st.dataframe(
        df,
        hide_index=True,
        width="stretch",
        height=display_height,
        column_config={
            "Count": st.column_config.NumberColumn(format="%d"),
            "% of Total": st.column_config.ProgressColumn(
                min_value=0,
                max_value=100,
                format="%.1f%%",
            ),
        },
    )

    # --- Quick stats ---
    if unique_count > 1:
        top_value = rows[0]["Value"]
        top_pct = rows[0]["% of Total"]
        st.caption(f"Most common: **{top_value}** ({top_pct}%)")
