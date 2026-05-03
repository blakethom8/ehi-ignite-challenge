"""EHI Atlas Console — Gold & Provenance page.

The final unified canonical record + Provenance lineage walker.
Every fact in the gold tier knows where it came from via FHIR Provenance edges.
"""

from __future__ import annotations

import json
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
    load_manifest,
    load_gold_bundle,
    load_provenance,
    GOLD_PATIENT_DIR,
)

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="EHI Atlas — Gold & Provenance",
    page_icon="🏆",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------

render_header("Gold & Provenance (Layer 3 output)")

st.markdown("""
**Gold is the unified canonical record.** Every resource in the gold tier is a cross-source merge
with all original source records preserved via identifiers, source-tags, and FHIR Provenance edges.
Every fact knows where it came from — a Provenance resource records the merge or derivation
activity, the agent (ehi-atlas pipeline versioned), and the entity references pointing back to
the silver-tier sources. The lineage walker at the bottom of this page lets you follow any
Provenance edge from a gold resource back to its contributing sources.
""")

# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------

with st.sidebar:
    st.markdown("### Engine key")
    engine_badge_row([("script", "Provenance emission")])
    st.write("")
    st.markdown("All Provenance records are emitted deterministically by the pipeline — no LLM involvement in lineage tracking.")
    st.divider()
    st.page_link("streamlit_app.py", label="← Overview", icon="🏠")

PATIENT_ID = "rhett759"

# ---------------------------------------------------------------------------
# Load data
# ---------------------------------------------------------------------------

manifest = load_manifest(PATIENT_ID)
gold_bundle = load_gold_bundle(PATIENT_ID)
provenance_records = load_provenance(PATIENT_ID)

if manifest is None or gold_bundle is None:
    st.error("Gold tier not found. Run `make pipeline` from `ehi-atlas/` first.")
    st.stop()

# ---------------------------------------------------------------------------
# Manifest viewer
# ---------------------------------------------------------------------------

st.subheader("Manifest")
with st.expander("manifest.json — full build metadata", expanded=True):
    st.json(manifest)

# ---------------------------------------------------------------------------
# Gold bundle resource explorer
# ---------------------------------------------------------------------------

st.divider()
st.subheader("Gold Bundle — Resource Explorer")

# Build index of all resources
all_resources: list[dict] = []
for entry in gold_bundle.get("entry", []):
    r = entry.get("resource", {})
    if r:
        all_resources.append(r)

# Group by type for the searchable list
from collections import defaultdict, Counter

by_type: dict[str, list[dict]] = defaultdict(list)
for r in all_resources:
    by_type[r.get("resourceType", "Unknown")].append(r)

type_counts = {k: len(v) for k, v in sorted(by_type.items())}
total_gold = sum(type_counts.values())

# Summary bar
st.metric("Total gold resources", total_gold)

# Resource type selector
selected_type = st.selectbox(
    "Filter by resource type:",
    options=sorted(type_counts.keys()),
    format_func=lambda t: f"{t} ({type_counts[t]})",
)

type_resources = by_type.get(selected_type, [])

# Resource list
st.markdown(f"**{len(type_resources)} {selected_type} resource(s):**")
resource_rows = []
for r in type_resources:
    rid = r.get("id", "—")
    tags = r.get("meta", {}).get("tag", [])
    sources = [t.get("code") for t in tags if "source-tag" in t.get("system", "")]
    lifecycle = next(
        (t.get("code") for t in tags if "lifecycle" in t.get("system", "")),
        "—"
    )
    quality = next(
        (e.get("valueDecimal") for e in r.get("meta", {}).get("extension", [])
         if "quality-score" in e.get("url", "")),
        None
    )
    # Short display name
    display_name = rid
    if selected_type == "Condition":
        display_name = r.get("code", {}).get("text", rid)
    elif selected_type == "MedicationRequest":
        display_name = r.get("medicationCodeableConcept", {}).get("text", rid)
    elif selected_type == "Observation":
        codes = r.get("code", {}).get("coding", [])
        display_name = codes[0].get("display", rid) if codes else rid

    resource_rows.append({
        "ID": rid,
        "Display": display_name[:60] if len(display_name) > 60 else display_name,
        "Sources": ", ".join(sources) if sources else "—",
        "Lifecycle": lifecycle,
        "Quality score": quality if quality is not None else "—",
    })

