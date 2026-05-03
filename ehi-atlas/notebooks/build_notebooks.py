"""Build all 10 EHI Atlas pedagogical notebooks.

Run with:
    uv run python notebooks/build_notebooks.py

Each notebook is written to notebooks/<name>.ipynb with kernel set to ehi-atlas.
"""
import json
import sys
from pathlib import Path

import nbformat
from nbformat.v4 import new_notebook, new_markdown_cell, new_code_cell

NOTEBOOKS_DIR = Path(__file__).parent
REPO_ROOT = NOTEBOOKS_DIR.parent

KERNELSPEC = {
    "display_name": "Python (ehi-atlas)",
    "language": "python",
    "name": "ehi-atlas",
}


def nb(cells):
    """Create a notebook with the standard kernelspec."""
    notebook = new_notebook()
    notebook.metadata.kernelspec = KERNELSPEC
    notebook.metadata.language_info = {"name": "python"}
    notebook.cells = cells
    return notebook


def md(source):
    return new_markdown_cell(source)


def code(source):
    return new_code_cell(source)


# ---------------------------------------------------------------------------
# 00 — Welcome and Setup
# ---------------------------------------------------------------------------

nb00 = nb([
    md("""# 00 — Welcome and Setup

This series walks the EHI Atlas data platform **end-to-end, cell by cell**, against the live corpus. Each notebook covers one layer of the five-layer pipeline. Work through them in order or jump to a specific artifact deep-dive (notebooks 06–08).

**Reading order:** 00 → 01 → 02 → 03 → 04 → 05 → 06 → 07 → 08 → 09
"""),

    md("""## Kernel setup

Select **Python (ehi-atlas)** in VS Code / Cursor. To verify the kernel is correct, run the cell below.
"""),

    code("""\
import ehi_atlas
print("ehi_atlas version:", ehi_atlas.__version__)
"""),

    md("""## Where the corpus lives

The corpus is a file-based three-tier store:

```
ehi-atlas/corpus/
├── _sources/    ← raw acquisitions (gitignored for personal data)
├── bronze/      ← Layer 1 output: per-source, immutable
├── silver/      ← Layer 2 output: per-source FHIR R4 bundles
├── gold/        ← Layer 3 output: merged canonical record
└── reference/   ← terminology (LOINC subset, hand-curated crosswalk)
```

From the shell:
```bash
ls ehi-atlas/corpus/bronze/
ls ehi-atlas/corpus/gold/patients/rhett759/
```
"""),

    code("""\
from pathlib import Path

ATLAS_ROOT = Path("..").resolve()   # notebooks/ is one level below ehi-atlas/
CORPUS     = ATLAS_ROOT / "corpus"

for tier in ("bronze", "silver", "gold"):
    path = CORPUS / tier
    if path.exists():
        children = sorted(path.iterdir())
        print(f"{tier}/  ({len(children)} entries):", [c.name for c in children[:6]])
    else:
        print(f"{tier}/  — not found")
"""),

    md("""## Five-layer pipeline

```
            ┌─────────────────────────────────────────┐
            │  Source A: Synthea FHIR R4              │
            │  Source B: Epic EHI Export (SQLite)     │
            │  Source C: Synthea-Payer (Claim/EoB)    │
            │  Source D: Synthesized lab PDF          │
            │  Source E: Clinical note (FHIR)         │
            └────────────────────┬────────────────────┘
                                 │
                    ┌────────────▼─────────────┐
                    │ LAYER 1: INGEST          │  🔧 Script
                    │ Per-source adapters →    │
                    │ raw immutable bronze     │
                    └────────────┬─────────────┘
                                 │
                    ┌────────────▼─────────────┐
                    │ LAYER 2: STANDARDIZE     │  🔧 Script + 📚 Reference
                    │ Convert all sources to   │
                    │ FHIR R4 (silver)         │
                    └────────────┬─────────────┘
                                 │
                    ┌────────────▼─────────────┐
                    │ LAYER 3: HARMONIZE       │  🔧 Script + 📚 Reference
                    │ Cross-source dedup,      │  ← our differentiation
                    │ entity resolution, code  │
                    │ mapping, temporal align, │
                    │ conflict detection       │
                    └────────────┬─────────────┘
                                 │
                    ┌────────────▼─────────────┐
                    │ LAYER 4: CURATE          │  🔧 Script (existing SOF DB)
                    │ SQL-on-FHIR views        │
                    └────────────┬─────────────┘
                                 │
                    ┌────────────▼─────────────┐
                    │ LAYER 5: INTERPRET       │  ⚙️ Hybrid (existing app)
                    │ Context pipeline,        │
                    │ surgical risk, briefing  │
                    └──────────────────────────┘
```

Engine legend: 🔧 Script · 🤖 LLM · 📚 Reference · ⚙️ Hybrid
"""),

    code("""\
# Quick sanity: gold tier for showcase patient
import json

manifest_path = CORPUS / "gold" / "patients" / "rhett759" / "manifest.json"
manifest = json.loads(manifest_path.read_text())
print("Patient:", manifest["patient_id"])
print("Sources:", [s["name"] for s in manifest["sources"]])
print("Merge summary:", manifest["merge_summary"])
"""),

    md("**Next:** [01_bronze_tier.ipynb](./01_bronze_tier.ipynb)"),
])


# ---------------------------------------------------------------------------
# 01 — Bronze Tier
# ---------------------------------------------------------------------------

nb01 = nb([
    md("""# 01 — Layer 1: Bronze Tier

🔧 Script

Per-source adapters write raw, immutable bronze records. Every source is treated as a black box at this layer — no format conversion, no merging. This notebook tours what the bronze tier looks like.
"""),

    md("## 1. Source inventory"),

    code("""\
from pathlib import Path
import json

ATLAS_ROOT = Path("..").resolve()
CORPUS     = ATLAS_ROOT / "corpus"

sources = sorted((CORPUS / "bronze").iterdir())
for s in sources:
    if not s.is_dir():
        continue
    patients = [p.name for p in s.iterdir() if p.is_dir()]
    print(f"  bronze/{s.name}/  → patients: {patients}")
"""),

    md("## 2. Per-source metadata.json — the SourceMetadata contract"),

    code("""\
# 🔧 Script — every adapter writes metadata.json alongside the data file
meta = json.loads((CORPUS / "bronze" / "synthea" / "rhett759" / "metadata.json").read_text())
for k, v in meta.items():
    print(f"  {k}: {v}")
"""),

    md("## 3. SyntheaAdapter — listing patients and ingesting"),

    code("""\
# 🔧 Script
from ehi_atlas.adapters.synthea import SyntheaAdapter

adapter = SyntheaAdapter(
    source_root=CORPUS / "_sources" / "synthea" / "raw",
    bronze_root=CORPUS / "bronze",
)
patients = adapter.list_patients()
print("Available patients:", patients)
"""),

    code("""\
# Run ingest (idempotent — same output every time due to frozen ACQUISITION_TS)
meta = adapter.ingest("rhett759")
print("source:       ", meta.source)
print("patient_id:   ", meta.patient_id)
print("document_type:", meta.document_type)
print("fetched_at:   ", meta.fetched_at)
print("sha256:       ", meta.sha256[:16], "...")
"""),

    md("## 4. Inspect the bronze FHIR Bundle"),

    code("""\
import json

bronze_bundle = json.loads(
    (CORPUS / "bronze" / "synthea" / "rhett759" / "data.json").read_text()
)
entries = bronze_bundle.get("entry", [])
print(f"Total entries: {len(entries)}")

# Count by resource type
from collections import Counter
types = Counter(e["resource"]["resourceType"] for e in entries if "resource" in e)
for rtype, count in sorted(types.items()):
    print(f"  {rtype}: {count}")
"""),

    md("## 5. Compare bronze shapes across sources"),

    code("""\
# 🔧 Script — same contract, different data shapes
sources_info = {}
for source in ["synthea", "epic-ehi", "lab-pdf", "synthesized-clinical-note", "synthea-payer"]:
    patient_dir = CORPUS / "bronze" / source / "rhett759"
    if not patient_dir.exists():
        sources_info[source] = "not present"
        continue
    files = [f.name for f in sorted(patient_dir.iterdir())]
    sources_info[source] = files

for src, files in sources_info.items():
    print(f"  {src}: {files}")
"""),

    md("**Next:** [02_layer2_synthea_standardize.ipynb](./02_layer2_synthea_standardize.ipynb)"),
])


