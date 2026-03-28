"""
FHIR Explorer — Internal Data Review Tool
Run with: streamlit run app.py (from the fhir_explorer/ directory)
"""

import os
import sys
from pathlib import Path

import streamlit as st

# Add parent dir to path so relative imports work when run via streamlit
sys.path.insert(0, str(Path(__file__).parent.parent))

from fhir_explorer.parser.bundle_parser import parse_bundle
from fhir_explorer.catalog.single_patient import compute_patient_stats

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="FHIR Explorer",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Data directory — relative to this file's location
# ---------------------------------------------------------------------------

DATA_DIR = Path(__file__).parent.parent / "data" / "synthea-samples" / "synthea-r4-individual" / "fhir"

# ---------------------------------------------------------------------------
# Sidebar — file picker + navigation
# ---------------------------------------------------------------------------

PAGES = [
    "Overview",
    "Timeline",
    "Encounter Hub",
    "Code Catalogs",
    "Field Profiler",
    "Corpus Explorer",
    "Signal vs. Noise",
]

TIER_COLORS = {
    "simple": "🟢",
    "moderate": "🟡",
    "complex": "🟠",
    "highly_complex": "🔴",
}


@st.cache_data(show_spinner=False)
def get_patient_files() -> list[Path]:
    if not DATA_DIR.exists():
        return []
    return sorted(DATA_DIR.glob("*.json"))


@st.cache_data(show_spinner=False)
def load_patient(file_path: str, _mtime: float):
    """Cache keyed by path + mtime so stale files are re-parsed."""
    record = parse_bundle(file_path)
    stats = compute_patient_stats(record)
    return record, stats


def sidebar():
    st.sidebar.title("🏥 FHIR Explorer")
    st.sidebar.markdown("---")

    files = get_patient_files()
    if not files:
        st.sidebar.error(f"No patient files found in:\n{DATA_DIR}")
        return None, None, None

    # Build display labels: "Name (tier icon) — N resources"
    @st.cache_data(show_spinner=False)
    def build_labels(_files_hash: str, file_paths: list[str]) -> list[str]:
        labels = []
        for fp in file_paths:
            name = Path(fp).stem.split("_")[0] + " " + Path(fp).stem.split("_")[1]
            labels.append(name)
        return labels

    file_paths = [str(f) for f in files]
    labels = [f.stem.rsplit("_", 1)[0].replace("_", " ") for f in files]

    selected_idx = st.sidebar.selectbox(
        "Select patient",
        range(len(files)),
        format_func=lambda i: labels[i],
    )

    selected_file = files[selected_idx]
    mtime = os.path.getmtime(selected_file)

    with st.spinner(f"Parsing {selected_file.name}..."):
        record, stats = load_patient(str(selected_file), mtime)

    # Show complexity badge
    tier = stats.complexity_tier
    icon = TIER_COLORS.get(tier, "⚪")
    st.sidebar.markdown(
        f"**{stats.name}**  \n"
        f"{icon} `{tier}` · score {stats.complexity_score:.0f}/100  \n"
        f"{stats.total_resources:,} resources · {stats.encounter_count} encounters  \n"
        f"Age {stats.age_years:.1f} · {'Deceased' if stats.is_deceased else 'Living'}"
    )

    st.sidebar.markdown("---")
    page = st.sidebar.radio("Navigate", PAGES)

    return record, stats, page


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    record, stats, page = sidebar()

    if record is None:
        st.error("No patient data found. Check your data directory.")
        st.code(str(DATA_DIR))
        return

    # Lazy import pages to keep startup fast
    if page == "Overview":
        from fhir_explorer.views.overview import render
    elif page == "Timeline":
        from fhir_explorer.views.timeline import render
    elif page == "Encounter Hub":
        from fhir_explorer.views.encounter_hub import render
    elif page == "Code Catalogs":
        from fhir_explorer.views.catalog_view import render
    elif page == "Field Profiler":
        from fhir_explorer.views.field_profiler_view import render
    elif page == "Corpus Explorer":
        from fhir_explorer.views.corpus_view import render
    elif page == "Signal vs. Noise":
        from fhir_explorer.views.signal_filter import render
    else:
        st.error(f"Unknown page: {page}")
        return

    render(record, stats)


if __name__ == "__main__":
    main()
