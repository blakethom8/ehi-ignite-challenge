"""EHI Atlas Console — Sources & Bronze page.

Layer 1: INGEST. One record per source. Per-source adapters are deterministic
scripts that convert raw formats to immutable bronze-tier artifacts.
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
    list_bronze_sources,
    load_bronze_metadata,
    load_bronze_bundle,
    count_bronze_records,
    BRONZE_ROOT,
)

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="EHI Atlas — Sources & Bronze",
    page_icon="📦",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------

render_header("Sources & Bronze")

st.markdown("""
**Bronze is what we received.** Layer 1 ingests raw patient data from each source using a
per-source adapter script — no transformation, no merging. Each adapter produces one immutable
bronze record per patient. Per-source READMEs (where present) document acquisition, license, and
consent posture. This page lets you inspect what each source contributed before any harmonization.
""")

# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------

with st.sidebar:
    st.markdown("### Engine key")
    engine_badge_row([("script", "Layer-1 adapters")])
    st.caption("All Layer-1 adapters are deterministic scripts — no LLM involvement.")
    st.divider()
    st.page_link("streamlit_app.py", label="← Overview", icon="🏠")

# ---------------------------------------------------------------------------
# Source table
# ---------------------------------------------------------------------------

PATIENT_ID = "rhett759"

_SOURCE_META: dict[str, dict] = {
    "synthea": {
        "description": "Synthea-generated FHIR R4 clinical bundle (patient Rhett759)",
        "license": "Apache-2.0",
        "consent": "Fully synthetic — no real PHI",
        "format": "FHIR R4 JSON Bundle",
        "engine": [("script", "passthrough adapter")],
    },
    "synthea-payer": {
        "description": "Synthea-generated payer claims (Claim + ExplanationOfBenefit for Rhett759)",
        "license": "Apache-2.0",
        "consent": "Fully synthetic — no real PHI",
        "format": "FHIR R4 JSON Bundle (CARIN BB flavored)",
        "engine": [("script", "Synthea-payer adapter")],
    },
    "epic-ehi": {
        "description": "Josh Mandel's Epic EHI Export fixture (SQLite dump, Rhett759 projection)",
        "license": "MIT (per package.json)",
        "consent": "Open source fixture — no real PHI",
        "format": "SQLite dump (415 tables / 7,294 rows)",
        "engine": [("script", "Epic EHI TSV adapter")],
    },
    "lab-pdf": {
        "description": "Synthesized Quest-style CMP lab report PDF (3 pages)",
        "license": "Synthesized — no real PHI",
        "consent": "Fully synthesized — no real PHI",
        "format": "PDF + per-page PNG rasterization + bbox text JSON",
        "engine": [("script", "LabPDF adapter"), ("llm", "vision extraction in L2-B")],
    },
    "synthesized-clinical-note": {
        "description": "Synthesized pulmonary/oncology SOAP progress note (DocumentReference + Binary)",
        "license": "Synthesized — no real PHI",
        "consent": "Fully synthesized — no real PHI",
        "format": "FHIR R4 JSON Bundle (DocumentReference + Binary, base64-encoded note)",
        "engine": [("script", "pass-through adapter")],
    },
    "ccda": {
        "description": "Josh Mandel's Cerner Transition-of-Care CCDA fixture (92 KB XML, 13 sections)",
        "license": "CC BY 4.0",
        "consent": "Open source fixture",
        "format": "C-CDA XML (HL7 CDA R2)",
        "engine": [("script", "CCDA adapter (XML passthrough; L2 deferred)")],
    },
}

sources = list_bronze_sources()

st.subheader("All Sources")

rows = []
for source in sources:
    meta = load_bronze_metadata(source, PATIENT_ID)
    smeta = _SOURCE_META.get(source, {})
    sha_head = ""
    if meta:
        sha = meta.get("sha256", meta.get("bundle_sha256", ""))
        sha_head = sha[:12] + "…" if len(sha) > 12 else sha

    counts = count_bronze_records(source, PATIENT_ID)
    count_str = ", ".join(f"{v} {k}" for k, v in sorted(counts.items()))
    rows.append({
        "Source": source,
        "Format": smeta.get("format", "—"),
        "License": smeta.get("license", "—"),
        "Consent posture": smeta.get("consent", "—"),
        "SHA-256 head": sha_head or "—",
        "Bronze contents": count_str or "—",
    })

df = pd.DataFrame(rows)
st.dataframe(df, use_container_width=True, hide_index=True)

# ---------------------------------------------------------------------------
# Per-source drill-down
# ---------------------------------------------------------------------------

st.subheader("Source Drill-Down")
selected = st.selectbox("Select a source to inspect:", sources)

if selected:
    smeta = _SOURCE_META.get(selected, {})
    st.markdown(f"**Description:** {smeta.get('description', '—')}")
    st.markdown(f"**Format:** {smeta.get('format', '—')}")
    st.markdown(f"**License:** {smeta.get('license', '—')}")
    st.markdown(f"**Consent posture:** {smeta.get('consent', '—')}")

    st.markdown("**Engine:**")
    engine_badge_row(smeta.get("engine", [("script", "adapter")]))

    st.divider()

    bronze_dir = BRONZE_ROOT / selected / PATIENT_ID

    if selected == "epic-ehi":
        st.markdown("#### Epic EHI — SQLite dump")
        dump_path = bronze_dir / "data.sqlite.dump"
        if dump_path.exists():
            st.caption(f"File: `{dump_path}` ({dump_path.stat().st_size:,} bytes)")
            # Show a text preview — first 100 non-blank lines
            lines = dump_path.read_text(encoding="utf-8").splitlines()
            preview_lines = [l for l in lines if l.strip()][:80]
            st.code("\n".join(preview_lines), language="sql")
            st.caption("Preview: first 80 non-blank lines of the SQL dump.")
        else:
            st.warning("SQLite dump not found in bronze tier.")

        # Epic Rhett759 projection artifact summary
        st.markdown("#### Projected tables (Rhett759)")
        st.markdown("""