# ---------------------------------------------------------------------------
# 02 — Layer 2: Synthea Standardize
# ---------------------------------------------------------------------------

nb02 = nb([
    md("""# 02 — Layer 2: Standardize (Synthea)

🔧 Script · 📚 Reference

Layer 2 converts every source into profile-validated FHIR R4 silver. For Synthea the data is already FHIR — the work is annotation: source-tag, lifecycle, and USCDI profile URLs. This notebook traces a single resource from bronze to silver.
"""),

    md("## 1. Silver tier layout"),

    code("""\
from pathlib import Path
import json

ATLAS_ROOT = Path("..").resolve()
CORPUS     = ATLAS_ROOT / "corpus"

silver_dir = CORPUS / "silver" / "synthea" / "rhett759"
print("Silver files:", [f.name for f in silver_dir.iterdir()])
"""),

    md("## 2. Run SyntheaStandardizer"),

    code("""\
# 🔧 Script + 📚 Reference (USCDI profiles)
from ehi_atlas.standardize.synthea import SyntheaStandardizer

standardizer = SyntheaStandardizer(
    bronze_root=CORPUS / "bronze",
    silver_root=CORPUS / "silver",
)
result = standardizer.standardize("rhett759")

print("Hash:              ", result.sha256[:16], "...")
print("Silver path:       ", result.silver_path.split("/")[-2:])
print("Validator errors:  ", len(result.validation_errors))
print("Validator warnings:", len(result.validation_warnings))
"""),

    md("## 3. Bronze → silver: before and after"),

    code("""\
# Pick a Condition entry from bronze and silver and compare meta
bronze_bundle = json.loads(
    (CORPUS / "bronze" / "synthea" / "rhett759" / "data.json").read_text()
)
silver_bundle = json.loads(
    (CORPUS / "silver" / "synthea" / "rhett759" / "bundle.json").read_text()
)

bronze_cond = next(
    e["resource"] for e in bronze_bundle["entry"]
    if e["resource"]["resourceType"] == "Condition"
)
silver_cond = next(
    e["resource"] for e in silver_bundle["entry"]
    if e["resource"]["resourceType"] == "Condition"
)

print("--- BRONZE meta.tag ---")
print(bronze_cond.get("meta", {}).get("tag", "(none)"))

print()
print("--- SILVER meta.tag ---")
for tag in silver_cond.get("meta", {}).get("tag", []):
    print(" ", tag)

print()
print("--- SILVER meta.profile ---")
for prof in silver_cond.get("meta", {}).get("profile", []):
    print(" ", prof)
"""),

    md("## 4. BundleValidator output"),

    code("""\
# 📚 Reference — validates against 32 known USCDI + CARIN-BB profile URLs
# BundleValidator.validate() returns a list of issue strings (empty = clean)
from ehi_atlas.standardize.validators import BundleValidator

validator = BundleValidator(strict=False)
issues = validator.validate(silver_bundle)

print(f"Validation issues: {len(issues)}")
if issues:
    print("First issue:", issues[0])
else:
    print("Silver bundle passes BundleValidator (non-strict mode).")
"""),

    md("**Next:** [03_layer2b_vision_extraction.ipynb](./03_layer2b_vision_extraction.ipynb)"),
])


# ---------------------------------------------------------------------------
# 03 — Layer 2-B: Vision Extraction (PDF → FHIR)
# ---------------------------------------------------------------------------

