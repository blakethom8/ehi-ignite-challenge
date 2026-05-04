# Crosswalk Workflow

> How vendor-specific code mappings (Epic table → FHIR resource, vendor-local code → standard code) are generated, validated, and frozen. **LLMs at build time, scripts at runtime.**

## The principle

Crosswalks map "this vendor's idiosyncratic identifier" to "the canonical FHIR/UMLS form." Examples:

- Epic's `ORDER_PROC` table → FHIR `ServiceRequest`
- Epic's `LAB_RSLT` row → FHIR `Observation` with LOINC code mapping
- A health system's local condition code `HTN-001` → SNOMED `38341003` "Hypertensive disorder"

These crosswalks are **generated once with LLM assistance, validated against ground truth, frozen as static JSON files, and applied deterministically at runtime**. We never re-generate at runtime, and we never allow runtime LLM calls in the standardization layer.

## Two kinds of crosswalks

| Kind | Example | How generated | Where stored |
|---|---|---|---|
| **Schema mapping** | Epic table → FHIR resource type | LLM reads vendor docs + sample rows; emits mapping spec | `ehi_atlas/standardize/crosswalks/<vendor>_to_fhir.json` |
| **Code mapping** | local code → standard code | LLM reads vendor code list + UMLS lookup; emits mapping table | `ehi_atlas/standardize/crosswalks/codes_<system>.json` |

Both follow the same workflow.

## Workflow (build time)

### 1. Gather inputs

For a schema mapping:
- The vendor's documentation (PDF / web pages / text)
- A representative sample of source records (10-50 rows)
- The target FHIR profile (USCDI, CARIN BB, etc.)
- Existing crosswalks in the same domain (UMLS, OHDSI Athena, public published mappings)

For a code mapping:
- The vendor's full code list (CSV / JSON / from source data)
- UMLS Metathesaurus snapshot (or the relevant code system's published crosswalks)
- A small set of "ground truth" mappings (10-20 hand-verified examples)

### 2. Run an LLM-bootstrap pass

A notebook or one-off script in `notebooks/crosswalk-<name>.ipynb` calls Claude with:
- The inputs above
- A schema-constrained output format (Pydantic model for the crosswalk row)
- An instruction to produce the full mapping plus per-row confidence

Default model: **Sonnet 4.6**. Opus only if Sonnet's accuracy is insufficient on a held-out validation sample.

### 3. Validate against ground truth

The LLM output is validated against:
- Hand-verified ground truth (must achieve ≥95% exact-match)
- Schema validity (each row conforms to the Pydantic model)
- UMLS round-trip (mapped codes resolve to valid concepts)
- Semantic plausibility checks (rule-based: e.g., a Condition can't map to an Observation)

If validation fails, iterate on the prompt; never iterate on the data.

### 4. Freeze

The validated crosswalk is written to `ehi_atlas/standardize/crosswalks/<name>.json` with:

```json
{
  "name": "epic_to_fhir",
  "version": "0.1.0",
  "generated_at": "2026-04-29T14:21:00Z",
  "model": "claude-sonnet-4-6",
  "validation": {
    "ground_truth_size": 18,
    "exact_match_rate": 0.97,
    "schema_validity": 1.0,
    "umls_round_trip": 0.96
  },
  "source_inputs": [
    "docs/epic-data-model.pdf",
    "_sources/josh-epic-ehi/raw/db.sqlite.dump"
  ],
  "rows": [
    {"source_table": "ORDER_PROC", "fhir_resource": "ServiceRequest", "confidence": 0.98, "notes": "..."},
    ...
  ]
}
```

The crosswalk is **versioned** in git. Subsequent re-generation requires a version bump and validation report update.

### 5. Apply at runtime (script)

The Layer 2 standardization code reads the frozen crosswalk and applies it deterministically:

```python
# ehi_atlas/standardize/ehi_to_fhir.py
import json
from pathlib import Path

CROSSWALK = json.loads((Path(__file__).parent / "crosswalks" / "epic_to_fhir.json").read_text())
TABLE_TO_RESOURCE = {row["source_table"]: row["fhir_resource"] for row in CROSSWALK["rows"]}

def map_epic_table(table_name: str) -> str | None:
    return TABLE_TO_RESOURCE.get(table_name)
```

No LLM calls. No network. Same input → same output, byte-identical.

## When to regenerate

Crosswalks need regeneration when:

- The source vendor changes their schema (drift)
- A new domain is added (e.g., adding a new Epic table type)
- Validation accuracy degrades on new ground truth
- A bug is discovered in the existing crosswalk

Regeneration is a deliberate action: bump version, re-run validation, commit the new file with a note in the commit message.

## Drift detection (audit-time)

`ehi_atlas/audit/crosswalk_drift.py` is an offline LLM-judge agent that periodically samples bronze records and checks whether the crosswalk's predictions still hold against the source documentation. Output is a flag, not a regeneration — humans decide whether to act.

## What sub-agents producing crosswalks must do

When dispatched to generate a crosswalk:

1. **Stay in a notebook.** Don't write directly to `ehi_atlas/standardize/crosswalks/` from a sub-agent. The notebook is the staging ground; main thread reviews and freezes.
2. **Document the validation.** Every notebook ends with a validation cell showing the metrics in §3.
3. **Surface low-confidence rows.** Anything < 0.85 confidence gets flagged for human review, not silently included.
4. **Don't invent ground truth.** Ground truth is hand-verified by Blake or by a published crosswalk. LLM-generated "self-evaluation" is not ground truth.

## What runtime code must NEVER do

- Call an LLM to generate or extend a crosswalk
- Modify a crosswalk file in-place
- Skip validation when loading a crosswalk

These are smell-tests. If you find yourself wanting to do any of them, the answer is "regenerate at build time, freeze, then apply."
