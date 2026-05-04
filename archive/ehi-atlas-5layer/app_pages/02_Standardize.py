"""EHI Atlas Console — Standardize page.

Layer 2: STANDARDIZE. Convert each source's bronze record to FHIR R4 with
USCDI / CARIN BB profiles. Layer 2 adds source-tag and lifecycle-tag to every
resource. Vision extraction (Layer 2-B) lifts unstructured PDFs into FHIR via
Claude vision — the only LLM step in the standardize layer.
"""

from __future__ import annotations

import sys
from pathlib import Path

_APP_DIR = Path(__file__).parent.parent.resolve()
if str(_APP_DIR) not in sys.path:
    sys.path.insert(0, str(_APP_DIR))

import streamlit as st
import pandas as pd

from components.header import render_header
from components.badges import engine_badge_row
from components.corpus_loader import (
    load_silver_bundle,
    count_silver_resources,
    count_bronze_records,
    SILVER_ROOT,
)

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="EHI Atlas — Standardize",
    page_icon="🔄",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------

render_header("Standardize (Layer 2 — Silver)")

st.markdown("""
**Standardize converts each source's bronze record to FHIR R4** with USCDI and CARIN BB profiles.
Layer 2 annotates every resource with a `source-tag` (which system provided it) and a
`lifecycle-tag` (`standardized` for real silver, `stub-silver` for Phase-1 placeholders). Vision
extraction (Layer 2-B) lifts unstructured PDFs into FHIR via Claude vision — **the only LLM step
in the Standardize layer**. Everything else is deterministic scripts and frozen reference tables.
""")

# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------

with st.sidebar:
    st.markdown("### Engine key")
    engine_badge_row([("script", "L2 standardizers")])
    st.write("")
    engine_badge_row([("table", "USCDI profile lookup")])
    st.write("")
    engine_badge_row([("llm", "vision extraction (lab-pdf)")])
    st.divider()
    st.page_link("streamlit_app.py", label="← Overview", icon="🏠")

PATIENT_ID = "rhett759"

# ---------------------------------------------------------------------------
# Source-by-source silver status table
# ---------------------------------------------------------------------------

st.subheader("Per-Source Standardization Status")

_SOURCE_L2: dict[str, dict] = {
    "synthea": {
        "status": "real silver (task 2.8 done)",
        "description": "SyntheaStandardizer passthrough annotates 2,640 resources with source-tag + lifecycle + 15 USCDI profile URLs.",
        "engine": [("script", "SyntheaStandardizer"), ("table", "USCDI profiles")],
        "silver_exists": True,
    },
    "synthea-payer": {
        "status": "stub-silver (Phase 1)",
        "description": "Passthrough from bronze with stub-silver tags. Claim + EoB resources flow through as 'other' in harmonizer (no merge logic in Phase 1).",
        "engine": [("script", "stub passthrough")],
        "silver_exists": False,
    },
    "epic-ehi": {
        "status": "stub-silver (Phase 1)",
        "description": "Synthesized from SQLite dump in orchestrator (6-table projection: Patient, Conditions, MedicationRequests, Observations). Real L2 standardizer is Phase-2 work (task 2.7).",
        "engine": [("hybrid", "script + SQLite projection")],
        "silver_exists": False,
    },
    "lab-pdf": {
        "status": "stub-silver (Phase 1) — creatinine only",
        "description": "Emits the Artifact 5 creatinine Observation (LOINC 2160-0, 1.4 mg/dL, 2025-09-12) from known PDF values. Phase 2 wires 4.3 vision wrapper → real silver.",
        "engine": [("script", "stub (known values)"), ("llm", "vision extraction in Phase 2")],
        "silver_exists": False,
    },
    "synthesized-clinical-note": {
        "status": "stub-silver (Phase 1)",
        "description": "Near-passthrough — the bronze bundle is already FHIR. Adds stub-silver tags so it joins the harmonizer pipeline. Phase 2: clinical-note vision extraction → Condition (SNOMED 23924001 chest tightness).",
        "engine": [("script", "FHIR passthrough + tagging")],
        "silver_exists": False,
    },
    "ccda": {
        "status": "deferred",
        "description": "L2 toolchain decision pending (Microsoft FHIR-Converter requires Docker/build-from-source; no commonly-published npm CLI). Phase-2 decision: Docker-subprocess OR LinuxForHealth Java OR pure-Python.",
        "engine": [("script", "deferred")],
        "silver_exists": False,
    },
}