nb03 = nb([
    md("""# 03 — Layer 2-B: PDF → FHIR (Vision Extraction)

🔧 Script (rasterization, bbox extraction) · 🤖 LLM (actual extraction, cached)

Layer 2-B handles unstructured sources. The showcase lab PDF goes through three steps: rasterize → extract text+bbox → vision LLM → FHIR Observation. This notebook walks each step. **LLM calls read from cache** — running this notebook never hits the Claude API unless you explicitly re-extract.
"""),

    md("## 1. The lab PDF"),

    code("""\
from pathlib import Path
import json

ATLAS_ROOT = Path("..").resolve()
CORPUS     = ATLAS_ROOT / "corpus"

pdf_path = CORPUS / "_sources" / "synthesized-lab-pdf" / "raw" / "lab-report-2025-09-12-quest.pdf"
print("PDF path:", pdf_path)
print("Exists:  ", pdf_path.exists())
print("Size:    ", pdf_path.stat().st_size, "bytes")
"""),

    md("## 2. Render page 2 as an image"),

    code("""\
# 🔧 Script — pypdfium2 rasterization (no system deps)
# Page 2 PNG is pre-generated by the LabPDFAdapter (bronze pages/)
page2_png = CORPUS / "bronze" / "lab-pdf" / "rhett759" / "pages" / "002.png"
print("Pre-generated page 2 image exists:", page2_png.exists())
print("Size:", page2_png.stat().st_size, "bytes")

try:
    import matplotlib.pyplot as plt
    import matplotlib.image as mpimg
    img = mpimg.imread(str(page2_png))
    fig, ax = plt.subplots(figsize=(8, 10))
    ax.imshow(img)
    ax.axis("off")
    ax.set_title("Page 2 — Quest Lab Report (synthesized)", fontsize=11)
    plt.tight_layout()
    plt.show()
    print(f"Image shape: {img.shape}")
except ImportError:
    print("matplotlib not installed — image display skipped.")
    print("Run: uv add matplotlib  (or install in your kernel env)")
"""),

    md("## 3. Extracted text + bbox for page 2"),

    code("""\
# 🔧 Script — pdfplumber text extraction with bounding boxes (bottom-left origin)
# Format: {page, width, height, spans: [{text, page, x1, y1, x2, y2, font_name, font_size}]}
text_json_path = CORPUS / "bronze" / "lab-pdf" / "rhett759" / "pages" / "002.text.json"
page2_text = json.loads(text_json_path.read_text())

spans = page2_text.get("spans", [])
print(f"Spans on page 2: {len(spans)}")
print(f"Page dimensions: {page2_text.get('width')} x {page2_text.get('height')} pt")
print()
# Show first 10 spans with bbox
for span in spans[:10]:
    print(f"  '{span['text']}' @ ({span['x1']:.0f},{span['y1']:.0f},{span['x2']:.0f},{span['y2']:.0f})")
"""),

    md("## 4. Find Creatinine via find_text_bbox"),

    code("""\
# 🔧 Script — extract_layout builds a DocumentLayout; find_text_bbox queries it
from ehi_atlas.extract.layout import extract_layout, find_text_bbox

doc_layout = extract_layout(pdf_path)
print(f"Pages extracted: {len(doc_layout.pages)}")

creatinine_bbox = find_text_bbox(doc_layout, "Creatinine", page=2)
if creatinine_bbox:
    # BBoxResult has .x1/.y1/.x2/.y2; convert to schemas.BBox for to_locator_string()
    schemas_bbox = creatinine_bbox.to_schemas_bbox()
    print("Creatinine bbox (page 2):", schemas_bbox.to_locator_string())
    print("  x1={:.0f}, y1={:.0f}, x2={:.0f}, y2={:.0f}".format(
        schemas_bbox.x1, schemas_bbox.y1, schemas_bbox.x2, schemas_bbox.y2
    ))
    print("Expected (documented): page=2;bbox=72,574,540,590  (within ±5pt)")
else:
    print("Not found on page 2 — check that layout extraction succeeded")
"""),

    md("""## 5. Extraction cache

The vision extraction result is cached by `CacheKey(file_sha256, prompt_version, schema_version, model_name)`. If the cache is empty, running `ehi-atlas extract run` once populates it. The expected `ExtractionResult` shape is shown below.

🤖 LLM step — cached; no API call during this notebook.
"""),

    code("""\
from ehi_atlas.extract.cache import ExtractionCache, CacheKey, hash_file

cache = ExtractionCache()
key = CacheKey(
    file_sha256=hash_file(pdf_path),
    prompt_version="v0.1.0",
    schema_version="extraction-result-v0.1.0",
    model_name="claude-opus-4-7",
)

cached = cache.get(key)
if cached is not None:
    print("Cache hit — showing extraction result:")
    print(json.dumps(cached, indent=2)[:800], "...")
else:
    print("Cache miss — run 'ehi-atlas extract run' once to populate the cache.")
    print()
    shape_lines = [
        '{',
        '  "doc_type": "lab_report",',
        '  "lab_report": {',
        '    "patient_name": "Rhett759 Rohan584",',
        '    "collection_date": "2025-09-12",',
        '    "lab_results": [{"test_name": "Creatinine", "loinc_code": "2160-0",',
        '       "value": 1.4, "unit": "mg/dL", "reference_range": "0.7-1.2",',
        '       "flag": "H", "bbox": {"page": 2, "x1": 72, "y1": 574, "x2": 540, "y2": 590}}]',
        '  }',
        '}',
    ]
    print("Expected ExtractionResult shape:")
    print(chr(10).join(shape_lines))
"""),

    md("## 6. to_fhir: ExtractionResult → FHIR Observation with 5 extraction extensions"),

    code("""\
# 🔧 Script — deterministic FHIR conversion; no LLM involved here
from ehi_atlas.extract.schemas import BBox, ExtractedLabResult
from ehi_atlas.extract.to_fhir import lab_result_to_observation
from ehi_atlas.harmonize.provenance import (
    EXT_EXTRACTION_MODEL, EXT_EXTRACTION_CONFIDENCE,
    EXT_EXTRACTION_PROMPT_VER, EXT_SOURCE_ATTACHMENT, EXT_SOURCE_LOCATOR,
)

result_row = ExtractedLabResult(
    test_name="Creatinine",
    loinc_code="2160-0",
    value_quantity=1.4,
    unit="mg/dL",
    reference_range_low=0.7,
    reference_range_high=1.2,
    flag="H",
    effective_date="2025-09-12",
    bbox=BBox(page=2, x1=72, y1=574, x2=540, y2=590),
)

obs = lab_result_to_observation(
    result=result_row,
    patient_id="rhett759",
    source_attachment_id="quest-2025-09-12",
    model="claude-opus-4-7",
    prompt_version="v0.1.0",
    confidence=0.97,
)

print("resourceType:", obs["resourceType"])
print("code:", obs.get("code"))
print("valueQuantity:", obs.get("valueQuantity"))
print()
meta_exts = obs.get("meta", {}).get("extension", [])
ext_urls = [e["url"].split("/")[-1] for e in meta_exts]
print("meta.extension count:", len(meta_exts))
print("Extension types:", ext_urls)
locator = next((e.get("valueString") for e in meta_exts
                if "source-locator" in e.get("url", "")), None)
print("source-locator:", locator)
"""),

    md("**Next:** [04_layer3_code_mapping.ipynb](./04_layer3_code_mapping.ipynb)"),
])


# ---------------------------------------------------------------------------
# 04 — Layer 3a: Code Mapping / UMLS-CUI bridge
# ---------------------------------------------------------------------------

nb04 = nb([
    md("""# 04 — Layer 3a: Code Mapping (UMLS-CUI Bridge)

🔧 Script · 📚 Reference

Layer 3 starts with code-system unification. Two conditions coded in SNOMED (Synthea) and ICD-10 (Epic) are the same condition — they share a UMLS CUI in our hand-curated crosswalk. This notebook shows the lookup and annotation machinery.
"""),

    md("## 1. The hand-curated crosswalk"),

    code("""\
from pathlib import Path
import json

ATLAS_ROOT = Path("..").resolve()
CORPUS     = ATLAS_ROOT / "corpus"

xwalk_path = CORPUS / "reference" / "handcrafted-crosswalk" / "showcase.json"
xwalk = json.loads(xwalk_path.read_text())

print(f"Crosswalk version: {xwalk['version']}")
print(f"Entries: {len(xwalk['codes'])}")
print()
for entry in xwalk["codes"][:4]:
    print(f"  {entry['concept_label']}  (CUI {entry['umls_cui']})")
    if entry.get("snomed_ct"):
        print(f"    SNOMED {entry['snomed_ct']['code']} — {entry['snomed_ct']['display']}")
    if entry.get("icd_10_cm"):
        print(f"    ICD-10 {entry['icd_10_cm']['code']} — {entry['icd_10_cm']['display']}")
    if entry.get("rxnorm"):
        print(f"    RxNorm {entry['rxnorm']['rxcui']} — {entry['rxnorm']['display']}")
"""),

    md("## 2. lookup_cross — Artifact 1 anchor: Hyperlipidemia"),

    code("""\
# 📚 Reference — both codes resolve to CUI C0020473 (Hyperlipidemia)
from ehi_atlas.terminology import lookup_cross
from ehi_atlas.harmonize.code_map import SYS_SNOMED, SYS_ICD10_CM

# Synthea uses SNOMED
snomed_entry = lookup_cross(SYS_SNOMED, "55822004")
print("SNOMED 55822004 →", snomed_entry["concept_label"] if snomed_entry else "not found")
print("  CUI:", snomed_entry["umls_cui"] if snomed_entry else "—")

print()
# Epic projection uses ICD-10
icd10_entry = lookup_cross(SYS_ICD10_CM, "E78.5")
print("ICD-10 E78.5 →", icd10_entry["concept_label"] if icd10_entry else "not found")
print("  CUI:", icd10_entry["umls_cui"] if icd10_entry else "—")
"""),

    md("## 3. codings_equivalent"),

    code("""\
# 🔧 Script
from ehi_atlas.harmonize.code_map import codings_equivalent

snomed_coding = {"system": SYS_SNOMED,   "code": "55822004", "display": "Hyperlipidemia"}
icd10_coding  = {"system": SYS_ICD10_CM, "code": "E78.5",    "display": "Hyperlipidemia, unspecified"}

result = codings_equivalent(snomed_coding, icd10_coding)
print("codings_equivalent(SNOMED 55822004, ICD-10 E78.5):", result)
print("→ Both map to UMLS CUI C0020473 via the crosswalk")
"""),

    md("## 4. annotate_codeable_concept_with_cui"),

    code("""\
# 🔧 Script — attaches EXT_UMLS_CUI to each coding in place
import copy
from ehi_atlas.harmonize.code_map import annotate_codeable_concept_with_cui
from ehi_atlas.harmonize.provenance import EXT_UMLS_CUI

sample_cc = {
    "coding": [
        {"system": SYS_SNOMED,   "code": "55822004", "display": "Hyperlipidemia"},
        {"system": SYS_ICD10_CM, "code": "E78.5",    "display": "Hyperlipidemia, unspecified"},
    ],
    "text": "Hyperlipidemia",
}

before_ext = [c.get("extension", []) for c in sample_cc["coding"]]
annotate_codeable_concept_with_cui(sample_cc)
after_ext  = [c.get("extension", []) for c in sample_cc["coding"]]

print("Before: no extensions on codings")
print("After:")
for i, coding in enumerate(sample_cc["coding"]):
    for ext in coding.get("extension", []):
        if ext["url"] == EXT_UMLS_CUI:
            print(f"  coding[{i}] ({coding['system'].split('/')[-1]}) → CUI {ext['valueString']}")
"""),

    md("""## 5. Note: This is the Artifact 1 anchor mechanism

`annotate_codeable_concept_with_cui` is called on every Condition in every silver bundle during the orchestrator's annotation pass. Once both the Synthea SNOMED and Epic ICD-10 codings carry `EXT_UMLS_CUI = C0020473`, the condition merger clusters them into one gold-tier Condition (notebook 06).
"""),

    md("**Next:** [05_layer3_temporal_and_identity.ipynb](./05_layer3_temporal_and_identity.ipynb)"),
])