- **PAT_PATIENT** → Patient resource (ICD-10-only identifiers)
- **PROBLEM_LIST** → Condition resources (ICD-10-only → forces UMLS-CUI merge with Synthea SNOMED)
- **ORDER_MED** → MedicationRequest (Artifact 2: atorvastatin, RxCUI 83367, discontinued 2025-09-01)
- **ORDER_RESULTS + LNC_DB_MAIN join** → Observation (Artifact 5: creatinine 1.4 mg/dL 2025-09-12)

_Key finding from inspection (task 1.6): `ORDER_RESULTS.COMPON_LNC_ID` is NULL — LOINC codes must
be joined via `LNC_DB_MAIN.COMPONENT_ID`. Without this join, creatinine would emit without a LOINC
code and Artifact 5's cross-format merge would silently fail._
""")

    elif selected == "lab-pdf":
        st.markdown("#### Lab PDF — Quest-style CMP (3 pages)")
        pdf_path = bronze_dir / "data.pdf"
        pages_dir = bronze_dir / "pages"
        if pdf_path.exists():
            st.caption(f"PDF: `{pdf_path}` ({pdf_path.stat().st_size:,} bytes)")

        if pages_dir.exists():
            png_files = sorted(pages_dir.glob("*.png"))
            st.markdown(f"**{len(png_files)} rasterized page(s):**")
            img_cols = st.columns(min(len(png_files), 3))
            for col, png in zip(img_cols, png_files):
                with col:
                    st.image(str(png), caption=png.name, use_container_width=True)

            # Show bbox text JSON for page 2 (creatinine row)
            text_json_path = pages_dir / "002.text.json"
            if text_json_path.exists():
                with st.expander("Page 2 — bbox text extraction (creatinine row is here)"):
                    data = json.loads(text_json_path.read_text(encoding="utf-8"))
                    st.json(data)
        else:
            st.warning("Pages directory not found. Run `make pipeline` to regenerate.")

    elif selected == "synthesized-clinical-note":
        st.markdown("#### Synthesized Clinical Note")
        bundle = load_bronze_bundle(selected, PATIENT_ID)
        if bundle:
            for entry in bundle.get("entry", []):
                resource = entry.get("resource", {})
                rtype = resource.get("resourceType", "")
                if rtype == "Binary":
                    import base64
                    b64_data = resource.get("data", "")
                    try:
                        note_text = base64.b64decode(b64_data).decode("utf-8")
                        st.markdown("**Progress note (plaintext):**")
                        st.text_area("Note content", note_text, height=300)
                    except Exception:
                        st.json(resource)
                elif rtype == "DocumentReference":
                    with st.expander("DocumentReference resource"):
                        st.json(resource)
        else:
            st.warning("Bronze bundle not found for synthesized-clinical-note.")

        st.info(
            "Planted fact: 'occasional chest tightness on exertion since approximately "
            "November of last year' — target for Artifact 4 extraction (Phase 2: vision wrapper "
            "on clinical note → Condition SNOMED 23924001)."
        )

    else:
        # Generic FHIR bundle viewer
        bundle = load_bronze_bundle(selected, PATIENT_ID)
        if bundle:
            counts = count_bronze_records(selected, PATIENT_ID)
            st.markdown("**Entry type counts:**")
            count_df = pd.DataFrame(
                [{"Resource type": k, "Count": v} for k, v in sorted(counts.items())]
            )
            st.dataframe(count_df, use_container_width=True, hide_index=True)

            with st.expander("Sample entry (first resource)"):
                entries = bundle.get("entry", [])
                if entries:
                    st.json(entries[0])
        else:
            if selected == "ccda":
                xml_path = bronze_dir / "data.xml"
                if xml_path.exists():
                    st.caption(f"CCDA XML: `{xml_path}` ({xml_path.stat().st_size:,} bytes)")
                    preview = xml_path.read_text(encoding="utf-8")[:3000]
                    st.code(preview, language="xml")
                else:
                    st.info("No bronze data found for CCDA (Layer-2 toolchain deferred).")
            else:
                st.info("No FHIR bundle found for this source in the bronze tier.")
