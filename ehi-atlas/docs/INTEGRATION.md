# Integration

> How the existing patient-journey app consumes EHI Atlas's gold-tier output. **No code-level coupling.** Pure data interface on disk.

## The contract

```
ehi-atlas/corpus/gold/                    ← EHI Atlas writes here
    patients/<patient-id>/
        bundle.json                        ← merged FHIR R4 Bundle
        provenance.ndjson                  ← Provenance graph (one resource per line)
        manifest.json                      ← what was merged, when, with what version
```

The existing app's loader (`api/core/loader.py`) reads this path. EHI Atlas writes to it. **No Python imports cross the boundary in either direction.**

## How the app finds the gold tier

We use a symlink at the existing app's expected data path so no app code changes:

```bash
# One-time setup
ln -s /Users/blake/Repo/ehi-ignite-challenge/ehi-atlas/corpus/gold \
      /Users/blake/Repo/ehi-ignite-challenge/data/ehi-atlas-output
```

The app's loader gains a single new path option (a flag or env var) pointing at `data/ehi-atlas-output/`. Existing Synthea-based loading paths stay untouched.

## What the app reads, in order

For a given patient ID:

1. **`manifest.json`** — overall metadata: build version, sources merged, harmonizer version, timestamp, source counts. The app uses this for the "Sources panel" header.

2. **`bundle.json`** — FHIR R4 Bundle, profile-validated. Contains the harmonized resources (Patient, Conditions, Observations, MedicationRequests, etc.). Each resource carries `meta.source`, `meta.tag[]`, `meta.profile[]`, and Extensions (`.../quality-score`, `.../extraction-*`, `.../conflict-pair`).

3. **`provenance.ndjson`** — line-delimited JSON, one `Provenance` resource per line. Each `Provenance.target` references a resource in `bundle.json`; `Provenance.entity[]` references source records (which the app does not need to load — those live in silver/bronze, accessed only when the user clicks "show source"). Loaded lazily.

4. **Optional binaries** — `binaries/<binary-id>` paths for source PDFs (referenced from Provenance via `Binary` resources). Loaded only when the user opens a source PDF.

## Manifest format

```json
{
  "patient_id": "showcase-blake",
  "harmonizer_version": "0.3.1",
  "built_at": "2026-04-29T14:21:00Z",
  "sources": [
    {"name": "synthea", "bundle_path": "../silver/synthea/showcase-blake.json", "fetched_at": "2026-04-29T10:02:11Z"},
    {"name": "epic-ehi-fixture", "bundle_path": "../silver/epic-ehi/showcase-blake.json", "fetched_at": "2026-04-29T11:45:00Z"},
    {"name": "blue-button", "bundle_path": "../silver/blue-button/showcase-blake.json", "fetched_at": "2026-04-29T12:18:33Z"},
    {"name": "ccda-fixture", "bundle_path": "../silver/ccda/showcase-blake.json", "fetched_at": "2026-04-29T13:05:42Z"},
    {"name": "lab-pdf", "bundle_path": "../silver/lab-pdf/showcase-blake.json", "fetched_at": "2026-04-29T13:55:18Z"}
  ],
  "resource_counts": {
    "Patient": 1,
    "Condition": 14,
    "Observation": 287,
    "MedicationRequest": 9,
    "Encounter": 22,
    "Provenance": 156
  },
  "merge_summary": {
    "duplicates_merged": 11,
    "conflicts_detected": 3,
    "orphans": 4,
    "extracted_from_text": 2,
    "extracted_from_pdf": 1
  }
}
```

## Symlink setup

The symlink is established once via `make integrate`:

```bash
cd ehi-atlas
make integrate    # creates the symlink in ../data/ehi-atlas-output/
```

The Makefile target verifies the source path exists, the target doesn't already exist as a real directory, and creates the symlink atomically.

## What the app must NOT do

- Import from `ehi_atlas/` — the harmonizer's Python modules are not part of the app's runtime
- Write to `corpus/gold/` — gold is owned by the harmonizer; app reads only
- Modify silver or bronze tiers
- Walk Provenance edges into bronze without explicit user action (those references are the "click source" path)

## What the harmonizer must NOT do

- Call into `api/` or `app/` code
- Assume the app's runtime environment is present
- Use any path outside `ehi-atlas/`

## Versioning

The manifest's `harmonizer_version` is the contract version. When that changes, the app should warn or reject if the version skew is too wide. Default policy: same major version required; minor versions OK.

## Health check

`make integrate-check` runs:

1. Symlink resolves
2. `manifest.json` parses
3. `bundle.json` parses and contains a `Patient` resource
4. `provenance.ndjson` has at least one Provenance per harmonized resource

If all pass, the app is safe to load.