# ---------------------------------------------------------------------------
# 05 — Layer 3b: Temporal + Identity
# ---------------------------------------------------------------------------

nb05 = nb([
    md("""# 05 — Layer 3b: Temporal Alignment + Patient Identity

🔧 Script

Two more Layer 3 sub-tasks: (1) temporal alignment, especially the Mandel rule for DocumentReferences; (2) patient identity resolution across sources via Fellegi-Sunter probabilistic linkage.
"""),

    md("## Section 1 — Temporal alignment"),

    md("### 1a. The Mandel rule on DocumentReference"),

    code("""\
from pathlib import Path
from ehi_atlas.harmonize.temporal import clinical_time

# Build a DocumentReference with only the metadata date set (NOT context.period.start)
docref_metadata_only = {
    "resourceType": "DocumentReference",
    "id": "docref-metadata-test",
    "date": "2025-11-01T09:00:00Z",   # ← this is INDEX time, not clinical time
    "status": "current",
    "type": {"coding": [{"system": "http://loinc.org", "code": "11506-3"}]},
}

ct = clinical_time(docref_metadata_only)
print("DocumentReference with ONLY date set:")
print("  timestamp:", ct.timestamp)
print("  confidence:", ct.confidence)
print("  source_field:", ct.source_field)
print()
print("→ The Mandel rule: docRef.date is NOT used as clinical time (confidence='uncertain')")
"""),

    code("""\
# Now add context.period.start — this IS clinical time
docref_with_context = {
    "resourceType": "DocumentReference",
    "id": "docref-context-test",
    "date": "2025-11-01T09:00:00Z",
    "status": "current",
    "context": {
        "period": {
            "start": "2026-01-15",   # ← this is the clinical encounter date
        }
    },
    "type": {"coding": [{"system": "http://loinc.org", "code": "11506-3"}]},
}

ct = clinical_time(docref_with_context)
print("DocumentReference with context.period.start set:")
print("  timestamp:", ct.timestamp)
print("  confidence:", ct.confidence)
print("  source_field:", ct.source_field)
"""),

    md("### 1b. normalize_bundle_temporal on a small bundle"),

    code("""\
from ehi_atlas.harmonize.temporal import normalize_bundle_temporal, EXT_CLINICAL_TIME

# Build a mini bundle with two resources
mini_bundle = {
    "resourceType": "Bundle",
    "type": "collection",
    "entry": [
        {"resource": {
            "resourceType": "Observation",
            "id": "obs-creatinine",
            "status": "final",
            "effectiveDateTime": "2025-09-12",
            "code": {"coding": [{"system": "http://loinc.org", "code": "2160-0"}]},
            "valueQuantity": {"value": 1.4, "unit": "mg/dL"},
        }},
        {"resource": {
            "resourceType": "Condition",
            "id": "cond-hyperlipidemia",
            "onsetDateTime": "2020-03-01",
            "code": {"coding": [{"system": "http://snomed.info/sct", "code": "55822004"}]},
        }},
    ],
}

normalize_bundle_temporal(mini_bundle)

for entry in mini_bundle["entry"]:
    res = entry["resource"]
    exts = res.get("meta", {}).get("extension", [])
    ct_ext = next((e for e in exts if e.get("url") == EXT_CLINICAL_TIME), None)
    if ct_ext:
        print(f"{res['resourceType']}/{res['id']} → clinical_time = {ct_ext.get('valueDateTime') or ct_ext.get('valueString')}")
"""),

    md("## Section 2 — Patient identity resolution"),

    md("### 2a. Build two PatientFingerprints for Rhett759 from different sources"),

    code("""\
from ehi_atlas.harmonize.identity import PatientFingerprint, score

fp_synthea = PatientFingerprint(
    source="synthea",
    local_patient_id="rhett759-synthea",
    family_name="Rohan584",
    given_names=("Rhett759",),
    birth_date="1966-09-14",
    gender="male",
    address_zip="01001",
    mrn_value="rhett759-mrn-synthea",
    mrn_system="synthea://mrn",
)

fp_epic = PatientFingerprint(
    source="epic-ehi",
    local_patient_id="RHETT759",
    family_name="Rohan584",
    given_names=("Rhett759",),
    birth_date="1966-09-14",
    gender="male",
    address_zip=None,
    mrn_value="MRN-EPIC-RHETT",
    mrn_system="urn:epic:mrn",
)

match_score = score(fp_synthea, fp_epic)
print("Fellegi-Sunter aggregate score:", round(match_score.aggregate, 4))
print("Decision:", match_score.decision)
print()
print("Component scores:")
print("  name:   ", round(match_score.name, 4))
print("  dob:    ", round(match_score.dob, 4))
print("  address:", round(match_score.address, 4))
print("  gender: ", round(match_score.gender, 4))
"""),

    md("### 2b. build_identity_index → one canonical record"),

    code("""\
from ehi_atlas.harmonize.identity import build_identity_index, merged_patient_resource

index = build_identity_index(
    [fp_synthea, fp_epic],
    canonical_id_for={
        fp_synthea.local_patient_id: "rhett759",
        fp_epic.local_patient_id:    "rhett759",
    },
)

canon = index.canonical_patients["rhett759"]
print("Canonical ID:", canon.canonical_id)
print("Contributing sources:", [fp.source for fp in canon.fingerprints])
merged_pat = merged_patient_resource(canon)
print("Merged Patient.id:", merged_pat["id"])
print("Merged identifiers:")
for ident in merged_pat.get("identifier", [])[:4]:
    print(f"  {ident.get('system')}: {ident.get('value')}")
"""),

    md("**Next:** [06_layer3_condition_merge_artifact_1.ipynb](./06_layer3_condition_merge_artifact_1.ipynb)"),
])


# ---------------------------------------------------------------------------
# 06 — Artifact 1: Condition merge (Hyperlipidemia)
# ---------------------------------------------------------------------------

