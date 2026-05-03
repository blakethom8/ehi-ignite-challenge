"""EHI Atlas Console — Harmonize page.

Layer 3: HARMONIZE. The differentiation layer. Merges silver records across
sources into a single canonical patient record: identity resolution, code
mapping (UMLS), temporal alignment, condition/medication/observation merges,
and conflict detection.
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
)

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="EHI Atlas — Harmonize",
    page_icon="🔗",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------

render_header("Harmonize (Layer 3 — the differentiation layer)")

st.markdown("""
**Harmonize merges silver records from all sources into a single canonical patient record.**
This is the layer Josh Mandel's stack explicitly does not address — each provider is a separate
slice, no merging. EHI Atlas closes that gap: identity resolution clusters patients across sources
(Fellegi-Sunter), UMLS CUI mapping bridges code systems (SNOMED ↔ ICD-10), temporal alignment
normalizes dates to UTC, and condition/medication/observation merge logic produces one canonical
fact per logical concept. Conflict detection flags cases where sources disagree and preserves
both records with a cross-reference extension for the UI to display side-by-side.
""")

# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------

with st.sidebar:
    st.markdown("### Engine key")
    engine_badge_row([("script", "identity / dedup / merge")])
    st.write("")
    engine_badge_row([("table", "UMLS CUI crosswalk")])
    st.write("")
    engine_badge_row([("llm", "conflict narration (Phase 2)")])
    st.divider()
    st.page_link("streamlit_app.py", label="← Overview", icon="🏠")

PATIENT_ID = "rhett759"

# ---------------------------------------------------------------------------
# Load data
# ---------------------------------------------------------------------------

manifest = load_manifest(PATIENT_ID)
gold_bundle = load_gold_bundle(PATIENT_ID)

if manifest is None or gold_bundle is None:
    st.error("Gold tier not found. Run `make pipeline` from `ehi-atlas/` first.")
    st.stop()

# ---------------------------------------------------------------------------
# Merge metrics
# ---------------------------------------------------------------------------

st.subheader("Harmonization Metrics")

ms = manifest.get("merge_summary", {})
rc = manifest.get("resource_counts", {})

col1, col2, col3, col4 = st.columns(4)
col1.metric("Conditions merged", ms.get("conditions_merged", 0))
col2.metric("Medications reconciled", ms.get("medications_reconciled", 0))
col3.metric("Observations deduped", ms.get("observations_deduped", 0))
col4.metric("Conflicts detected", ms.get("conflicts_detected", 0))

# ---------------------------------------------------------------------------
# Sub-task engine table
# ---------------------------------------------------------------------------

st.subheader("Sub-tasks and Engines")
engine_badge_row([("script", "identity resolution"), ("table", "UMLS CUI crosswalk")])
st.write("")

_SUBTASK_TABLE = [
    ("Patient identity resolution", "Fellegi-Sunter record linkage (inline Jaro-Winkler)", "script"),
    ("Provider identity resolution", "NPI-exact match + name Jaro-Winkler fallback", "script"),
    ("Code mapping (SNOMED ↔ ICD-10 ↔ RxNorm)", "UMLS CUI crosswalk (hand-curated for Phase 1)", "table"),
    ("Temporal alignment", "UTC normalize; DocRef.context.period.start precedence (Mandel rule)", "script"),
    ("Condition merge", "UMLS CUI grouping + earliest-onset-wins temporal envelope", "script"),
    ("Medication episode reconciliation", "RxNorm-ingredient grouping + STATUS_PRIORITY merge", "script"),
    ("Observation dedup", "(LOINC, date, value, unit) hash + UCUM normalization", "script"),
    ("Conflict detection", "Rule-based: obs near-match + medication cross-class (statin)", "script"),
    ("Conflict narration", "LLM-judge with note excerpts as context", "llm"),
    ("Quality scoring", "Recency (40%) × source authority (40%) × completeness (20%)", "script"),
    ("Provenance emission", "FHIR Provenance per MERGE/DERIVE activity", "script"),
]

rows = []
for name, mechanism, engine in _SUBTASK_TABLE:
    rows.append({"Sub-task": name, "Mechanism": mechanism, "Engine": engine.upper()})
st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

# ---------------------------------------------------------------------------
# Helper: find resource by ID in gold bundle
# ---------------------------------------------------------------------------


def _find_resource(resource_id: str) -> dict | None:
    """Find a resource in the gold bundle by its id field."""
    for entry in gold_bundle.get("entry", []):
        r = entry.get("resource", {})
        if r.get("id") == resource_id:
            return r
    return None


def _find_resources_by_type(rtype: str) -> list[dict]:
    """Return all resources of a given type from the gold bundle."""
    return [
        entry.get("resource", {})
        for entry in gold_bundle.get("entry", [])
        if entry.get("resource", {}).get("resourceType") == rtype
    ]


def _find_condition_by_cui(cui: str) -> dict | None:
    """Find a merged Condition resource by its UMLS CUI id."""
    target_id = f"merged-cond-{cui}"
    return _find_resource(target_id)


# ---------------------------------------------------------------------------
# Artifact 1: Hyperlipidemia merge (SNOMED + ICD-10 → UMLS CUI)
# ---------------------------------------------------------------------------

st.divider()
st.subheader("Artifact 1 — Hyperlipidemia Cross-Source Merge")
engine_badge_row([("script", "condition merge"), ("table", "UMLS CUI C0020473")])
st.write("")

st.markdown("""
Rhett759's hyperlipidemia appears in two sources with different code systems:
- **Synthea**: SNOMED CT 55822004 (Hyperlipidemia)
- **Epic EHI**: ICD-10-CM E78.5 (Hyperlipidemia, unspecified)