if resource_rows:
    df = pd.DataFrame(resource_rows)
    st.dataframe(df, use_container_width=True, hide_index=True)

    # Click-to-view
    if len(type_resources) <= 30:
        resource_ids = [r.get("id", "—") for r in type_resources]
        chosen_id = st.selectbox("Inspect a resource:", resource_ids)
        chosen = next((r for r in type_resources if r.get("id") == chosen_id), None)
        if chosen:
            st.json(chosen)

            # Provenance walk button
            matching_prov = [
                p for p in provenance_records
                if any(
                    target.get("reference", "").endswith(f"/{chosen_id}")
                    or target.get("reference") == f"{selected_type}/{chosen_id}"
                    for target in p.get("target", [])
                )
            ]
            if matching_prov:
                with st.expander(f"Provenance for {selected_type}/{chosen_id} ({len(matching_prov)} record(s))"):
                    for prov in matching_prov:
                        st.json(prov)
                        st.divider()
            else:
                st.caption(f"No Provenance records found targeting {selected_type}/{chosen_id}.")

# ---------------------------------------------------------------------------
# Provenance walker
# ---------------------------------------------------------------------------

st.divider()
st.subheader("Provenance.ndjson Walker")
engine_badge_row([("script", "FHIR Provenance emission")])
st.write("")

st.markdown(f"**{len(provenance_records)} total Provenance records** in `provenance.ndjson`")

if not provenance_records:
    st.warning("No provenance records found. Run `make pipeline` to build the gold tier.")
else:
    # Summary table
    prov_rows = []
    for i, prov in enumerate(provenance_records):
        targets = [t.get("reference", "?") for t in prov.get("target", [])]
        entities = prov.get("entity", [])
        activity = "—"
        for coding in prov.get("activity", {}).get("coding", []):
            activity = coding.get("code", "—")
            break
        prov_rows.append({
            "#": i + 1,
            "Activity": activity,
            "Target(s)": ", ".join(targets[:3]) + ("…" if len(targets) > 3 else ""),
            "Source entities": len(entities),
            "Recorded": prov.get("recorded", "—"),
        })

    prov_df = pd.DataFrame(prov_rows)
    st.dataframe(prov_df, use_container_width=True, hide_index=True)

    # Expandable per-record view
    st.markdown("**Detailed view — click to expand each Provenance record:**")
    for i, prov in enumerate(provenance_records):
        targets = [t.get("reference", "?") for t in prov.get("target", [])]
        activity_code = "—"
        for coding in prov.get("activity", {}).get("coding", []):
            activity_code = coding.get("code", "—")
            break
        entities = prov.get("entity", [])
        label = f"#{i+1} {activity_code} → {', '.join(targets[:2])}{'…' if len(targets)>2 else ''}"

        with st.expander(label):
            # Target + entities summary
            st.markdown(f"**Target(s):** {', '.join(targets)}")
            st.markdown(f"**Activity:** {activity_code}")
            st.markdown(f"**Agent:** {prov.get('agent', [{}])[0].get('who', {}).get('display', '—')}")
            st.markdown(f"**Recorded:** {prov.get('recorded', '—')}")

            if entities:
                st.markdown("**Entity sources:**")
                ent_rows = [
                    {
                        "Role": e.get("role", "—"),
                        "Reference": e.get("what", {}).get("reference", "—"),
                    }
                    for e in entities
                ]
                st.dataframe(pd.DataFrame(ent_rows), use_container_width=True, hide_index=True)

            with st.expander("Full JSON"):
                st.json(prov)