nb06 = nb([
    md("""# 06 — Artifact 1: Hyperlipidemia Condition Merge

🔧 Script · 📚 Reference

**Artifact 1:** Rhett759 has Hyperlipidemia in two sources — Synthea (SNOMED 55822004) and Epic projection (ICD-10 E78.5). These are the same condition under different code systems. Layer 3 merges them into one canonical gold-tier Condition using the UMLS-CUI bridge.
"""),

    md("## 1. Build the two silver-tier Conditions"),

    code("""\
from ehi_atlas.harmonize.provenance import SYS_SOURCE_TAG, SYS_LIFECYCLE

# Synthea: SNOMED
cond_synthea = {
    "resourceType": "Condition",
    "id": "synthea-cond-hyperlipid",
    "meta": {"tag": [
        {"system": SYS_SOURCE_TAG, "code": "synthea"},
        {"system": SYS_LIFECYCLE,  "code": "standardized"},
    ]},
    "clinicalStatus": {"coding": [{"system": "http://terminology.hl7.org/CodeSystem/condition-clinical", "code": "active"}]},
    "code": {
        "coding": [{"system": "http://snomed.info/sct", "code": "55822004", "display": "Hyperlipidemia"}],
        "text": "Hyperlipidemia",
    },
    "subject": {"reference": "Patient/rhett759"},
    "onsetDateTime": "2020-03-15",
}

# Epic projection: ICD-10 only (forces the UMLS-CUI bridge)
cond_epic = {
    "resourceType": "Condition",
    "id": "epic-cond-e785",
    "meta": {"tag": [
        {"system": SYS_SOURCE_TAG, "code": "epic-ehi"},
        {"system": SYS_LIFECYCLE,  "code": "stub-silver"},
    ]},
    "clinicalStatus": {"coding": [{"system": "http://terminology.hl7.org/CodeSystem/condition-clinical", "code": "active"}]},
    "code": {
        "coding": [{"system": "http://hl7.org/fhir/sid/icd-10-cm", "code": "E78.5", "display": "Hyperlipidemia, unspecified"}],
        "text": "Hyperlipidemia, unspecified",
    },
    "subject": {"reference": "Patient/rhett759"},
    "onsetDateTime": "2021-09-01",
}

print("Built cond_synthea (SNOMED 55822004) and cond_epic (ICD-10 E78.5)")
"""),

    md("## 2. cluster_conditions_by_cui"),

    code("""\
# 🔧 Script + 📚 Reference
from ehi_atlas.harmonize.code_map import (
    annotate_resource_codings,
    collect_concept_groups,
)

# First, annotate each condition with UMLS CUI extensions
annotate_resource_codings(cond_synthea)
annotate_resource_codings(cond_epic)

# cluster_conditions_by_cui groups by shared CUI
conditions_by_source = {
    "synthea":  [cond_synthea],
    "epic-ehi": [cond_epic],
}

clusters = collect_concept_groups([cond_synthea, cond_epic])
print(f"CUI clusters found: {len(clusters)}")
for cui, group in clusters.items():
    print(f"  CUI {cui}: {len(group)} condition(s)")
    for c in group:
        print(f"    id={c['id']}, codings={[cd['code'] for cd in c['code']['coding']]}")
"""),

    md("## 3. merge_conditions"),

    code("""\
from ehi_atlas.harmonize.condition import merge_conditions

# Take the first (and only) cluster
cui, cluster = next(iter(clusters.items()))
result = merge_conditions(cluster, f"merged-cond-rhett-hyperlipid")

merged = result.merged
print("Merged Condition ID:", merged["id"])
print("Sources:",            result.sources)
print("Rationale:",          result.rationale)
"""),

    md("## 4. Inspect the merged result"),

    code("""\
import json

print("code.coding (both systems preserved):")
for coding in merged["code"]["coding"]:
    cui_ext = next((e["valueString"] for e in coding.get("extension", [])
                    if "umls-cui" in e.get("url", "")), None)
    print(f"  {coding['system'].split('/')[-1]} {coding['code']}: {coding.get('display', '')}  →  CUI {cui_ext}")

print()
print("meta.tag (both source-tags + lifecycle=harmonized):")
for tag in merged.get("meta", {}).get("tag", []):
    print(f"  {tag.get('system','').split('/')[-1]}: {tag.get('code','')}")

print()
print("onsetDateTime (earliest = Synthea's 2020-03-15):", merged.get("onsetDateTime"))

print()
print("merge-rationale extension:")
from ehi_atlas.harmonize.provenance import EXT_MERGE_RATIONALE
for ext in merged.get("meta", {}).get("extension", []):
    if EXT_MERGE_RATIONALE in ext.get("url", ""):
        print(" ", ext.get("valueString"))
"""),

    md("## 5. Confirm against the actual gold bundle"),

    code("""\
from pathlib import Path
import json

ATLAS_ROOT = Path("..").resolve()
gold_bundle = json.loads(
    (ATLAS_ROOT / "corpus" / "gold" / "patients" / "rhett759" / "bundle.json").read_text()
)

# Find the merged Hyperlipidemia condition
gold_hyperlipid = None
for entry in gold_bundle["entry"]:
    res = entry["resource"]
    if res.get("resourceType") != "Condition":
        continue
    codings = res.get("code", {}).get("coding", [])
    codes = {c.get("code") for c in codings}
    if "55822004" in codes or "E78.5" in codes:
        gold_hyperlipid = res
        break

if gold_hyperlipid:
    print("Found in gold bundle: Condition/", gold_hyperlipid["id"])
    print("Codings:", [(c.get("system","").split("/")[-1], c["code"]) for c in gold_hyperlipid["code"]["coding"]])
    tags = [t["code"] for t in gold_hyperlipid.get("meta", {}).get("tag", [])]
    print("Source tags:", [t for t in tags if t not in ("harmonized", "gold")])
else:
    print("Not found — re-run 'make pipeline' to regenerate gold tier")
"""),

    md("**Next:** [07_layer3_medication_artifact_2.ipynb](./07_layer3_medication_artifact_2.ipynb)"),
])


# ---------------------------------------------------------------------------
# 07 — Artifact 2: Medication cross-class (statin divergence)
# ---------------------------------------------------------------------------

