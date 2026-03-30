"""
Raw Resources — Browse a patient's actual FHIR JSON by resource type.

Paginated view with optional side-by-side parsed model display.
"""

from __future__ import annotations

import json
import os
from dataclasses import fields as dc_fields
from datetime import date, datetime
from pathlib import Path

import pandas as pd
import streamlit as st

from ..parser.models import PatientRecord
from ..parser.raw_loader import load_raw_resources, summarize_raw_resource
from ..catalog.single_patient import PatientStats

PAGE_SIZE = 25

# Map FHIR resourceType to the PatientRecord list attribute and ID field name
_RESOURCE_LIST_MAP: dict[str, tuple[str, str]] = {
    "Encounter": ("encounters", "encounter_id"),
    "Observation": ("observations", "obs_id"),
    "Condition": ("conditions", "condition_id"),
    "MedicationRequest": ("medications", "med_id"),
    "Procedure": ("procedures", "procedure_id"),
    "DiagnosticReport": ("diagnostic_reports", "report_id"),
    "Immunization": ("immunizations", "imm_id"),
    "AllergyIntolerance": ("allergies", "allergy_id"),
    "Claim": ("claims", "claim_id"),
    "ImagingStudy": ("imaging_studies", "study_id"),
}


@st.cache_data(show_spinner="Loading raw FHIR data...")
def _load_raw(file_path: str, _mtime: float) -> dict[str, list[dict]]:
    """Load and partition raw FHIR resources, cached by file path + mtime."""
    return load_raw_resources(file_path)


def render(record: PatientRecord, stats: PatientStats) -> None:
    st.title(f"Raw Resources — {stats.name}")

    file_path = record.summary.file_path
    if not file_path or not Path(file_path).exists():
        st.error("Source FHIR bundle file not found. Cannot display raw resources.")
        return

    mtime = os.path.getmtime(file_path)
    raw_resources = _load_raw(file_path, mtime)

    # --- Resource type selector ---
    available_types = sorted(raw_resources.keys(), key=lambda t: -len(raw_resources[t]))
    if not available_types:
        st.info("No resources found in bundle.")
        return

    type_labels = [f"{t} ({len(raw_resources[t])})" for t in available_types]
    selected_idx = st.selectbox(
        "Resource Type",
        range(len(available_types)),
        format_func=lambda i: type_labels[i],
    )
    selected_type = available_types[selected_idx]
    resources = raw_resources[selected_type]

    # --- Controls row ---
    col_filter, col_toggle = st.columns([3, 1])

    with col_filter:
        filter_text = st.text_input(
            "Filter resources",
            placeholder="Search by display text, code, or ID...",
        )

    with col_toggle:
        show_parsed = st.checkbox("Show parsed model", value=False)

    # --- Filter ---
    if filter_text:
        filter_lower = filter_text.lower()
        resources = [
            r for r in resources
            if filter_lower in json.dumps(r, default=str).lower()
        ]

    total = len(resources)
    if total == 0:
        st.info(f"No {selected_type} resources match the filter.")
        return

    # --- Pagination ---
    total_pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)

    if total_pages > 1:
        page = st.number_input(
            f"Page (1–{total_pages})",
            min_value=1,
            max_value=total_pages,
            value=1,
            step=1,
        )
    else:
        page = 1

    start_idx = (page - 1) * PAGE_SIZE
    end_idx = min(start_idx + PAGE_SIZE, total)

    st.caption(f"Showing {start_idx + 1}–{end_idx} of {total} {selected_type} resources")

    # Build parsed lookup for side-by-side
    parsed_lookup: dict[str, object] = {}
    if show_parsed and selected_type in _RESOURCE_LIST_MAP:
        attr_name, id_field = _RESOURCE_LIST_MAP[selected_type]
        parsed_list = getattr(record, attr_name, [])
        for item in parsed_list:
            rid = getattr(item, id_field, "")
            if rid:
                parsed_lookup[rid] = item

    # --- Render resources ---
    page_resources = resources[start_idx:end_idx]

    for i, raw in enumerate(page_resources):
        label = summarize_raw_resource(selected_type, raw)
        rid = raw.get("id", "")
        display_idx = start_idx + i + 1

        with st.expander(f"**#{display_idx}** — {label}", expanded=False):
            if show_parsed and rid in parsed_lookup:
                col_raw, col_parsed = st.columns(2)
                with col_raw:
                    st.markdown("*Raw FHIR JSON:*")
                    st.code(json.dumps(raw, indent=2, default=str), language="json")
                with col_parsed:
                    st.markdown(f"*Parsed → `{type(parsed_lookup[rid]).__name__}`*:")
                    _render_parsed_fields(parsed_lookup[rid])
            else:
                st.code(json.dumps(raw, indent=2, default=str), language="json")


def _render_parsed_fields(obj: object) -> None:
    """Render a parsed dataclass as a field/value table."""
    rows = []
    for f in dc_fields(obj):
        val = getattr(obj, f.name)
        # Skip large list fields (linked_* etc.)
        if isinstance(val, list) and len(val) > 5:
            display_val = f"[{len(val)} items]"
        elif isinstance(val, list):
            display_val = ", ".join(str(v) for v in val) if val else "[]"
        elif isinstance(val, dict):
            display_val = f"{{{len(val)} keys}}" if len(val) > 3 else str(val)
        elif isinstance(val, (datetime, date)):
            display_val = val.isoformat()
        elif val is None:
            display_val = "—"
        elif val == "":
            display_val = '""'
        else:
            display_val = str(val)

        rows.append({"Field": f.name, "Value": display_val})

    df = pd.DataFrame(rows)
    st.dataframe(df, hide_index=True, width="stretch")
