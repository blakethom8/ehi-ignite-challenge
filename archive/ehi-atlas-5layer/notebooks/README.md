# EHI Atlas — Pedagogical Notebook Series

Ten Jupyter notebooks that walk the EHI Atlas data platform end-to-end, layer by layer, against the live corpus. Each notebook is 10–20 cells and readable in 5–10 minutes.

## Reading order

| Notebook | Topic | Engine |
|---|---|---|
| `00_welcome_and_setup.ipynb` | Orientation, kernel check, corpus layout, pipeline diagram | — |
| `01_bronze_tier.ipynb` | Layer 1: per-source bronze records, SyntheaAdapter | 🔧 Script |
| `02_layer2_synthea_standardize.ipynb` | Layer 2: bronze → silver annotation + BundleValidator | 🔧 Script · 📚 Reference |
| `03_layer2b_vision_extraction.ipynb` | Layer 2-B: lab PDF rasterize → bbox → vision LLM → FHIR | 🔧 Script · 🤖 LLM (cached) |
| `04_layer3_code_mapping.ipynb` | Layer 3a: UMLS-CUI bridge, crosswalk lookups | 🔧 Script · 📚 Reference |
| `05_layer3_temporal_and_identity.ipynb` | Layer 3b: Mandel rule + Fellegi-Sunter identity resolution | 🔧 Script |
| **`06_layer3_condition_merge_artifact_1.ipynb`** | **Artifact 1: Hyperlipidemia SNOMED+ICD-10 merge** | 🔧 Script · 📚 Reference |
| **`07_layer3_medication_artifact_2.ipynb`** | **Artifact 2: statin cross-class conflict (simvastatin vs atorvastatin)** | 🔧 Script · 📚 Reference |
| **`08_layer3_observation_artifact_5.ipynb`** | **Artifact 5: creatinine cross-format merge (Epic EHI + lab PDF)** | 🔧 Script · 📚 Reference |
| `09_orchestrator_end_to_end.ipynb` | Full pipeline run, manifest, all 5 artifacts, provenance graph | ⚙️ Hybrid |

Notebooks 06–08 are the showcase artifact deep-dives — start there if you want the demo content directly.

## How to open in VS Code / Cursor

1. Open the `ehi-atlas/` folder in VS Code or Cursor.
2. Open any `.ipynb` file.
3. Click **Select Kernel** in the top-right and choose **Python (ehi-atlas)**.
   - If the kernel is not listed, run `uv sync` in the `ehi-atlas/` directory first, then reload VS Code.
4. Run cells with `Shift+Enter`.

The kernel is set in each notebook's metadata (`kernelspec.name = "ehi-atlas"`), so VS Code should pre-select it automatically.

## Prerequisites — corpus must be built

The notebooks read the live corpus. If the gold tier is missing, run:

```bash
cd ehi-atlas
make corpus    # acquires sources (Synthea, Josh's repos, synthesized PDF)
make pipeline  # runs the full harmonization pipeline → writes corpus/gold/
```

If `corpus/gold/patients/rhett759/bundle.json` already exists the notebooks are ready to use.

## Engine legend

Each notebook's markdown cells annotate which engine handles each step:

- 🔧 **Script** — deterministic Python; no LLM at runtime
- 🤖 **LLM** — Claude vision/extraction (always cached; never calls the API in the notebooks)
- 📚 **Reference** — static terminology lookup (LOINC subset, hand-curated crosswalk)
- ⚙️ **Hybrid** — orchestrator combining all of the above

## Re-generating the notebooks

The notebooks are built from `notebooks/build_notebooks.py`:

```bash
cd ehi-atlas
uv run python notebooks/build_notebooks.py
```

This writes all 10 `.ipynb` files and validates them with `nbformat.validate()`.