nb07 = nb([
    md("""# 07 — Artifact 2: Statin Cross-Class Divergence

🔧 Script · 📚 Reference

**Artifact 2:** Rhett759 is on simvastatin (Synthea) and atorvastatin (Epic). These are *different* drugs in the same therapeutic class (HMG-CoA reductase inhibitors — statins). The harmonizer does NOT merge them; it surfaces a `CrossClassFlag` and attaches `EXT_CONFLICT_PAIR` to both resources.
"""),

    md("## 1. Build the two silver-tier MedicationRequests"),

    code("""\
from ehi_atlas.harmonize.provenance import SYS_SOURCE_TAG, SYS_LIFECYCLE

# Synthea uses RxCUI 316672 (product-level SCD: "Simvastatin 10 MG Oral Tablet")
med_synthea = {
    "resourceType": "MedicationRequest",
    "id": "synthea-med-simvastatin",
    "meta": {"tag": [
        {"system": SYS_SOURCE_TAG, "code": "synthea"},
        {"system": SYS_LIFECYCLE,  "code": "standardized"},
    ]},
    "status": "active",
    "intent": "order",
    "medicationCodeableConcept": {
        "coding": [{"system": "http://www.nlm.nih.gov/research/umls/rxnorm",
                    "code": "316672", "display": "Simvastatin 10 MG Oral Tablet"}],
        "text": "Simvastatin 10 MG Oral Tablet",
    },
    "subject": {"reference": "Patient/rhett759"},
    "authoredOn": "2022-06-01",
}

# Epic uses RxCUI 83367 (ingredient-level: atorvastatin), discontinued
med_epic = {
    "resourceType": "MedicationRequest",
    "id": "epic-med-atorvastatin",
    "meta": {"tag": [
        {"system": SYS_SOURCE_TAG, "code": "epic-ehi"},
        {"system": SYS_LIFECYCLE,  "code": "stub-silver"},
    ]},
    "status": "stopped",
    "intent": "order",
    "medicationCodeableConcept": {
        "coding": [{"system": "http://www.nlm.nih.gov/research/umls/rxnorm",
                    "code": "83367", "display": "atorvastatin"}],
        "text": "atorvastatin",
    },
    "subject": {"reference": "Patient/rhett759"},
    "authoredOn": "2024-01-15",
    "dispenseRequest": {"validityPeriod": {"start": "2024-01-15", "end": "2025-09-01"}},
}

print("Built simvastatin (RxCUI 316672, active) and atorvastatin (RxCUI 83367, stopped)")
"""),

    md("## 2. episode_from_medication_request"),

    code("""\
# 🔧 Script
from ehi_atlas.harmonize.medication import episode_from_medication_request

ep_simva = episode_from_medication_request(med_synthea)
ep_atorva = episode_from_medication_request(med_epic)

print("Simvastatin episode:")
print(f"  rxcui={ep_simva.rxcui}  status={ep_simva.status}  label={ep_simva.ingredient_label}")

print()
print("Atorvastatin episode:")
print(f"  rxcui={ep_atorva.rxcui}  status={ep_atorva.status}  period={ep_atorva.period_start} → {ep_atorva.period_end}")
"""),

    md("## 3. episodes_same_ingredient → False"),

    code("""\
from ehi_atlas.harmonize.medication import episodes_same_ingredient

same = episodes_same_ingredient(ep_simva, ep_atorva)
print("episodes_same_ingredient(simvastatin, atorvastatin):", same)
print("→ Different ingredients → kept as separate gold episodes")
"""),

    md("## 4. detect_cross_class_flags"),

    code("""\
from ehi_atlas.harmonize.medication import detect_cross_class_flags

flags = detect_cross_class_flags([ep_simva, ep_atorva])
print(f"Cross-class flags found: {len(flags)}")
if flags:
    f = flags[0]
    # ingredient_a / ingredient_b are RxCUI strings; sources_a / sources_b are source-tag lists
    print(f"  ingredient_a (RxCUI): {f.ingredient_a}  sources: {f.sources_a}")
    print(f"  ingredient_b (RxCUI): {f.ingredient_b}  sources: {f.sources_b}")
    print(f"  class_label: {f.common_class_label}")
"""),

    md("## 5. detect_medication_class_conflicts + apply_conflict_pairs"),

    code("""\
from ehi_atlas.harmonize.conflict import detect_medication_class_conflicts, apply_conflict_pairs
from dataclasses import dataclass

# Adapt CrossClassFlag to the protocol shape expected by conflict.py
@dataclass
class AdaptedFlag:
    ingredient_a: str
    ingredient_b: str
    class_label: str
    source_a: str
    source_b: str
    resource_a_reference: str
    resource_b_reference: str

if flags:
    f = flags[0]
    adapted = [AdaptedFlag(
        ingredient_a=f.ingredient_a,
        ingredient_b=f.ingredient_b,
        class_label=f.common_class_label,
        source_a=ep_simva.source_tag or "synthea",
        source_b=ep_atorva.source_tag or "epic-ehi",
        resource_a_reference=f"MedicationRequest/{med_synthea['id']}",
        resource_b_reference=f"MedicationRequest/{med_epic['id']}",
    )]

    conflicts = detect_medication_class_conflicts(adapted)
    print(f"ConflictPairs detected: {len(conflicts)}")
    if conflicts:
        cp = conflicts[0]
        print(f"  kind:    {cp.kind}")
        print(f"  label:   {cp.label}")
        print(f"  summary: {cp.summary}")

    # Apply symmetric conflict-pair extensions to both resources
    resources_by_ref = {
        f"MedicationRequest/{med_synthea['id']}": med_synthea,
        f"MedicationRequest/{med_epic['id']}": med_epic,
    }
    apply_conflict_pairs(conflicts, resources_by_ref)

    from ehi_atlas.harmonize.provenance import EXT_CONFLICT_PAIR
    for med, name in [(med_synthea, "simvastatin"), (med_epic, "atorvastatin")]:
        ext = next((e for e in med.get("extension", []) if e.get("url") == EXT_CONFLICT_PAIR), None)
        print(f"  {name} EXT_CONFLICT_PAIR → {ext.get('valueReference', {}).get('reference') if ext else 'not set'}")
"""),

    md("""## 6. Note: two-part bug fix (task 3.11)

The integration test found two issues and fixed them inline:
1. Synthea emits RxCUI **316672** (product-level SCD) not 36567 (ingredient-level). Added 316672 to `_RXCUI_CLASS_LABEL`.
2. `apply_conflict_pairs` mutated the silver dict, but the merged gold dict is a new object. The orchestrator now propagates `EXT_CONFLICT_PAIR` from silver to gold after the merge step.

Both fixes are in `ehi_atlas/harmonize/medication.py` and `ehi_atlas/harmonize/orchestrator.py`.
"""),

    md("## 7. Confirm in the actual gold bundle"),

    code("""\
from pathlib import Path
import json

ATLAS_ROOT = Path("..").resolve()
gold_bundle = json.loads(
    (ATLAS_ROOT / "corpus" / "gold" / "patients" / "rhett759" / "bundle.json").read_text()
)

from ehi_atlas.harmonize.provenance import EXT_CONFLICT_PAIR

statin_meds = []
for entry in gold_bundle["entry"]:
    res = entry["resource"]
    if res.get("resourceType") != "MedicationRequest":
        continue
    codings = res.get("medicationCodeableConcept", {}).get("coding", [])
    rxcuis = {c.get("code") for c in codings}
    if rxcuis & {"316672", "83367", "36567"}:
        statin_meds.append(res)

print(f"Statin MedicationRequests in gold: {len(statin_meds)}")
for med in statin_meds:
    codings = med.get("medicationCodeableConcept", {}).get("coding", [])
    rxcui = next((c.get("code") for c in codings), "?")
    has_conflict = any(e.get("url") == EXT_CONFLICT_PAIR for e in med.get("extension", []))
    print(f"  {med['id']}  RxCUI={rxcui}  status={med['status']}  conflict_pair={has_conflict}")
"""),

    md("**Next:** [08_layer3_observation_artifact_5.ipynb](./08_layer3_observation_artifact_5.ipynb)"),
])


# ---------------------------------------------------------------------------
# 08 — Artifact 5: Creatinine cross-format merge
# ---------------------------------------------------------------------------