The UMLS CUI bridge (C0020473) recognizes these as the same concept. The condition merge
collapses them into one Condition resource with **both codings preserved**, both source identifiers
retained, and the UMLS CUI annotated on each coding via extension. Earliest onset wins.
""")

merged_hyperl = _find_condition_by_cui("C0020473")

# Find the pre-merge source conditions for "before" view
# Synthea: SNOMED 55822004
synthea_hyperl = None
# Epic: ICD-10 E78.5
epic_hyperl = None
for entry in gold_bundle.get("entry", []):
    r = entry.get("resource", {})
    if r.get("resourceType") != "Condition":
        continue
    codings = r.get("code", {}).get("coding", [])
    for c in codings:
        if c.get("code") == "55822004":
            synthea_hyperl = {"id": r.get("id"), "code": r.get("code"), "source": "synthea (SNOMED)"}
        if c.get("code") == "E78.5":
            epic_hyperl = {"id": r.get("id"), "code": r.get("code"), "source": "epic-ehi (ICD-10)"}

col_before, col_after = st.columns(2)

with col_before:
    st.markdown("**Before merge (silver tier — two separate records):**")

    st.markdown("*Synthea silver — SNOMED 55822004:*")
    st.json({
        "resourceType": "Condition",
        "id": "e801fa72-b819-40a6-bdea-21378291c7fe",
        "meta": {"tag": [
            {"system": "…/source-tag", "code": "synthea"},
            {"system": "…/lifecycle", "code": "standardized"},
        ]},
        "code": {"coding": [{"system": "http://snomed.info/sct", "code": "55822004", "display": "Hyperlipidemia"}]},
        "onsetDateTime": "2006-10-03",
    })

    st.markdown("*Epic EHI stub-silver — ICD-10 E78.5:*")
    st.json({
        "resourceType": "Condition",
        "id": "epic-cond-prob000004",
        "meta": {"tag": [
            {"system": "…/source-tag", "code": "epic-ehi"},
            {"system": "…/lifecycle", "code": "stub-silver"},
        ]},
        "code": {"coding": [{"system": "http://hl7.org/fhir/sid/icd-10-cm", "code": "E78.5", "display": "Hyperlipidemia, unspecified"}]},
    })

with col_after:
    st.markdown("**After merge (gold tier — one unified record):**")
    if merged_hyperl:
        st.json(merged_hyperl)
    else:
        st.warning("Merged hyperlipidemia condition not found in gold bundle.")

# ---------------------------------------------------------------------------
# Artifact 2: Statin cross-class conflict
# ---------------------------------------------------------------------------

st.divider()
st.subheader("Artifact 2 — Statin Cross-Class Conflict (simvastatin vs. atorvastatin)")
engine_badge_row([("script", "medication reconciliation"), ("table", "RxNorm class lookup")])
st.write("")

st.markdown("""
Rhett759 has two statins from different sources:
- **Synthea**: Simvastatin (RxCUI 316672 / product-level) — active
- **Epic EHI**: Atorvastatin 40mg (RxCUI 83367) — discontinued 2025-09-01

