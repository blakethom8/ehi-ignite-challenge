"""5-layer pipeline diagram component.

Renders the five-layer EHI Atlas pipeline as a Graphviz chart using
st.graphviz_chart, or falls back to an ASCII code block if Graphviz
is not available.
"""

from __future__ import annotations

import streamlit as st


_ASCII_DIAGRAM = """\
            ┌─────────────────────────────────────────┐
            │  Source A: Synthea FHIR R4 (clinical)   │
            │  Source B: Epic EHI Export (SQLite)     │
            │  Source C: Synthea-payer (Claim + EoB)  │
            │  Source D: Lab PDF (Quest-style)        │
            │  Source E: Synthesized clinical note    │
            └────────────────────┬────────────────────┘
                                 │
                    ┌────────────▼─────────────┐
                    │ LAYER 1: INGEST          │  🔧 Script
                    │ Per-source adapters →    │
                    │ raw immutable bronze     │
                    └────────────┬─────────────┘
                                 │
                    ┌────────────▼─────────────┐
                    │ LAYER 2: STANDARDIZE     │  🔧 Script + 📚 Ref + 🤖 LLM*
                    │ Convert all sources to   │  (* lab-pdf vision extraction)
                    │ FHIR R4 (silver)         │
                    └────────────┬─────────────┘
                                 │
                    ┌────────────▼─────────────┐
                    │ LAYER 3: HARMONIZE       │  🔧 Script + 📚 UMLS ref
                    │ Cross-source dedup,      │  (differentiation layer)
                    │ entity resolution, code  │
                    │ mapping, temporal align, │
                    │ conflict detection       │
                    └────────────┬─────────────┘
                                 │
                    ┌────────────▼─────────────┐
                    │ LAYER 4: CURATE          │  ← exists today (SOF warehouse)
                    │ SQL-on-FHIR views,       │
                    │ enrichments, episodes    │
                    └────────────┬─────────────┘
                                 │
                    ┌────────────▼─────────────┐
                    │ LAYER 5: INTERPRET       │  ← exists today (patient-journey)
                    │ Context pipeline,        │
                    │ surgical risk, briefing  │
                    └──────────────────────────┘
"""

_GRAPHVIZ_DOT = """
digraph pipeline {
    rankdir=TB;
    node [shape=box, style="rounded,filled", fontname="Courier", fontsize=11];
    graph [bgcolor="transparent"];
    edge [color="#4a8aab"];

    sources [
        label="SOURCES\\nSynthea · Epic EHI · Synthea-payer\\nLab PDF · Synthesized clinical note",
        fillcolor="#0d2a3a",
        color="#1a6aab",
        fontcolor="#c0e0ff"
    ];

    ingest [
        label="LAYER 1: INGEST\\nPer-source adapters → bronze\\n🔧 Script",
        fillcolor="#0d2a1a",
        color="#1a6a2a",
        fontcolor="#c0ffc0"
    ];

    standardize [
        label="LAYER 2: STANDARDIZE\\nConvert to FHIR R4 → silver\\n🔧 Script + 📚 Ref table + 🤖 LLM (lab-pdf)",
        fillcolor="#1a2a0d",
        color="#4a6a1a",
        fontcolor="#d0e0a0"
    ];

    harmonize [
        label="LAYER 3: HARMONIZE  ← DIFFERENTIATION\\nCross-source dedup, entity resolution,\\ncode mapping, temporal align, conflict detection\\n🔧 Script + 📚 UMLS ref",
        fillcolor="#2a0d0d",
        color="#8a2a2a",
        fontcolor="#ffc0c0"
    ];

    curate [
        label="LAYER 4: CURATE  (exists today)\\nSQL-on-FHIR views, enrichments\\n🔧 Script",
        fillcolor="#1a1a2a",
        color="#4a4a8a",
        fontcolor="#c0c0ff"
    ];

    interpret [
        label="LAYER 5: INTERPRET  (exists today)\\nContext pipeline, surgical risk, briefing\\n🔧 Script + 🤖 LLM",
        fillcolor="#2a1a2a",
        color="#8a2a8a",
        fontcolor="#ffc0ff"
    ];

    sources -> ingest;
    ingest -> standardize;
    standardize -> harmonize;
    harmonize -> curate;
    curate -> interpret;
}
"""


def render_pipeline_diagram(use_graphviz: bool = True) -> None:
    """Render the 5-layer pipeline diagram.

    Tries Graphviz first (prettier); falls back to ASCII code block.

    Parameters
    ----------
    use_graphviz : bool
        If False, always use ASCII.
    """
    if use_graphviz:
        try:
            st.graphviz_chart(_GRAPHVIZ_DOT, use_container_width=True)
            return
        except Exception:
            pass

    # ASCII fallback
    st.code(_ASCII_DIAGRAM, language=None)
