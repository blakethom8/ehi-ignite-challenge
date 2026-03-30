"""
Patient Journey — Clinician-facing patient history visualization tool.

Run with: streamlit run patient-journey/app.py (from the repo root)

Part of the EHI Ignite Challenge submission.
"""

import os
import sys
from pathlib import Path

import streamlit as st

# Add repo root to path so fhir_explorer imports work,
# and add this directory so local package imports work with hyphenated dir name
_REPO_ROOT = str(Path(__file__).parent.parent)
_APP_DIR = str(Path(__file__).parent)
sys.path.insert(0, _REPO_ROOT)
sys.path.insert(0, _APP_DIR)

from core.loader import (
    list_patient_files,
    load_patient_with_stats,
    patient_display_name,
)

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="Patient Journey",
    page_icon="🗺️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Navigation pages
# ---------------------------------------------------------------------------

PAGES = [
    "Journey Timeline",
    "Pre-Op Safety Panel",
    "Medication History",
    "Conditions",
]

# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------


@st.cache_data(show_spinner=False)
def _cached_patient_files():
    return list_patient_files()


@st.cache_data(show_spinner=False)
def _cached_load(file_path: str, _mtime: float):
    return load_patient_with_stats(file_path)


def sidebar():
    st.sidebar.title("🗺️ Patient Journey")
    st.sidebar.caption("EHI Ignite Challenge")
    st.sidebar.markdown("---")

    files = _cached_patient_files()
    if not files:
        st.sidebar.error("No patient files found in data directory.")
        return None, None, None

    labels = [patient_display_name(f) for f in files]

    selected_idx = st.sidebar.selectbox(
        "Select patient",
        range(len(files)),
        format_func=lambda i: labels[i],
    )

    selected_file = files[selected_idx]
    mtime = os.path.getmtime(selected_file)

    with st.spinner(f"Loading {selected_file.name}..."):
        record, stats = _cached_load(str(selected_file), mtime)

    # Patient summary in sidebar
    st.sidebar.markdown(
        f"**{stats.name}**  \n"
        f"Age {stats.age_years:.0f} · {record.summary.gender}  \n"
        f"{stats.total_resources:,} resources · "
        f"{stats.encounter_count} encounters  \n"
        f"{len(record.medications)} medications · "
        f"{len(record.conditions)} conditions"
    )

    st.sidebar.markdown("---")
    page = st.sidebar.radio("View", PAGES)

    # Upload option
    st.sidebar.markdown("---")
    uploaded = st.sidebar.file_uploader(
        "Or upload a FHIR bundle JSON",
        type=["json"],
    )
    if uploaded is not None:
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
            tmp.write(uploaded.getvalue())
            tmp_path = tmp.name
        record, stats = load_patient_with_stats(tmp_path)
        st.sidebar.success(f"Loaded: {stats.name}")

    return record, stats, page


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    record, stats, page = sidebar()

    if record is None:
        st.error("No patient data available. Check data directory or upload a file.")
        return

    if page == "Journey Timeline":
        from views.journey_timeline import render
    elif page == "Pre-Op Safety Panel":
        from views.safety_panel import render
    elif page == "Medication History":
        from views.medication_history import render
    elif page == "Conditions":
        from views.condition_tracker import render
    else:
        st.error(f"Unknown page: {page}")
        return

    render(record, stats)


if __name__ == "__main__":
    main()