These are **different ingredients within the same therapeutic class (statin)** — they cannot be
merged. The medication reconciler preserves both as separate episodes and flags each with a
`conflict-pair` extension pointing to the other. A `DERIVE` Provenance record documents the
cross-class detection. This pattern is clinically significant: one statin discontinued (Epic) while
Synthea shows another active — a potential polypharmacy or therapy-switch scenario.
""")

# Find the statin meds
meds = _find_resources_by_type("MedicationRequest")
simva = None
atorva = None
for m in meds:
    text = m.get("medicationCodeableConcept", {}).get("text", "").lower()
    mid = m.get("id", "")
    if "simvastatin" in text or "316672" in mid or "merged-med-316672" in mid:
        simva = m
    if "atorvastatin" in text or "83367" in mid or "epic-med-med000002" in mid:
        atorva = m

col_sim, col_ator = st.columns(2)
with col_sim:
    st.markdown("**Simvastatin (Synthea → merged gold):**")
    if simva:
        # Compact display
        compact = {
            "id": simva.get("id"),
            "status": simva.get("status"),
            "medicationCodeableConcept": simva.get("medicationCodeableConcept"),
            "authoredOn": simva.get("authoredOn"),
            "extension": [e for e in simva.get("extension", []) if "conflict" in e.get("url", "")],
            "meta_tags": simva.get("meta", {}).get("tag", []),
        }
        st.json(compact)
    else:
        st.info("Simvastatin not found in gold bundle.")

with col_ator:
    st.markdown("**Atorvastatin (Epic EHI — discontinued):**")
    if atorva:
        compact = {
            "id": atorva.get("id"),
            "status": atorva.get("status"),
            "medicationCodeableConcept": atorva.get("medicationCodeableConcept"),
            "authoredOn": atorva.get("authoredOn"),
            "dispenseRequest": atorva.get("dispenseRequest"),
            "extension": [e for e in atorva.get("extension", []) if "conflict" in e.get("url", "")],
            "meta_tags": atorva.get("meta", {}).get("tag", []),
        }
        st.json(compact)
    else:
        st.info("Atorvastatin not found in gold bundle.")

st.markdown("""
Each medication carries a `conflict-pair` extension referencing the other.
The DERIVE Provenance record documents the cross-class detection:
- **target:** both MedicationRequest references
- **activity:** DERIVE
- **entity[role=source]:** atorvastatin + simvastatin
""")

# ---------------------------------------------------------------------------
# Artifact 5: Creatinine cross-format merge
# ---------------------------------------------------------------------------

st.divider()
st.subheader("Artifact 5 — Creatinine Cross-Format Merge (Epic EHI + Lab PDF)")
engine_badge_row([("script", "observation dedup"), ("table", "LOINC 2160-0 + UCUM mg/dL")])
st.write("")

st.markdown("""
Creatinine 1.4 mg/dL on 2025-09-12 appears in **two sources with different formats**:
- **Epic EHI SQLite**: `ORDER_RESULTS` row — creatinine value obtained by joining `LNC_DB_MAIN`
  on `COMPONENT_ID` (since `COMPON_LNC_ID` is NULL in this fixture)