nb08 = nb([
    md("""# 08 — Artifact 5: Creatinine Cross-Format Merge

🔧 Script · 📚 Reference

**Artifact 5:** A creatinine result (1.4 mg/dL on 2025-09-12) appears in two sources — the Epic EHI SQLite dump and the synthesized lab PDF. Both express LOINC 2160-0. Layer 3 deduplicates them into one merged Observation with both source-tags, both identifiers, and the max quality score.
"""),

    md("## 1. Build the two silver-tier Observations"),

    code("""\
from ehi_atlas.harmonize.provenance import SYS_SOURCE_TAG, SYS_LIFECYCLE

obs_epic = {
    "resourceType": "Observation",
    "id": "epic-obs-creatinine",
    "meta": {
        "tag": [
            {"system": SYS_SOURCE_TAG, "code": "epic-ehi"},
            {"system": SYS_LIFECYCLE,  "code": "stub-silver"},
        ],
        "extension": [{"url": "https://ehi-atlas.example/fhir/StructureDefinition/quality-score",
                        "valueDecimal": 0.78}],
    },
    "status": "final",
    "category": [{"coding": [{"system": "http://terminology.hl7.org/CodeSystem/observation-category",
                               "code": "laboratory"}]}],
    "code": {
        "coding": [{"system": "http://loinc.org", "code": "2160-0",
                    "display": "Creatinine [Mass/volume] in Serum or Plasma"}],
        "text": "Creatinine",
    },
    "subject": {"reference": "Patient/rhett759"},
    "effectiveDateTime": "2025-09-12",
    "valueQuantity": {"value": 1.4, "unit": "mg/dL", "system": "http://unitsofmeasure.org", "code": "mg/dL"},
}

obs_lab_pdf = {
    "resourceType": "Observation",
    "id": "lab-pdf-obs-creatinine-rhett759",
    "meta": {
        "tag": [
            {"system": SYS_SOURCE_TAG, "code": "lab-pdf"},
            {"system": SYS_LIFECYCLE,  "code": "stub-silver"},
        ],
        "extension": [{"url": "https://ehi-atlas.example/fhir/StructureDefinition/quality-score",
                        "valueDecimal": 0.48}],
    },
    "status": "final",
    "category": [{"coding": [{"system": "http://terminology.hl7.org/CodeSystem/observation-category",
                               "code": "laboratory"}]}],
    "code": {
        "coding": [{"system": "http://loinc.org", "code": "2160-0",
                    "display": "Creatinine [Mass/volume] in Serum or Plasma"}],
        "text": "Creatinine",
    },
    "subject": {"reference": "Patient/rhett759"},
    "effectiveDateTime": "2025-09-12",
    "valueQuantity": {"value": 1.4, "unit": "mg/dL", "system": "http://unitsofmeasure.org", "code": "mg/dL"},
}

print("Built obs_epic (quality 0.78) and obs_lab_pdf (quality 0.48)")
"""),

    md("## 2. extract_observation_key"),

    code("""\
# 🔧 Script
from ehi_atlas.harmonize.observation import extract_observation_key

key_epic    = extract_observation_key(obs_epic)
key_lab_pdf = extract_observation_key(obs_lab_pdf)

print("Epic key:   ", key_epic)
print("Lab-PDF key:", key_lab_pdf)
"""),

    md("## 3. observations_equivalent → True"),

    code("""\
from ehi_atlas.harmonize.observation import observations_equivalent

equivalent = observations_equivalent(obs_epic, obs_lab_pdf)
print("observations_equivalent(obs_epic, obs_lab_pdf):", equivalent)
print("→ Same LOINC + same date + same value (±0.1%) + same unit → exact dedup")
"""),

    md("## 4. merge_observations"),

    code("""\
from ehi_atlas.harmonize.observation import merge_observations

result = merge_observations([obs_epic, obs_lab_pdf], "merged-obs-rhett-creatinine")
merged = result.merged

print("Merged Observation ID:", merged["id"])
print("Sources:", result.sources)
print("Rationale:", result.rationale)
"""),

    md("## 5. Inspect the merged Observation"),

    code("""\
import json

print("status:", merged["status"])
print("effectiveDateTime:", merged.get("effectiveDateTime"))
print("valueQuantity:", merged.get("valueQuantity"))

print()
print("meta.tag (both source-tags):")
for tag in merged.get("meta", {}).get("tag", []):
    print(f"  {tag.get('system','').split('/')[-1]}: {tag.get('code','')}")

print()
quality_ext = next(
    (e for e in merged.get("meta", {}).get("extension", [])
     if "quality-score" in e.get("url", "")),
    None
)
print("quality score (max of 0.78, 0.48):", quality_ext.get("valueDecimal") if quality_ext else "—")

print()
rationale_ext = next(
    (e for e in merged.get("meta", {}).get("extension", [])
     if "merge-rationale" in e.get("url", "")),
    None
)
print("merge-rationale:", rationale_ext.get("valueString") if rationale_ext else "—")
"""),

    md("## 6. Confirm in the actual gold bundle"),

    code("""\
from pathlib import Path
import json

ATLAS_ROOT = Path("..").resolve()
gold_bundle = json.loads(
    (ATLAS_ROOT / "corpus" / "gold" / "patients" / "rhett759" / "bundle.json").read_text()
)

creatinine_obs = None
for entry in gold_bundle["entry"]:
    res = entry["resource"]
    if res.get("resourceType") != "Observation":
        continue
    codings = res.get("code", {}).get("coding", [])
    if any(c.get("code") == "2160-0" for c in codings):
        creatinine_obs = res
        break

if creatinine_obs:
    print("Gold creatinine Observation:", creatinine_obs["id"])
    print("effectiveDateTime:", creatinine_obs.get("effectiveDateTime"))
    print("valueQuantity:", creatinine_obs.get("valueQuantity"))
    src_tags = [t["code"] for t in creatinine_obs.get("meta", {}).get("tag", [])
                if "source-tag" in t.get("system", "")]
    print("source-tags:", src_tags)
else:
    print("Not found — re-run 'make pipeline' to regenerate gold tier")
"""),

    md("**Next:** [09_orchestrator_end_to_end.ipynb](./09_orchestrator_end_to_end.ipynb)"),
])


# ---------------------------------------------------------------------------
# 09 — Orchestrator: end-to-end + all 5 artifacts
# ---------------------------------------------------------------------------