rows = []
for source, info in _SOURCE_L2.items():
    silver_counts = count_silver_resources(source, PATIENT_ID)
    total = sum(silver_counts.values())
    rows.append({
        "Source": source,
        "L2 status": info["status"],
        "Silver resources": total if total else "—",
        "Description": info["description"][:80] + "…" if len(info["description"]) > 80 else info["description"],
    })
df = pd.DataFrame(rows)
st.dataframe(df, use_container_width=True, hide_index=True)

# ---------------------------------------------------------------------------
# Synthea real silver — detailed view
# ---------------------------------------------------------------------------

st.divider()
st.subheader("Synthea — Real Silver (task 2.8)")
engine_badge_row([("script", "SyntheaStandardizer"), ("table", "USCDI profile lookup")])
st.write("")

silver_bundle = load_silver_bundle("synthea", PATIENT_ID)
bronze_counts = count_bronze_records("synthea", PATIENT_ID)
silver_counts = count_silver_resources("synthea", PATIENT_ID)

if silver_bundle is None:
    st.warning(
        f"No silver bundle found at `{SILVER_ROOT}/synthea/{PATIENT_ID}/bundle.json`. "
        "Run `make pipeline` to build."
    )
else:
    total_bronze = sum(bronze_counts.values())
    total_silver = sum(silver_counts.values())

    col1, col2, col3 = st.columns(3)
    col1.metric("Bronze entries", total_bronze)
    col2.metric("Silver resources", total_silver)
    col3.metric("Added annotations", "source-tag + lifecycle + 15 USCDI profiles per resource")

    tab1, tab2 = st.tabs(["Resource type counts", "Sample annotated resource"])

    with tab1:
        count_rows = [{"Resource type": k, "Count": v} for k, v in sorted(silver_counts.items())]
        st.dataframe(pd.DataFrame(count_rows), use_container_width=True, hide_index=True)

    with tab2:
        # Find a Condition resource (most interesting to show tags + profiles)
        sample_resource = None
        for entry in silver_bundle.get("entry", []):
            resource = entry.get("resource", {})
            if resource.get("resourceType") == "Condition":
                sample_resource = resource
                break
        if sample_resource:
            st.caption("A standardized Synthea Condition showing added meta.tag (source + lifecycle) and meta.profile (USCDI URL):")
            st.json(sample_resource)
        else:
            entries = silver_bundle.get("entry", [])
            if entries:
                st.json(entries[0].get("resource", {}))

# ---------------------------------------------------------------------------
# Stub-silver sources
# ---------------------------------------------------------------------------

st.divider()
st.subheader("Stub-Silver Sources (Phase 1)")
st.info(
    "The following sources do not yet have real Layer-2 standardizers. "
    "The orchestrator synthesizes minimal FHIR bundles from bronze data at runtime, "
    "tagged with `lifecycle=stub-silver`. Phase-2 work adds dedicated standardizers per source."
)

for source in ["synthea-payer", "epic-ehi", "lab-pdf", "synthesized-clinical-note"]:
    info = _SOURCE_L2[source]
    with st.expander(f"**{source}** — {info['status']}"):
        st.markdown(info["description"])
        st.markdown("**Engine:**")
        engine_badge_row(info["engine"])

st.divider()
st.subheader("CCDA — Deferred")
engine_badge_row([("script", "deferred — no L2 toolchain yet")])
st.write("")
st.markdown(_SOURCE_L2["ccda"]["description"])
st.markdown("""
**What ships in Phase 1:** CCDAAdapter passes through the XML to bronze (byte-identical copy).
`make pipeline` skips CCDA in the harmonizer (returns None from stub-silver synthesizer).

**Phase-2 options:**
1. Docker-subprocess invocation of Microsoft FHIR-Converter
2. LinuxForHealth Java-based CCDA → FHIR converter
3. Pure-Python CCDA → FHIR port

See `ehi-atlas/docs/FHIR-CONVERTER-SETUP.md` for investigation notes.
""")