- **Lab PDF (synthesized Quest CMP)**: value extracted from page 2, bounding box bbox=72,574,540,590

The observation deduper recognizes these as the same fact by matching on `(LOINC 2160-0, 2025-09-12, 1.4, mg/dL)`.
The merged Observation carries **both source-tags**, both source identifiers, and the higher quality
score (0.94 from epic-ehi vs 0.48 from lab-pdf → merged takes max = 0.94).
""")

# Find the merged creatinine observation
creatinine_obs = None
for entry in gold_bundle.get("entry", []):
    r = entry.get("resource", {})
    if r.get("resourceType") != "Observation":
        continue
    codings = r.get("code", {}).get("coding", [])
    if any(c.get("code") == "2160-0" for c in codings):
        tags = r.get("meta", {}).get("tag", [])
        sources = [t.get("code") for t in tags if "source-tag" in t.get("system", "")]
        if len(sources) >= 2 or "merged" in r.get("extension", [{}])[0].get("url", "") if r.get("extension") else False:
            creatinine_obs = r
            break
        elif creatinine_obs is None:
            creatinine_obs = r

col_epic, col_lab, col_merged = st.columns(3)
with col_epic:
    st.markdown("**Epic EHI source (SQLite):**")
    st.json({
        "source": "epic-ehi",
        "LOINC": "2160-0",
        "value": "1.4 mg/dL",
        "date": "2025-09-12",
        "path": "ORDER_RESULTS JOIN LNC_DB_MAIN ON COMPONENT_ID",
        "lifecycle": "stub-silver",
    })

with col_lab:
    st.markdown("**Lab PDF source (page 2, bbox):**")
    st.json({
        "source": "lab-pdf",
        "LOINC": "2160-0",
        "value": "1.4 mg/dL",
        "date": "2025-09-12",
        "path": "synthesized-lab-pdf/raw/lab-report-2025-09-12-quest.pdf",
        "page": 2,
        "bbox": "72,574,540,590",
        "lifecycle": "stub-silver",
    })

with col_merged:
    st.markdown("**Merged gold Observation:**")
    if creatinine_obs:
        compact = {
            "id": creatinine_obs.get("id"),
            "code": creatinine_obs.get("code"),
            "valueQuantity": creatinine_obs.get("valueQuantity"),
            "effectiveDateTime": creatinine_obs.get("effectiveDateTime"),
            "quality_score": next(
                (e.get("valueDecimal") for e in creatinine_obs.get("meta", {}).get("extension", [])
                 if "quality-score" in e.get("url", "")), None
            ),
            "source_tags": [t.get("code") for t in creatinine_obs.get("meta", {}).get("tag", [])
                           if "source-tag" in t.get("system", "")],
            "merge_rationale": next(
                (e.get("valueString") for e in creatinine_obs.get("extension", [])
                 if "merge-rationale" in e.get("url", "")), None
            ),
        }
        st.json(compact)
    else:
        st.warning("Merged creatinine not found — check if dedup ran correctly.")

# ---------------------------------------------------------------------------
# Skipped artifacts
# ---------------------------------------------------------------------------

st.divider()
st.subheader("Artifacts 3 & 4 — Not shown in detail")
st.markdown("""
- **Artifact 3 (Orphan claims):** 136 Claim + 59 EoB resources from synthea-payer flow through
  as 'other' resources (no merge logic for claims in Phase 1). Too many to show individually —
  visible in the Gold & Provenance page resource list.
- **Artifact 4 (Chest tightness extraction):** Phase-2 partial. The synthesized clinical note
  contains a planted phrase ("occasional chest tightness on exertion since approximately November
  of last year"). Extracting this into a Condition (SNOMED 23924001) requires the Claude vision
  wrapper (task 4.3) wired to a Layer-2 standardizer for clinical notes. Both are implemented
  but not yet integrated — 2 tests in the integration suite are Phase-2 skips.
""")
