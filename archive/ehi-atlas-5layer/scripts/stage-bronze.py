#!/usr/bin/env python3
"""stage-bronze.py — Phase 1 manual staging from _sources/ to bronze/.

This is a one-shot staging script for Phase 1 corpus assembly. Stage 2 work
replaces this with proper Adapter.ingest() implementations per source. For now,
this script writes bronze records with metadata.json conforming to the
SourceMetadata contract — exercising the contract end-to-end before any
adapters exist.

Usage:
    uv run python scripts/stage-bronze.py [--clean]

Idempotent: re-running produces byte-identical bronze records.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

ATLAS_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ATLAS_ROOT))

from ehi_atlas.adapters.base import Adapter, SourceMetadata  # noqa: E402
from ehi_atlas.adapters.epic_ehi import EpicEhiAdapter  # noqa: E402
from ehi_atlas.adapters.lab_pdf import LabPDFAdapter  # noqa: E402

SOURCES_ROOT = ATLAS_ROOT / "corpus" / "_sources"
BRONZE_ROOT = ATLAS_ROOT / "corpus" / "bronze"

# Showcase patient ID used across all sources where the patient is the same logical person.
SHOWCASE = "rhett759"

# Synthea bundle is staged into _sources/synthea/raw/ during corpus acquisition.
SYNTHEA_BUNDLE = (
    SOURCES_ROOT
    / "synthea"
    / "raw"
    / "Rhett759_Rohan584_cd64ff18-472b-4d58-b73c-2a04a2bf3e61.json"
)

# Frozen acquisition timestamp for determinism (matches lab-pdf SOURCE_DATE_EPOCH).
ACQUISITION_TS = "2000-01-01T00:00:00+00:00"


def stage_synthea() -> SourceMetadata:
    src = SYNTHEA_BUNDLE
    dst_dir = BRONZE_ROOT / "synthea" / SHOWCASE
    dst_dir.mkdir(parents=True, exist_ok=True)
    dst = dst_dir / "data.json"
    shutil.copyfile(src, dst)
    return SourceMetadata(
        source="synthea",
        patient_id=SHOWCASE,
        fetched_at=ACQUISITION_TS,
        document_type="fhir-bundle",
        license="Apache-2.0",
        consent="open",
        sha256=Adapter.hash_file(dst),
        notes="Synthea-generated FHIR R4 Bundle; ground-truth showcase patient.",
    )


def stage_ccda() -> SourceMetadata:
    src = (
        SOURCES_ROOT
        / "josh-ccdas"
        / "raw"
        / "Cerner Samples"
        / "Transition_of_Care_Referral_Summary.xml"
    )
    dst_dir = BRONZE_ROOT / "ccda" / SHOWCASE
    dst_dir.mkdir(parents=True, exist_ok=True)
    dst = dst_dir / "data.xml"
    shutil.copyfile(src, dst)
    return SourceMetadata(
        source="ccda",
        patient_id=SHOWCASE,
        fetched_at=ACQUISITION_TS,
        document_type="ccda-r2-transition-of-care",
        license="CC BY 4.0",
        consent="open",
        sha256=Adapter.hash_file(dst),
        notes="Cerner-vendor CCDA R2 Transition of Care; selected via task 1.7. "
        "Used as the cross-vendor referral document for the showcase patient.",
    )


def stage_lab_pdf() -> SourceMetadata:
    """Stage lab-pdf bronze record via LabPDFAdapter.

    Delegates to LabPDFAdapter.ingest() — produces the same data.pdf as the
    old implementation PLUS the new pages/ directory (rasterizations + bbox
    text JSON) consumed by Layer-2-B vision extraction (task 4.3).
    """
    adapter = LabPDFAdapter(
        source_root=SOURCES_ROOT / "synthesized-lab-pdf" / "raw",
        bronze_root=BRONZE_ROOT / "lab-pdf",
    )
    return adapter.ingest(SHOWCASE)


def stage_clinical_note() -> SourceMetadata:
    """Bundle the DocumentReference + Binary into a single FHIR Bundle for bronze."""
    docref_path = (
        SOURCES_ROOT / "synthea" / "synthesized-clinical-note" / "DocumentReference.json"
    )
    binary_path = SOURCES_ROOT / "synthea" / "synthesized-clinical-note" / "Binary.json"
    docref = json.loads(docref_path.read_text())
    binary = json.loads(binary_path.read_text())

    bundle = {
        "resourceType": "Bundle",
        "id": "synthesized-clinical-note-rhett759-2026-01-15",
        "type": "collection",
        "entry": [
            {"resource": docref, "fullUrl": f"DocumentReference/{docref['id']}"},
            {"resource": binary, "fullUrl": f"Binary/{binary['id']}"},
        ],
    }
    dst_dir = BRONZE_ROOT / "synthesized-clinical-note" / SHOWCASE
    dst_dir.mkdir(parents=True, exist_ok=True)
    dst = dst_dir / "data.json"
    dst.write_text(json.dumps(bundle, indent=2, sort_keys=True) + "\n")
    return SourceMetadata(
        source="synthesized-clinical-note",
        patient_id=SHOWCASE,
        fetched_at=ACQUISITION_TS,
        document_type="fhir-bundle",
        license="MIT",
        consent="constructed",
        sha256=Adapter.hash_file(dst),
        notes="Synthesized progress note (DocumentReference + Binary); contains "
        "Artifact 4 planted free-text fact (chest tightness on exertion). "
        "Source: corpus/_sources/synthea/synthesized-clinical-note/.",
    )


def stage_synthea_payer() -> SourceMetadata:
    """Payer-side split of the Synthea bundle (D10: Source C for Phase 1).

    Reads the same Synthea bundle as stage_synthea() but filters to only
    Claim, ExplanationOfBenefit, Coverage, and Patient resources.  The
    filtered Bundle is written to bronze/synthea-payer/rhett759/data.json.

    Entries are sorted by (resourceType, resource.id) for determinism.
    """
    src = SYNTHEA_BUNDLE
    bundle = json.loads(src.read_text(encoding="utf-8"))

    payer_types = {"Claim", "ExplanationOfBenefit", "Coverage", "Patient"}
    filtered_entries = [
        entry
        for entry in bundle.get("entry", [])
        if isinstance(entry, dict)
        and isinstance(entry.get("resource"), dict)
        and entry["resource"].get("resourceType") in payer_types
    ]
    # Sort for determinism: (resourceType, resource.id)
    filtered_entries.sort(
        key=lambda e: (
            e["resource"].get("resourceType", ""),
            e["resource"].get("id", ""),
        )
    )

    payer_bundle = {
        "resourceType": "Bundle",
        "id": f"synthea-payer-{SHOWCASE}",
        "type": "collection",
        "entry": filtered_entries,
    }

    dst_dir = BRONZE_ROOT / "synthea-payer" / SHOWCASE
    dst_dir.mkdir(parents=True, exist_ok=True)
    dst = dst_dir / "data.json"
    dst.write_text(json.dumps(payer_bundle, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    return SourceMetadata(
        source="synthea-payer",
        patient_id=SHOWCASE,
        fetched_at=ACQUISITION_TS,
        document_type="fhir-bundle-payer-subset",
        license="Apache-2.0",
        consent="open",
        sha256=Adapter.hash_file(dst),
        notes=(
            "Synthea-payer split per decision D10: payer-only view of Rhett759's "
            "clinical Bundle. Contains Claim, ExplanationOfBenefit, Coverage, and "
            "Patient resources only. Same raw source as bronze/synthea/. "
            "See docs/mapping-decisions.md for rationale."
        ),
    )


def stage_epic_ehi() -> list[SourceMetadata]:
    """Stage both Epic EHI bronze records via the EpicEhiAdapter.

    Produces two records:
      - epic-ehi/josh-fixture/  — Josh Mandel's redacted dump (parser validation)
      - epic-ehi/rhett759/      — Rhett759 Synthea data projected into Epic-EHI
                                  shape (showcase patient, three artifact anchors)

    Stage 2 adapter (task 2.3) now handles both flows; the old
    stage_epic_ehi_fixture() function is replaced by this delegate.
    """
    adapter = EpicEhiAdapter(
        source_root=SOURCES_ROOT / "josh-epic-ehi" / "raw",
        bronze_root=BRONZE_ROOT / "epic-ehi",
    )
    results: list[SourceMetadata] = []
    for patient_id in ["josh-fixture", "rhett759"]:
        try:
            md = adapter.ingest(patient_id)
            results.append(md)
        except FileNotFoundError as exc:
            # If a source file is missing, skip that patient gracefully
            print(f"  ⚠ epic-ehi/{patient_id} skipped: {exc}", file=sys.stderr)
    return results


def _stage_epic_ehi_flat() -> SourceMetadata:
    """Shim: stages epic-ehi/josh-fixture only (for STAGES dict compatibility).

    The full stage_epic_ehi() produces two records.  The main() loop calls
    STAGES functions expecting a single SourceMetadata return; this shim
    is used internally.  The rhett759 record is staged separately via the
    EXTRA_STAGES mechanism.
    """
    adapter = EpicEhiAdapter(
        source_root=SOURCES_ROOT / "josh-epic-ehi" / "raw",
        bronze_root=BRONZE_ROOT / "epic-ehi",
    )
    return adapter.ingest("josh-fixture")


def _stage_epic_ehi_rhett759() -> SourceMetadata:
    """Stage the Epic EHI Rhett759 projection."""
    adapter = EpicEhiAdapter(
        source_root=SOURCES_ROOT / "josh-epic-ehi" / "raw",
        bronze_root=BRONZE_ROOT / "epic-ehi",
    )
    return adapter.ingest("rhett759")


STAGES = {
    "synthea": stage_synthea,
    "synthea-payer": stage_synthea_payer,  # D10: payer-side split of Synthea bundle
    "ccda": stage_ccda,
    "lab-pdf": stage_lab_pdf,
    "synthesized-clinical-note": stage_clinical_note,
    "epic-ehi/josh-fixture": _stage_epic_ehi_flat,
    "epic-ehi/rhett759": _stage_epic_ehi_rhett759,
}


def write_metadata(source: str, patient_id: str, metadata: SourceMetadata) -> None:
    """Write metadata.json alongside the bronze data file."""
    out = BRONZE_ROOT / source / patient_id / "metadata.json"
    out.write_text(json.dumps(metadata.model_dump(), indent=2, sort_keys=True) + "\n")


def write_manifest(metadatas: list[SourceMetadata]) -> None:
    """Write a top-level bronze STAGING-MANIFEST.md showing what was staged."""
    lines = [
        "# Bronze Staging Manifest",
        "",
        "Phase 1 corpus staged manually via `scripts/stage-bronze.py` "
        "(replaced by Adapter.ingest() implementations in Stage 2).",
        "",
        "## What's staged",
        "",
        "| source | patient | document_type | license | consent | sha256 |",
        "|---|---|---|---|---|---|",
    ]
    for m in metadatas:
        lines.append(
            f"| `{m.source}` | `{m.patient_id}` | `{m.document_type}` | "
            f"{m.license} | {m.consent} | `{m.sha256[:16]}…` |"
        )
    lines += [
        "",
        "## What's NOT staged (intentional)",
        "",
        "- **`blue-button/rhett759/`** — Source C deferred (task 1.5 deferred per "
        "Blake 2026-04-29). D10 resolved via synthea-payer split instead.",
        "- **Personal sources** (`blake-cedars`, `devon-cedars`, `cedars-portal-pdfs`) "
        "— not part of the Phase 1 showcase pipeline; gitignored.",
        "",
        "## How to regenerate",
        "",
        "```bash",
        "cd ehi-atlas",
        "uv run python scripts/stage-bronze.py --clean",
        "```",
        "",
        "Bronze tier is reproducible from `_sources/`. The `data.*` files are "
        "byte-identical across runs (sources are immutable; we only copy).",
    ]
    (BRONZE_ROOT / "STAGING-MANIFEST.md").write_text("\n".join(lines) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--clean",
        action="store_true",
        help="Wipe bronze/ first before re-staging",
    )
    args = parser.parse_args()

    if args.clean and BRONZE_ROOT.exists():
        for child in BRONZE_ROOT.iterdir():
            if child.name.startswith("."):
                continue
            if child.is_dir():
                shutil.rmtree(child)
            else:
                child.unlink()
        print("✓ bronze/ wiped")

    BRONZE_ROOT.mkdir(parents=True, exist_ok=True)

    metadatas: list[SourceMetadata] = []
    for name, stage_fn in STAGES.items():
        try:
            md = stage_fn()
            write_metadata(md.source, md.patient_id, md)
            metadatas.append(md)
            print(f"✓ {name:35s}  → bronze/{md.source}/{md.patient_id}/  ({md.sha256[:12]}…)")
        except Exception as e:
            print(f"✗ {name:35s}  FAILED: {e}", file=sys.stderr)
            return 1

    write_manifest(metadatas)
    print(f"\n✓ {len(metadatas)} sources staged")
    print(f"✓ manifest at bronze/STAGING-MANIFEST.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