nb09 = nb([
    md("""# 09 — Full Pipeline: Orchestrator + All 5 Artifacts

⚙️ Hybrid

`harmonize_patient` is the entry point for the entire Layer 3 pipeline. It reads silver bundles, runs every sub-task in dependency order, and writes gold-tier output. This notebook re-runs the pipeline (idempotent), inspects the manifest, and locates each of the 5 showcase artifacts in the gold bundle.
"""),

    md("## 1. Run harmonize_patient (idempotent)"),

    code("""\
from pathlib import Path
import json

ATLAS_ROOT = Path("..").resolve()
CORPUS     = ATLAS_ROOT / "corpus"

from ehi_atlas.harmonize.orchestrator import harmonize_patient

result = harmonize_patient(
    silver_root = CORPUS / "silver",
    bronze_root = CORPUS / "bronze",
    gold_root   = CORPUS / "gold",
    patient_id  = "rhett759",
)

print("patient_id:   ", result.patient_id)
print("source_count: ", result.source_count)
print("conflicts:    ", result.conflict_count)
print("bundle_sha256:", result.bundle_sha256[:16], "...")
"""),

    md("## 2. manifest.json"),

    code("""\
manifest = json.loads(result.manifest_path.read_text())
print("Built at:", manifest["built_at"])
print("Sources:")
for s in manifest["sources"]:
    print(f"  {s['name']}")
print()
print("Resource counts:")
for rtype, count in sorted(manifest["resource_counts"].items()):
    print(f"  {rtype}: {count}")
print()
print("Merge summary:", manifest["merge_summary"])
"""),

    md("## 3. Load the gold bundle"),

    code("""\
gold_bundle = json.loads(result.bundle_path.read_text())
entries = gold_bundle["entry"]
print(f"Total gold resources: {len(entries)}")

from collections import Counter
types = Counter(e["resource"]["resourceType"] for e in entries)
for rtype, count in sorted(types.items()):
    print(f"  {rtype}: {count}")
"""),

    md("## 4. Artifact 1 — Hyperlipidemia merge (SNOMED + ICD-10 → one Condition)"),

    code("""\
# 🔧 Script + 📚 Reference
from ehi_atlas.harmonize.provenance import EXT_UMLS_CUI

gold_hyperlipid = None
for entry in gold_bundle["entry"]:
    res = entry["resource"]
    if res.get("resourceType") != "Condition":
        continue
    codes = {c.get("code") for c in res.get("code", {}).get("coding", [])}
    if codes & {"55822004", "E78.5"}:
        gold_hyperlipid = res
        break

if gold_hyperlipid:
    print("Artifact 1 — Condition:", gold_hyperlipid["id"])
    for coding in gold_hyperlipid["code"]["coding"]:
        cui = next((e["valueString"] for e in coding.get("extension", [])
                    if "umls-cui" in e.get("url","")), None)
        print(f"  {coding.get('system','').split('/')[-1]} {coding['code']} → CUI {cui}")
    src_tags = [t["code"] for t in gold_hyperlipid.get("meta",{}).get("tag",[])
                if "source-tag" in t.get("system","")]
    print("  source-tags:", src_tags)
else:
    print("Artifact 1 not found")
"""),

    md("## 5. Artifact 2 — statin MedicationRequests with EXT_CONFLICT_PAIR"),

    code("""\
# 🔧 Script + 📚 Reference
from ehi_atlas.harmonize.provenance import EXT_CONFLICT_PAIR

statin_meds = []
for entry in gold_bundle["entry"]:
    res = entry["resource"]
    if res.get("resourceType") != "MedicationRequest":
        continue
    rxcuis = {c.get("code") for c in res.get("medicationCodeableConcept",{}).get("coding",[])}
    if rxcuis & {"316672", "83367", "36567"}:
        statin_meds.append(res)

print(f"Artifact 2 — statin MedicationRequests: {len(statin_meds)}")
for med in statin_meds:
    rxcui = next((c.get("code") for c in med.get("medicationCodeableConcept",{}).get("coding",[])), "?")
    conflict = next((e.get("valueReference",{}).get("reference") for e in med.get("extension",[])
                     if e.get("url") == EXT_CONFLICT_PAIR), None)
    print(f"  {med['id']}  rxcui={rxcui}  status={med['status']}  conflict_pair → {conflict}")
"""),

    md("## 6. Artifact 3 — single-source Claim (pass-through)"),

    code("""\
# Claim resources are pass-through (no merge logic in Phase 1)
claims = [e["resource"] for e in gold_bundle["entry"]
          if e["resource"]["resourceType"] == "Claim"]
print(f"Artifact 3 — Claims in gold: {len(claims)}")
if claims:
    c0 = claims[0]
    src_tags = [t["code"] for t in c0.get("meta",{}).get("tag",[])
                if "source-tag" in t.get("system","")]
    print(f"  Example: {c0['id']}  source-tags: {src_tags}")
    print(f"  (Single source — pass-through; no cross-source merge)")
"""),

    md("## 7. Artifact 4 — synthesized clinical note DocumentReference"),

    code("""\
# Phase-1 partial: DocumentReference present; NLP extraction of chest-tightness
# Condition is a Phase-2 gap (requires vision wrapper wired to clinical note).
doc_refs = [e["resource"] for e in gold_bundle["entry"]
            if e["resource"]["resourceType"] == "DocumentReference"]
print(f"Artifact 4 — DocumentReferences in gold: {len(doc_refs)}")
for dr in doc_refs:
    src_tags = [t["code"] for t in dr.get("meta",{}).get("tag",[])
                if "source-tag" in t.get("system","")]
    loinc = next(
        (c.get("code") for c in dr.get("type",{}).get("coding",[])),
        "?"
    )
    print(f"  {dr['id']}  type-LOINC={loinc}  source={src_tags}")
    print(f"  Phase-2 gap: chest-tightness Condition extraction requires vision wrapper on .txt")
"""),

    md("## 8. Artifact 5 — creatinine merged Observation (epic-ehi + lab-pdf)"),

    code("""\
from ehi_atlas.harmonize.provenance import EXT_MERGE_RATIONALE

creatinine = None
for entry in gold_bundle["entry"]:
    res = entry["resource"]
    if res.get("resourceType") != "Observation":
        continue
    if any(c.get("code") == "2160-0" for c in res.get("code",{}).get("coding",[])):
        creatinine = res
        break

if creatinine:
    print("Artifact 5 — Observation:", creatinine["id"])
    print("  effectiveDateTime:", creatinine.get("effectiveDateTime"))
    print("  valueQuantity:", creatinine.get("valueQuantity"))
    src_tags = [t["code"] for t in creatinine.get("meta",{}).get("tag",[])
                if "source-tag" in t.get("system","")]
    print("  source-tags:", src_tags)
    rationale = next((e.get("valueString") for e in creatinine.get("meta",{}).get("extension",[])
                      if EXT_MERGE_RATIONALE in e.get("url","")), None)
    print("  rationale:", rationale)
else:
    print("Artifact 5 not found")
"""),

    md("## 9. Provenance graph — walking a MERGE edge"),

    code("""\
# Read provenance.ndjson and show one MERGE edge for a merged Condition
provenance_records = []
with result.provenance_path.open() as fh:
    for line in fh:
        line = line.strip()
        if line:
            provenance_records.append(json.loads(line))

print(f"Total Provenance records: {len(provenance_records)}")

# Find a MERGE record for a Condition
merge_prov = next(
    (p for p in provenance_records
     if p.get("activity", {}).get("coding", [{}])[0].get("code") == "MERGE"
     and any("Condition" in (t.get("reference","")) for t in p.get("target",[]))),
    None
)

if merge_prov:
    print()
    print("Sample MERGE Provenance:")
    print("  activity:", merge_prov["activity"]["coding"][0]["code"])
    print("  target:", [t.get("reference") for t in merge_prov.get("target", [])])
    print("  entity sources:", [e.get("what",{}).get("reference") for e in merge_prov.get("entity",[])])
    print("  agent:", [a.get("who",{}).get("display") for a in merge_prov.get("agent",[])])
"""),

    md("""## Summary

The gold tier for Rhett759 is the output of a 3-source harmonization pipeline:

| Artifact | Description | Status |
|---|---|---|
| 1 | Hyperlipidemia: SNOMED 55822004 + ICD-10 E78.5 → 1 Condition, CUI C0020473 | ✅ |
| 2 | Statin divergence: simvastatin (active) + atorvastatin (stopped) → EXT_CONFLICT_PAIR | ✅ |
| 3 | Claims: 136 Claim + 59 EoB pass-through from synthea-payer | ✅ |
| 4 | Synthesized clinical note → DocumentReference in gold; Condition extraction = Phase 2 | ⚠️ |
| 5 | Creatinine 1.4 mg/dL: epic-ehi + lab-pdf → 1 merged Observation, max quality 0.78 | ✅ |

The Streamlit console at port 8503 (`make console`) visualizes these outputs interactively.
"""),

    md("Series complete. Start over at [00_welcome_and_setup.ipynb](./00_welcome_and_setup.ipynb) or explore the Streamlit console."),
])


# ---------------------------------------------------------------------------
# Write all notebooks
# ---------------------------------------------------------------------------

notebooks = [
    ("00_welcome_and_setup.ipynb", nb00),
    ("01_bronze_tier.ipynb", nb01),
    ("02_layer2_synthea_standardize.ipynb", nb02),
    ("03_layer2b_vision_extraction.ipynb", nb03),
    ("04_layer3_code_mapping.ipynb", nb04),
    ("05_layer3_temporal_and_identity.ipynb", nb05),
    ("06_layer3_condition_merge_artifact_1.ipynb", nb06),
    ("07_layer3_medication_artifact_2.ipynb", nb07),
    ("08_layer3_observation_artifact_5.ipynb", nb08),
    ("09_orchestrator_end_to_end.ipynb", nb09),
]

errors = []
for filename, notebook in notebooks:
    path = NOTEBOOKS_DIR / filename
    try:
        nbformat.validate(notebook)
        nbformat.write(notebook, str(path))
        print(f"  wrote {filename}")
    except Exception as e:
        errors.append((filename, str(e)))
        print(f"  ERROR {filename}: {e}", file=sys.stderr)

if errors:
    print(f"\n{len(errors)} notebook(s) failed validation:", file=sys.stderr)
    for fname, err in errors:
        print(f"  {fname}: {err}", file=sys.stderr)
    sys.exit(1)
else:
    print(f"\nAll {len(notebooks)} notebooks written successfully.")
